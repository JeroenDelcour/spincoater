from machine import Pin, I2C, Timer, UART
import time
import uasyncio
import json

import ssd1306
import config
from rotary_irq_esp import RotaryIRQ
from dshot import Dshot
from pid import PID


def splash():
    # display.fill(0)
    # display.fill_rect(0, 0, 32, 32, 1)
    # display.fill_rect(2, 2, 28, 28, 0)
    # display.vline(9, 8, 22, 1)
    # display.vline(16, 2, 22, 1)
    # display.vline(23, 8, 22, 1)
    # display.fill_rect(26, 24, 2, 4, 1)
    # display.text("MicroPython", 40, 0, 1)
    # display.text("SSD1306", 40, 12, 1)
    # display.text("OLED 128x64", 40, 24, 1)

    display.fill(0)
    display.text("SPIN", 34, 4, 1)
    display.text("COATER", 50, 14, 1)

    display.show()


def start_view(state, rotary):
    display.text("SPIN", 34, 4, 1)
    display.text("COATER", 50, 14, 1)

    before = "> " if rotary.value() == 0 else "  "
    display.text(before + "Edit", 12, 36, 1)
    before = "> " if rotary.value() == 1 else "  "
    display.text(before + "Start", 12, 46, 1)


def draw_edit_menu(state, rotary):
    display.text("Deposit speed:", 0, 0, 1)
    display.text("{: >{w}} RPM".format(config["deposit_rpm"], w=5), 56, 10, 1)
    display.text("Coating speed:", 0, 21, 1)
    display.text("{: >{w}} RPM".format(config["coating_rpm"], w=5), 56, 31, 1)
    display.text("Coating time:", 0, 42, 1)
    display.text("{: >{w}} sec".format(config["coating_time"], w=5), 56, 52, 1)


def edit_deposit_view(state, rotary):
    config["deposit_rpm"] = rotary.value() * 100
    draw_edit_menu(state, rotary)
    display.text(">", 40, 10, 1)


def edit_coating_rpm_view(state, rotary):
    config["coating_rpm"] = rotary.value() * 100
    draw_edit_menu(state, rotary)
    display.text(">", 40, 32, 1)


def edit_coating_time_view(state, rotary):
    config["coating_time"] = rotary.value()
    draw_edit_menu(state, rotary)
    display.text(">", 40, 54, 1)


def draw_rpm(rpm):
    display.text("RPM:{: >{w}.0f}".format(rpm, w=5), 30, 27, 1)


def deposit_view(state, rotary):
    display.fill_rect(0, 0, 127, 14, 1)
    display.text("Deposit", 36, 3, 0)
    draw_rpm(state["rpm"])
    display.text("Press to", 32, 42, 1)
    display.text("continue", 32, 52, 1)


def coating_view(state, rotary):
    display.fill_rect(0, 0, 127, 14, 1)
    display.text("Coating", 36, 3, 0)
    draw_rpm(state["rpm"])
    display.text("{: >{w}} sec".format(state["timer"], w=4), 30, 48, 1)


def decode_ESC_telemetry(data, motor_poles=14):
    if len(data) > 10:
        # use latest telemetry
        data = data[-10:]

    temperature = int(data[0])  # degrees Celsius
    voltage = int((data[1] << 8) | data[2]) * 0.01  # Volt
    current = (
        int((data[3] << 8) | data[4]) * 0.01
    )  # Amps, only available if the ESC has a current meter
    consumption = int(
        (data[5] << 8) | data[6]
    )  # mAh, only available if the ESC has a current meter
    erpm = int((data[7] << 8) | data[8]) * 100
    rpm = erpm / (motor_poles / 2)
    crc = data[9]

    # print("         Temp (C):", temperature)
    # print("      Voltage (V):", voltage)
    # print("      Current (A):", current)
    # print("Consumption (mAh):", consumption)
    # print("             Erpm:", erpm)
    # print("              RPM:", rpm)
    # print("              CRC:", crc)
    # print()

    return temperature, voltage, current, consumption, erpm, rpm


async def update_display():
    global state
    global rotary
    while True:
        display.fill(0)
        state["view"](state, rotary)
        display.show()
        await uasyncio.sleep_ms(33)


