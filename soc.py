from amaranth import *
from amaranth_soc import wishbone

from minerva.core import Minerva

from amaranth_orchard.base.gpio import GPIOPeripheral
from amaranth_orchard.io.uart import UARTPeripheral
from amaranth_orchard.memory.sram import SRAMPeripheral

from mystorm_boards.icelogicbus import *

from wrapper import SoCWrapper
from software.soft_gen import SoftwareGenerator

from peripheral.seg7 import Seg7Peripheral
from peripheral.lcd import LcdPeripheral

def readbios():
    """ Read bios.bin into an array of integers """
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
        self.seg7_base = 0xb3000000
        self.lcd_base = 0xb4000000

    def elaborate(self, platform):
        # Elaborate the wrapper
        m = super().elaborate(platform)

        # We need a Wishbone arbiter as the Minerva CPU has instruction and data cache buses, which are both master
        self._arbiter = wishbone.Arbiter(addr_width=30, data_width=32, granularity=8)

        # A Wishbone decoder for the memory and peripherals
        self._decoder = wishbone.Decoder(addr_width=30, data_width=32, granularity=8)

        # Use a Minerva CPU without a cache
        self.cpu = Minerva(with_icache=False, icache_nlines=8, icache_limit=0x800,
                           with_dcache=False, dcache_nlines=8, dcache_limit=0x400)

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
        self.rom =  SRAMPeripheral(size=self.rom_size, writable=False)
        self.rom.init = readbios()
        self._decoder.add(self.rom.bus, addr=self.rom_base)

        # Create BRAM RAM and add it to the decoder
        self.sram = SRAMPeripheral(size=self.sram_size)
        self._decoder.add(self.sram.bus, addr=self.sram_base)

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
        m.submodules.sram     = self.sram
        m.submodules.gpio     = self.gpio
        m.submodules.uart     = self.uart
        m.submodules.seg7     = self.seg7
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
            ram_start=self.sram_base, ram_size=self.sram_size, # place BIOS data in SRAM
        )

        sw.add_periph("gpio", "LED_GPIO", self.led_gpio_base)
        sw.add_periph("uart", "UART0", self.uart_base)
        sw.add_periph("seg7", "SEG70", self.seg7_base)
        sw.add_periph("lcd", "LCD0", self.lcd_base)

        sw.generate("software/generated")

        return m

if __name__ == "__main__":
    platform = IceLogicBusPlatform()
    platform.build(StormSoC(), do_program=True)


