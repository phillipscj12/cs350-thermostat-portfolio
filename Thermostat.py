#
# Thermostat - This is the Python code used to demonstrate
# the functionality of the thermostat that we have prototyped throughout
# the course.
#
# This code works with the test circuit that was built for module 7.
#
# Functionality:
#
# The thermostat has three states: off, heat, cool
#
# The lights will represent the state that the thermostat is in.
#
# If the thermostat is set to off, the lights will both be off.
#
# If the thermostat is set to heat, the Red LED will be fading in
# and out if the current temperature is blow the set temperature;
# otherwise, the Red LED will be on solid.
#
# If the thermostat is set to cool, the Blue LED will be fading in
# and out if the current temperature is above the set temperature;
# otherwise, the Blue LED will be on solid.
#
# One button will cycle through the three states of the thermostat.
#
# One button will raise the setpoint by a degree.
#
# One button will lower the setpoint by a degree.
#
# The LCD display will display the date and time on one line and
# alternate the second line between the current temperature and
# the state of the thermostat along with its set temperature.
#
# The Thermostat will send a status update to the TemperatureServer
# over the serial port every 30 seconds in a comma delimited string
# including the state of the thermostat, the current temperature
# in degrees Fahrenheit, and the setpoint of the thermostat.
#
#------------------------------------------------------------------
# Change History
#------------------------------------------------------------------
# Version   |   Description
#------------------------------------------------------------------
#    1          Initial Development
#------------------------------------------------------------------

##
## Import necessary to provide timing in the main loop
##
from time import sleep
from datetime import datetime
from statemachine import StateMachine, State

import board
import adafruit_ahtx0

# import board (already imported)
import digitalio
import adafruit_character_lcd.character_lcd as characterlcd

import serial

from gpiozero import Button, PWMLED
from threading import Thread
from math import floor

DEBUG = True

i2c = board.I2C()
thSensor = adafruit_ahtx0.AHTx0(i2c)

SER_PORTS = ['/dev/serial0', '/dev/ttyS0', '/dev/ttyAMA0']  # try best -> fallback
ser = None
for _port in SER_PORTS:
    try:
        ser = serial.Serial(
            port=_port,
            baudrate=115200,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=1
        )
        if DEBUG: print(f"UART opened on {_port} @115200")
        break
    except Exception as e:
        if DEBUG: print(f"UART open failed on {_port}: {e}")
redLight = PWMLED(18)
blueLight = PWMLED(23)

class ManagedDisplay:
    """
    16x2 HD44780 helper.
    - Use show(line1, line2) for flicker-free updates.
    - updateScreen(message) kept for backward compatibility (expects one '\n').
    """
    def __init__(self):
        # GPIO pin mapping (unchanged)
        self.lcd_rs = digitalio.DigitalInOut(board.D17)
        self.lcd_en = digitalio.DigitalInOut(board.D27)
        self.lcd_d4 = digitalio.DigitalInOut(board.D5)
        self.lcd_d5 = digitalio.DigitalInOut(board.D6)
        self.lcd_d6 = digitalio.DigitalInOut(board.D13)
        self.lcd_d7 = digitalio.DigitalInOut(board.D26)

        self.lcd_columns = 16
        self.lcd_rows = 2

        self.lcd = characterlcd.Character_LCD_Mono(
            self.lcd_rs, self.lcd_en,
            self.lcd_d4, self.lcd_d5, self.lcd_d6, self.lcd_d7,
            self.lcd_columns, self.lcd_rows
        )
        self.lcd.clear()
        # cache last text to avoid redundant redraws
        self._last = [" " * self.lcd_columns, " " * self.lcd_columns]

    # ---- public API ----
    def show(self, line1: str, line2: str, force: bool = False):
        """Write two lines (padded/truncated to 16 chars) without clearing each time."""
        l1 = (line1[:self.lcd_columns]).ljust(self.lcd_columns)
        l2 = (line2[:self.lcd_columns]).ljust(self.lcd_columns)
        if force or [l1, l2] != self._last:
            self.lcd.message = f"{l1}\n{l2}"
            self._last = [l1, l2]

    def updateScreen(self, message: str, force: bool = False):
        """
        Back-compat: accepts a single string with one newline.
        Example: updateScreen("Line 1 text\\nLine 2 text")
        """
        parts = (message.split("\n", 1) + [""])[:2]
        self.show(parts[0], parts[1], force=force)

    def clear(self):
        self.lcd.clear()
        self._last = [" " * self.lcd_columns, " " * self.lcd_columns]

    def cleanupDisplay(self):
        try:
            self.clear()
        finally:
            # deinit pins
            self.lcd_rs.deinit()
            self.lcd_en.deinit()
            self.lcd_d4.deinit()
            self.lcd_d5.deinit()
            self.lcd_d6.deinit()
            self.lcd_d7.deinit()