async def update_motor():
    global state
    dshot = Dshot(pin=Pin(18))
    rpm_pid = PID(
        Kp=config["PID"]["Kp"],
        Ki=config["PID"]["Ki"],
        Kd=config["PID"]["Kd"],
        setpoint=0,
        sample_time=None,
        output_limits=(0.0, 1.0),
        # proportional_on_measurement=True,
    )
    while True:
        rpm_pid.setpoint = state["target_rpm"]

        # read ESC telemetry
        if uart.any() >= 10:
            telemetry = decode_ESC_telemetry(uart.read())
            if telemetry is not None:
                state["rpm"] = telemetry[5]
                throttle = rpm_pid(state["rpm"])
                # print(
                #     "Throttle:",
                #     throttle,
                #     "pid components:",
                #     rpm_pid.components,
                #     "RPM:",
                #     state["rpm"],
                # )

        if state["target_rpm"] == 0 and state["rpm"] < 1000:
            throttle = 0
            rpm_pid.reset()
        dshot.set_throttle(throttle)

        await uasyncio.sleep_ms(1)


def debounce_button(p):
    p.irq(trigger=Pin.IRQ_FALLING, handler=None)  # remove irq
    timer0 = Timer(0)
    timer0.init(period=20, mode=Timer.ONE_SHOT, callback=lambda t: on_button_press(p))


def on_button_press(p):
    p.irq(trigger=Pin.IRQ_FALLING, handler=debounce_button)  # restore irq
    if p.value() == 1:  # debounce
        return
    global state
    global config
    global rotary
    if state["view"] == start_view:
        if rotary.value() == 0:
            state["view"] = edit_deposit_view
            rotary.set(
                min_val=0,
                max_val=1000,
                range_mode=RotaryIRQ.RANGE_BOUNDED,
                value=int(0.01 * config["deposit_rpm"]),
            )
            return
        if rotary.value() == 1:
            state["view"] = deposit_view
            state["target_rpm"] = config["deposit_rpm"]
            return
    if state["view"] == edit_deposit_view:
        state["view"] = edit_coating_rpm_view
        rotary.set(
            min_val=0,
            max_val=1000,
            range_mode=RotaryIRQ.RANGE_BOUNDED,
            value=int(0.01 * config["coating_rpm"]),
        )
        return
    if state["view"] == edit_coating_rpm_view:
        state["view"] = edit_coating_time_view
        rotary.set(
            min_val=0,
            max_val=9999,
            range_mode=RotaryIRQ.RANGE_BOUNDED,
            value=config["coating_time"],
        )
        return
    if state["view"] == edit_coating_time_view:
        save_config()
        rotary.set(min_val=0, max_val=1, range_mode=RotaryIRQ.RANGE_BOUNDED, value=0)
        state["view"] = start_view
        return
    if state["view"] == deposit_view:
        state["view"] = coating_view
        start_coating(state)
        return
    if state["view"] == coating_view:
        stop_coating()
        return


def start_coating(state):
    global timer1
    global timer2

    state["timer"] = config["coating_time"]

    timer1.init(
        period=config["coating_time"] * 1000,
        mode=Timer.ONE_SHOT,
        callback=lambda t: stop_coating(),
    )

    def decrement_timer(t):
        state["timer"] -= 1

    timer2.init(period=1000, mode=Timer.PERIODIC, callback=decrement_timer)

    # state["throttle"] = 0.10
    state["target_rpm"] = config["coating_rpm"]


def stop_coating():
    global state
    global rotary
    global timer1
    global timer2
    timer1.deinit()
    timer2.deinit()
    state["target_rpm"] = 0
    rotary.set(min_val=0, max_val=1, range_mode=RotaryIRQ.RANGE_BOUNDED, value=0)
    state["view"] = start_view


def save_config():
    global config
    with open("config.json", "w") as f:
        json.dump(config, f)


# using default address 0x3c
i2c = I2C(1, sda=Pin(21), scl=Pin(22))
display = ssd1306.SSD1306_I2C(128, 64, i2c)
display.rotate(0)

timer1 = Timer(1)
timer2 = Timer(2)


splash()

rotary = RotaryIRQ(
    pin_num_clk=14,
    pin_num_dt=13,
    min_val=0,
    max_val=1,
    range_mode=RotaryIRQ.RANGE_BOUNDED,
    pull_up=True,
)

button = Pin(19, Pin.IN, Pin.PULL_UP)
button.irq(trigger=Pin.IRQ_FALLING, handler=on_button_press)

uart = UART(1, baudrate=115200, rx=5)  # to receive ESC telemetry

state = {
    "view": start_view,
    "rpm": 0,
    "target_rpm": 0,
    "timer": 0,
}

with open("config.json", "r") as f:
    config = json.load(f)

event_loop = uasyncio.get_event_loop()
event_loop.create_task(update_display())
event_loop.create_task(update_motor())
event_loop.run_forever()
