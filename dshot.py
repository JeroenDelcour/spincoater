import time

from esp32 import RMT


class Dshot:
    def __init__(self, pin):
        # https://brushlesswhoop.com/dshot-and-bidirectional-dshot/
        # clock freq = 80  # Mhz
        # clock divider = 7
        # pulse time = 1 / (80 / 7) = 0.0875 us
        # bit duration = 3.33 us
        # T1H = 2.50 us
        # T0H = 1.25 us
        self._ON_PULSES = 57  # number of pulses for an ON bit
        self._OFF_PULSES = 29  # number of pulses for an OFF bit
        self._BIT_PULSES = 76  # total number of pulses per bit
        self._PAUSE_PULSES = 21  # pause after sending packet

        self.rmt = RMT(0, pin=pin, clock_div=7)

        self._arm()
        self._enable_telemetry()

    def _arm(self, duration=3):
        """
        Send arming sequence.

        Args:
            duration: How long to send the arming sequence, in seconds.
        """
        t0 = time.time()
        while time.time() - t0 < duration:
            self.set_throttle(0)
            # time.sleep(0.01)

    def _enable_telemetry(self):
        # for i in range(6):
        #     value = self._create_packet(13)
        #     print(bin(value))
        #     self._send(value)
        for i in range(6):
            value = self._create_packet(34)
            print(bin(value))
            self._send(value)
        # for i in range(6):
        #     value = self._create_packet(34)
        #     print(bin(value))
        #     self._send(value)
        # for i in range(6):
        #     value = self._create_packet(35)
        #     print(bin(value))
        #     self._send(value)
        for i in range(6):
            value = self._create_packet(12)
            print(bin(value))
            self._send(value)
        time.sleep(0.040)

        # self._send(self._create_packet(42))
        # self._send(self._create_packet(43))
        # self._send(self._create_packet(44))
        # self._send(self._create_packet(45))
        # self._send(self._create_packet(46))
        # self._send(self._create_packet(47))

        # beep
        # time.sleep(0.050)
        # for i in range(5):
        #     self._send(self._create_packet(i + 1))
        #     time.sleep(0.250)

    def _encode_throttle(self, value):
        # 11 bit throttle: 2048 possible values.
        # 0 is reserved for disarmed. 1-47 are reserved for special commands.
        # Leaving 48 to 2047 (2000 steps) for the actual throttle value
        value = min(max(value, 0), 1)  # clamp to between 0 and 1
        if value == 0:
            value = 0  # disarmed
        else:
            value = int(value * 2000 + 47)
        return value

    def set_throttle(self, value: float, telemetry=True):
        """
        Set throttle to a value between 0 and 1.
        """
        value = self._encode_throttle(value)
        value = self._create_packet(value)
        self._send(value)

    def _create_packet(self, value, telemetry=True):
        # add telemetry bit
        value = (value << 1) | telemetry

        # add CRC (Cyclic Redundancy Check)
        crc = (value ^ (value >> 4) ^ (value >> 8)) & 0x0F
        value = (value << 4) | crc

        return value

    def _send(self, value):
        """
        Send value to ESC.
        """
        duration = []

        for i in reversed(range(16)):
            bit = (value & (2**i)) == 2**i  # select bit
            if bit == 1:
                duration += [self._ON_PULSES, self._BIT_PULSES - self._ON_PULSES]
            else:
                duration += [self._OFF_PULSES, self._BIT_PULSES - self._OFF_PULSES]

        duration[-1] += self._PAUSE_PULSES

        self.rmt.write_pulses(duration, True)
