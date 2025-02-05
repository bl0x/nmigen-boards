import os
import subprocess

from amaranth.build import *
from amaranth.vendor import XilinxPlatform
from .resources import *

"""
Board features:
    FPGA: XC7A100T-2CSG324I
    DDR3: 2Gb DDR3 (MT41J128M16JT-125:K, 400 MHz, 16 bit data)
    Flash memory: 128 Mb SPI flash memory (N25Q128A13ESE40E or N25Q128A13EF840E)
    Clock: 100MHz CMOS oscillator
    USB: High-Speed USB 2.0 interface for On-board flash programming.
    Revision V1: FT2232H Channel A is dedicated to SPI Flash /JTAG Programming.
                         Channel B can be used for custom applications.
    Revision V2: FT2232H Channel B is dedicated to SPI Flash /JTAG Programming.
                         Channel A can be used for custom applications.
    On-board voltage regulators for single power rail operation
    FPGA configuration via JTAG or USB
    Maximum IOs for user-defined purposes FPGA – 140 IOs FT2232H – 8 IOs

Documentation:
    https://numato.com/docs/neso-artix-7-fpga-development-board/

Example Usage:
    platform = NumatoNesoPlatform(toolchain="Vivado")
    platform.build(Top(), do_program=True)

Supported programmer:
    tentative: openFPGAloader with arty_a7_100t or nexys_a7_100 board
    requires custom cable (similar to 'numato'?):
      FTDI_SER(0x2a19, 0x1005, FTDI_INTF_[A|B], 0x08, 0x4b, 0x00, 0x00)

Voltage settings:
    set_property CFGBVS VCCO [current_design]
    set_property CONFIG_VOLTAGE 3.3 [current_design]

"""

__all__ = ["NumatoNesoPlatform"]

class NumatoNesoPlatform(XilinxPlatform):
    device = "xc7a100t"
    package = "csg324"
    speed = "2"
    default_clk = "clk100"
    default_rst = "rst"
    resources   = [
        # On-board oscillator
        Resource("clk100", 0, Pins("F4", dir="i"),
                 Clock(100e6), Attrs(IOSTANDARD="LVCMOS33")),
       
        # DDR3 RAM
        Resource("ddr3", 0,
            Subsignal("rst",    PinsN("U8", dir="o")),
            Subsignal("clk",    DiffPairs("L6", "L5", dir="o"),
                                Attrs(IOSTANDARD="DIFF_SSTL15", IN_TERM="UNTUNED_SPLIT_50")),
            Subsignal("clk_en", Pins("M1", dir="o")),
            Subsignal("cs",     PinsN("K6", dir="o")),
            Subsignal("we",     PinsN("N2", dir="o")),
            Subsignal("ras",    PinsN("N4", dir="o")),
            Subsignal("cas",    PinsN("L1", dir="o")),
            Subsignal("a",      Pins("M4 P4 M6 T1 L3 P5 M2 N1 L4 N5 R2 K5 N6 K3", dir="o")),
            Subsignal("ba",     Pins("P2 P3 R1", dir="o")),
            Subsignal("dqs",    DiffPairs("U9 U2", "V9 V2", dir="io"),
                                Attrs(IOSTANDARD="DIFF_SSTL15", IN_TERM="UNTUNED_SPLIT_50")),
            Subsignal("dq",     Pins("R7 V6 R8 U7 V7 R6 U6 R5 T5 U3 V5 U4 V4 T4 V1 T3", dir="io"),
                                Attrs(IN_TERM="UNTUNED_SPLIT_50")),
            Subsignal("dm",     Pins("T6 U1", dir="o")),
            Subsignal("odt",    Pins("M3", dir="o")),
            Attrs(IOSTANDARD="SSTL15", SLEW="FAST"),
        ),

        # QSPI Flash
        # To be verified:
        *SPIFlashResources(0,
            # IO[0..3] = [K17, K18, L14, M14]
            cs_n="L13", clk="E9", copi="K17", cipo="K18", wp_n="L14",
            hold_n="F18", 
            attrs=Attrs(IOSTANDARD="LVCMOS33")
        )
    ]
    # Pin header connectors
    connectors = [
        Connector("p", 4, # IOSTANDARD="LVCMOS33"
            """
            A14 A13 D13 D12  A11 B11 F14 F13  B14 B13 A16 A15   A9 A10 B12 C12
             A8  B8 C10 C11   B9  C9  B6  B7   C5  C6  A5  A6   C7  D8  D7  E7
             D4  D5  D3  E3   A3  A4  B2  B3   C1  C2  A1  B1   G1  H1  E1  F1
             D2  E2  K1  K2   J2  J3  B4  C4   E5  E6  G2  H2   F3  F5  G3  G4
             H5  H6  H4  J4   F6  G6
            """),
        Connector("p", 5, # IOSTANDARD="LVCMOS33"
            """
            B16 B17 D14 C14  C16 C17 H14 G14   T8  J5 E15 E16  E17 D17 F15 F16
            J14 H15 H17 G17  H16 G16 K13 J13  L15 L16 L18 M18  R12 R13 K15 J15
            M16 M17 R18 T18  P15 R15 N15 N16  N14 P14 P17 R17  N17 P18 U16 V17
            U17 U18 U14 V14  V15 V16 T14 T15  R16 T16  T9 T10  T13 U13 T11 U11
            R10 R11 V10 V11  U12 V12 
            """),
        # FTDI Chip
        Connector("ftdi", 0, { # IOSTANDARD="LVCMOS33"
            "d0": "A18",
            "d1": "B18",
            "d2": "D18",
            "d3": "E18",
            "d4": "F18",
            "d5": "G18",
            "d6": "J17",
            "d7": "J18",
            "txe": "K16",
            "rxf": "G13",
            "wr_n": "M13",
            "rd_n": "D9",
             "siwub": "J18"
         })
    ]
    
    def toolchain_prepare(self, fragment, name, **kwargs):
        overrides = {
            "script_before_bitstream":
                "set_property BITSTREAM.CONFIG.SPI_BUSWIDTH 4 [current_design]",
            "script_after_bitstream":
                "write_cfgmem -force -format bin -interface spix4 -size 16 "
                "-loadbit \"up 0x0 {name}.bit\" -file {name}.bin".format(name=name),
            "add_constraints":
                """
                set_property CFGBVS VCCO [current_design]
                set_property CONFIG_VOLTAGE 3.3 [current_design]
                """
        }
        return super().toolchain_prepare(fragment, name, **overrides, **kwargs)

if __name__ == "__main__":
    from .test.blinky import *
    NumatoNesoPlatform().build(Blinky())
