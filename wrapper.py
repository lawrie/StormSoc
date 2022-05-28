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
