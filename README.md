# Spin coater

## Installation

Flash MicroPython to your ESP32 according to these instructions: https://micropython.org/download/esp32/

Then use [rshell](https://github.com/dhylands/rshell) to copy the code to the board:

```
rshell -p /dev/ttyUSB0  # connect
rsync src /pyboard/  # sync code to ESP32
repl  # enter MicroPython REPL, press ctrl+D to soft reboot
```