screen = ManagedDisplay()


class TemperatureMachine(StateMachine):
    "A state machine designed to manage our thermostat"

    off = State(initial = True)
    heat = State()
    cool  = State()

    setPoint = 72

    cycle = (
        off.to(heat) |
        heat.to(cool) |
        cool.to(off)
    )

    def _stop_pulses(self):
        # stop any background PWM pulse sources before setting new states
        for led in (redLight, blueLight):
            try: led.source = None
            except Exception: pass

    def on_enter_heat(self):
        self.updateLights()
        if(DEBUG):
            print("* Changing state to heat")

    def on_exit_heat(self):
        self._stop_pulses()
        redLight.off()

    def on_enter_cool(self):
        self.updateLights()
        if(DEBUG):
            print("* Changing state to cool")

    def on_exit_cool(self):
        self._stop_pulses()
        blueLight.off()

    def on_enter_off(self):
        self._stop_pulses()
        redLight.off()
        blueLight.off()
        if(DEBUG):
            print("* Changing state to off")

    def processTempStateButton(self):
        if(DEBUG):
            print("Cycling Temperature State")
        self.cycle()

    def processTempIncButton(self):
        if(DEBUG):
            print("Increasing Set Point")
        self.setPoint = min(self.setPoint + 1, 90)
        self.updateLights()

    def processTempDecButton(self):
        if(DEBUG):
            print("Decreasing Set Point")
        self.setPoint = max(self.setPoint - 1, 50)
        self.updateLights()

    def updateLights(self):
        # compare in Fahrenheit (rounded down per template)
        temp = floor(self.getFahrenheit())

        # reset any existing pulses, then decide behavior
        self._stop_pulses()
        redLight.off(); blueLight.off()

        if(DEBUG):
            print(f"State: {self.current_state.id}")
            print(f"SetPoint: {self.setPoint}")
            print(f"Temp: {temp}")

        # HEAT: below setpoint → red fading; at/above → red solid; blue off
        if self.current_state == self.heat:
            if temp < self.setPoint:
                redLight.pulse(fade_in_time=1, fade_out_time=1, n=None, background=True)
                blueLight.off()
            else:
                redLight.on()
                blueLight.off()

        # COOL: above setpoint → blue fading; at/below → blue solid; red off
        elif self.current_state == self.cool:
            if temp > self.setPoint:
                blueLight.pulse(fade_in_time=1, fade_out_time=1, n=None, background=True)
                redLight.off()
            else:
                blueLight.on()
                redLight.off()

        # OFF: both off
        else:
            redLight.off()
            blueLight.off()

    def run(self):
        myThread = Thread(target=self.manageMyDisplay)
        myThread.start()

    def getFahrenheit(self):
        t = thSensor.temperature
        return (((9/5) * t) + 32)

    def setupSerialOutput(self):
        # state,current_F,setpoint_F
        state_str = self.current_state.id
        temp_f = f"{self.getFahrenheit():.1f}"
        output = f"{state_str},{temp_f},{self.setPoint:.0f}"
        return output

    endDisplay = False

    def manageMyDisplay(self):
        counter = 1
        altCounter = 1
        while not self.endDisplay:
            if(DEBUG):
                print("Processing Display Info...")

            current_time = datetime.now()

            # Line 1: date/time (16 chars) + newline
            lcd_line_1 = current_time.strftime('%b %d  %H:%M:%S\n')

            # Line 2 alternates every ~5 seconds between temp and state+setpoint
            if(altCounter < 6):
                lcd_line_2 = f"T:{self.getFahrenheit():5.1f}F".ljust(16)
                altCounter = altCounter + 1
            else:
                lcd_line_2 = f"{self.current_state.id.upper()} SP:{self.setPoint:3.0f}F".ljust(16)
                altCounter = altCounter + 1
                if(altCounter >= 11):
                    # refresh LEDs every 10 seconds for smooth operation
                    self.updateLights()
                    altCounter = 1

            # Update LCD
            screen.updateScreen(lcd_line_1 + lcd_line_2)

            # UART output every 30 seconds
            if(DEBUG):
               print(f"Counter: {counter}")
            if((counter % 30) == 0):
                ser.write((self.setupSerialOutput() + "\n").encode('ascii'))
                counter = 1
            else:
                counter = counter + 1

            sleep(1)

        screen.cleanupDisplay()


tsm = TemperatureMachine()
tsm.run()

greenButton = Button(24)
greenButton.when_pressed = tsm.processTempStateButton

redButton = Button(25)
redButton.when_pressed = tsm.processTempIncButton

blueButton = Button(12)
blueButton.when_pressed = tsm.processTempDecButton

repeat = True

while repeat:
    try:
        sleep(30)
    except KeyboardInterrupt:
        print("Cleaning up. Exiting...")
        repeat = False
        tsm.endDisplay = True
        sleep(1)