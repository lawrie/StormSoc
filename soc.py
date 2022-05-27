from wrapper import SoCWrapper
from software.soft_gen import SoftwareGenerator

from amaranth import *
from amaranth_soc import wishbone

from minerva.core import Minerva

from amaranth_orchard.base.gpio import GPIOPeripheral
from amaranth_orchard.io.uart import UARTPeripheral
from amaranth_orchard.memory.sram import SRAMPeripheral

from mystorm_boards.icelogicbus import *

def readbios():
    f = open("software/bios.bin","rb")
    l = []
    while True:
        b = f.read(4)
        if b:
            l.append(int.from_bytes(b, "little"))
        else:
            break
    f.close()
    return l

class StormSoC(SoCWrapper):
    def __init__(self):
        super().__init__()

        # Memory regions
        self.rom_base = 0x00000000
        self.rom_size = 2 * 1024  # 2KiB
        self.sram_base = 0x10000000
        self.sram_size = 1*1024 # 1KiB

        # CSR regions
        self.led_gpio_base = 0xb1000000
        self.uart_base = 0xb2000000

    def elaborate(self, platform):
        m = super().elaborate(platform)

        self._arbiter = wishbone.Arbiter(addr_width=30, data_width=32, granularity=8)
        self._decoder = wishbone.Decoder(addr_width=30, data_width=32, granularity=8)

        self.cpu = Minerva(with_icache=True, icache_nlines=8, icache_limit=0x800,
                           with_dcache=True, dcache_nlines=8, dcache_limit=0x400)
        self.ibus = wishbone.Interface(addr_width=30, data_width=32, granularity=8,
                                       features={"err", "cti", "bte"})
        self.dbus = wishbone.Interface(addr_width=30, data_width=32, granularity=8,
                                       features={"err", "cti", "bte"})
        self.ip   = Signal.like(self.cpu.external_interrupt)
        self._arbiter.add(self.ibus)
        self._arbiter.add(self.dbus)

        self.rom =  SRAMPeripheral(size=self.rom_size, writable=False)
        data=readbios()
        self.rom.init = data
        print(len(data))
        print(data)
        self._decoder.add(self.rom.bus, addr=self.rom_base)

        self.sram = SRAMPeripheral(size=self.sram_size)
        self._decoder.add(self.sram.bus, addr=self.sram_base)

        self.gpio = GPIOPeripheral(pins=super().get_led_gpio(m, platform))
        self._decoder.add(self.gpio.bus, addr=self.led_gpio_base)

        self.uart = UARTPeripheral(
            init_divisor=(25000000//115200),
            pins=super().get_uart(m, platform))
        self._decoder.add(self.uart.bus, addr=self.uart_base)

        m.submodules.arbiter  = self._arbiter
        m.submodules.cpu      = self.cpu
        m.submodules.decoder  = self._decoder
        m.submodules.rom      = self.rom
        m.submodules.sram     = self.sram
        m.submodules.gpio     = self.gpio
        m.submodules.uart     = self.uart

        m.d.comb += [
            self._arbiter.bus.connect(self._decoder.bus),
            self.cpu.ibus.connect(self.ibus),
            self.cpu.dbus.connect(self.dbus),
            self.cpu.external_interrupt.eq(self.ip)
        ]

        if self.is_sim(platform):
            m.submodules.bus_mon = platform.add_monitor("wb_mon", self._decoder.bus)

        sw = SoftwareGenerator(
            rom_start=self.rom_base, rom_size=self.rom_size, # place BIOS in SRAM
            ram_start=self.sram_base, ram_size=self.sram_size, # place BIOS data in SRAM
        )

        sw.add_periph("gpio", "LED_GPIO", self.led_gpio_base)
        sw.add_periph("uart", "UART0", self.uart_base)

        sw.generate("software/generated")

        return m

if __name__ == "__main__":
    platform = IceLogicBusPlatform()
    platform.build(StormSoC(), do_program=True)


