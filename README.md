# StormSoc

![Blackice Nxt](https://raw.githubusercontent.com/lawrie/lawrie.github.io/master/images/stormsoc.jpg)

## Introduction

StormSoc is a Risc-V System -on-a-chip using the [Minerva](https://github.com/minerva-cpu/minerva) CPU and the [amaranth-orchard](https://gitlab.com/ChipFlow/amaranth-orchard) SoC cores for memory and some of its peripherals.

It runs on the [Blackice Nxt](https://github.com/folknology/BlackIceNxt) ice40 FPGA board.

One reason to use amaranth-orchard rather than, say, [lambdasoc](https://github.com/lambdaconcept/lambdasoc) is that amaranth-orchard has a HyperRAM controller,
and the Blackice Nxt board includes HyperRAM.

The Blackice Nxt board also supports HyperFlash, but there is currently no controller for that.

The peripherals from amaranth-orchard that are used are the uart and the LED gpio peripherals. The uart currently needs an external USB to serial devices (such as an FTDI one), plugged into Pmod pins. The LED gpio peripheral uses the single led on the IceLogicBus board, plus 6 leds on an LED blade.

The Soc includes other peripheral cores for the Blackice 7-segment tile, and the Blackice LCD blade.

Two SoCs are supported: a minimal BRAM version(soc.py) and a HyperRAM version(hypersoc.py).

## Remote loading

It is possible to stop the CPU, load a new program, and execute it, remotely from the PC.

This is done by:

```python
send_reset(True)
send_file("software/bios.test")
send_reset(False)
```

after programming the bitstream with `platform.build(... do_program=True)`.


