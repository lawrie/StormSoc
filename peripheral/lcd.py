from amaranth import *

from amaranth_orchard.base.peripheral import Peripheral

from peripheral.st7789 import ST7789


class LcdPins(Record):
    def __init__(self):
        layout = [
            ("sclk", 1),
            ("csn", 1),
            ("resn", 1),
            ("dc", 1),
            ("copi", 1)
        ]
        super().__init__(layout)


class LcdPeripheral(Peripheral, Elaboratable):
    def __init__(self, pins, **kwargs):
        super().__init__()

        self.pins = pins

        bank            = self.csr_bank()
        self.ch         = bank.csr(8, "w")
        self.x          = bank.csr(8, "w")
        self.y          = bank.csr(8, "w")
        self.color      = bank.csr(16, "w")

        self._bridge    = self.bridge(data_width=32, granularity=8, alignment=2)
        self.bus        = self._bridge.bus

    def elaborate(self, platform):
        m = Module()
        m.submodules.bridge  = self._bridge

        m.submodules.lcd = lcd = ST7789(reset_delay=10000, reset_period=10000)

        m.d.comb += [
            self.pins.resn.eq(lcd.spi_resn),
            self.pins.csn.eq(lcd.spi_csn),
            self.pins.dc.eq(lcd.spi_dc),
            self.pins.sclk.eq(lcd.spi_clk),
            self.pins.copi.eq(lcd.spi_mosi)
        ]

        # Draw chequered pattern
        #with m.If(lcd.x[4] ^ lcd.y[4]):
        #    m.d.comb += lcd.color.eq(lcd.x[3:8] << 6)
        #with m.Else():
        #    m.d.comb += lcd.color.eq(lcd.y[3:8] << 11)

        with m.If(lcd.eof):
            m.d.sync += lcd.color.eq(self.color.w_data[:16])

        return m



