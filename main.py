from machine import Pin, I2C
import time
import uasyncio

import ssd1306
from rotary_irq_esp import RotaryIRQ

# using default address 0x3c
i2c = I2C(1, sda=Pin(21), scl=Pin(22))
display = ssd1306.SSD1306_I2C(128, 64, i2c)


def splash():
    display.fill(0)
    display.fill_rect(0, 0, 32, 32, 1)
    display.fill_rect(2, 2, 28, 28, 0)
    display.vline(9, 8, 22, 1)
    display.vline(16, 2, 22, 1)
    display.vline(23, 8, 22, 1)
    display.fill_rect(26, 24, 2, 4, 1)
    display.text("MicroPython", 40, 0, 1)
    display.text("SSD1306", 40, 12, 1)
    display.text("OLED 128x64", 40, 24, 1)
    display.show()


def start_view(state, rotary):
    before = "> " if rotary.value() == 0 else "  "
    display.text(before + "Start", 12, 26, 1)
    before = "> " if rotary.value() == 1 else "  "
    display.text(before + "Edit", 12, 36, 1)


def draw_edit_menu(state, rotary):
    display.text("Deposit speed:", 0, 0, 1)
    display.text("{: >{w}} RPM".format(state["deposit_rpm"], w=4), 62, 10, 1)
    display.text("Coating speed:", 0, 22, 1)
    display.text("{: >{w}} RPM".format(state["spin_rpm"], w=4), 62, 32, 1)
    display.text("Coating time:", 0, 44, 1)
    display.text("{: >{w}} sec".format(state["spin_time"], w=4), 62, 54, 1)


def edit_deposit_view(state, rotary):
    state["deposit_rpm"] = rotary.value() * 10
    draw_edit_menu(state, rotary)
    display.text(">", 40, 10, 1)


def edit_spin_rpm_view(state, rotary):
    state["spin_rpm"] = rotary.value() * 10
    draw_edit_menu(state, rotary)
    display.text(">", 40, 32, 1)


def edit_spin_time_view(state, rotary):
    state["spin_time"] = rotary.value()
    draw_edit_menu(state, rotary)
    display.text(">", 40, 54, 1)


def draw_rpm(rpm):
    display.text("RPM:{: >{w}}".format(rpm, w=5), 30, 16, 1)


def deposit_view(state):
    draw_rpm(state["rpm"])
    display.text("Press to", 32, 38, 1)
    display.text("continue", 32, 48, 1)


def spinning_view(state):
    draw_rpm(state["rpm"])
    display.text("{: >{w}} sec".format(state.timer, w=4), 30, 48, 1)


async def update():
    global state
    global rotary
    while True:
        display.fill(0)
        state["view"](state, rotary)
        display.show()
        await uasyncio.sleep_ms(33)


def on_button_press():
    global state
    global rotary
    if state["view"] == start_view:
        if rotary.value() == 0:
            state["view"] = deposit_view
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
        state["view"] = edit_spin_rpm_view
        rotary.set(
            min_val=0,
            max_val=9990,
            range_mode=RotaryIRQ.RANGE_BOUNDED,
            value=int(0.1 * state["spin_rpm"]),
        )
        return
    if state["view"] == edit_spin_rpm_view:
        state["view"] = edit_spin_time_view
        rotary.set(
            min_val=0,
            max_val=9999,
            range_mode=RotaryIRQ.RANGE_BOUNDED,
            value=state["spin_time"],
        )
        return
    if state["view"] == edit_spin_time_view:
        rotary.set(min_val=0, max_val=1, range_mode=RotaryIRQ.RANGE_BOUNDED)
        state["view"] = start_view
        return
    if state["view"] == deposit_view:
        state["view"] = spinning_view
        return


splash()
time.sleep(1)

rotary = RotaryIRQ(
    pin_num_clk=12,
    pin_num_dt=13,
    min_val=0,
    max_val=500,
    range_mode=RotaryIRQ.RANGE_BOUNDED,
    pull_up=True,
)

state = {
    "view": edit_spin_time_view,
    "rpm": 0,
    "timer": 0,
    "deposit_rpm": 500,
    "spin_rpm": 6000,
    "spin_time": 120,
}

event_loop = uasyncio.get_event_loop()
event_loop.create_task(update())
# event_loop.create_task(user_input())
event_loop.run_forever()
