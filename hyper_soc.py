from amaranth_orchard.memory.hyperram import HyperRAM
from wrapper import SoCWrapper
from software.soft_gen import SoftwareGenerator

from amaranth import *
from amaranth_soc import wishbone
from amaranth.hdl.xfrm import ResetInserter

from minerva.core import Minerva

from amaranth_orchard.base.gpio import GPIOPeripheral
from amaranth_orchard.io.uart import UARTPeripheral
from peripheral.sram import SRAMPeripheral

from mystorm_boards.icelogicbus import *

from peripheral.seg7 import Seg7Peripheral
from peripheral.lcd import LcdPeripheral

from pll import PLL
from qspimem import QspiMem

import time


def readbios():
    """ Read bios.bin into an array of integers """
    f = open("software/bios.bin", "rb")
    l = []
    while True:
        b = f.read(4)
        if b:
            l.append(int.from_bytes(b, "little"))
        else:
            break
    f.close()
    return l


class StormHyperSoC(SoCWrapper):
    def __init__(self):
        super().__init__()

        # Memory regions
        self.rom_base = 0x00000000
        self.rom_size = 4 * 1024  # 4KiB
        self.hyperram_base = 0x10000000
        self.hyperram_size = 1 * 1024  # Use just 1KiB as in SRAM version

        # CSR regions
        self.led_gpio_base = 0xb1000000
        self.uart_base = 0xb2000000
        self.seg7_base = 0xb3000000
        self.lcd_base = 0xb4000000
        self.hram_ctrl_base = 0xb5000000

    def elaborate(self, platform):
        # Elaborate the wrapper
        m = super().elaborate(platform)

        # Qspi domain
        clk_freq = 100000000
        # Create a Pll for higher speed clock
        m.submodules.pll = pll = PLL(freq_in_mhz=int(platform.default_clk_frequency / 1e6),
                                     freq_out_mhz=int(clk_freq / 1e6),
                                     domain_name="qspi")
        # Set the sync domain to the pll domain
        m.domains.qspi = cd_qspi = pll.domain
        m.d.comb += pll.clk_pin.eq(ClockSignal())
        platform.add_clock_constraint(cd_qspi.clk, clk_freq)

        # Add QspiMem submodule
        m.submodules.qspimem = qspimem = QspiMem(domain="qspi")

        # Connect pins
        qspi = platform.request("qspi")
        led = platform.request("led")
        m.d.comb += [
            qspimem.qss.eq(qspi.cs),
            qspimem.qck.eq(qspi.clk),
            qspimem.qd_i.eq(qspi.data.i),
            qspi.data.o.eq(qspimem.qd_o),
            qspi.data.oe.eq(qspimem.qd_oe)
        ]

        cpu_reset = Signal()
        with m.If(qspimem.wr & (qspimem.addr == 0x10000)):
            m.d.qspi += cpu_reset.eq(qspimem.dout[0])

        m.d.sync += led.eq(cpu_reset)

        # We need a Wishbone arbiter as the Minerva CPU has instruction and data cache buses, which are both master
        self._arbiter = wishbone.Arbiter(addr_width=30, data_width=32, granularity=8)

        # A Wishbone decoder for the memory and peripherals
        self._decoder = wishbone.Decoder(addr_width=30, data_width=32, granularity=8)

        # Use a Minerva CPU without a cache
        self.cpu = ResetInserter(cpu_reset)(Minerva(with_icache=True, icache_nlines=8, icache_limit=0x800,
                                                    with_dcache=False, dcache_nlines=8, dcache_limit=0x400))

        # Create wishbone buses for the cpu instruction and data caches. Needed even for dummy caches
        self.ibus = wishbone.Interface(addr_width=30, data_width=32, granularity=8,
                                       features={"err", "cti", "bte"})
        self.dbus = wishbone.Interface(addr_width=30, data_width=32, granularity=8,
                                       features={"err", "cti", "bte"})

        # We need a signal for an external interrupt
        self.ip   = Signal.like(self.cpu.external_interrupt)

        # Add the buses to the arbiter
        self._arbiter.add(self.ibus)
        self._arbiter.add(self.dbus)

        # Create a BRAM Rom and load the Bios into it and add it to the decoder
        self.rom =  SRAMPeripheral(size=self.rom_size, loadable=True, writable=False)
        self.rom.init = readbios()
        self._decoder.add(self.rom.bus, addr=self.rom_base)

        # Load interface
        din = Signal(24)
        m.d.comb += [
            self.rom.addr.eq(qspimem.addr[2:]),
            self.rom.wr.eq(qspimem.wr & (qspimem.addr < 0x10000) & (qspimem.addr[:2] == 3)),
            self.rom.din.eq(Cat(din, qspimem.dout))
        ]

        with m.If(qspimem.wr & (qspimem.addr < 0x10000) & (qspimem.addr[:2] < 3)):
            m.d.qspi += din.eq(Cat(din[8:], qspimem.dout))

        self.hyperram = HyperRAM(pins=super().get_hram(m, platform), init_latency=7)
        self._decoder.add(self.hyperram.data_bus, addr=self.hyperram_base)
        self._decoder.add(self.hyperram.ctrl_bus, addr=self.hram_ctrl_base)

        # Create the GPIO peripheral and add it to the decoder
        self.gpio = GPIOPeripheral(pins=super().get_led_gpio(m, platform))
        self._decoder.add(self.gpio.bus, addr=self.led_gpio_base)

        # Create the uart peripheral and add it to the decoder
        self.uart = UARTPeripheral(
            init_divisor=(25000000//115200),
            pins=super().get_uart(m, platform))
        self._decoder.add(self.uart.bus, addr=self.uart_base)

        self.seg7 = Seg7Peripheral(
            pins=super().get_seg7(m, platform)
        )
        self._decoder.add(self.seg7.bus, addr=self.seg7_base)

        self.lcd = LcdPeripheral(
            pins=super().get_lcd(m, platform)
        )
        self._decoder.add(self.lcd.bus, addr=self.lcd_base)

        # Add all the submodules
        m.submodules.arbiter  = self._arbiter
        m.submodules.cpu      = self.cpu
        m.submodules.decoder  = self._decoder
        m.submodules.rom      = self.rom
        m.submodules.hyperram  = self.hyperram
        m.submodules.gpio     = self.gpio
        m.submodules.uart     = self.uart
        m.submodules.seg7 = self.seg7
        m.submodules.lcd = self.lcd

        m.d.comb += [
            # Connect the arbiter to the decoder
            self._arbiter.bus.connect(self._decoder.bus),
            # Connect the Minerva cpu buses to the Wishbone buses
            self.cpu.ibus.connect(self.ibus),
            self.cpu.dbus.connect(self.dbus),
            # Connect the external interrupt signal
            self.cpu.external_interrupt.eq(self.ip)
        ]

        if self.is_sim(platform):
            m.submodules.bus_mon = platform.add_monitor("wb_mon", self._decoder.bus)

        # Generate soc.h, start.S and the linker script
        sw = SoftwareGenerator(
            rom_start=self.rom_base, rom_size=self.rom_size, # place BIOS in SRAM
            ram_start=self.hyperram_base, ram_size=self.hyperram_size, # place BIOS data in HyperRam
        )

        sw.add_periph("gpio", "LED_GPIO", self.led_gpio_base)
        sw.add_periph("uart", "UART0", self.uart_base)
        sw.add_periph("seg7", "SEG70", self.seg7_base)
        sw.add_periph("lcd", "LCD0", self.lcd_base)

        sw.generate("software/generated")

        return m


def send_cmd(addr, data, debug=True):
    command = b'\x03' + addr.to_bytes(4, 'big') + len(data).to_bytes(4, 'big') + data
    if debug:
        print("Sending command: ", command)
    platform.bus_send(command)


def send_reset(rst):
    addr = 0x10000
    data = b"\x01" if rst else b"\x00"
    send_cmd(addr, data)


def send_small_file(fn):
    data = bytearray()
    with open(fn, "rb") as f:
        byte = f.read(1)
        while byte:
            data += byte
            byte = f.read(1)
    print("Sending file: ", fn)
    send_cmd(0, data, debug=False)


def send_file(fn):
    """ Send file in 256 byte chunks """
    data = bytearray()
    addr = 0
    with open(fn, "rb") as f:
        print("Sending file: ", fn)
        byte = f.read(1)
        n = 0
        while True:
            while byte and n < 256:
                data += byte
                byte = f.read(1)
                n += 1
            print("Sending to address {0}, number of bytes {1}".format(addr, n))
            send_cmd(addr, data, debug=False)
            if not byte:
                break
            data = bytearray()
            n = 0
            addr += 256


if __name__ == "__main__":
    platform = IceLogicBusPlatform()
    platform.build(StormHyperSoC(), nextpnr_opts="--timing-allow-fail", do_program=True)
    time.sleep(5)
    send_reset(True)
    send_file("software/bios.save")
    send_reset(False)
