LINKER_SCR=generated/sections.lds
CC=riscv-none-embed-gcc
CINC=-I.
CFLAGS=-g -march=rv32ima -mabi=ilp32 -Wl,--build-id=none,-Bstatic,-T,$(LINKER_SCR),--strip-debug -static -ffreestanding -nostdlib $(CINC)
OBJCOPY=riscv-none-embed-objcopy

BIOS_START=generated/start.S
DRV_SOURCES=$(wildcard drivers/*.c) $(wildcard drivers/*.S)
DRV_HEADERS=$(wildcard drivers/*.h)

bios.elf: $(BIOS_START) $(DRV_SOURCES) $(DRV_HEADERS) $(BIOS_HEADERS) $(BIOS_SOURCES) $(LINKER_SCR)
	riscv-none-embed-gcc $(CFLAGS) -o bios.elf $(BIOS_START) $(DRV_SOURCES) $(BIOS_SOURCES)

bios.bin: bios.elf
	riscv-none-embed-objcopy -O binary bios.elf bios.bin

clean:
	rm -f bios.bin bios.elf
