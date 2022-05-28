from amaranth import *
from amaranth.build import *
from amaranth.lib.cdc import ResetSynchronizer
from amaranth_boards.ulx3s import *
from amaranth_boards.ulx3s import *

from amaranth_orchard.memory.spimemio import QSPIPins
from amaranth_orchard.base.gpio import GPIOPins
from amaranth_orchard.io.uart import UARTPins
from amaranth_orchard.memory.hyperram import HyperRAMPins

BLADE = 1

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
                               Pins("1 2 3 4 5 6", dir="o", invert=True, conn=("blade", BLADE)),
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

    def get_hram(self, m, platform):
        # Dual HyperRAM PMOD, starting at GPIO 0+/-
        hram = HyperRAMPins(cs_count=4)
        if self.is_sim(platform):
            m.submodules.hram = platform.add_model("hyperram_model", hram, edge_det=['clk_o', ])
        else:
            platform.add_resources([
                Resource("hyperram", 0,
                    Subsignal("csn",    Pins("9- 9+ 10- 10+", conn=("gpio", 0), dir='o')),
                    Subsignal("rstn",   Pins("8+", conn=("gpio", 0), dir='o')),
                    Subsignal("clk",    Pins("8-", conn=("gpio", 0), dir='o')),
                    Subsignal("rwds",   Pins("7+", conn=("gpio", 0), dir='io')),

                    Subsignal("dq",     Pins("3- 2- 1- 0- 0+ 1+ 2+ 3+", conn=("gpio", 0), dir='io')),

                    Attrs(IO_TYPE="LVCMOS33"),
                )
            ])

            plat_hram = platform.request("hyperram", 0)
            m.d.comb += [
                plat_hram.clk.o.eq(hram.clk_o),
                plat_hram.csn.o.eq(hram.csn_o),
                plat_hram.rstn.o.eq(hram.rstn_o),

                plat_hram.rwds.o.eq(hram.rwds_o),
                plat_hram.rwds.oe.eq(hram.rwds_oe),
                hram.rwds_i.eq(plat_hram.rwds.i),

                plat_hram.dq.o.eq(hram.dq_o),
                plat_hram.dq.oe.eq(hram.dq_oe),
                hram.dq_i.eq(plat_hram.dq.i),
            ]
        return hram

    def elaborate(self, platform):
        m = Module()

        if self.is_sim(platform):
            m.domains.sync = ClockDomain()
            m.d.comb += ClockSignal().eq(platform.clk)
            m.d.comb += ResetSignal().eq(platform.rst)

        return m
