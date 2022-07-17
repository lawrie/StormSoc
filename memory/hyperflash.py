# Original litehyperbus version:
# Copyright (c) 2019 Antti Lukats <antti.lukats@gmail.com>
# Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
# Improved aramanth-soc port:
# Copyright (c) 2021-2022 gatecat <gatecat@ds0.me>
# SPDX-License-Identifier: BSD-2-Clause

from amaranth import *

from amaranth.sim import Simulator, Delay, Settle

from amaranth_soc import wishbone
from amaranth_soc.memory import MemoryMap
from amaranth_orchard.base.peripheral import Peripheral

from math import ceil, log2

# HyperFlash -----------------------------------------------------------------------------------------


class HyperFlashPins(Record):
    def __init__(self, cs_count=1):
        layout = [
            ("clk_o", 1),
            ("csn_o", cs_count),
            ("rstn_o", 1),
            ("rwds_o", 1),
            ("rwds_oe", 1),
            ("rwds_i", 1),
            ("dq_o", 8),
            ("dq_oe", 1),
            ("dq_i", 8),
        ]
        super().__init__(layout)

class HyperFlash(Peripheral, Elaboratable):
    """HyperFlash

    Provides a very simple/minimal HyperFlash read core that should work with all FPGA/HyperFlash chips:
    - FPGA vendor agnostic.
    - no setup/chip configuration (use default latency).

    This core favors portability and ease of use over performance.
    """
    def __init__(self, *, pins, init_latency=16, index=0):
        super().__init__()
        self.pins = pins
        self.cs_count = len(self.pins.csn_o)
        self.size = 2**24 * self.cs_count  # 16MB per CS pin
        self.init_latency = init_latency
        # assert self.init_latency in (16) # TODO: anything else possible ?
        self.data_bus = wishbone.Interface(addr_width=ceil(log2(self.size / 4)),
                                           data_width=32, granularity=8)
        map = MemoryMap(addr_width=ceil(log2(self.size)), data_width=8)
        map.add_resource(name=f"hyperram{index}", size=self.size, resource=self)
        self.data_bus.memory_map = map

        # Control registers
        self.latency = Signal(5, reset=self.init_latency)

    def elaborate(self, platform):
        m = Module()

        latched_adr = Signal(len(self.data_bus.adr))

        counter = Signal(8)
        wait_count = Signal(4)
        clk = Signal()
        csn = Signal(self.cs_count)

        # Data shift register
        sr = Signal(48)

        # Drive out clock on negedge while active
        m.domains += ClockDomain("neg", clk_edge="neg")
        m.d.comb += [
            ClockSignal("neg").eq(ClockSignal()),
            ResetSignal("neg").eq(ResetSignal()),
        ]
        with m.If(csn.all()):
            # Reset clock if nothing active
            m.d.neg += clk.eq(0)
        with m.Elif(counter.any()):
            m.d.neg += clk.eq(~clk)
            m.d.sync += counter.eq(counter-1)
        with m.If(counter.any()):
            # move shift register (sample/output data) on posedge
            m.d.sync += sr.eq(Cat(self.pins.dq_i, sr[:-8]))

        m.d.comb += [
            self.pins.clk_o.eq(clk),
            self.pins.csn_o.eq(csn),
            self.pins.rstn_o.eq(~ResetSignal()),
            self.pins.rwds_oe.eq(0),  # Pin is read only for HyperFlash
            self.pins.dq_o.eq(sr[-8:]),
            self.data_bus.dat_r.eq(sr[:32]),
        ]

        with m.FSM() as fsm:
            with m.State("IDLE"):
                m.d.sync += [
                    counter.eq(0),
                    csn.eq((1 << self.cs_count) - 1),  # all disabled
                ]
                with m.If(self.data_bus.stb & self.data_bus.cyc):  # data bus activity
                    m.d.sync += [
                        csn.eq(~(1 << (self.data_bus.adr[21:]))),
                        self.pins.dq_oe.eq(1),
                        counter.eq(6),
                        # Assign CA
                        sr[47].eq(1),  # Only reads supported
                        sr[46].eq(0),  # memory space
                        sr[45].eq(1),  # linear burst
                        sr[16:45].eq(self.data_bus.adr[2:21]),  # upper address
                        sr[3:16].eq(0),  # RFU
                        sr[1:3].eq(self.data_bus.adr[0:2]),  # lower address
                        sr[0].eq(0),  # address LSB (0 for 32-bit xfers)
                        latched_adr.eq(self.data_bus.adr),
                    ]
                    m.next = "WAIT_CA"
            with m.State("WAIT_CA"):
                # Waiting to shift out CA
                with m.If(counter == 1):
                    m.d.sync += counter.eq(2 * self.latency - 2)
                    m.next = "WAIT_LAT"
            with m.State("WAIT_LAT"):
                m.d.sync += self.pins.dq_oe.eq(0)
                with m.If(counter == 1):
                    # About to shift data
                    m.d.sync += [
                        sr[:16].eq(0),
                        sr[16:].eq(0),  # Only reads supported
                        self.pins.dq_oe.eq(0),
                        counter.eq(4),
                    ]
                    m.next = "SHIFT_DAT"
            with m.State("SHIFT_DAT"):
                with m.If(counter == 1):
                    m.next = "ACK_XFER"
            with m.State("ACK_XFER"):
                m.d.sync += [
                    self.pins.dq_oe.eq(0),
                    self.data_bus.ack.eq(1),
                    wait_count.eq(9)
                ]
                m.next = "WAIT_NEXT"
            with m.State("WAIT_NEXT"):
                m.d.sync += [
                    self.data_bus.ack.eq(0),
                    wait_count.eq(wait_count-1),
                ]
                with m.If(self.data_bus.stb & self.data_bus.cyc & ~self.data_bus.ack):
                    # Is a valid continuation within same page
                    with m.If((self.data_bus.adr[6:] == latched_adr[6:]) & (self.data_bus.adr[:6] == latched_adr[:6] + 1)):
                        m.d.sync += [
                            sr[:16].eq(0),
                            sr[16:].eq(0),
                            self.pins.dq_oe.eq(0),
                            latched_adr.eq(self.data_bus.adr),
                            counter.eq(4),
                        ]
                        m.next = "SHIFT_DAT"
                    with m.Else():
                        # start a new xfer
                        m.d.sync += csn.eq((1 << self.cs_count) - 1)
                        m.next = "IDLE"
                with m.Elif(wait_count == 0):
                    m.d.sync += csn.eq((1 << self.cs_count) - 1)
                    m.next = "IDLE"

        return m
