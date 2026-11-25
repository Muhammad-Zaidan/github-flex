#!/usr/bin/env python3
"""
Generator skematik KiCad: Power bank / BMS 2-4S + USB-C PD dua arah + output terminal 1-16V.
Semua part dipilih yang tersedia di Tokopedia (lihat docs/bom_tokopedia.md).

    python3 tools/gen_schematic.py

menulis ulang ../kicad/*.kicad_sch, bms.kicad_sym, sym-lib-table, bms.kicad_pro,
serta ../docs/netlist.md dan ../docs/bom.csv.

Gaya gambar:
  * komponen pendukung diletakkan di dekat pin IC dan disambung dengan wire
  * rail daya memakai simbol power (VBUS_SYS, VSYS, PACK+, BATT+, +3V3, GND)
  * sinyal antar sheet memakai hierarchical label + sheet pin (root = diagram blok)
  * nomor referensi per sheet: 1xx USB/PD, 2xx charger, 3xx baterai, 4xx output, 5xx MCU
"""
import os
import sys
import json
import re
from collections import defaultdict, OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from schlib import (SYMS, add, ic_symbol, two_pin, rect, poly, circle, Pin, Sym, Sheet, sheet_file,  # noqa: E402
                    uid, q, g, snap, G)

PROJECT = "bms"
LIB = "bms"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "..", "kicad")
DOC_DIR = os.path.join(HERE, "..", "docs")
ROOT_UUID = uid("root")
DATE = "2026-11-25"
REV = "0.2"

# ============================================================================
# Simbol tambahan
# ============================================================================
add(two_pin("C_Pol", "C", [poly([(-2.032, 0.762), (2.032, 0.762)], 0.508),
                           "(arc (start -2.032 -1.016) (mid 0 -0.508) (end 2.032 -1.016) "
                           "(stroke (width 0.508) (type default)) (fill (type none)))",
                           poly([(0, 2.54), (0, 0.762)]), poly([(0, -2.54), (0, -0.762)]),
                           poly([(-1.778, 1.778), (-0.762, 1.778)]), poly([(-1.27, 2.286), (-1.27, 1.27)])],
            desc="Kapasitor elektrolit (pin 1 = +)"))
_tri = poly([(0, 1.27), (-1.27, -1.27), (1.27, -1.27), (0, 1.27)], 0.254)
add(two_pin("D_Schottky", "D", [poly([(-1.27, 1.27), (1.27, 1.27)], 0.254), poly([(-1.27, 1.27), (-1.27, 0.762)], 0.254),
                                poly([(1.27, 1.27), (1.27, 1.778)], 0.254), _tri,
                                poly([(0, 2.54), (0, 1.27)]), poly([(0, -2.54), (0, -1.27)])],
            names=("K", "A"), desc="Dioda Schottky (1=K, 2=A)"))
add(two_pin("D_Zener", "D", [poly([(-1.27, 1.27), (1.27, 1.27)], 0.254), poly([(1.27, 1.27), (1.778, 1.778)], 0.254), _tri,
                             poly([(0, 2.54), (0, 1.27)]), poly([(0, -2.54), (0, -1.27)])],
            names=("K", "A"), desc="Dioda zener (1=K, 2=A)"))
add(two_pin("Fuse", "F", [rect(-0.762, 2.54, 0.762, -2.54, fill="none"), poly([(0, 2.54), (0, -2.54)])], desc="Sekring"))
# BAT54C: 1=A1 (kiri), 2=A2 (kanan), 3=K bersama (bawah)
add(Sym("BAT54C", "D", [Pin("1", "A1", "passive", -7.62, 0, 0, 2.54), Pin("2", "A2", "passive", 7.62, 0, 180, 2.54),
                        Pin("3", "K", "passive", 0, -5.08, 90, 2.54)],
        [poly([(-5.08, 0), (5.08, 0)]), poly([(0, 0), (0, -2.54)]),
         poly([(-3.81, 1.27), (-3.81, -1.27), (-1.27, 0), (-3.81, 1.27)], 0.254),
         poly([(-1.27, 1.27), (-1.27, -1.27)], 0.254),
         poly([(3.81, 1.27), (3.81, -1.27), (1.27, 0), (3.81, 1.27)], 0.254),
         poly([(1.27, 1.27), (1.27, -1.27)], 0.254)],
        desc="Dual Schottky common cathode (1=A1, 2=A2, 3=K)", hide_pin_names=True, kind="fet",
        footprint="Package_TO_SOT_SMD:SOT-23"))


def dip(name, n):
    from schlib import dip as _dip
    return add(_dip(name, n))


dip("SW_DIP_x02", 2)
dip("SW_DIP_x03", 3)

def fet_pkg(name, base, gnum, snums, dnums, desc):
    from schlib import fet as _fet
    b = _fet(base, pch=base == "Q_PMOS")
    pins = []
    for pn in b.pins:
        nums = {"G": [gnum], "S": snums, "D": dnums}[pn.name]
        for k, n in enumerate(nums):
            pins.append(Pin(n, pn.name, pn.etype, pn.x, pn.y, pn.ang, pn.length, hidden=k > 0))
    s = Sym(name, "Q", pins, b.graphics, desc=desc, hide_pin_names=True, pin_name_offset=0, kind="fet")
    return add(s)


fet_pkg("Q_NMOS_DFN8", "Q_NMOS", "4", ["1", "2", "3"], ["5"],
        "N-MOSFET DFN 3.3x3.3 (AON7410): 1-3=S, 4=G, 5=D/EP")
fet_pkg("Q_PMOS_SO8", "Q_PMOS", "4", ["1", "2", "3"], ["5", "6", "7", "8"],
        "P-MOSFET SO-8 (AO4407A): 1-3=S, 4=G, 5-8=D")


def nfet8(g, s, d):
    return {"4": g, "1": s, "2": s, "3": s, "5": d}


def pfet8(g, s, d):
    return {"4": g, "1": s, "2": s, "3": s, "5": d, "6": d, "7": d, "8": d}


# --- IC (urutan pin dari atas; None = baris kosong) ------------------------
add(ic_symbol("USB_C_Receptacle_USB2.0_16P", "J", [],
              [("VBUS", ["A4", "A9", "B4", "B9"], "passive")] + [None] * 4 +
              [("CC1", ["A5"], "bidirectional")] + [None] * 4 +
              [("CC2", ["B5"], "bidirectional")] + [None] * 4 +
              [("D+", ["A6", "B6"], "bidirectional"), ("D-", ["A7", "B7"], "bidirectional"), None,
               ("SBU1", ["A8"], "bidirectional"), ("SBU2", ["B8"], "bidirectional"), None,
               ("GND", ["A1", "A12", "B1", "B12"], "passive"), ("SHIELD", ["SH"], "passive")],
              desc="USB Type-C receptacle 16P. Nomor pad sesuai footprint HRO TYPE-C-31-M-12",
              footprint="Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12"))

add(ic_symbol("TPS65988", "U",
              [("VBUS1", ["13", "14"], "passive"), ("VBUS2", ["3", "4"], "passive")] + [None] * 3 +
              [("C1_CC1", ["24"], "bidirectional")] + [None] * 4 +
              [("C1_CC2", ["26"], "bidirectional")] + [None] * 4 +
              [("C1_USB_P", ["50"], "bidirectional"), ("C1_USB_N", ["53"], "bidirectional"), None,
               ("PP1_CABLE", ["25"], "passive"), ("PP2_CABLE", ["46"], "passive"), None,
               ("C2_CC1", ["45"], "bidirectional"), ("C2_CC2", ["47"], "bidirectional"),
               ("C2_USB_P", ["54"], "bidirectional"), ("C2_USB_N", ["55"], "bidirectional"), None,
               ("ADCIN1", ["6"], "input")] + [None] * 4 +
              [("ADCIN2", ["10"], "input")] + [None] * 4 +
              [("HRESET", ["44"], "input"), None, ("GPIO1", ["17"], "bidirectional")],
              [("PP_HV1", ["11", "12"], "passive"), ("PP_HV2", ["1", "2"], "passive")] + [None] * 4 +
              [("VIN_3V3", ["5"], "power_in"), ("LDO_3V3", ["9"], "power_out"), ("LDO_1V8", ["35"], "power_out")] +
              [None] * 5 +
              [("I2C1_SDA", ["28"], "bidirectional"), ("I2C1_SCL", ["27"], "bidirectional"),
               ("~{I2C1_IRQ}", ["29"], "output"), None,
               ("I2C2_SDA", ["33"], "bidirectional"), None, None, ("I2C2_SCL", ["32"], "bidirectional"),
               ("~{I2C2_IRQ}", ["34"], "output")] + [None] * 3 +
              [("SPI_POCI", ["36"], "bidirectional"), ("SPI_CLK", ["38"], "bidirectional"),
               ("SPI_PICO", ["37"], "bidirectional"), ("SPI_CS", ["39"], "bidirectional")] + [None] * 4 +
              [("I2C3_SCL", ["21"], "bidirectional"), ("I2C3_SDA", ["22"], "bidirectional"),
               ("I2C3_IRQ", ["23"], "bidirectional"), ("GPIO0", ["16"], "bidirectional"),
               ("GPIO2", ["18"], "bidirectional"), ("GPIO3", ["30"], "bidirectional"),
               ("GPIO4", ["31"], "bidirectional"), ("GPIO12", ["40"], "bidirectional"),
               ("GPIO13", ["41"], "bidirectional"), ("GPIO14", ["42"], "bidirectional"),
               ("GPIO15", ["43"], "bidirectional"), ("GPIO16", ["48"], "bidirectional"),
               ("GPIO17", ["49"], "bidirectional"), None,
               ("DRAIN1", ["8", "15", "19", "58"], "passive"), ("DRAIN2", ["7", "52", "56", "57"], "passive"), None,
               ("GND", ["20", "51", "59"], "power_in")],
              desc="TPS65988 USB-C PD controller, 2x switch 20V/5A dua arah, QFN-56 7x7 (RSH). "
                   "Pinout: datasheet SLVSDB5B Table 5-1. Pin 57/58/59 = thermal pad",
              datasheet="https://www.ti.com/lit/ds/symlink/tps65988.pdf"))

add(ic_symbol("W25Qxx_SOIC8", "U",
              [("DO", ["2"], "output"), ("CLK", ["6"], "input"), ("DI", ["5"], "input"), ("~{CS}", ["1"], "input")],
              [("VCC", ["8"], "power_in"), ("~{WP}", ["3"], "input"), ("~{HOLD}", ["7"], "input"),
               ("GND", ["4"], "power_in")],
              desc="SPI NOR flash SOIC-8 (W25Q16/W25Q80/W25X05), pinout standar",
              footprint="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"))

add(ic_symbol("BQ25713", "U",
              [("VBUS", ["1"], "passive"), None, None, ("ACP", ["3"], "passive")] + [None] * 4 +
              [("ACN", ["2"], "passive")] + [None] * 3 +
              [("ILIM_HIZ", ["6"], "input")] + [None] * 4 +
              [("CELL_BATPRESZ", ["18"], "input")] + [None] * 8 +
              [("CMPIN", ["14"], "input"), ("CMPOUT", ["15"], "open_collector"), None,
               ("IADPT", ["8"], "output")] + [None] * 4 +
              [("IBAT", ["9"], "output")] + [None] * 4 +
              [("PSYS", ["10"], "output")] + [None] * 4 +
              [("COMP1", ["16"], "passive")] + [None] * 6 +
              [("COMP2", ["17"], "passive")],
              [("REGN", ["28"], "power_out"), None, None, ("VDDA", ["7"], "passive")] + [None] * 4 +
              [("HIDRV1", ["31"], "output"), ("BTST1", ["30"], "passive"), ("SW1", ["32"], "passive"),
               ("LODRV1", ["29"], "output"), None,
               ("HIDRV2", ["24"], "output"), ("BTST2", ["25"], "passive"), ("SW2", ["23"], "passive"),
               ("LODRV2", ["26"], "output"), None,
               ("VSYS", ["22"], "passive"), ("~{BATDRV}", ["21"], "output"), None,
               ("SRP", ["20"], "passive"), ("SRN", ["19"], "passive")] + [None] * 3 +
              [("OTG/VAP", ["5"], "input"), ("SDA", ["12"], "bidirectional"), ("SCL", ["13"], "input"),
               ("CHRG_OK", ["4"], "open_collector"), ("~{PROCHOT}", ["11"], "open_collector")] + [None] * 20 +
              [("PGND", ["27", "33"], "power_in")],
              desc="BQ25713 I2C 1-4S NVDC buck-boost charger controller, WQFN-32 4x4 (RSN). Pin 33 = thermal pad. "
                   "Pinout: datasheet SLUSD83C Table 7-1",
              datasheet="https://www.ti.com/lit/ds/symlink/bq25713.pdf"))

