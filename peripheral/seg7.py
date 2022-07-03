from amaranth import *

from amaranth_orchard.base.peripheral import Peripheral

from peripheral.seven_seg_tile import SevenSegTile

class Seg7Pins(Record):
    def __init__(self):
        layout = [
            ("leds", 7),
            ("ca", 3)
        ]
        super().__init__(layout)

class Seg7Peripheral(Peripheral, Elaboratable):
    def __init__(self, pins, **kwargs):
        super().__init__()

        self.pins = pins

        bank            = self.csr_bank()
        self.data       = bank.csr(12, "w")

        self._bridge    = self.bridge(data_width=32, granularity=8, alignment=2)
        self.bus        = self._bridge.bus

    def elaborate(self, platform):
        m = Module()
        m.submodules.bridge  = self._bridge

        m.submodules.seg7 = seg7 = SevenSegTile()

        m.d.comb += [
            self.pins.leds.eq(seg7.leds),
            self.pins.ca.eq(seg7.ca),
            seg7.val.eq(self.data.w_data)
        ]

        return m



