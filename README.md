# cs350-thermostat-portfolio
Project Summary

I built a thermostat on a Raspberry Pi 4. It reads room temperature from an AHT20 over I²C, shows status on a 16×2 LCD, and uses two LEDs to indicate heating (red) and cooling (blue). The LEDs fade when the system is calling and stay solid at the setpoint. Every 30 seconds the Pi sends a CSV status line over UART. A small state machine (OFF → HEAT → COOL) runs the behavior so the buttons stay responsive while the display and serial output update.

What I Did Well

I kept the code in clear pieces. The state machine handles mode rules; separate functions handle the LCD, LEDs, sensor reads, and UART. I added a simple LCD helper that updates only when text changes, which stopped screen flicker. I also added a UART fallback that tries multiple device names so it works across different Pi setups without editing the code.

Where I Could Improve

I’d add a user-set deadband and a small LCD menu to change it and the update interval. I’d also move all pin numbers and LCD wiring into one config block so hardware swaps are one edit.

Tools/Resources I Added

gpiozero for buttons and PWM LEDs

Adafruit AHTx0 library for the temperature sensor

A lightweight state-machine library

raspi-config changes so the serial login shell doesn’t block the UART

Transferable Skills

Writing interface code for I²C, GPIO, and UART

Designing and debugging a small state machine

Using threads to keep inputs responsive during display/telemetry updates

Careful bring-up: pin mapping, quick test scripts, and step-by-step integration

Maintainability, Readability, Adaptability

Clear function boundaries (sensor → rules → display → serial)

Small helpers to avoid repeated code and LCD flicker

Comments where behavior matters (e.g., LED rules at setpoint)

Constants grouped so wiring changes don’t require refactoring
