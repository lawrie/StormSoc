from amaranth import *
from amaranth.build import *

from amaranth_orchard.base.gpio import GPIOPins
from amaranth_orchard.io.uart import UARTPins
from amaranth_orchard.memory.hyperram import HyperRAMPins

from peripheral.seg7 import Seg7Pins
from peripheral.lcd import LcdPins

from typing import List

LED_BLADE = 1
LCD_BLADE = 3
SEG7_TILE = 3

PINMAP = {"a": "6", "b": "8", "c": "12", "d": "10", "e": "7", "f": "5", "g": "4", "dp": "9", "ca": "3 2 1"}


def tile_resources(tile: int) -> List:
    signals = [
        Subsignal(signal,
                  Pins(pin, invert=True, dir="o", conn=("tile", tile)),
                  Attrs(IO_STANDARD="SB_LVCMOS")
                  ) for signal, pin in PINMAP.items()
    ]

    return [Resource("seven_seg_tile", 0, *signals)]

class SoCWrapper(Elaboratable):
    """
    This wrapper provides glue to simplify use of the Blackice Nxt platform, and integrate between
    the Amaranth platform and the format of pins that the IP cores expect.
    """

    def is_sim(self, platform):
        return hasattr(platform, "is_sim")

    def get_led_gpio(self, m, platform):
        leds = GPIOPins(width=7)

        platform.add_resources([
            Resource("leds6", 0,
                     Subsignal("leds",
                               Pins("1 2 3 4 5 6", dir="o", invert=True, conn=("blade", LED_BLADE)),
                               Attrs(IO_STANDARD="SB_LVCMOS")
                               )
                     )
        ])

        if self.is_sim(platform):
            # TODO
            pass
        else:
            leds6 = platform.request("leds6")
            led = platform.request("led")
            m.d.comb += [
                leds6.eq(leds.o[1:]),
                led.eq(leds.o[0])
            ]

        return leds

    def get_uart(self, m, platform):
        uart = UARTPins()
        if self.is_sim(platform):
            m.submodules.uart_model = platform.add_model("uart_model", uart, edge_det=[])
        else:
            platform.add_resources([
                Resource("ext_uart", 0,
                         Subsignal("tx", Pins("10", dir="o", conn=("pmod", 5)), Attrs(IO_STANDARD="SB_LVCMOS")),
                         Subsignal("rx", Pins("4", dir="i", conn=("pmod", 5)), Attrs(IO_STANDARD="SB_LVCMOS")),
                         Subsignal("gnd", Pins("9", dir="o", conn=("pmod", 5)), Attrs(IO_STANDARD="SB_LVCMOS")))
            ])
            ext_uart = platform.request("ext_uart")
            m.d.comb += [
                ext_uart.tx.eq(uart.tx_o),
                uart.rx_i.eq(ext_uart.rx)
            ]
        return uart

    def get_seg7(self, m, platform):
        seg7 = Seg7Pins()

        platform.add_resources(tile_resources(SEG7_TILE))

        seg7_pins = platform.request("seven_seg_tile")

        m.d.comb += [
            Cat([seg7_pins.a,seg7_pins.b, seg7_pins.c, seg7_pins.d,
                 seg7_pins.e, seg7_pins.f, seg7_pins.g]).eq(seg7.leds),
            seg7_pins.ca.eq(seg7.ca)
        ]
        return seg7

    def get_lcd(self, m, platform):
        lcd = LcdPins()

        platform.add_resources([
            Resource("oled", 0,
                     Subsignal("oled_bl", Pins("1", dir="o", conn=("blade", LCD_BLADE))),
                     Subsignal("oled_resn", Pins("2", dir="o", conn=("blade", LCD_BLADE))),
                     Subsignal("oled_csn", Pins("3", dir="o", conn=("blade", LCD_BLADE))),
                     Subsignal("oled_clk", Pins("4", dir="o", conn=("blade", LCD_BLADE))),
                     Subsignal("oled_dc", Pins("5", dir="o", conn=("blade", LCD_BLADE))),
                     Subsignal("oled_mosi", Pins("6", dir="o", conn=("blade", LCD_BLADE))),
                     Attrs(IO_STANDARD="SB_LVCMOS"))
        ])

        oled_pins =  seg7_pins = platform.request("oled")

        m.d.comb += [
            oled_pins.oled_clk.eq(lcd.sclk),
            oled_pins.oled_bl.eq(0),
            oled_pins.oled_resn.eq(lcd.resn),
            oled_pins.oled_csn.eq(lcd.csn),
            oled_pins.oled_dc.eq(lcd.dc),
            oled_pins.oled_mosi.eq(lcd.copi)
        ]

        return lcd

    def get_hram(self, m, platform):
        # HyperRam on the Blackice Nxt board
        hram = HyperRAMPins(cs_count=1)
        if self.is_sim(platform):
            m.submodules.hram = platform.add_model("hyperram_model", hram, edge_det=['clk_o', ])
        else:
            plat_hram = platform.request("hyperbus", 0)
            m.d.comb += [
                plat_hram.clk.o.eq(hram.clk_o),
                plat_hram.cs.o.eq(hram.csn_o),

                plat_hram.rd.o.eq(hram.rwds_o),
                plat_hram.rd.oe.eq(hram.rwds_oe),
                hram.rwds_i.eq(plat_hram.rd.i),

                plat_hram.data.o.eq(hram.dq_o),
                plat_hram.data.oe.eq(hram.dq_oe),
                hram.dq_i.eq(plat_hram.data.i),
            ]
        return hram

    def elaborate(self, platform):
        m = Module()

        if self.is_sim(platform):
            m.domains.sync = ClockDomain()
            m.d.comb += ClockSignal().eq(platform.clk)
            m.d.comb += ResetSignal().eq(platform.rst)

        return m