add(ic_symbol("HY2213-BB3A", "U", [("VDD", ["2"], "power_in"), None, ("VSS", ["3"], "power_in")],
              [("CB", ["6"], "output"), None, ("NC", ["1", "4", "5"], "no_connect")],
              desc="HY2213-BB3A balancer 1 cell (mulai bleed 4.20V), SOT-23-6. 1/4/5=NC, 2=VDD, 3=VSS, 6=CB",
              footprint="Package_TO_SOT_SMD:SOT-23-6"))

add(ic_symbol("XL4005", "U", [("VIN", ["5"], "power_in"), None, ("EN", ["4"], "input")],
              [("SW", ["3"], "output"), None, ("FB", ["2"], "input"), None, ("GND", ["1"], "power_in")],
              desc="XL4005E1 buck 5A, VIN 5-32V, Vref 0.8V, TO-263-5 (tab = SW). Pinout: datasheet XLSEMI Rev 2.5",
              footprint="Package_TO_SOT_SMD:TO-263-5_TabPin3"))

add(ic_symbol("HT7533", "U", [("VIN", ["2"], "power_in")], [("VOUT", ["3"], "power_out"), None, ("GND", ["1"], "power_in")],
              desc="HT7533-1 LDO 3.3V 100mA, input maks 24V (HT75xx-1), SOT-89. Pinout dari library KiCad HT75xx-1-SOT89",
              footprint="Package_TO_SOT_SMD:SOT-89-3"))

STM = {"1": "PB9", "2": "PC14", "3": "PC15", "4": "VDD", "5": "VSS", "6": "PF2/NRST", "7": "PA0", "8": "PA1",
       "9": "PA2", "10": "PA3", "11": "PA4", "12": "PA5", "13": "PA6", "14": "PA7", "15": "PB0", "16": "PB1",
       "17": "PB2", "18": "PA8", "19": "NC", "20": "PC6", "21": "NC", "22": "PA9/PA11", "23": "PA10/PA12",
       "24": "PA13/SWDIO", "25": "PA14/SWCLK", "26": "PA15", "27": "PB3", "28": "PB4", "29": "PB5", "30": "PB6",
       "31": "PB7", "32": "PB8"}


def st(n, et="bidirectional"):
    return (STM[n], [n], et)


add(ic_symbol("STM32G031K8Tx", "U",
              [st("4", "power_in"), None, st("6", "input"), None, None,
               st("7"), st("8"), st("9"), st("10"), None, st("11"), st("12"), st("13"), None, None,
               st("30"), st("31"), None, st("22"), st("23"), st("32"), st("18"), None, None, st("5", "power_in")],
              [st("26"), st("27"), None, st("15"), st("20"), st("14"), None, None,
               st("29"), st("3"), st("2"), st("1"), None, st("28")] + [None] * 5 +
              [st("16"), st("17")] + [None] * 4 + [st("24"), st("25"), None,
               ("NC", ["19", "21"], "no_connect")],
              desc="STM32G031K8T6, LQFP-32. Pinout dari library KiCad MCU_ST_STM32G0:STM32G031K8Tx",
              datasheet="https://www.st.com/resource/en/datasheet/stm32g031k8.pdf",
              footprint="Package_QFP:LQFP-32_7x7mm_P0.8mm"))

# ============================================================================
# Footprint & helper
# ============================================================================
FP = {
    "R0402": "Resistor_SMD:R_0603_1608Metric", "R0603": "Resistor_SMD:R_0603_1608Metric",
    "R0805": "Resistor_SMD:R_0805_2012Metric", "R1206": "Resistor_SMD:R_1206_3216Metric",
    "R2512": "Resistor_SMD:R_2512_6332Metric",
    "C0402": "Capacitor_SMD:C_0603_1608Metric", "C0603": "Capacitor_SMD:C_0603_1608Metric",
    "C0805": "Capacitor_SMD:C_0805_2012Metric", "C1206": "Capacitor_SMD:C_1206_3216Metric",
    "CP8": "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm", "CP10": "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm",
    "LED": "LED_SMD:LED_0603_1608Metric", "SMB": "Diode_SMD:D_SMB", "SMA": "Diode_SMD:D_SMA",
    "SOD123": "Diode_SMD:D_SOD-123", "SOT23": "Package_TO_SOT_SMD:SOT-23",
    "SO8": "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "DFN33": "Package_SO:Vishay_PowerPAK_1212-8_Single",
    "XH5": "Connector_JST:JST_XH_B5B-XH-A_1x05_P2.50mm_Vertical",
    "PH2": "Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical",
    "TB2": "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal",
    "HDR5": "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical",
    "DIP2": "Button_Switch_THT:SW_DIP_SPSTx02_Slide_9.78x7.26mm_W7.62mm_P2.54mm",
    "DIP3": "Button_Switch_THT:SW_DIP_SPSTx03_Slide_9.78x9.8mm_W7.62mm_P2.54mm",
    "DIP4": "Button_Switch_THT:SW_DIP_SPSTx04_Slide_9.78x12.34mm_W7.62mm_P2.54mm",
    "BTN": "Button_Switch_THT:SW_PUSH_6mm", "RTHT": "Resistor_THT:R_Axial_DIN0411_L9.9mm_D3.6mm_P12.70mm_Horizontal",
    "L12": "Inductor_SMD:L_12x12mm_H8mm", "FUSE": "Fuse:Fuse_Blade_Mini_directSolder",
}

D = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}
SHEETS = OrderedDict()


def mv(p, d, L):
    return (round(p[0] + D[d][0] * L, 2), round(p[1] + D[d][1] * L, 2))


def to_lbl(s, p, name, d, L=2.54):
    e = mv(p, d, L)
    s.w(p, e)
    s.label(name, e, d)
    return e


def to_hl(s, p, name, d, L=2.54, shape="bidirectional"):
    e = mv(p, d, L)
    s.w(p, e)
    s.hlabel(name, e, d, shape)
    return e


def to_pwr(s, p, name, d, L=2.54, sd=None):
    e = mv(p, d, L)
    s.w(p, e)
    s.pwr(name, e, sd)
    return e


def bus_to_gnd(s, pts, x, gnd="GND"):
    """Tarik beberapa pin (satu sisi) ke garis vertikal di x, lalu satu simbol ground di bawahnya."""
    for p in pts:
        s.w(p, (x, p[1]))
    ys = sorted(p[1] for p in pts)
    bottom = (x, ys[-1] + 2.54)
    s.w((x, ys[0]), bottom)
    s.pwr(gnd, bottom)


