from machine import Pin, I2C, Timer, UART
import time
import uasyncio

import ssd1306
from rotary_irq_esp import RotaryIRQ
from dshot import Dshot

# using default address 0x3c
i2c = I2C(1, sda=Pin(21), scl=Pin(22))
display = ssd1306.SSD1306_I2C(128, 64, i2c)
display.rotate(0)


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
    display.text(before + "Start", 12, 36, 1)
    before = "> " if rotary.value() == 1 else "  "
    display.text(before + "Edit", 12, 46, 1)


def draw_edit_menu(state, rotary):
    display.text("Deposit speed:", 0, 0, 1)
    display.text("{: >{w}} RPM".format(state["deposit_rpm"], w=4), 62, 10, 1)
    display.text("Coating speed:", 0, 22, 1)
    display.text("{: >{w}} RPM".format(state["coating_rpm"], w=4), 62, 32, 1)
    display.text("Coating time:", 0, 44, 1)
    display.text("{: >{w}} sec".format(state["coating_time"], w=4), 62, 54, 1)


def edit_deposit_view(state, rotary):
    state["deposit_rpm"] = rotary.value() * 10
    draw_edit_menu(state, rotary)
    display.text(">", 40, 10, 1)


def edit_coating_rpm_view(state, rotary):
    state["coating_rpm"] = rotary.value() * 10
    draw_edit_menu(state, rotary)
    display.text(">", 40, 32, 1)


def edit_coating_time_view(state, rotary):
    state["coating_time"] = rotary.value()
    draw_edit_menu(state, rotary)
    display.text(">", 40, 54, 1)


def draw_rpm(rpm):
    display.text("RPM:{: >{w}}".format(rpm, w=5), 30, 27, 1)


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


def handle_ESC_telemetry(data):
    if data is None:
        return
    print("Telemetry: ", data)
    pass


async def update():
    global state
    global rotary
    global dshot
    global uart
    while True:
        display.fill(0)
        state["view"](state, rotary)
        display.show()
        dshot.set_throttle(state["throttle"])
        handle_ESC_telemetry(uart.read())
        await uasyncio.sleep_ms(33)


def debounce_button(p):
    p.irq(trigger=Pin.IRQ_FALLING, handler=None)  # remove irq
    timer0 = Timer(0)
    timer0.init(period=20, mode=Timer.ONE_SHOT, callback=lambda t: on_button_press(p))


def on_button_press(p):
    p.irq(trigger=Pin.IRQ_FALLING, handler=debounce_button)  # restore irq
    if p.value() == 1:  # debounce
        return
    global state
    global rotary
    global dshot
    if state["view"] == start_view:
        if rotary.value() == 0:
            state["view"] = deposit_view
            state["throttle"] = 0.02
            return
        if rotary.value() == 1:
            state["view"] = edit_deposit_view
            rotary.set(
                min_val=0,
                max_val=9990,
                range_mode=RotaryIRQ.RANGE_BOUNDED,
                value=int(0.1 * state["deposit_rpm"]),
            )
            return
    if state["view"] == edit_deposit_view:
        state["view"] = edit_coating_rpm_view
        rotary.set(
            min_val=0,
            max_val=9990,
            range_mode=RotaryIRQ.RANGE_BOUNDED,
            value=int(0.1 * state["coating_rpm"]),
        )
        return
    if state["view"] == edit_coating_rpm_view:
        state["view"] = edit_coating_time_view
        rotary.set(
            min_val=0,
            max_val=9999,
            range_mode=RotaryIRQ.RANGE_BOUNDED,
            value=state["coating_time"],
        )
        return
    if state["view"] == edit_coating_time_view:
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


timer1 = Timer(1)
timer2 = Timer(2)


def start_coating(state):
    global timer1
    global timer2

    state["timer"] = state["coating_time"]

    timer1.init(
        period=state["coating_time"] * 1000,
        mode=Timer.ONE_SHOT,
        callback=lambda t: stop_coating(),
    )

    def decrement_timer(t):
        state["timer"] -= 1

    timer2.init(period=1000, mode=Timer.PERIODIC, callback=decrement_timer)

    state["throttle"] = 0.10


def stop_coating():
    global state
    global rotary
    global timer1
    global timer2
    dshot.set_throttle(0)
    timer1.deinit()
    timer2.deinit()
    state["throttle"] = 0
    rotary.set(min_val=0, max_val=1, range_mode=RotaryIRQ.RANGE_BOUNDED, value=0)
    state["view"] = start_view


splash()
# time.sleep(1)

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

dshot = Dshot(pin=Pin(18))

uart = UART(1, baudrate=115200, bits=8, tx=17, rx=5, flow=0)

state = {
    "view": start_view,
    "rpm": 0,
    "timer": 0,
    "deposit_rpm": 500,
    "coating_rpm": 6000,
    "coating_time": 10,
    "throttle": 0,
}

event_loop = uasyncio.get_event_loop()
event_loop.create_task(update())
event_loop.run_forever()
