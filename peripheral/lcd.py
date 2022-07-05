from amaranth import *

from amaranth_orchard.base.peripheral import Peripheral

from peripheral.st7789 import ST7789
from readbin import readbin


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
    def __init__(self, pins, font_file="peripheral/font_bizcat8x16.mem", **kwargs):
        super().__init__()

        self.pins       = pins
        self.font_file  = font_file

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

        # Create the tile map
        tile_data = Memory(width=8, depth=30 * 15)
        m.submodules.tr = tr = tile_data.read_port()
        m.submodules.tw = tw = tile_data.write_port()

        # Read in the font
        font = readbin(self.font_file)
        font_data = Memory(width=8, depth=4096, init=font)
        m.submodules.fr = fr = font_data.read_port()

        y = Signal(8)

        # Connect tilemap
        m.d.comb += [
            tw.addr.eq(self.y.w_data * 30 + self.x.w_data),
            tw.en.eq(self.ch.w_stb),
            tw.data.eq(self.ch.w_data),
            y.eq(239 - lcd.y),
            tr.addr.eq(lcd.x[4:] * 30 + y[3:]),
            fr.addr.eq(Cat(lcd.x[:4], tr.data)),
            lcd.color.eq(Mux(fr.data.bit_select(~y[:3], 1), self.color.w_data, 0x0000))
        ]

        return m