# ============================================================================
# SHEET 1: USB-C + TPS65988
# ============================================================================
def sheet_usb():
    s = Sheet("usb", "USB-C PD dua arah (TPS65988)", "usb_pd.kicad_sch", refbase=100)
    SHEETS["usb"] = s
    U = s.part("U101", "TPS65988", "TPS65988DH", 190.5, 132.08, {
        "13": "VBUS_C", "14": "VBUS_C", "3": "GND", "4": "GND", "24": "CC1", "26": "CC2",
        "50": "USB_DP", "53": "USB_DN", "25": "GND", "46": "GND", "45": None, "47": None, "54": None, "55": None,
        "6": "PD_ADCIN1", "10": "PD_ADCIN2", "44": "GND", "17": "PD_GPIO1",
        "11": "VBUS_SYS", "12": "VBUS_SYS", "1": "GND", "2": "GND", "5": "+3V3", "9": "PD_LDO3V3", "35": "PD_LDO1V8",
        "28": "I2C_SDA", "27": "I2C_SCL", "29": "PD_IRQ_N", "33": "PD_I2C2_SDA", "32": "PD_I2C2_SCL", "34": None,
        "36": "PD_SPI_POCI", "38": "PD_SPI_CLK", "37": "PD_SPI_PICO", "39": "PD_SPI_CS",
        "21": None, "22": None, "23": None, "16": None, "18": None, "30": None, "31": None, "40": None, "41": None,
        "42": None, "43": None, "48": None, "49": None,
        "8": "PD_DRAIN1", "15": "PD_DRAIN1", "19": "PD_DRAIN1", "58": "PD_DRAIN1",
        "7": "PD_DRAIN2", "52": "PD_DRAIN2", "56": "PD_DRAIN2", "57": "PD_DRAIN2",
        "20": "GND", "51": "GND", "59": "GND"}, mpn="TPS65988DHRSHR")
    vb = U.p("13")
    # konektor: VBUS sejajar VBUS1
    J = s.part("J101", "USB_C_Receptacle_USB2.0_16P", "USB-C 16P", 50.8, 0, {
        "A4": "VBUS_C", "A9": "VBUS_C", "B4": "VBUS_C", "B9": "VBUS_C", "A5": "CC1", "B5": "CC2",
        "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DN", "B7": "USB_DN", "A8": None, "B8": None,
        "A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "SH": "GND"},
        note="HRO TYPE-C-31-M-12 / USB-C 16 pin SMD (Tokopedia)")
    J.y = snap(vb[1] - (J.p("A4")[1] - J.y))
    jv = J.p("A4")
    s.w(jv, vb)
    s.shunt("D101", "D_TVS", "SMBJ24A", (jv[0] + 15.24, jv[1]), "VBUS_C", fp=FP["SMB"], note="TVS VBUS")
    s.shunt("C101", "C", "1u 50V", (jv[0] + 30.48, jv[1]), "VBUS_C", fp=FP["C0805"], note="CVBUS 0.5-12uF")
    s.shunt("C102", "C", "10u 25V", (jv[0] + 45.72, jv[1]), "VBUS_C", fp=FP["C1206"])
    to_pwr(s, U.p("3"), "GND", "left")
    for jp, up_, ref in (("A5", "24", "C103"), ("B5", "26", "C104")):
        a, b = J.p(jp), U.p(up_)
        s.w(a, b)
        s.shunt(ref, "C", "220p 50V", (b[0] - 12.7, b[1]), "CC1" if jp == "A5" else "CC2", fp=FP["C0402"],
                note="Kapasitor CC dekat pin")
    s.w(J.p("A6"), U.p("50"))
    s.w(J.p("A7"), U.p("53"))
    s.nc(J.p("A8"))
    s.nc(J.p("B8"))
    bus_to_gnd(s, [J.p("A1"), J.p("SH")], J.p("A1")[0] + 5.08)
    s.flag((jv[0] + 5.08, jv[1]), "VBUS_C")
    # PPx_CABLE -> GND (VCONN tidak dipakai, kabel 3A)
    bus_to_gnd(s, [U.p("25"), U.p("46")], U.p("25")[0] - 5.08)
    for n in ("45", "47", "54", "55"):
        s.nc(U.p(n))
    # ADCIN1: 20k / 100k (DIV 0.83 -> BP_NoWait, konfigurasi dari flash)
    a1 = U.p("6")
    xa = a1[0] - 15.24
    s.w(a1, (xa, a1[1]))
    r = s.vert("R101", "R", "20k 1%", (xa, a1[1] - 7.62), ("PD_LDO3V3", "PD_ADCIN1"), fp=FP["R0402"])
    to_lbl(s, r.p(1), "PD_LDO3V3", "up")
    s.shunt("R102", "R", "100k 1%", (xa, a1[1]), "PD_ADCIN1", fp=FP["R0402"],
            note="ADCIN1 DIV=0.83 -> BP_NoWait, Safe Config (load dari SPI flash)")
    a2 = U.p("10")
    xb = a2[0] - 30.48
    s.w(a2, (xb, a2[1]))
    r = s.vert("R103", "R", "DNP", (xb, a2[1] - 7.62), ("PD_LDO3V3", "PD_ADCIN2"), fp=FP["R0402"], dnp=True)
    to_lbl(s, r.p(1), "PD_LDO3V3", "up")
    s.shunt("R104", "R", "0R", (xb, a2[1]), "PD_ADCIN2", fp=FP["R0402"], note="ADCIN2 DIV=0 -> alamat I2C index 000")
    to_pwr(s, U.p("44"), "GND", "left")
    g1 = U.p("17")
    s.w(g1, (g1[0] - 7.62, g1[1]))
    s.shunt("R105", "R", "1M", (g1[0] - 7.62, g1[1]), "PD_GPIO1", fp=FP["R0402"], note="GPIO1 tidak dipakai: 1M ke GND")
    # sisi kanan: PP_HV1 -> VBUS_SYS
    hv = U.p("11")
    e = (hv[0] + 53.34, hv[1])
    s.w(hv, e)
    s.shunt("C105", "C_Pol", "47u 25V", (hv[0] + 15.24, hv[1]), "VBUS_SYS", fp=FP["CP8"], note="CPP_HV sink 1-120uF")
    s.shunt("C106", "C", "10u 25V", (hv[0] + 30.48, hv[1]), "VBUS_SYS", fp=FP["C1206"])
    s.pwr("VBUS_SYS", e)
    s.flag((hv[0] + 43.18, hv[1]), "VBUS_SYS")
    to_pwr(s, U.p("1"), "GND", "right")
    # VIN_3V3 / LDO_3V3 / LDO_1V8 (bertingkat)
    p18 = U.p("35")
    s.w(p18, (p18[0] + 7.62, p18[1]))
    s.shunt("C109", "C", "4.7u 10V", (p18[0] + 7.62, p18[1]), "PD_LDO1V8", fp=FP["C0603"], note="CLDO_1V8 2.2-6uF")
    p33 = U.p("9")
    e33 = (p33[0] + 27.94, p33[1])
    s.w(p33, e33)
    s.shunt("C108", "C", "10u 10V", (p33[0] + 20.32, p33[1]), "PD_LDO3V3", fp=FP["C0603"], note="CLDO_3V3 5-25uF")
    s.label("PD_LDO3V3", e33, "right")
    pvin = U.p("5")
    s.w(pvin, (pvin[0] + 58.42, pvin[1]))
    s.shunt("C107", "C", "10u 10V", (pvin[0] + 50.8, pvin[1]), "+3V3", fp=FP["C0603"], note="CVIN_3V3 5-10uF")
    s.pwr("+3V3", (pvin[0] + 58.42, pvin[1]))
    # I2C1 -> MCU
    for n, name in (("28", "I2C_SDA"), ("27", "I2C_SCL"), ("29", "PD_IRQ_N")):
        to_hl(s, U.p(n), name, "right", 55.88, "bidirectional" if "I2C" in name else "output")
    # I2C2 tidak dipakai: wajib pull-up 10k ke LDO_3V3
    xb2 = U.p("33")[0] + 2.54
    for n, ref, net in (("33", "R106", "PD_I2C2_SDA"), ("32", "R107", "PD_I2C2_SCL")):
        p = U.p(n)
        s.w(p, (xb2, p[1]))
        r = s.horiz(ref, "R", "10k", (xb2, p[1]), (net, "PD_LDO3V3"), fp=FP["R0402"])
    xr = xb2 + 7.62 + 2.54
    pa, pb = U.p("33"), U.p("32")
    s.w((xb2 + 7.62, pa[1]), (xr, pa[1]), (xr, pb[1]), (xb2 + 7.62, pb[1]))
    to_lbl(s, (xr, pa[1]), "PD_LDO3V3", "right", 2.54)
    s.nc(U.p("34"))
    # SPI flash
    F = s.part("U102", "W25Qxx_SOIC8", "W25Q16JVSSIQ", 0, 0, {
        "2": "PD_SPI_POCI", "6": "PD_SPI_CLK", "5": "PD_SPI_PICO", "1": "PD_SPI_CS",
        "8": "PD_LDO3V3", "3": "PD_LDO3V3", "7": "PD_LDO3V3", "4": "GND"},
        note="Min 64KB, sektor 4KB, 12MHz. W25Q16/W25Q80 (Tokopedia). Diprogram dengan file dari TPS65988 config tool")
    F.x = snap(U.p("36")[0] + 60.96, G)
    F.y = snap(U.p("36")[1] - (F.p("2")[1] - F.y))
    for a, b in (("36", "2"), ("38", "6"), ("37", "5"), ("39", "1")):
        s.w(U.p(a), F.p(b))
    pp = U.p("36")
    s.vert("R108", "R", "10k", (pp[0] + 22.86, pp[1] - 7.62), ("PD_LDO3V3", "PD_SPI_POCI"), fp=FP["R0402"],
           note="Strap SPI_POCI=1 (flash terpasang)")
    to_lbl(s, (pp[0] + 22.86, pp[1] - 7.62), "PD_LDO3V3", "right")
    pc = U.p("39")
    s.vert("R109", "R", "10k", (pc[0] + 33.02, pc[1]), ("PD_SPI_CS", "PD_LDO3V3"), fp=FP["R0402"])
    to_lbl(s, (pc[0] + 33.02, pc[1] + 7.62), "PD_LDO3V3", "down")
    vcc = F.p("8")
    s.w(vcc, (vcc[0] + 7.62, vcc[1]))
    s.w(F.p("3"), (vcc[0] + 7.62, F.p("3")[1]))
    s.w(F.p("7"), (vcc[0] + 7.62, F.p("7")[1]))
    s.w((vcc[0] + 7.62, vcc[1]), (vcc[0] + 7.62, F.p("7")[1]))
    s.w((vcc[0] + 7.62, vcc[1]), (vcc[0] + 15.24, vcc[1]))
    s.shunt("C110", "C", "100n", (vcc[0] + 15.24, vcc[1]), "PD_LDO3V3", fp=FP["C0402"])
    s.w((vcc[0] + 15.24, vcc[1]), (vcc[0] + 20.32, vcc[1]))
    s.label("PD_LDO3V3", (vcc[0] + 20.32, vcc[1]), "right")
    to_pwr(s, F.p("4"), "GND", "right")
    for n in ("21", "22", "23", "16", "18", "30", "31", "40", "41", "42", "43", "48", "49"):
        s.nc(U.p(n))
    to_pwr(s, U.p("20"), "GND", "right")
    # kotak blok & catatan
    s.autobox("Konektor USB-C + proteksi VBUS", ["J101", "D101", "C101", "C102"])
    s.autobox("PD controller TPS65988 + flash konfigurasi", ["U101", "U102", "C103", "C104", "C105", "C106", "C107",
              "C108", "C109", "C110", "R101", "R102", "R103", "R104", "R105", "R106", "R107", "R108", "R109"])
    s.text("TPS65988 (dari Tokopedia, part laptop) dipakai 1 port:\n"
           "- Port 1 (C1_CC1/2, VBUS1, PP_HV1) = DRP: sink saat charging, source saat OTG.\n"
           "- PP_HV1 = VBUS_SYS: input BQ25713 saat charging, dan diisi OTG BQ25713 saat source.\n"
           "- Port 2, PP_HV2, VBUS2, PPx_CABLE tidak dipakai (GND / NC). VCONN tidak didukung (kabel 3A).\n"
           "- Konfigurasi dibuat dengan TI TPS65988 Configuration Tool, lalu ditulis ke U102.\n"
           "- ADCIN1 0.83 + SPI_POCI=1 -> BP_NoWait: sink langsung aktif saat baterai habis.\n"
           "- MCU bicara lewat I2C1 (PD_IRQ_N = interrupt kontrak).",
           256.54, 172.72, 1.524)
    return s


# ============================================================================
# SHEET 2: Charger BQ25713
# ============================================================================
def sheet_chg():
    s = Sheet("chg", "Charger buck-boost 2-4S (BQ25713)", "charger.kicad_sch", refbase=200)
    SHEETS["chg"] = s
    # --- power stage (atas) --------------------------------------------------
    yr = 50.8
    x0 = 33.02
    s.pwr("VBUS_SYS", (x0, yr))
    nA = (x0 + 10.16, yr)
    xacp = nA[0] + 15.24
    rac = s.horiz("R201", "R", "10m 1%", (xacp + 10.16, yr), ("VBUS_SYS", "CHG_VIN"), fp=FP["R2512"],
                  note="RAC sense arus input")
    s.w((x0, yr), rac.p(1))
    s.vert("R202", "R", "1R", nA, ("VBUS_SYS", "CHG_VBUS_F"), fp=FP["R0603"])
    s.shunt("C201", "C", "470n 50V", (nA[0], yr + 7.62), "CHG_VBUS_F", fp=FP["C0603"])
    s.w((nA[0], yr + 7.62), (nA[0] - 5.08, yr + 7.62))
    s.label("CHG_VBUS_F", (nA[0] - 5.08, yr + 7.62), "left")
    s.vert("R203", "R", "4.99R", (xacp, yr), ("VBUS_SYS", "CHG_ACP"), fp=FP["R0402"])
    s.shunt("C202", "C", "33n", (xacp, yr + 7.62), "CHG_ACP", fp=FP["C0402"])
    s.w((xacp, yr + 7.62), (xacp + 5.08, yr + 7.62))
    s.label("CHG_ACP", (xacp + 5.08, yr + 7.62), "right")
    nB = rac.p(2)
    xacn = nB[0] + 7.62
    s.vert("R204", "R", "4.99R", (xacn, yr), ("CHG_VIN", "CHG_ACN"), fp=FP["R0402"])
    s.shunt("C203", "C", "33n", (xacn, yr + 7.62), "CHG_ACN", fp=FP["C0402"])
    s.w((xacn, yr + 7.62), (xacn + 5.08, yr + 7.62))
    s.label("CHG_ACN", (xacn + 5.08, yr + 7.62), "right")
    xq1 = xacn + 50.8
    s.w(nB, (xq1 + 2.54, yr))
    s.shunt("C204", "C", "10n 50V", (xacn + 22.86, yr), "CHG_VIN", fp=FP["C0402"], note="Maks 10n+1n setelah RAC")
    s.shunt("C205", "C", "1n 50V", (xacn + 35.56, yr), "CHG_VIN", fp=FP["C0402"])
    q1 = s.part("Q201", "Q_NMOS_DFN8", "AON7410", xq1, yr + 10.16, nfet8("CHG_HIDRV1", "CHG_SW1", "CHG_VIN"),
                fp=FP["DFN33"], note="30V 24A, Tokopedia")
    q2 = s.part("Q202", "Q_NMOS_DFN8", "AON7410", xq1, yr + 33.02, nfet8("CHG_LODRV1", "GND", "CHG_SW1"),
                fp=FP["DFN33"])
    s.w((xq1 + 2.54, yr), q1.p("D"))
    ysw = snap((q1.p("S")[1] + q2.p("D")[1]) / 2, 2.54)
    s.w(q1.p("S"), (q1.p("S")[0], ysw), q2.p("D"))
    s.pwr("GND", q2.p("S"))
    to_lbl(s, q1.p("G"), "CHG_HIDRV1", "left", 5.08)
    to_lbl(s, q2.p("G"), "CHG_LODRV1", "left", 5.08)
    xsw1 = q1.p("S")[0]
    xq4 = xsw1 + 63.5
    L1 = s.horiz("L201", "L", "2.2u 12x12", (xsw1 + 27.94, ysw), ("CHG_SW1", "CHG_SW2"), fp=FP["L12"],
                 note="DS1207/CD127 2R2 (Tokopedia). Cek Isat; batasi arus induktor di firmware")
    s.w((xsw1, ysw), L1.p(1))
    cb1 = s.vert("C206", "C", "47n 25V", (xsw1 + 12.7, ysw - 7.62), ("CHG_BTST1", "CHG_SW1"), fp=FP["C0402"])
    to_lbl(s, cb1.p(1), "CHG_BTST1", "up")
    q4 = s.part("Q204", "Q_NMOS_DFN8", "AON7410", xq4, yr + 10.16, nfet8("CHG_HIDRV2", "CHG_SW2", "VSYS"),
                mirror=True, fp=FP["DFN33"])
    q3 = s.part("Q203", "Q_NMOS_DFN8", "AON7410", xq4, yr + 33.02, nfet8("CHG_LODRV2", "GND", "CHG_SW2"),
                mirror=True, fp=FP["DFN33"])
    xsw2 = q4.p("S")[0]
    s.w(q4.p("S"), (xsw2, ysw), q3.p("D"))
    s.w(L1.p(2), (xsw2, ysw))
    cb2 = s.vert("C207", "C", "47n 25V", (xsw2 - 12.7, ysw - 7.62), ("CHG_BTST2", "CHG_SW2"), fp=FP["C0402"])
    to_lbl(s, cb2.p(1), "CHG_BTST2", "up")
    s.pwr("GND", q3.p("S"))
    to_lbl(s, q4.p("G"), "CHG_HIDRV2", "right", 5.08)
    to_lbl(s, q3.p("G"), "CHG_LODRV2", "right", 5.08)
    s.label("CHG_SW1", (xsw1 + 20.32, ysw), "up")
    s.label("CHG_SW2", (xsw2 - 5.08, ysw), "up")
    xv = q4.p("D")[0]
    s.w(q4.p("D"), (xv, yr))
    xcap = xv + 10.16
    caps = [("C208", "10u 25V"), ("C209", "10u 25V"), ("C210", "10u 25V"), ("C211", "10u 25V"),
            ("C212", "10u 25V"), ("C213", "10u 25V"), ("C214", "22u 25V")]
    for i, (ref, val) in enumerate(caps):
        s.shunt(ref, "C", val, (xcap + i * 12.7, yr), "VSYS", fp=FP["C1206" if "22u" in val else "C0805"],
                note="Dekat Q203/Q204 (min 50uF efektif)" if i == 0 else "")
    xvs = xcap + len(caps) * 12.7
    s.w((xv, yr), (xvs + 5.08, yr))
    s.pwr("VSYS", (xvs, yr))
    s.flag((xvs + 5.08, yr), "VSYS")
    qb = s.part("Q205", "Q_PMOS_SO8", "AO4407A", xvs + 17.78, yr - 2.54, pfet8("CHG_BATDRV", "VSYS", "CHG_BATP"),
                rot=270, fp=FP["SO8"], note="BATFET P-ch -30V, Tokopedia", ref_at=(xvs + 12.7, yr + 5.08, "left"),
                val_at=(xvs + 12.7, yr + 7.62, "left"))
    s.w((xvs + 5.08, yr), qb.p("S"))
    to_lbl(s, qb.p("G"), "CHG_BATDRV", "up")
    nP = (qb.p("D")[0] + 7.62, yr)
    s.w(qb.p("D"), nP)
    rsr = s.horiz("R205", "R", "10m 1%", (nP[0] + 2.54, yr), ("CHG_BATP", "PACK+"), fp=FP["R2512"],
                  note="RSR sense arus charge")
    s.w(nP, rsr.p(1))
    nQ = (rsr.p(2)[0] + 2.54, yr)
    rsp = s.vert("R206", "R", "10R", nP, ("CHG_BATP", "CHG_SRP_F"), fp=FP["R0402"])
    rsn = s.vert("R207", "R", "10R", nQ, ("PACK+", "CHG_SRN_F"), fp=FP["R0402"])
    ya = rsp.p(2)[1] + 7.62
    s.w(rsp.p(2), (nP[0], ya))
    s.w(rsn.p(2), (nQ[0], ya))
    s.horiz("C216", "C", "100n", (nP[0] + 2.54, ya), ("CHG_SRP_F", "CHG_SRN_F"), fp=FP["C0402"])
    s.w((nP[0], ya), (nP[0] + 2.54, ya))
    s.w((nP[0] + 10.16, ya), (nQ[0], ya))
    s.w((nQ[0], ya), (nQ[0] + 7.62, ya))
    s.shunt("C217", "C", "100n", (nQ[0] + 7.62, ya), "CHG_SRN_F", fp=FP["C0402"])
    s.w((nQ[0] + 7.62, ya), (nQ[0] + 12.7, ya))
    s.label("CHG_SRN_F", (nQ[0] + 12.7, ya), "right")
    to_lbl(s, (nP[0], ya), "CHG_SRP_F", "down", 5.08)
    xpk = nQ[0] + 45.72
    s.w(rsr.p(2), (xpk, yr))
    s.shunt("C218", "C", "10u 25V", (nQ[0] + 25.4, yr), "PACK+", fp=FP["C0805"], note=">=20uF setelah RSR")
    s.shunt("C219", "C", "10u 25V", (nQ[0] + 38.1, yr), "PACK+", fp=FP["C0805"])
    s.pwr("PACK+", (xpk, yr))
    s.flag((nQ[0] + 15.24, yr), "PACK+")
    s.autobox("Power stage: RAC -> buck-boost 4-switch -> VSYS -> BATFET -> RSR -> PACK+",
              ["R201", "R202", "R203", "R204", "C201", "C202", "C203", "C204", "C205", "Q201", "Q202", "Q203", "Q204",
               "L201", "C206", "C207", "Q205", "R205", "R206", "R207", "C216", "C217", "C218", "C219"] +
              [c[0] for c in caps])

    # --- IC --------------------------------------------------------------------
    U = s.part("U201", "BQ25713", "BQ25713RSNR", 165.1, 182.88, {
        "1": "CHG_VBUS_F", "3": "CHG_ACP", "2": "CHG_ACN", "6": "CHG_ILIM", "18": "CELL_BATPRESZ",
        "5": "OTG_EN", "12": "I2C_SDA", "13": "I2C_SCL", "4": "CHRG_OK", "11": "PROCHOT_N",
        "14": "GND", "15": None, "8": "CHG_IADPT", "9": "CHG_IBAT", "10": "CHG_PSYS",
        "16": "CHG_COMP1", "17": "CHG_COMP2",
        "28": "CHG_REGN", "7": "CHG_VDDA", "31": "CHG_HIDRV1", "30": "CHG_BTST1", "32": "CHG_SW1",
        "29": "CHG_LODRV1", "24": "CHG_HIDRV2", "25": "CHG_BTST2", "23": "CHG_SW2", "26": "CHG_LODRV2",
        "22": "VSYS", "21": "CHG_BATDRV", "20": "CHG_SRP_F", "19": "CHG_SRN_F", "27": "GND", "33": "GND"},
        mpn="BQ25713RSNR")
    for n, name in (("1", "CHG_VBUS_F"), ("3", "CHG_ACP"), ("2", "CHG_ACN")):
        to_lbl(s, U.p(n), name, "left", 5.08)
    # ILIM_HIZ: pembagi dari REGN
    pi = U.p("6")
    xi = pi[0] - 25.4
    s.w(pi, (xi, pi[1]))
    r = s.vert("R208", "R", "383k", (xi, pi[1] - 7.62), ("CHG_REGN", "CHG_ILIM"), fp=FP["R0402"],
               note="ILIM_HIZ ~2.19V -> batas arus input ~3A (hardware)")
    to_lbl(s, r.p(1), "CHG_REGN", "up")
    s.shunt("R209", "R", "220k", (xi, pi[1]), "CHG_ILIM", fp=FP["R0402"])
    # CELL_BATPRESZ: DIP jumlah cell (one-hot)
    pc = U.p("18")
    xd = pc[0] - 40.64
    s.w(pc, (xd, pc[1]))
    sw = s.part("SW201", "SW_DIP_x03", "CELL 2S/3S/4S", xd - 7.62, 0, {
        "1": "CELLSEL_2S", "6": "CELL_BATPRESZ", "2": "CELLSEL_3S", "5": "CELL_BATPRESZ",
        "3": "CELLSEL_4S", "4": "CELL_BATPRESZ"}, fp=FP["DIP3"], note="Hanya SATU posisi ON")
    sw.y = snap(pc[1] - (sw.p("6")[1] - sw.y))
    s.w(sw.p("6"), (xd, pc[1]))
    s.w((xd, sw.p("6")[1]), (xd, sw.p("4")[1]))
    s.w(sw.p("5"), (xd, sw.p("5")[1]))
    s.w(sw.p("4"), (xd, sw.p("4")[1]))
    ytop = sw.p("1")[1] - 17.78
    for i, (k, ref, val, net) in enumerate((("3", "R212", "3.3k 1%", "CELLSEL_4S"), ("2", "R211", "8.2k 1%", "CELLSEL_3S"),
                                           ("1", "R210", "15k 1%", "CELLSEL_2S"))):
        p = sw.p(k)
        xk = p[0] - 33.02 + i * 10.16
        rr = s.vert(ref, "R", val, (xk, ytop), ("CHG_VDDA", net), fp=FP["R0402"],
                    note=["75% VDDA = 4S", "55% = 3S", "40% = 2S"][i])
        s.w(rr.p(2), (xk, p[1]), p)
    x1 = sw.p("3")[0] - 33.02
    s.w((x1, ytop), (x1 + 20.32, ytop))
    to_lbl(s, (x1, ytop), "CHG_VDDA", "left", 2.54)
    s.shunt("R213", "R", "10k 1%", (xd, sw.p("4")[1]), "CELL_BATPRESZ", fp=FP["R0402"],
            note="Semua OFF -> baterai dianggap tidak ada, charge mati")
    # readback CELL_SENSE
    xcs = xd + 12.7
    s.w((xd, pc[1]), (xcs, pc[1]))
    r = s.vert("R214", "R", "100k", (xcs, pc[1]), ("CELL_BATPRESZ", "CELL_SENSE"), fp=FP["R0402"])
    s.shunt("R215", "R", "100k", r.p(2), "CELL_SENSE", fp=FP["R0402"])
    s.w(r.p(2), (xcs + 10.16, r.p(2)[1]))
    s.shunt("C220", "C", "10n", (xcs + 10.16, r.p(2)[1]), "CELL_SENSE", fp=FP["C0402"])
    to_hl(s, (xcs + 10.16, r.p(2)[1]), "CELL_SENSE", "right", 5.08, "output")
    # OTG, I2C, status
    for n, name, sh in (("5", "OTG_EN", "input"), ("12", "I2C_SDA", "bidirectional"), ("13", "I2C_SCL", "bidirectional"),
                        ("4", "CHRG_OK", "output"), ("11", "PROCHOT_N", "output")):
        to_hl(s, U.p(n), name, "right", 25.4, sh)
    to_pwr(s, U.p("14"), "GND", "left")
    s.nc(U.p("15"))
    # IADPT / IBAT / PSYS / COMP (bertingkat)
    p = U.p("8")
    s.w(p, (p[0] - 22.86, p[1]))
    s.shunt("R217", "R", "137k", (p[0] - 22.86, p[1]), "CHG_IADPT", fp=FP["R0402"], note="137k untuk L=2.2uH")
    s.shunt("C221", "C", "100p", (p[0] - 12.7, p[1]), "CHG_IADPT", fp=FP["C0402"])
    p = U.p("9")
    s.w(p, (p[0] - 12.7, p[1]))
    s.shunt("C222", "C", "100p", (p[0] - 12.7, p[1]), "CHG_IBAT", fp=FP["C0402"])
    p = U.p("10")
    s.w(p, (p[0] - 12.7, p[1]))
    s.shunt("R218", "R", "30.1k", (p[0] - 12.7, p[1]), "CHG_PSYS", fp=FP["R0402"])
    for pin, (rn, rv, cn, cv, cpn, cpv, net) in (("16", ("R219", "40.2k", "C223", "1800p", "C224", "33p", "CHG_COMP1")),
                                                  ("17", ("R220", "10k", "C225", "680p", "C226", "15p", "CHG_COMP2"))):
        p = U.p(pin)
        xc = p[0] - 25.4 if pin == "16" else p[0] - 12.7
        s.w(p, (xc - 7.62, p[1]))
        s.shunt(cpn, "C", cpv, (xc, p[1]), net, fp=FP["C0402"])
        rr = s.vert(rn, "R", rv, (xc - 7.62, p[1]), (net, net + "_RC"), fp=FP["R0402"],
                    note="Kompensasi dari diagram aplikasi datasheet - bandingkan dengan EVM")
        s.shunt(cn, "C", cv, rr.p(2), net + "_RC", fp=FP["C0402"])
    # sisi kanan: REGN / VDDA
    pr, pv = U.p("28"), U.p("7")
    xr2 = pr[0] + 30.48
    s.w(pr, (xr2 + 10.16, pr[1]))
    s.vert("R221", "R", "10R", (xr2, pr[1]), ("CHG_REGN", "CHG_VDDA"), fp=FP["R0402"])
    s.w(pv, (xr2, pv[1]))
    s.shunt("C227", "C", "1u 10V", (xr2 + 5.08, pv[1]), "CHG_VDDA", fp=FP["C0402"])
    s.w((xr2, pv[1]), (xr2 + 5.08, pv[1]))
    s.w((xr2 + 5.08, pv[1]), (xr2 + 7.62, pv[1]))
    s.label("CHG_VDDA", (xr2 + 7.62, pv[1]), "right")
    s.shunt("C228", "C", "3.3u 10V", (xr2 + 10.16, pr[1]), "CHG_REGN", fp=FP["C0603"])
    s.w((xr2 + 10.16, pr[1]), (xr2 + 17.78, pr[1]))
    s.label("CHG_REGN", (xr2 + 17.78, pr[1]), "right")
    for n, name in (("31", "CHG_HIDRV1"), ("30", "CHG_BTST1"), ("32", "CHG_SW1"), ("29", "CHG_LODRV1"),
                    ("24", "CHG_HIDRV2"), ("25", "CHG_BTST2"), ("23", "CHG_SW2"), ("26", "CHG_LODRV2"),
                    ("21", "CHG_BATDRV"), ("20", "CHG_SRP_F"), ("19", "CHG_SRN_F")):
        to_lbl(s, U.p(n), name, "right", 5.08)
    to_pwr(s, U.p("22"), "VSYS", "right", 7.62, "up")
    to_pwr(s, U.p("27"), "GND", "right")
    s.autobox("Kontrol charger + DIP jumlah cell", [p.ref for p in s.parts if p.ref.startswith(("U2", "SW2")) or (p.ref[1:].isdigit() and 208 <= int(p.ref[1:]) <= 299 and p.ref[0] in "RC" and p.ref not in ("C208", "C209", "C210", "C211", "C212", "C213", "C214", "C216", "C217", "C218", "C219"))])
    s.text("SW201 CELL (dibaca BQ25713 saat start; juga menentukan SYSOVP):\n"
           "  2S: pos1 ON | 3S: pos2 ON | 4S: pos3 ON  (HANYA satu yang ON)\n"
           "  Harus sama dengan SW301 (tap balance) di sheet Baterai.\n"
           "  MCU mengecek CELL_SENSE vs tegangan tap -> tidak cocok = FAULT.\n\n"
           "BQ25713 (I2C 0x6B):\n"
           "- ChargeCurrent default 0A: tidak mengisi sebelum MCU menulis register.\n"
           "- ILIM_HIZ membatasi arus input ~3A (hardware).\n"
           "- OTG: mengisi VBUS_SYS 3-20.8V dari baterai (untuk USB-C source & output XL4005).",
           256.54, 182.88, 1.524)
    return s


# ============================================================================
# SHEET 3: Baterai: konektor, sekring, FET proteksi, balancer, monitor tap, NTC
# ============================================================================
def sheet_bat():
    s = Sheet("bat", "Baterai 2-4S: proteksi, balancing, monitor cell", "battery.kicad_sch", refbase=300)
    SHEETS["bat"] = s
    # --- jalur daya --------------------------------------------------------------
    J = s.part("J301", "Conn_01x02", "BATTERY", 38.1, 48.26, {"1": "BATT_RAW", "2": "GND"}, mirror=True, fp=FP["TB2"],
               note="Kabel daya pack: 1 = + (atas stack), 2 = -. Bisa diganti XT30")
    jp = J.p("1")
    yr = jp[1]
    to_pwr(s, J.p("2"), "GND", "right", 5.08)
    f = s.horiz("F301", "Fuse", "15A", (jp[0] + 10.16, yr), ("BATT_RAW", "BATT+"), fp=FP["FUSE"],
                note="Sekring blade mini 15A = proteksi short (hardware, tanpa firmware)")
    s.w(jp, f.p(1))
    xq1 = f.p(2)[0] + 33.02
    xs = xq1 - 15.24
    s.w(f.p(2), (xq1 - 5.08, yr))
    s.pwr("BATT+", (f.p(2)[0] + 5.08, yr))
    s.flag((f.p(2)[0] + 12.7, yr), "BATT+")
    q1 = s.part("Q301", "Q_PMOS_SO8", "AO4407A", xq1, yr - 2.54, pfet8("BAT_DSG_G", "BATT+", "BAT_FETMID"),
                rot=270, fp=FP["SO8"], note="DSG FET P-ch -30V. OFF = discharge diblok",
                ref_at=(xq1 - 6.35, yr + 5.08, "left"), val_at=(xq1 - 6.35, yr + 7.62, "left"))
    gd = q1.p("G")
    s.w((xs, yr), (xs, gd[1] - 10.16))
    s.horiz("R301", "R", "100k", (xs, gd[1]), ("BATT+", "BAT_DSG_G"), fp=FP["R0402"], note="Gate-source: default OFF")
    s.w((xs + 7.62, gd[1]), gd)
    s.horiz("D301", "D_Zener", "Zener 12V SOD123", (xs, gd[1] - 10.16), ("BATT+", "BAT_DSG_G"), fp=FP["SOD123"],
            note="Clamp Vgs 12V (K ke source)")
    s.w((xs + 7.62, gd[1] - 10.16), (gd[0], gd[1] - 10.16), gd)
    to_lbl(s, (gd[0], gd[1] - 10.16), "BAT_DSG_G", "right", 2.54)
    xq2 = q1.p("D")[0] + 17.78
    q2 = s.part("Q302", "Q_PMOS_SO8", "AO4407A", xq2, yr + 2.54, pfet8("BAT_CHG_G", "PACK+", "BAT_FETMID"),
                rot=90, fp=FP["SO8"], note="CHG FET P-ch -30V. OFF = charge diblok",
                ref_at=(xq2 - 6.35, yr - 7.62, "left"), val_at=(xq2 - 6.35, yr - 5.08, "left"))
    s.w(q1.p("D"), q2.p("D"))
    gc = q2.p("G")
    sc = q2.p("S")
    s.vert("R302", "R", "100k", sc, ("PACK+", "BAT_CHG_G"), fp=FP["R0402"], note="Gate-source: default OFF")
    s.w((sc[0], sc[1] + 7.62), gc)
    xz = sc[0] + 15.24
    s.vert("D302", "D_Zener", "Zener 12V SOD123", (xz, yr), ("PACK+", "BAT_CHG_G"), fp=FP["SOD123"], note="Clamp Vgs 12V")
    s.w((xz, yr + 7.62), (sc[0], yr + 7.62))
    to_lbl(s, gc, "BAT_CHG_G", "down", 5.08)
    xpk = xz + 33.02
    s.w(sc, (xpk, yr))
    s.shunt("C301", "C", "10u 25V", (xz + 17.78, yr), "PACK+", fp=FP["C0805"])
    s.pwr("PACK+", (xpk, yr))
    s.autobox("Jalur daya: sekring + FET proteksi P-ch back-to-back", ["J301", "F301", "Q301", "Q302", "R301", "D301",
              "R302", "D302", "C301"])
    # --- driver gate ---------------------------------------------------------------
    for i, (gnet, en, rr, qq, rpd) in enumerate((("BAT_DSG_G", "DSG_EN", "R303", "Q303", "R304"),
                                                ("BAT_CHG_G", "CHG_EN", "R305", "Q304", "R306"))):
        xd = 279.4 + i * 50.8
        top = (xd, 33.02)
        s.label(gnet, top, "up")
        r = s.vert(rr, "R", "10k", top, (gnet, gnet + "_D"), fp=FP["R0402"], note="Batasi arus saat zener clamp")
        q = s.part(qq, "Q_NMOS", "AO3400", xd - 2.54, top[1] + 12.7, {"1": en, "3": gnet + "_D", "2": "GND"},
                   fp=FP["SOT23"], note="N-FET logic level")
        s.w(r.p(2), q.p(3))
        s.pwr("GND", q.p(2))
        pg = q.p(1)
        s.w(pg, (pg[0] - 7.62, pg[1]))
        s.shunt(rpd, "R", "100k", (pg[0] - 7.62, pg[1]), en, fp=FP["R0402"], note="Default OFF")
        to_hl(s, (pg[0] - 7.62, pg[1]), en, "left", 7.62, "input")
    s.autobox("Driver gate (MCU -> FET proteksi)", ["R303", "Q303", "R304", "R305", "Q304", "R306"])
    # --- konektor balance ---------------------------------------------------------
    JB = s.part("J302", "Conn_01x05", "BALANCE", 33.02, 127.0, {"1": "GND", "2": "BAL_B1", "3": "BAL_B2", "4": "BAL_B3",
                                                               "5": "BAL_B4"}, mirror=True, fp=FP["XH5"],
                note="1=B0(-) 2=B1 3=B2 4=B3 5=B4. Untuk 2S/3S pin atas kosong + set SW301")
    to_pwr(s, JB.p("1"), "GND", "right", 5.08)
    for k in range(1, 5):
        to_lbl(s, JB.p(str(k + 1)), f"BAL_B{k}", "right", 5.08)
    # --- balancer per cell (4 kolom identik) ----------------------------------------
    y1 = 101.6
    for k in range(1, 5):
        xk = 63.5 + (k - 1) * 78.74
        top, lo = f"BAL_B{k}", ("GND" if k == 1 else f"BAL_B{k - 1}")
        yv, yb = y1 + 7.62, y1 + 17.78
        xe = xk + 50.8
        s.w((xk, y1), (xe, y1))
        to_lbl(s, (xk, y1), top, "left", 2.54)
        s.vert(f"R3{10 + k}", "R", "100R", (xk, y1), (top, f"BAL{k}_VDD"), fp=FP["R0402"])
        s.vert(f"C3{10 + k}", "C", "100n", (xk, yv), (f"BAL{k}_VDD", lo), fp=FP["C0402"])
        s.w((xk, yv + 7.62), (xk, yb))
        u = s.part(f"U30{k}", "HY2213-BB3A", "HY2213-BB3A", xk + 25.4, yv + 2.54,
                   {"2": f"BAL{k}_VDD", "3": lo, "6": f"BAL{k}_CB", "1": None, "4": None, "5": None},
                   note=f"Balancer cell {k}: bleed saat > 4.20V")
        s.w((xk, yv), u.p("2"))
        s.w(u.p("3"), (u.p("3")[0], yb))
        s.nc(u.p("1"))
        q = s.part(f"Q3{10 + k}", "Q_NMOS", "AO3400", xk + 48.26, yv + 5.08,
                   {"1": f"BAL{k}_CB", "3": f"BAL{k}_BLD", "2": lo}, fp=FP["SOT23"])
        s.w(u.p("6"), (u.p("6")[0] + 2.54, u.p("6")[1]), (u.p("6")[0] + 2.54, q.p(1)[1]), q.p(1))
        s.vert(f"R3{20 + k}", "R", "39R 1W", (xe, y1), (top, f"BAL{k}_BLD"), fp=FP["RTHT"],
               note="Bleed ~100mA @ 4.2V")
        s.w((xk, yb), (xe, yb))
        if lo == "GND":
            s.pwr("GND", (xk + 12.7, yb))
        else:
            to_lbl(s, (xk, yb), lo, "left", 2.54)
        s.text(f"Cell {k}", xk + 17.78, y1 - 6.35, 1.778, bold=True)
    # --- monitor tap (divider 1/6) ----------------------------------------------------
    ym = 152.4
    for k in range(1, 5):
        xm = 63.5 + (k - 1) * 78.74 + 12.7
        net = f"BAL_B{k}"
        s.label(net, (xm, ym), "up")
        rt = s.vert(f"R3{30 + k}", "R", "1M 1%", (xm, ym), (net, f"CELL_B{k}"), fp=FP["R0402"],
                    note="Divider 1/6: 16.8V -> 2.8V. Arus diam ~14uA")
        s.shunt(f"R3{40 + k}", "R", "200k 1%", rt.p(2), f"CELL_B{k}", fp=FP["R0402"])
        s.w(rt.p(2), (xm + 10.16, rt.p(2)[1]))
        s.shunt(f"C3{20 + k}", "C", "100n", (xm + 10.16, rt.p(2)[1]), f"CELL_B{k}", fp=FP["C0402"],
                note="Reservoir ADC (sumber impedansi tinggi)")
        to_hl(s, (xm + 10.16, rt.p(2)[1]), f"CELL_B{k}", "right", 10.16, "output")
    s.autobox("Balance per cell (HY2213 + bleeder) + monitor tap ke ADC MCU",
              ["J302", "U301", "U302", "U303", "U304"] + [f"{a}3{b}" for a in "RCQ" for b in range(10, 45)
                                                          if f"{a}3{b}" != "C325"])
    # --- SW301 tap tak terpakai ------------------------------------------------------
    sw = s.part("SW301", "SW_DIP_x02", "TAP 2S/3S", 76.2, 213.36, {"1": "TAPSEL_43", "4": "BAL_B3",
                                                                   "2": "TAPSEL_32", "3": "BAL_B2"}, fp=FP["DIP2"],
                note="4S: semua OFF | 3S: pos1 ON | 2S: pos1+pos2 ON")
    for pinl, pinr, a, b, ref, net in (("1", "4", "BAL_B4", "BAL_B3", "R350", "TAPSEL_43"),
                                       ("2", "3", "BAL_B3", "BAL_B2", "R351", "TAPSEL_32")):
        pl = sw.p(pinl)
        dx = 12.7 if pinl == "1" else 27.94
        rr = s.horiz(ref, "R", "100R", (pl[0] - dx, pl[1]), (a, net), fp=FP["R1206"],
                     note="Batasi arus jika SW301 salah set (~42mA, terdeteksi firmware)")
        s.w(rr.p(2), pl)
        to_lbl(s, rr.p(1), a, "left", 2.54)
        to_lbl(s, sw.p(pinr), b, "right", 2.54)
    # --- NTC baterai -----------------------------------------------------------------
    jn = s.part("J303", "Conn_01x02", "NTC_BAT", 210.82, 215.9, {"1": "NTC_BAT", "2": "GND"}, fp=FP["PH2"],
                note="NTC 10k (B3950) ditempel di pack")
    pn = jn.p("1")
    xn = pn[0] - 15.24
    s.w(pn, (xn - 12.7, pn[1]))
    rp = s.vert("R352", "R", "10k 1%", (xn, pn[1] - 7.62), ("+3V3", "NTC_BAT"), fp=FP["R0402"])
    s.pwr("+3V3", rp.p(1))
    s.shunt("C325", "C", "100n", (xn - 7.62, pn[1]), "NTC_BAT", fp=FP["C0402"])
    to_hl(s, (xn - 12.7, pn[1]), "NTC_BAT", "left", 5.08, "output")
    to_pwr(s, jn.p("2"), "GND", "left", 2.54)
    s.autobox("Pilih tap (2S/3S)", ["SW301", "R350", "R351"])
    s.autobox("NTC baterai", ["J303", "R352", "C325"])
    s.text("Proteksi baterai (tanpa modul BMS):\n"
           "1. F301 sekring: short circuit (hardware).\n"
           "2. HY2213 per cell: bleed ~100mA saat cell > 4.20V (balancing + batas overcharge per cell).\n"
           "3. Firmware STM32: baca tap (CELL_B1..4) dan NTC; cell < 3.0V / > 4.25V / suhu di luar 0-45C\n"
           "   -> matikan DSG_EN / CHG_EN (Q301/Q302). Default OFF saat MCU mati.\n"
           "4. BQ25713: BATOVP total pack, watchdog, batas arus input.\n\n"
           "SW301 harus sesuai SW201 (sheet charger): 4S semua OFF, 3S pos1, 2S pos1+pos2.",
           246.38, 193.04, 1.524)
    return s


# ============================================================================
# SHEET 4: Output XL4005
# ============================================================================
def sheet_out():
    s = Sheet("out", "Output terminal 1-16V (XL4005)", "output.kicad_sch", refbase=400)
    SHEETS["out"] = s
    U = s.part("U401", "XL4005", "XL4005E1", 139.7, 76.2, {"5": "VBUS_SYS", "4": "BB_EN", "3": "BB_SW", "2": "BB_FB",
                                                          "1": "GND"}, mpn="XL4005E1")
    pv = U.p("5")
    x0 = pv[0] - 78.74
    s.pwr("VBUS_SYS", (x0, pv[1]))
    s.w((x0, pv[1]), pv)
    s.shunt("C401", "C_Pol", "220u 50V", (x0 + 7.62, pv[1]), "VBUS_SYS", fp=FP["CP10"])
    s.shunt("C402", "C", "1u 50V", (x0 + 22.86, pv[1]), "VBUS_SYS", fp=FP["C0805"], note="Dekat VIN-GND")
    pe = U.p("4")
    xe = pe[0] - 12.7
    s.w(pe, (xe, pe[1]))
    s.shunt("R401", "R", "100k", (xe, pe[1]), "BB_EN", fp=FP["R0402"], note="Default OFF")
    to_hl(s, (xe, pe[1]), "BB_EN", "left", 20.32, "input")
    to_pwr(s, U.p("1"), "GND", "right", 5.08)
    psw = U.p("3")
    nsw = (psw[0] + 15.24, psw[1])
    s.w(psw, nsw)
    s.shunt("D401", "D_Schottky", "SS54", nsw, "BB_SW", fp=FP["SMB"], note="Schottky 5A 40V")
    L = s.horiz("L401", "L", "33u 12x12", (nsw[0] + 7.62, psw[1]), ("BB_SW", "BB_VOUT"), fp=FP["L12"],
                note="CD127 33uH 12x12x7 (Tokopedia, ~3A) -> arus output dibatasi 3A")
    s.w(nsw, L.p(1))
    yo = psw[1]
    xa = L.p(2)[0]
    xo = xa + 132.08
    s.w(L.p(2), (xo, yo))
    s.shunt("C403", "C_Pol", "330u 25V", (xa + 7.62, yo), "BB_VOUT", fp=FP["CP8"])
    s.shunt("C404", "C", "1u 25V", (xa + 17.78, yo), "BB_VOUT", fp=FP["C0805"])
    xfb = xa + 33.02
    r2 = s.vert("R402", "R", "30k 1%", (xfb, yo), ("BB_VOUT", "BB_FB"), fp=FP["R0402"],
                note="Vout = 0.8(1+R402/R403) + (0.8-Vdac)*R402/R404")
    s.vert("C405", "C", "1n", (xfb + 12.7, yo), ("BB_VOUT", "BB_FB"), fp=FP["C0402"], note="CFF = 1/(31k*R402)")
    nfb = r2.p(2)
    s.w((xfb + 12.7, yo + 7.62), nfb)
    s.shunt("R403", "R", "2k 1%", nfb, "BB_FB", fp=FP["R0402"])
    # FB pin (kiri) -> turun -> bus FB di bawah IC -> naik ke node FB
    pfb = U.p("2")
    yfb = yo + 30.48
    xl = pfb[0] - 5.08
    s.w(pfb, (xl, pfb[1]), (xl, yfb), (xfb - 5.08, yfb), (xfb - 5.08, nfb[1]), nfb)
    # injeksi DAC dari bus FB, ke bawah
    xj = nsw[0]
    r404 = s.vert("R404", "R", "6.34k 1%", (xj, yfb), ("BB_FB", "BB_DAC"), fp=FP["R0402"],
                  note="Vdac 3.3V -> 0.97V ; Vdac 0V -> 16.6V")
    nd = r404.p(2)
    s.w(nd, (nd[0] - 7.62, nd[1]))
    s.shunt("C406", "C", "1u", (nd[0] - 7.62, nd[1]), "BB_DAC", fp=FP["C0603"])
    r405 = s.vert("R405", "R", "10k", nd, ("BB_DAC", "BB_PWMI"), fp=FP["R0402"])
    npw = (nd[0], r405.p(2)[1] + 5.08)
    s.w(r405.p(2), npw)
    s.w(npw, (npw[0] + 12.7, npw[1]))
    rpu = s.vert("R406", "R", "10k", (npw[0] + 12.7, npw[1] - 7.62), ("+3V3", "BB_PWMI"), fp=FP["R0402"])
    s.pwr("+3V3", rpu.p(1))
    q = s.part("Q401", "Q_NMOS", "AO3400", npw[0] - 2.54, npw[1] + 5.08, {"1": "BB_ADJ", "3": "BB_PWMI", "2": "GND"},
               fp=FP["SOT23"], note="Inverter: PWM LOW / MCU mati -> Vdac = 3.3V -> Vout minimum")
    s.pwr("GND", q.p(2))
    pg = q.p(1)
    s.w(pg, (pg[0] - 10.16, pg[1]))
    s.shunt("R407", "R", "100k", (pg[0] - 10.16, pg[1]), "BB_ADJ", fp=FP["R0402"])
    to_hl(s, (pg[0] - 10.16, pg[1]), "BB_ADJ", "left", 10.16, "input")
    # proteksi & sense output
    s.shunt("D402", "D_TVS", "SMBJ24A", (xfb + 30.48, yo), "BB_VOUT", fp=FP["SMB"], note="Clamp output")
    rs = s.vert("R408", "R", "100k 1%", (xfb + 48.26, yo), ("BB_VOUT", "VOUT_SENSE"), fp=FP["R0402"],
                note="16.6V -> 1.5V")
    s.shunt("R409", "R", "10k 1%", rs.p(2), "VOUT_SENSE", fp=FP["R0402"])
    s.w(rs.p(2), (xfb + 58.42, rs.p(2)[1]))
    s.shunt("C407", "C", "10n", (xfb + 58.42, rs.p(2)[1]), "VOUT_SENSE", fp=FP["C0402"])
    to_hl(s, (xfb + 58.42, rs.p(2)[1]), "VOUT_SENSE", "right", 7.62, "output")
    J = s.part("J401", "Conn_01x02", "OUTPUT 1-16V", xo + 7.62, yo + 1.27, {"1": "BB_VOUT", "2": "GND"}, fp=FP["TB2"])
    s.w((xo, yo), J.p("1"))
    to_pwr(s, J.p("2"), "GND", "left", 2.54)
    s.autobox("Buck XL4005: input VBUS_SYS (adapter / OTG BQ25713), tegangan diatur MCU",
              [p.ref for p in s.parts if p.ref[0] in "RCDLUQJ" and p.ref[1:].isdigit()])
    s.text("Cara kerja:\n"
           "- Input = VBUS_SYS. Adapter tercolok: tegangan adapter (PD 20V).\n"
           "  Dari baterai: MCU menyalakan OTG BQ25713, VBUS_SYS = Vout + 2V (maks 20.8V).\n"
           "- MCU mengatur tegangan lewat PWM BB_ADJ -> Q401 -> RC (R405/C406) -> R404 ke FB,\n"
           "  loop tertutup memakai VOUT_SENSE. Pilihan tegangan dari DIP + APPLY (sheet MCU).\n"
           "- Fail-safe: EN default LOW (R401); PWM LOW / MCU mati -> Vout minimum (~1V).\n"
           "- Saat USB-C jadi source, VBUS_SYS = tegangan PD -> Vout maks ~ VPD - 2V.",
           30.48, 165.1, 1.524)
    return s


# ============================================================================
# SHEET 5: MCU
# ============================================================================
def sheet_mcu():
    s = Sheet("mcu", "MCU STM32G031K8 + catu 3.3V + DIP + LED", "mcu.kicad_sch", refbase=500)
    SHEETS["mcu"] = s
    U = s.part("U501", "STM32G031K8Tx", "STM32G031K8T6", 177.8, 106.68, {
        "4": "+3V3", "6": "NRST", "7": "CELL_B1", "8": "CELL_B2", "9": "CELL_B3", "10": "CELL_B4", "11": "NTC_BAT",
        "12": "VOUT_SENSE", "13": "CELL_SENSE", "30": "I2C_SCL", "31": "I2C_SDA", "22": "PD_IRQ_N", "23": "CHRG_OK",
        "32": "PROCHOT_N", "18": "OTG_EN", "5": "GND",
        "26": "CHG_EN", "27": "DSG_EN", "15": None, "20": "BB_EN", "14": "BB_ADJ",
        "29": "DIP_V0", "3": "DIP_V1", "2": "DIP_V2", "1": "DIP_V3", "28": "BTN_APPLY",
        "16": "LED_STAT", "17": "LED_FAULT", "24": "SWDIO", "25": "SWCLK", "19": None, "21": None}, mpn="STM32G031K8T6")
    pv = U.p("4")
    s.w(pv, (pv[0] - 38.1, pv[1]))
    s.shunt("C501", "C", "100n", (pv[0] - 20.32, pv[1]), "+3V3", fp=FP["C0402"])
    s.shunt("C502", "C", "4.7u 10V", (pv[0] - 30.48, pv[1]), "+3V3", fp=FP["C0603"])
    s.pwr("+3V3", (pv[0] - 38.1, pv[1]))
    to_lbl(s, U.p("6"), "NRST", "left", 5.08)
    for n, name in (("7", "CELL_B1"), ("8", "CELL_B2"), ("9", "CELL_B3"), ("10", "CELL_B4"), ("11", "NTC_BAT"),
                    ("12", "VOUT_SENSE"), ("13", "CELL_SENSE"), ("22", "PD_IRQ_N"), ("23", "CHRG_OK"),
                    ("32", "PROCHOT_N")):
        to_hl(s, U.p(n), name, "left", 33.02, "input")
    to_hl(s, U.p("18"), "OTG_EN", "left", 33.02, "output")
    for n, name in (("30", "I2C_SCL"), ("31", "I2C_SDA")):
        to_hl(s, U.p(n), name, "left", 33.02)
    to_pwr(s, U.p("5"), "GND", "left")
    for n, name in (("26", "CHG_EN"), ("27", "DSG_EN"), ("20", "BB_EN"), ("14", "BB_ADJ")):
        to_hl(s, U.p(n), name, "right", 25.4, "output")
    s.nc(U.p("15"))
    # DIP VOUT langsung ke pin
    sw = s.part("SW501", "SW_DIP_x04", "VOUT SELECT", 0, 0, {"1": "DIP_V0", "8": "GND", "2": "DIP_V1", "7": "GND",
                                                            "3": "DIP_V2", "6": "GND", "4": "DIP_V3", "5": "GND"},
                fp=FP["DIP4"], note="Pull-up internal MCU, ON = 0")
    p0 = U.p("29")
    sw.x = snap(p0[0] + 33.02, 2.54)
    sw.y = snap(p0[1] - (sw.p("1")[1] - sw.y))
    for a, b in (("29", "1"), ("3", "2"), ("2", "3"), ("1", "4")):
        s.w(U.p(a), sw.p(b))
    bus_to_gnd(s, [sw.p("8"), sw.p("7"), sw.p("6"), sw.p("5")], sw.p("8")[0] + 5.08)
    pb = U.p("28")
    s.w(pb, (pb[0] + 20.32, pb[1]))
    s.shunt("C503", "C", "100n", (pb[0] + 10.16, pb[1]), "BTN_APPLY", fp=FP["C0402"], note="Debounce")
    s.part("SW502", "SW_Push", "APPLY", pb[0] + 20.32, pb[1] + 3.81, {"1": "BTN_APPLY", "2": "GND"}, fp=FP["BTN"])
    s.pwr("GND", (pb[0] + 20.32, pb[1] + 7.62))
    # LED (bertingkat: baris atas lebih panjang)
    for n, ref_r, ref_d, net, col, dx in (("16", "R501", "D501", "LED_STAT", "hijau", 30.48),
                                          ("17", "R502", "D502", "LED_FAULT", "merah", 10.16)):
        p = U.p(n)
        r = s.horiz(ref_r, "R", "1k", (p[0] + dx, p[1]), (net, net + "_A"), fp=FP["R0402"])
        s.w(p, r.p(1))
        a = r.p(2)
        s.w(a, (a[0] + 5.08, a[1]))
        d = s.part(ref_d, "LED", col, a[0] + 5.08, a[1] + 3.81, {"2": net + "_A", "1": "GND"}, rot=180, fp=FP["LED"],
                   ref_at=(a[0] + 8.89, a[1] + 2.54, "right"), val_at=(a[0] + 8.89, a[1] + 5.08, "right"))
        s.pwr("GND", d.p(1))
    # SWD
    J = s.part("J501", "Conn_01x05", "SWD", 0, 0, {"1": "+3V3", "2": "SWDIO", "3": "SWCLK", "4": "NRST", "5": "GND"},
               fp=FP["HDR5"])
    ps = U.p("24")
    J.x = snap(ps[0] + 48.26, 2.54)
    J.y = snap(ps[1] - (J.p("2")[1] - J.y))
    s.w(ps, J.p("2"))
    s.w(U.p("25"), J.p("3"))
    to_pwr(s, J.p("1"), "+3V3", "left", 5.08, "up")
    to_lbl(s, J.p("4"), "NRST", "left", 7.62)
    to_pwr(s, J.p("5"), "GND", "left", 2.54)
    s.nc(U.p("19"))
    # blok pull-up / pull-down / NRST
    xp, yp = 38.1, 203.2
    s.pwr("+3V3", (xp, yp))
    pulls = [("R503", "4.7k", "I2C_SCL"), ("R504", "4.7k", "I2C_SDA"), ("R505", "10k", "PD_IRQ_N"),
             ("R506", "10k", "CHRG_OK"), ("R507", "10k", "PROCHOT_N")]
    s.w((xp, yp), (xp + (len(pulls) - 1) * 12.7, yp))
    for i, (ref, val, net) in enumerate(pulls):
        r = s.vert(ref, "R", val, (xp + i * 12.7, yp), ("+3V3", net), fp=FP["R0402"])
        to_lbl(s, r.p(2), net, "down", 2.54)
    xq = xp + len(pulls) * 12.7 + 5.08
    s.label("OTG_EN", (xq, yp), "up")
    s.shunt("R508", "R", "100k", (xq, yp), "OTG_EN", fp=FP["R0402"], note="Default OTG mati")
    s.label("NRST", (xq + 12.7, yp), "up")
    s.shunt("C504", "C", "100n", (xq + 12.7, yp), "NRST", fp=FP["C0402"])
    s.autobox("Pull-up / pull-down / reset", ["R503", "R504", "R505", "R506", "R507", "R508", "C504"])
    # catu 3.3V
    L = s.part("U502", "HT7533", "HT7533-1", 203.2, 213.36, {"2": "LDO_IN", "3": "+3V3", "1": "GND"},
               note="Vin maks 24V, Iq 2.5uA")
    pin = L.p("2")
    dd = s.part("D503", "BAT54C", "BAT54C", pin[0] - 25.4, pin[1] - 7.62, {"1": "BATT+", "2": "VSYS", "3": "LDO_IN"},
                note="OR: MCU tetap hidup dari baterai walau FET proteksi OFF")
    s.w(dd.p(3), (dd.p(3)[0], pin[1]), pin)
    to_pwr(s, dd.p(1), "BATT+", "left", 5.08, "up")
    to_pwr(s, dd.p(2), "VSYS", "right", 5.08, "up")
    s.shunt("C505", "C", "1u 25V", (pin[0] - 10.16, pin[1]), "LDO_IN", fp=FP["C0805"])
    po = L.p("3")
    s.w(po, (po[0] + 25.4, po[1]))
    s.shunt("C506", "C", "10u 10V", (po[0] + 10.16, po[1]), "+3V3", fp=FP["C0805"])
    s.pwr("+3V3", (po[0] + 25.4, po[1]))
    s.flag((po[0] + 17.78, po[1]), "+3V3")
    to_pwr(s, L.p("1"), "GND", "right", 2.54)
    s.flag((xq + 25.4, yp + 12.7), "GND")
    s.pwr("GND", (xq + 25.4, yp + 12.7))
    s.autobox("Catu 3.3V (BATT+ / VSYS)", ["U502", "D503", "C505", "C506"])
    s.autobox("Mikrokontroler + DIP VOUT + tombol + LED + SWD", ["U501", "C501", "C502", "C503", "SW501", "SW502",
              "R501", "R502", "D501", "D502", "J501"])
    s.text("STM32G031K8T6:\n"
           "- ADC: CELL_B1..B4 (tap x1/6), NTC_BAT, VOUT_SENSE, CELL_SENSE.\n"
           "- I2C1 PB6/PB7 100kHz: BQ25713 (0x6B), TPS65988 (I2C1).\n"
           "- CHG_EN / DSG_EN: FET proteksi baterai (default OFF).\n"
           "- BB_EN + BB_ADJ (PA7 = TIM3_CH2 PWM): output XL4005.\n"
           "- SW501 VOUT 4 bit (16 preset) + SW502 APPLY.\n"
           "- Firmware: OV/UV per cell, suhu, gauge dari ADC BQ25713.",
           271.78, 187.96, 1.524)
    return s


# ============================================================================
# Root
# ============================================================================
ROOT_PINS = {
    "mcu": ["I2C_SCL", "I2C_SDA", "PD_IRQ_N", "CHRG_OK", "PROCHOT_N", "OTG_EN", "CELL_SENSE", "CHG_EN", "DSG_EN",
            "CELL_B1", "CELL_B2", "CELL_B3", "CELL_B4", "NTC_BAT", "BB_EN", "BB_ADJ", "VOUT_SENSE"],
}


def write_root(sheet_uuids):
    """Diagram blok: MCU di kiri, 4 sheet lain di kanan, sinyal disambung dengan wire."""
    shape_of = {}
    for sk, s in SHEETS.items():
        for name, pt, d, shape in s.hlabels:
            shape_of[(sk, name)] = shape
    sig = defaultdict(list)
    for sk, s in SHEETS.items():
        for name, pt, d, shape in s.hlabels:
            if sk not in sig[name]:
                sig[name].append(sk)
    order = ROOT_PINS["mcu"]
    others = ["usb", "chg", "bat", "out"]
    # sheet lain: urutkan pin sesuai urutan MCU
    pins_of = {k: [n for n in order if k in sig[n]] for k in others}
    items = []
    # posisi
    mx, my, mw = 50.8, 45.72, 63.5
    mh = (len(order) + 1) * 5.08
    sx, sw_ = 254.0, 76.2
    y = 30.48
    rects = {}
    pinpos = defaultdict(dict)
    for i, n in enumerate(order):
        pinpos["mcu"][n] = (mx + mw, my + (i + 1) * 5.08)
    rects["mcu"] = (mx, my, mw, mh)
    for k in others:
        h = max(2, len(pins_of[k]) + 1) * 5.08 + 5.08
        rects[k] = (sx, y, sw_, h)
        for i, n in enumerate(pins_of[k]):
            pinpos[k][n] = (sx, y + (i + 1) * 5.08 + 2.54)
        y += h + 12.7
    # wire: I2C bus (2 lajur paling kanan), lainnya lajur menurun ke kiri
    wires = []
    lanes_x = {}
    lane0 = sx - 12.7
    k = 0
    for n in order:
        lanes_x[n] = lane0 - k * 3.81
        k += 1
    js = []
    for n in order:
        src = pinpos["mcu"][n]
        tg = [pinpos[kk][n] for kk in others if n in pinpos[kk]]
        lx = lanes_x[n]
        wires.append((src, (lx, src[1])))
        ys = [t[1] for t in tg] + [src[1]]
        wires.append(((lx, min(ys)), (lx, max(ys))))
        for t in tg:
            wires.append(((lx, t[1]), t))
            if t[1] not in (min(ys), max(ys)):
                js.append((lx, t[1]))
        if src[1] not in (min(ys), max(ys)):
            js.append((lx, src[1]))
    for kk, (x, y0, w, h) in rects.items():
        sh = SHEETS[kk]
        su = sheet_uuids[kk]
        pins = []
        for n, pt in pinpos[kk].items():
            shape = shape_of.get((kk, n), "bidirectional")
            # bentuk pin sheet = bentuk hierarchical label di sub-sheet
            side = 0 if kk == "mcu" else 180
            just = "right" if kk == "mcu" else "left"
            pins.append(f"    (pin {q(n)} {shape} (at {g(pt[0])} {g(pt[1])} {side})\n"
                        f"      (effects (font (size 1.27 1.27)) (justify {just}))\n"
                        f"      (uuid {q(uid('rootpin', kk, n))}))")
        idx = list(SHEETS).index(kk) + 2
        items.append(
            f"  (sheet (at {g(x)} {g(y0)}) (size {g(w)} {g(h)}) (fields_autoplaced)\n"
            f"    (stroke (width 0.1524) (type solid))\n    (fill (color 255 255 194 1.0000))\n"
            f"    (uuid {q(su)})\n"
            f"    (property \"Sheetname\" {q(sh.title)} (at {g(x)} {g(y0 - 0.71)} 0)\n"
            f"      (effects (font (size 1.524 1.524) bold) (justify left bottom)))\n"
            f"    (property \"Sheetfile\" {q(sh.file)} (at {g(x)} {g(y0 + h + 0.59)} 0)\n"
            f"      (effects (font (size 1.27 1.27)) (justify left top)))\n" + "\n".join(pins) + "\n"
            f"    (instances (project {q(PROJECT)} (path {q('/' + ROOT_UUID)} (page {q(str(idx))}))))\n  )")
    rs = Sheet("root", "", "")
    rs.wires = [((round(a[0], 2), round(a[1], 2)), (round(b[0], 2), round(b[1], 2))) for a, b in wires]
    js = rs._junctions()
    wires = rs._split_wires(js)
    for i, (a, b) in enumerate(wires):
        items.append(f"  (wire (pts (xy {g(a[0])} {g(a[1])}) (xy {g(b[0])} {g(b[1])})) "
                     f"(stroke (width 0) (type default)) (uuid {q(uid('rootw', i, a, b))}))")
    for i, pt in enumerate(js):
        items.append(f"  (junction (at {g(pt[0])} {g(pt[1])}) (diameter 0) (color 0 0 0 0) "
                     f"(uuid {q(uid('rootj', i, pt))}))")
    blk = ("BMS 2-4S Li-ion + USB-C PD dua arah + output terminal 1-16V\n"
           "Semua part tersedia di Tokopedia (docs/bom_tokopedia.md)\n\n"
           "Alur daya:\n"
           "  USB-C -> TPS65988 (PD, switch 20V/5A) -> VBUS_SYS -> BQ25713 (buck-boost) -> VSYS\n"
           "  VSYS -> BATFET -> PACK+ -> FET proteksi P-ch -> sekring -> cell 2-4S\n"
           "  VBUS_SYS -> XL4005 -> terminal 1-16V (saat baterai: OTG BQ25713 mengisi VBUS_SYS)\n"
           "  BATT+/VSYS -> BAT54C -> HT7533 -> +3V3 (STM32G031, TPS65988)\n\n"
           "Rail global (simbol power): VBUS_SYS, VSYS, PACK+, BATT+, +3V3, GND\n"
           "Sinyal antar sheet: wire di diagram ini (sheet pin = hierarchical label)\n\n"
           f"Status: DRAFT v{REV} - lihat README.md bagian VERIFIKASI sebelum layout PCB.")
    items.append(f"  (text {q(blk)} (at 30.48 195.58 0)\n    (effects (font (size 1.778 1.778)) (justify left top))\n"
                 f"    (uuid {q(uid('root', 'note'))})\n  )")
    tb = (f"  (title_block\n    (title \"BMS 2-4S + USB-C PD + Output 1-16V\")\n    (date \"{DATE}\")\n"
          f"    (rev \"{REV}\")\n    (company \"Power bank 2-4S (part Tokopedia)\")\n"
          f"    (comment 1 \"Dibuat oleh tools/gen_schematic.py\")\n  )")
    txt = (f"(kicad_sch (version 20230121) (generator eeschema)\n\n  (uuid {q(ROOT_UUID)})\n\n"
           f"  (paper \"A3\")\n\n{tb}\n\n  (lib_symbols\n  )\n\n" + "\n".join(items) +
           "\n\n  (sheet_instances\n    (path \"/\" (page \"1\"))\n  )\n)\n")
    with open(os.path.join(OUT_DIR, PROJECT + ".kicad_sch"), "w") as f:
        f.write(txt)
    return sig


# ============================================================================
# validasi & output
# ============================================================================
POWER_NETS = {"GND", "+3V3", "VSYS", "VBUS_SYS", "PACK+", "BATT+"}


def intended():
    netconn = defaultdict(list)
    netsheets = defaultdict(set)
    errs = []
    refs = set()
    for sk, s in SHEETS.items():
        for p in s.parts:
            if p.symname == "PWR_FLAG":
                continue
            if p.ref in refs:
                errs.append(f"ref ganda {p.ref}")
            refs.add(p.ref)
            nums = {pn.num for pn in p.sym.pins}
            for n in nums:
                if n not in p.pins:
                    errs.append(f"{p.ref}: pin {n} belum diberi net")
            for n in p.pins:
                if n not in nums:
                    errs.append(f"{p.ref}: pin {n} tidak ada di simbol")
            for n, net in p.pins.items():
                if net:
                    netconn[net].append(f"{p.ref}.{n}")
                    netsheets[net].add(sk)
    for net, sks in netsheets.items():
        if len(sks) > 1 and net not in POWER_NETS and not any(net == h[0] for s in SHEETS.values() for h in s.hlabels):
            errs.append(f"net {net} lintas sheet tanpa hierarchical label / simbol power: {sorted(sks)}")
    for net, c in netconn.items():
        if len(c) < 2:
            errs.append(f"net {net} hanya 1 koneksi: {c}")
    return errs, netconn, netsheets


def write_lib():
    body = "\n".join("  " + s.body().replace("\n", "\n  ") for s in SYMS.values())
    with open(os.path.join(OUT_DIR, PROJECT + ".kicad_sym"), "w") as f:
        f.write(f"(kicad_symbol_lib (version 20220914) (generator kicad_symbol_editor)\n{body}\n)\n")
    with open(os.path.join(OUT_DIR, "sym-lib-table"), "w") as f:
        f.write('(sym_lib_table\n  (version 7)\n  (lib (name "bms")(type "KiCad")(uri "${KIPRJMOD}/bms.kicad_sym")'
                '(options "")(descr "Simbol proyek BMS"))\n)\n')


def write_pro(sheet_uuids):
    pro = {"board": {"design_settings": {}}, "boards": [],
           "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
           "meta": {"filename": PROJECT + ".kicad_pro", "version": 1},
           "pcbnew": {"last_paths": {}, "page_layout_descr_file": ""},
           "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
           "sheets": [[ROOT_UUID, ""]] + [[sheet_uuids[k], s.title] for k, s in SHEETS.items()],
           "text_variables": {}}
    with open(os.path.join(OUT_DIR, PROJECT + ".kicad_pro"), "w") as f:
        json.dump(pro, f, indent=2)
        f.write("\n")


def nat(r):
    m = re.match(r"([A-Z#]+)(\d+)", r)
    return (m.group(1), int(m.group(2))) if m else (r, 0)


def write_docs(netconn, netsheets):
    lines = ["# Netlist (otomatis dari gen_schematic.py)", "", "| Net | Sheet | Koneksi |", "|---|---|---|"]
    for net in sorted(netconn):
        lines.append(f"| `{net}` | {', '.join(sorted(netsheets[net]))} | {' '.join(sorted(netconn[net], key=nat))} |")
    with open(os.path.join(DOC_DIR, "netlist.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    rows = defaultdict(list)
    for sk, s in SHEETS.items():
        for p in s.parts:
            if p.symname == "PWR_FLAG":
                continue
            rows[(p.symname, p.value, p.fp or p.sym.footprint, p.dnp, p.mpn)].append(p.ref)
    out = ["Jumlah,Referensi,Value,Simbol,Footprint,MPN,DNP"]
    for (sym, val, fp, dnp, mpn), refs in sorted(rows.items(), key=lambda kv: nat(sorted(kv[1], key=nat)[0])):
        refs = sorted(refs, key=nat)
        out.append(f"{len(refs)},\"{' '.join(refs)}\",\"{val}\",{sym},\"{fp}\",\"{mpn}\",{'DNP' if dnp else ''}")
    with open(os.path.join(DOC_DIR, "bom.csv"), "w") as f:
        f.write("\n".join(out) + "\n")


def build():
    SHEETS.clear()
    sheet_usb()
    sheet_chg()
    sheet_bat()
    sheet_out()
    sheet_mcu()


def main():
    build()
    errs, netconn, netsheets = intended()
    if errs:
        print("VALIDASI GAGAL:")
        for e in errs:
            print("  -", e)
        raise SystemExit(1)
    os.makedirs(OUT_DIR, exist_ok=True)
    for old in os.listdir(OUT_DIR):
        if old.endswith(".kicad_sch"):
            os.remove(os.path.join(OUT_DIR, old))
    sheet_uuids = {k: uid("sheet", k) for k in SHEETS}
    for k, s in SHEETS.items():
        tb = (f"  (title_block\n    (title {q(s.title)})\n    (date \"{DATE}\")\n    (rev \"{REV}\")\n"
              f"    (company \"Power bank 2-4S (part Tokopedia)\")\n"
              f"    (comment 1 \"Draft - cek daftar VERIFIKASI di README sebelum layout\")\n  )")
        with open(os.path.join(OUT_DIR, s.file), "w") as f:
            f.write(sheet_file(s, PROJECT, ROOT_UUID, sheet_uuids[k], LIB, tb))
    write_root(sheet_uuids)
    write_lib()
    write_pro(sheet_uuids)
    write_docs(netconn, netsheets)
    n = sum(1 for s in SHEETS.values() for p in s.parts if p.symname != "PWR_FLAG")
    print(f"OK: {len(SHEETS)} sheet, {n} komponen, {len(netconn)} net")


if __name__ == "__main__":
    main()
