#!/usr/bin/env python3
"""
Generator skematik KiCad untuk BMS 1-4S + USB-C PD + output 1-16V.

File ini adalah *sumber kebenaran* untuk netlist. Jalankan:

    python3 tools/gen_schematic.py

dan file berikut akan ditulis ulang di folder ../kicad/:
    bms.kicad_pro, bms.kicad_sch (root), 5 sub-sheet, bms.kicad_sym, sym-lib-table

Format file: KiCad 7 (bisa dibuka KiCad 7, 8, 9; akan di-upgrade otomatis).

Konvensi:
  * Semua koneksi memakai label (global untuk net lintas sheet, lokal untuk
    net di dalam satu sheet) + simbol power GND / +3V3.
  * Nomor pin IC kustom (BQ25713, BQ40Z50-R2, TPS55289, TPS25750D) diambil
    dari tabel "Pin Functions" datasheet TI. Pin STM32G031G8U6, 24LC256,
    NCP718 dan USB-C 16P diambil dari library resmi KiCad.
"""
import os
import uuid as _uuid
from collections import defaultdict, OrderedDict

PROJECT = "bms"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "kicad")
LIB = "bms"

# ----------------------------------------------------------------------------
# util
# ----------------------------------------------------------------------------
_ns = _uuid.UUID("6f1c2a52-6a0b-4b8e-9d3f-2b5b1a9c0e11")


def uid(*parts):
    """UUID deterministik supaya diff git tetap kecil saat generate ulang."""
    return str(_uuid.uuid5(_ns, "/".join(str(p) for p in parts)))


def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def g(v):
    """Bulatkan ke grid 0.01 mm dan format."""
    v = round(v * 100) / 100.0
    s = ("%.2f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


FONT = "(effects (font (size 1.27 1.27)))"
FONT_H = "(effects (font (size 1.27 1.27)) hide)"
G = 2.54

# ----------------------------------------------------------------------------
# definisi simbol
# ----------------------------------------------------------------------------


class Pin:
    def __init__(self, num, name, etype, x, y, ang, length=G, hidden=False):
        self.num, self.name, self.etype = num, name, etype
        self.x, self.y, self.ang, self.length, self.hidden = x, y, ang, length, hidden


class Sym:
    def __init__(self, name, ref, pins, graphics, desc="", power=False,
                 hide_pin_numbers=False, hide_pin_names=False, pin_name_offset=1.016,
                 ref_at=(0, 0, 0), val_at=(0, 0, 0), datasheet="~", footprint=""):
        self.name, self.ref, self.pins, self.graphics = name, ref, pins, graphics
        self.desc, self.power = desc, power
        self.hide_pin_numbers, self.hide_pin_names = hide_pin_numbers, hide_pin_names
        self.pin_name_offset = pin_name_offset
        self.ref_at, self.val_at = ref_at, val_at
        self.datasheet, self.footprint = datasheet, footprint

    def body(self, lib_prefix=""):
        n = lib_prefix + self.name
        out = [f"(symbol {q(n)}"]
        if self.power:
            out.append(" (power)")
        if self.hide_pin_numbers:
            out.append(" (pin_numbers hide)")
        if self.hide_pin_names:
            out.append(f" (pin_names (offset {g(self.pin_name_offset)}) hide)")
        else:
            out.append(f" (pin_names (offset {g(self.pin_name_offset)}))")
        out.append(" (in_bom yes) (on_board yes)\n")
        rx, ry, ra = self.ref_at
        vx, vy, va = self.val_at
        hide_ref = self.power
        out.append(f"  (property \"Reference\" {q(self.ref)} (at {g(rx)} {g(ry)} {g(ra)}) "
                   f"{FONT_H if hide_ref else FONT})\n")
        out.append(f"  (property \"Value\" {q(self.name)} (at {g(vx)} {g(vy)} {g(va)}) {FONT})\n")
        out.append(f"  (property \"Footprint\" {q(self.footprint)} (at 0 0 0) {FONT_H})\n")
        out.append(f"  (property \"Datasheet\" {q(self.datasheet)} (at 0 0 0) {FONT_H})\n")
        if self.desc:
            out.append(f"  (property \"ki_description\" {q(self.desc)} (at 0 0 0) {FONT_H})\n")
        out.append(f"  (symbol {q(self.name + '_0_1')}\n")
        for gr in self.graphics:
            out.append("   " + gr + "\n")
        out.append("  )\n")
        out.append(f"  (symbol {q(self.name + '_1_1')}\n")
        for p in self.pins:
            hid = " hide" if p.hidden else ""
            out.append(f"   (pin {p.etype} line (at {g(p.x)} {g(p.y)} {p.ang}) (length {g(p.length)}){hid} "
                       f"(name {q(p.name)} {FONT}) (number {q(p.num)} {FONT}))\n")
        out.append("  )\n")
        out.append(")")
        return "".join(out)


def rect(x1, y1, x2, y2, fill="background", w=0.254):
    return (f"(rectangle (start {g(x1)} {g(y1)}) (end {g(x2)} {g(y2)}) "
            f"(stroke (width {g(w)}) (type default)) (fill (type {fill})))")


def poly(pts, w=0.254, fill="none"):
    p = " ".join(f"(xy {g(x)} {g(y)})" for x, y in pts)
    return f"(polyline (pts {p}) (stroke (width {g(w)}) (type default)) (fill (type {fill})))"


def circle(x, y, r, w=0.254, fill="none"):
    return f"(circle (center {g(x)} {g(y)}) (radius {g(r)}) (stroke (width {g(w)}) (type default)) (fill (type {fill})))"


def ic_symbol(name, ref, left, right, desc="", datasheet="~", footprint="", min_w=None):
    """
    left/right: list of (name, [numbers], etype) atau None untuk spasi.
    Nomor pertama terlihat, sisanya pin tersembunyi bertumpuk (stacked).
    """
    nrows = max(len(left), len(right))
    h = (nrows + 1) * G
    maxl = max([len(e[0]) for e in left if e] + [1])
    maxr = max([len(e[0]) for e in right if e] + [1])
    w = (maxl + maxr) * 1.27 + 5 * G
    if min_w:
        w = max(w, min_w)
    w = round(w / (2 * G) + 0.4999) * (2 * G)
    top = h / 2
    top = round(top / G) * G
    pins = []
    for side, lst in (("L", left), ("R", right)):
        for i, e in enumerate(lst):
            if not e:
                continue
            pname, nums, et = e
            y = top - (i + 1) * G
            if side == "L":
                x, ang = -w / 2 - G, 0
            else:
                x, ang = w / 2 + G, 180
            for k, n in enumerate(nums):
                pins.append(Pin(n, pname, et, x, y, ang, G, hidden=(k > 0)))
    bottom = top - (nrows + 1) * G
    gr = [rect(-w / 2, top, w / 2, bottom)]
    return Sym(name, ref, pins, gr, desc=desc, datasheet=datasheet, footprint=footprint,
               ref_at=(-w / 2, top + 1.27, 0), val_at=(-w / 2, bottom - 1.27, 0))


def two_pin(name, ref, graphics, etype=("passive", "passive"), names=("~", "~"), nums=("1", "2"),
            show_numbers=False, desc=""):
    """Pin 1 di atas, pin 2 di bawah (vertikal)."""
    p = [Pin(nums[0], names[0], etype[0], 0, 3.81, 270, 1.27),
         Pin(nums[1], names[1], etype[1], 0, -3.81, 90, 1.27)]
    return Sym(name, ref, p, graphics, desc=desc, hide_pin_numbers=not show_numbers,
               hide_pin_names=True, pin_name_offset=0,
               ref_at=(2.54, 1.27, 0), val_at=(2.54, -1.27, 0))


SYMS = OrderedDict()


def add(s):
    SYMS[s.name] = s
    return s


# --- pasif ---------------------------------------------------------------
add(two_pin("R", "R", [rect(-1.016, 2.54, 1.016, -2.54, fill="none")], desc="Resistor"))
add(two_pin("C", "C", [poly([(-2.032, 0.762), (2.032, 0.762)], 0.508),
                       poly([(-2.032, -0.762), (2.032, -0.762)], 0.508),
                       poly([(0, 2.54), (0, 0.762)]), poly([(0, -2.54), (0, -0.762)])],
            desc="Kapasitor"))
add(two_pin("L", "L", [
    "(arc (start 0 2.54) (mid 0.6323 1.905) (end 0 1.27) (stroke (width 0) (type default)) (fill (type none)))",
    "(arc (start 0 1.27) (mid 0.6323 0.635) (end 0 0) (stroke (width 0) (type default)) (fill (type none)))",
    "(arc (start 0 0) (mid 0.6323 -0.635) (end 0 -1.27) (stroke (width 0) (type default)) (fill (type none)))",
    "(arc (start 0 -1.27) (mid 0.6323 -1.905) (end 0 -2.54) (stroke (width 0) (type default)) (fill (type none)))"],
    desc="Induktor"))
add(two_pin("Thermistor_NTC", "TH", [rect(-1.016, 2.54, 1.016, -2.54, fill="none"),
                                     poly([(-1.905, -2.54), (-1.905, -1.905), (1.905, 1.905), (1.905, 2.54)], 0)],
            desc="Thermistor NTC"))
# dioda: K di atas (pin 1), A di bawah (pin 2) -> arus mengalir dari bawah ke atas
add(two_pin("D_TVS", "D", [poly([(-1.27, 1.27), (1.27, 1.27)], 0.254),
                           poly([(-1.27, 1.27), (-1.778, 1.778)], 0.254),
                           poly([(1.27, 1.27), (1.778, 0.762)], 0.254),
                           poly([(0, 1.27), (-1.27, -1.27), (1.27, -1.27), (0, 1.27)], 0.254, "none"),
                           poly([(0, 2.54), (0, 1.27)]), poly([(0, -2.54), (0, -1.27)])],
            names=("K", "A"), show_numbers=False, desc="TVS unidirectional (K=1, A=2)"))
add(two_pin("LED", "D", [poly([(-1.27, 1.27), (1.27, 1.27)], 0.254),
                         poly([(0, 1.27), (-1.27, -1.27), (1.27, -1.27), (0, 1.27)], 0.254, "none"),
                         poly([(0, 2.54), (0, 1.27)]), poly([(0, -2.54), (0, -1.27)]),
                         poly([(1.778, 0.508), (2.794, 1.524)]), poly([(1.778, -0.508), (2.794, 0.508)])],
            names=("K", "A"), nums=("1", "2"), desc="LED (K=1 atas, A=2 bawah)"))
add(two_pin("SW_Push", "SW", [circle(0, 2.032, 0.508), circle(0, -2.032, 0.508),
                              poly([(-1.27, 1.524), (-1.27, -1.524)], 0.254),
                              poly([(-1.778, 0), (-2.54, 0)], 0.254)],
            desc="Push button"))

# --- MOSFET: G kiri (1), S bawah (2), D atas (3) ------------------------------


def fet(name, pch=False):
    arrow = [(0.254, 0), (1.27, 0.508), (1.27, -0.508), (0.254, 0)] if not pch else \
            [(1.524, 0), (0.508, 0.508), (0.508, -0.508), (1.524, 0)]
    gr = [poly([(-0.254, 1.905), (-0.254, -1.905)], 0.254),
          poly([(0.254, 2.286), (0.254, 1.27)], 0.254),
          poly([(0.254, 0.508), (0.254, -0.508)], 0.254),
          poly([(0.254, -1.27), (0.254, -2.286)], 0.254),
          poly([(0.254, 1.778), (2.54, 1.778), (2.54, 2.54)]),
          poly([(0.254, -1.778), (2.54, -1.778), (2.54, -2.54)]),
          poly([(0.254, 0), (2.54, 0), (2.54, -1.778)]),
          poly(arrow, 0, "outline"),
          poly([(-2.54, 0), (-0.254, 0)])]
    p = [Pin("1", "G", "input", -5.08, 0, 0, 2.54),
         Pin("2", "S", "passive", 2.54, -5.08, 90, 2.54),
         Pin("3", "D", "passive", 2.54, 5.08, 270, 2.54)]
    return Sym(name, "Q", p, gr, desc=("P" if pch else "N") + "-channel MOSFET (1=G, 2=S, 3=D)",
               hide_pin_numbers=False, hide_pin_names=True, pin_name_offset=0,
               ref_at=(5.08, 1.27, 0), val_at=(5.08, -1.27, 0))


add(fet("Q_NMOS"))
add(fet("Q_PMOS", pch=True))

# --- power ---------------------------------------------------------------
add(Sym("GND", "#PWR", [Pin("1", "GND", "power_in", 0, 0, 270, 0, hidden=True)],
        [poly([(0, 0), (0, -1.27), (1.27, -1.27), (0, -2.54), (-1.27, -1.27), (0, -1.27)])],
        power=True, desc="Ground", hide_pin_numbers=True, pin_name_offset=0,
        ref_at=(0, -6.35, 0), val_at=(0, -3.81, 0)))
add(Sym("+3V3", "#PWR", [Pin("1", "+3V3", "power_in", 0, 0, 90, 0, hidden=True)],
        [poly([(-0.762, 1.27), (0, 2.54)]), poly([(0, 0), (0, 2.54)]), poly([(0, 2.54), (0.762, 1.27)])],
        power=True, desc="Rail +3.3V", hide_pin_numbers=True, pin_name_offset=0,
        ref_at=(0, -3.81, 0), val_at=(0, 3.556, 0)))
add(Sym("PWR_FLAG", "#FLG", [Pin("1", "pwr", "power_out", 0, 0, 90, 0)],
        [poly([(0, 0), (0, 1.27), (-1.016, 1.905), (0, 2.54), (1.016, 1.905), (0, 1.27)])],
        power=True, desc="Penanda net power untuk ERC", hide_pin_numbers=True, hide_pin_names=True,
        pin_name_offset=0, ref_at=(0, 1.905, 0), val_at=(0, 3.81, 0)))

# --- konektor & switch ----------------------------------------------------


def conn(name, n, desc=""):
    pins = []
    top = (n - 1) * G / 2
    top = round(top / 1.27) * 1.27
    for i in range(n):
        pins.append(Pin(str(i + 1), f"Pin_{i + 1}", "passive", -5.08, top - i * G, 0, 3.81))
    gr = [rect(-1.27, top + 1.27, 1.27, top - (n - 1) * G - 1.27, fill="background")]
    return Sym(name, "J", pins, gr, desc=desc, hide_pin_names=True, pin_name_offset=1.016,
               ref_at=(0, top + 2.54, 0), val_at=(0, top - (n - 1) * G - 2.54, 0))


add(conn("Conn_01x02", 2, "Konektor 1x02"))
add(conn("Conn_01x03", 3, "Konektor 1x03"))
add(conn("Conn_01x05", 5, "Konektor 1x05"))


def dip(name, n):
    """Saklar k: pin kiri = k, pin kanan = 2n+1-k (konvensi footprint DIP KiCad)."""
    pins, gr = [], []
    top = (n - 1) * G / 2
    top = round(top / 1.27) * 1.27
    for k in range(1, n + 1):
        y = top - (k - 1) * G
        pins.append(Pin(str(k), "~", "passive", -7.62, y, 0, 5.08))
        pins.append(Pin(str(2 * n + 1 - k), "~", "passive", 7.62, y, 180, 5.08))
        gr += [circle(-2.032, y, 0.508), circle(2.032, y, 0.508),
               poly([(-1.524, y + 0.127), (2.032, y + 1.016)], 0)]
    gr.insert(0, rect(-3.81, top + 1.905, 3.81, top - (n - 1) * G - 1.905, fill="background"))
    return Sym(name, "SW", pins, gr, desc=f"DIP switch {n} posisi", hide_pin_names=True,
               ref_at=(0, top + 3.175, 0), val_at=(0, top - (n - 1) * G - 3.175, 0))


add(dip("SW_DIP_x04", 4))
add(dip("SW_DIP_x08", 8))

# --- IC dari library resmi KiCad (pin & nomor disalin persis) -------------
add(ic_symbol("USB_C_Receptacle_USB2.0_16P", "J",
              [("VBUS", ["A4", "A9", "B4", "B9"], "passive"), None,
               ("CC1", ["A5"], "bidirectional"), ("CC2", ["B5"], "bidirectional"), None,
               ("D+", ["A6", "B6"], "bidirectional"), ("D-", ["A7", "B7"], "bidirectional"), None,
               ("SBU1", ["A8"], "bidirectional"), ("SBU2", ["B8"], "bidirectional"), None,
               ("GND", ["A1", "A12", "B1", "B12"], "passive"), ("SHIELD", ["SH"], "passive")],
              [], desc="USB Type-C receptacle 16P (USB2.0). Pinout dari library KiCad Connector:USB_C_Receptacle_USB2.0_16P"))

add(ic_symbol("24LC256", "U",
              [("A0", ["1"], "input"), ("A1", ["2"], "input"), ("A2", ["3"], "input"), ("WP", ["7"], "input")],
              [("VCC", ["8"], "power_in"), ("SDA", ["5"], "bidirectional"), ("SCL", ["6"], "input"),
               ("GND", ["4"], "power_in")],
              desc="EEPROM I2C 256Kbit (32KB). Pinout dari library KiCad Memory_EEPROM:24LC256",
              datasheet="http://ww1.microchip.com/downloads/en/DeviceDoc/21203M.pdf"))

add(ic_symbol("NCP718xSN330", "U",
              [("IN", ["1"], "power_in"), ("EN", ["3"], "input")],
              [("OUT", ["5"], "power_out"), ("NC", ["4"], "no_connect"), ("GND", ["2"], "power_in")],
              desc="LDO 3.3V 300mA, input 2.5-24V, Iq 4uA. Pinout dari library KiCad Regulator_Linear:NCP718xSN330",
              datasheet="https://www.onsemi.com/pub/Collateral/NCP718-D.PDF"))

STM_PINS = {"1": "PC14", "2": "PC15", "3": "VDD", "4": "VSS", "5": "PF2/NRST", "6": "PA0", "7": "PA1",
            "8": "PA2", "9": "PA3", "10": "PA4", "11": "PA5", "12": "PA6", "13": "PA7", "14": "PB0",
            "15": "PB1", "16": "PA8", "17": "PC6", "18": "PA9/PA11", "19": "PA10/PA12", "20": "PA13/SWDIO",
            "21": "PA14/SWCLK/BOOT0", "22": "PA15", "23": "PB3", "24": "PB4", "25": "PB5", "26": "PB6",
            "27": "PB7", "28": "PB8"}


def stm(n, et="bidirectional"):
    return (STM_PINS[n], [n], et)


add(ic_symbol("STM32G031G8Ux", "U",
              [stm("3", "power_in"), stm("5", "input"), None,
               stm("6"), stm("7"), stm("8"), stm("9"), stm("10"), stm("11"), stm("12"), stm("13"),
               stm("14"), stm("15"), None, stm("4", "power_in")],
              [stm("16"), stm("17"), stm("18"), stm("19"), stm("20"), stm("21"), stm("22"), stm("23"),
               stm("24"), stm("25"), stm("26"), stm("27"), stm("28"), stm("1"), stm("2")],
              desc="STM32G031G8U6, UFQFPN-28. Pinout dari library KiCad MCU_ST_STM32G0:STM32G031G8Ux",
              datasheet="https://www.st.com/resource/en/datasheet/stm32g031g8.pdf",
              footprint="Package_DFN_QFN:QFN-28_4x4mm_P0.5mm"))

# --- IC kustom (pinout dari datasheet TI) ---------------------------------
add(ic_symbol("BQ25713", "U",
              [("VBUS", ["1"], "passive"), ("ACP", ["3"], "passive"), ("ACN", ["2"], "passive"), None,
               ("ILIM_HIZ", ["6"], "input"), ("CELL_BATPRESZ", ["18"], "input"), ("OTG/VAP", ["5"], "input"), None,
               ("SDA", ["12"], "bidirectional"), ("SCL", ["13"], "input"),
               ("CHRG_OK", ["4"], "open_collector"), ("~{PROCHOT}", ["11"], "open_collector"), None,
               ("CMPIN", ["14"], "input"), ("CMPOUT", ["15"], "open_collector"), None,
               ("IADPT", ["8"], "output"), ("IBAT", ["9"], "output"), ("PSYS", ["10"], "output"), None,
               ("COMP1", ["16"], "passive"), ("COMP2", ["17"], "passive")],
              [("REGN", ["28"], "power_out"), ("VDDA", ["7"], "passive"), None,
               ("HIDRV1", ["31"], "output"), ("BTST1", ["30"], "passive"), ("SW1", ["32"], "passive"),
               ("LODRV1", ["29"], "output"), None,
               ("HIDRV2", ["24"], "output"), ("BTST2", ["25"], "passive"), ("SW2", ["23"], "passive"),
               ("LODRV2", ["26"], "output"), None,
               ("VSYS", ["22"], "passive"), ("~{BATDRV}", ["21"], "output"), None,
               ("SRP", ["20"], "passive"), ("SRN", ["19"], "passive"), None, None, None,
               ("PGND", ["27", "33"], "power_in")],
              desc="BQ25713 I2C 1-4S NVDC buck-boost charger controller, WQFN-32 4x4 (RSN). "
                   "Pin 33 = thermal pad. Pinout: datasheet SLUSD83C Table 7-1",
              datasheet="https://www.ti.com/lit/ds/symlink/bq25713.pdf"))

add(ic_symbol("BQ40Z50-R2", "U",
              [("BAT", ["32"], "power_in"), ("VCC", ["26"], "passive"), ("PACK", ["27"], "passive"),
               ("PBI", ["1"], "passive"), None,
               ("VC4", ["2"], "passive"), ("VC3", ["3"], "passive"), ("VC2", ["4"], "passive"),
               ("VC1", ["5"], "passive"), None,
               ("SRP", ["8"], "passive"), ("SRN", ["6"], "passive"), None,
               ("TS1", ["10"], "passive"), ("TS2", ["11"], "passive"), ("TS3", ["12"], "passive"),
               ("TS4", ["13"], "passive")],
              [("CHG", ["31"], "output"), ("DSG", ["28"], "output"), ("PCHG", ["30"], "output"),
               ("FUSE", ["25"], "output"), None,
               ("SMBD", ["18"], "bidirectional"), ("SMBC", ["19"], "bidirectional"),
               ("BTP_INT", ["15"], "output"), ("PRES/~{SHUTDN}", ["16"], "input"), ("DISP", ["17"], "input"), None,
               ("LEDCNTLA", ["20"], "passive"), ("LEDCNTLB", ["21"], "passive"), ("LEDCNTLC", ["22"], "passive"),
               ("PTC", ["23"], "passive"), ("PTCEN", ["24"], "passive"), None,
               ("NC", ["7", "14", "29"], "passive"), ("VSS", ["9", "33"], "power_in")],
              desc="BQ40Z50-R2 1-4S Li-ion gauge + proteksi + balancing, VQFN-32 4x4 (RSM). "
                   "Pin 33 = thermal pad. Pinout: datasheet SLUSCS4C Table 6-1",
              datasheet="https://www.ti.com/lit/ds/symlink/bq40z50-r2.pdf"))

add(ic_symbol("TPS55289", "U",
              [("VIN", ["7"], "power_in"), ("EN/UVLO", ["1"], "input"), None,
               ("SCL", ["3"], "input"), ("SDA", ["4"], "bidirectional"), ("MODE", ["2"], "input"), None,
               ("DITH/SYNC", ["5"], "input"), ("FSW", ["6"], "passive"), None,
               ("EXTVCC", ["21"], "input"), ("VCC", ["18"], "power_out"), None,
               ("AGND", ["17"], "power_in"), ("PGND", ["9"], "power_in")],
              [("SW1", ["8"], "passive"), ("BOOT1", ["20"], "passive"), None,
               ("SW2", ["10"], "passive"), ("BOOT2", ["19"], "passive"), None,
               ("VOUT", ["11"], "passive"), ("ISP", ["12"], "passive"), ("ISN", ["13"], "passive"), None,
               ("FB/~{INT}", ["14"], "open_collector"), ("COMP", ["15"], "passive"), ("CDC", ["16"], "passive")],
              desc="TPS55289 30V 8A buck-boost, output 0.8-22V via I2C, VQFN-HR-21 (RYQ). "
                   "Pinout: datasheet SLVSGA9A Table 5-1",
              datasheet="https://www.ti.com/lit/ds/symlink/tps55289.pdf"))

add(ic_symbol("TPS25750D", "U",
              [("VBUS_IN", ["23", "24", "25"], "passive"), ("VBUS", ["32", "33"], "passive"),
               ("PP5V", ["34", "35"], "passive"), None,
               ("CC1", ["28"], "bidirectional"), ("CC2", ["29"], "bidirectional"), None,
               ("ADCIN1", ["2"], "input"), ("ADCIN2", ["3"], "input"), None,
               ("GPIO0", ["5"], "bidirectional"), ("GPIO1", ["6"], "bidirectional"),
               ("GPIO2", ["7"], "output"), ("GPIO3", ["19"], "output"),
               ("GPIO4/USB_P", ["26"], "bidirectional"), ("GPIO5/USB_N", ["27"], "bidirectional"),
               ("GPIO6", ["37"], "output"), ("GPIO7", ["36"], "output"), ("GPIO11", ["13"], "output")],
              [("PPHV", ["20", "21", "22"], "passive"), None,
               ("VIN_3V3", ["38"], "power_in"), ("LDO_3V3", ["1"], "power_out"),
               ("LDO_1V5", ["4"], "power_out"), None,
               ("I2Cs_SDA", ["8"], "bidirectional"), ("I2Cs_SCL", ["9"], "input"),
               ("~{I2Cs_IRQ}", ["10"], "output"), None,
               ("I2Cm_SDA", ["16"], "bidirectional"), ("I2Cm_SCL", ["17"], "output"),
               ("~{I2Cm_IRQ}", ["18"], "input"), None,
               ("DRAIN", ["15", "30"], "passive"), None, None,
               ("GND", ["11", "12", "14", "31"], "power_in")],
              desc="TPS25750D USB-C PD controller, power path 5V/3A source + 28V/7A bidirectional, "
                   "QFN-38 4x6 (RJK). Pinout: datasheet SLVSFR7A Table 6-1",
              datasheet="https://www.ti.com/lit/ds/symlink/tps25750.pdf"))

# ----------------------------------------------------------------------------
# netlist / part
# ----------------------------------------------------------------------------


class Part:
    def __init__(self, ref, sym, value, pins, fp="", dnp=False, note="", pos=None, mpn=""):
        self.ref, self.sym, self.value, self.pins = ref, sym, value, pins
        self.fp, self.dnp, self.note, self.pos, self.mpn = fp, dnp, note, pos, mpn
        self.sheet = None


FP = {
    "R0402": "Resistor_SMD:R_0402_1005Metric",
    "R0603": "Resistor_SMD:R_0603_1608Metric",
    "R0805": "Resistor_SMD:R_0805_2012Metric",
    "R1206": "Resistor_SMD:R_1206_3216Metric",
    "R2512": "Resistor_SMD:R_2512_6332Metric",
    "C0402": "Capacitor_SMD:C_0402_1005Metric",
    "C0603": "Capacitor_SMD:C_0603_1608Metric",
    "C0805": "Capacitor_SMD:C_0805_2012Metric",
    "C1206": "Capacitor_SMD:C_1206_3216Metric",
    "LED": "LED_SMD:LED_0603_1608Metric",
    "SMB": "Diode_SMD:D_SMB",
    "SOIC8": "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
    "SOT235": "Package_TO_SOT_SMD:SOT-23-5",
    "USBC": "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12",
    "XH5": "Connector_JST:JST_XH_B5B-XH-A_1x05_P2.50mm_Vertical",
    "PH2": "Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical",
    "TB2": "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal",
    "HDR5": "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical",
    "HDR3": "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
    "DIP4": "Button_Switch_THT:SW_DIP_SPSTx04_Slide_9.78x12.34mm_W7.62mm_P2.54mm",
    "DIP8": "Button_Switch_THT:SW_DIP_SPSTx08_Slide_9.78x22.5mm_W7.62mm_P2.54mm",
    "BTN": "Button_Switch_SMD:SW_SPST_TL3342",
}

SHEETS = OrderedDict()   # key -> dict(title, file, parts, notes, paper)


def sheet(key, title, fname, paper="A3"):
    SHEETS[key] = {"title": title, "file": fname, "parts": [], "notes": [], "paper": paper}
    return SHEETS[key]


_cur = None


def use(key):
    global _cur
    _cur = SHEETS[key]


def P(ref, sym, value, pins, **kw):
    p = Part(ref, sym, value, pins, **kw)
    p.sheet = _cur
    _cur["parts"].append(p)
    return p


def R(ref, value, a, b, fp="R0402", **kw):
    return P(ref, "R", value, {"1": a, "2": b}, fp=FP[fp], **kw)


def C(ref, value, a, b="GND", fp="C0402", **kw):
    return P(ref, "C", value, {"1": a, "2": b}, fp=FP[fp], **kw)


def NOTE(text):
    _cur["notes"].append(text)


NC = None  # pin tidak terhubung -> no_connect

# ============================================================================
# SHEET 1 : USB-C + TPS25750D (PD)
# ============================================================================
sheet("usb", "USB-C & PD controller (TPS25750D)", "usb_pd.kicad_sch")
use("usb")
P("J1", "USB_C_Receptacle_USB2.0_16P", "USB-C 16P", {
    "A4": "VBUS_C", "A9": "VBUS_C", "B4": "VBUS_C", "B9": "VBUS_C",
    "A5": "CC1", "B5": "CC2", "A6": NC, "B6": NC, "A7": NC, "B7": NC, "A8": NC, "B8": NC,
    "A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "SH": "GND"},
  fp=FP["USBC"], pos=(40.64, 76.2), note="Konektor 16P 5A/3A, cek rating VBUS dari datasheet konektor")
P("U1", "TPS25750D", "TPS25750DRJKR", {
    "23": "VBUS_C", "24": "VBUS_C", "25": "VBUS_C", "32": "VBUS_C", "33": "VBUS_C",
    "34": "PD_PP5V", "35": "PD_PP5V", "28": "CC1", "29": "CC2",
    "2": "PD_ADCIN1", "3": "PD_ADCIN2",
    "5": "GND", "6": "GND", "7": "GND", "19": "GND", "26": "GND", "27": "GND", "37": "GND", "36": "GND",
    "13": "GND",
    "20": "VBUS_SYS", "21": "VBUS_SYS", "22": "VBUS_SYS",
    "38": "+3V3", "1": "PD_LDO3V3", "4": "PD_LDO1V5",
    "8": "I2C_SDA", "9": "I2C_SCL", "10": "PD_IRQ_N",
    "16": "PD_I2CM_SDA", "17": "PD_I2CM_SCL", "18": "GND",
    "15": "PD_DRAIN", "30": "PD_DRAIN",
    "11": "GND", "12": "GND", "14": "GND", "31": "GND"},
  pos=(139.7, 76.2), mpn="TPS25750DRJKR")
P("U2", "24LC256", "24LC256", {"1": "GND", "2": "GND", "3": "GND", "7": "GND", "8": "PD_LDO3V3",
                                "5": "PD_I2CM_SDA", "6": "PD_I2CM_SCL", "4": "GND"},
  fp=FP["SOIC8"], pos=(241.3, 66.04), note="Alamat 0x50 (A0..A2=GND). Berisi config TPS25750 dari GUI TI")
P("D1", "D_TVS", "SMBJ24A", {"1": "VBUS_C", "2": "GND"}, fp=FP["SMB"], note="TVS VBUS, standoff 24V")
C("C1", "4.7u/35V", "VBUS_C", fp="C0805", note="CVBUS 1-10uF")
C("C2", "390p/50V", "CC1", note="CCCy 200-480pF")
C("C3", "390p/50V", "CC2")
for i in range(4):
    C(f"C{4 + i}", "10u/35V", "VBUS_SYS", fp="C0805", note="CPPHV 47-100uF total (juga Cin BQ25713 sebelum RAC)")
C("C8", "10u/10V", "PD_LDO3V3", fp="C0603", note="CLDO_3V3 5-25uF")
C("C9", "10u/6.3V", "PD_LDO1V5", fp="C0603", note="CLDO_1V5 4.5-12uF")
C("C10", "10u/10V", "+3V3", fp="C0603", note="CVIN_3V3 >=5uF")
C("C11", "100n", "PD_LDO3V3", note="Decoupling EEPROM")
R("R1", "0R", "PD_LDO3V3", "PD_ADCIN1", note="ADCIN1 = 7 (tie LDO_3V3)")
R("R2", "DNP", "PD_ADCIN1", "GND", dnp=True)
R("R3", "DNP", "PD_LDO3V3", "PD_ADCIN2", dnp=True)
R("R4", "0R", "PD_ADCIN2", "GND", note="ADCIN2 = 0 (tie GND) -> SafeMode, I2C addr index #1 (0x20)")
R("R5", "10k", "PD_LDO3V3", "PD_I2CM_SDA")
R("R6", "10k", "PD_LDO3V3", "PD_I2CM_SCL")
R("R7", "10k", "+3V3", "PD_IRQ_N")
R("R8", "0R", "PD_PP5V", "GND", fp="R0603", note="PP5V tidak dipakai (source lewat PPHV + OTG BQ25713). VERIFIKASI")
P("FLG1", "PWR_FLAG", "PWR_FLAG", {"1": "VBUS_C"})
P("FLG2", "PWR_FLAG", "PWR_FLAG", {"1": "VBUS_SYS"})
NOTE("USB-C & PD\n"
     "- TPS25750D: sink + source (DRP). VBUS_IN<->PPHV = switch 28V/7A dua arah.\n"
     "- PPHV (VBUS_SYS) = node input BQ25713. Saat OTG, BQ25713 mengeluarkan tegangan ke PPHV -> VBUS.\n"
     "- Config/patch dimuat dari EEPROM U2 (0x50) lewat I2Cm. MCU hanya di I2Cs (0x20), multi-master TIDAK didukung.\n"
     "- ADCIN1=7, ADCIN2=0 -> SafeMode (sink path tidak aktif sampai config termuat).\n"
     "- VERIFIKASI di Application Customization Tool TI: mode DRP dengan charger di PPHV,\n"
     "  dan apakah PP5V boleh di-GND-kan (R8) untuk konfigurasi ini.")

# ============================================================================
# SHEET 2 : Charger BQ25713
# ============================================================================
sheet("chg", "Charger buck-boost 1-4S (BQ25713) + DIP jumlah cell", "charger.kicad_sch", paper="A2")
use("chg")
P("U3", "BQ25713", "BQ25713RSNR", {
    "1": "CHG_VBUS_F", "3": "CHG_ACP", "2": "CHG_ACN", "6": "CHG_ILIM", "18": "CELL_BATPRESZ",
    "5": "OTG_EN", "12": "I2C_SDA", "13": "I2C_SCL", "4": "CHRG_OK", "11": "PROCHOT_N",
    "14": "GND", "15": NC, "8": "CHG_IADPT", "9": "CHG_IBAT", "10": "CHG_PSYS",
    "16": "CHG_COMP1", "17": "CHG_COMP2",
    "28": "CHG_REGN", "7": "CHG_VDDA", "31": "CHG_HIDRV1", "30": "CHG_BTST1", "32": "CHG_SW1",
    "29": "CHG_LODRV1", "24": "CHG_HIDRV2", "25": "CHG_BTST2", "23": "CHG_SW2", "26": "CHG_LODRV2",
    "22": "VSYS", "21": "CHG_BATDRV", "20": "CHG_SRP_F", "19": "CHG_SRN_F", "27": "GND", "33": "GND"},
  pos=(116.84, 170.18), mpn="BQ25713RSNR")
# input sense + filter
R("R10", "10m 1%", "VBUS_SYS", "CHG_VIN", fp="R1206", note="RAC input current sense")
R("R11", "1R", "VBUS_SYS", "CHG_VBUS_F", fp="R0603")
C("C20", "470n/35V", "CHG_VBUS_F", fp="C0603")
R("R12", "4.99R", "VBUS_SYS", "CHG_ACP")
C("C21", "33n", "CHG_ACP")
R("R13", "4.99R", "CHG_VIN", "CHG_ACN")
C("C22", "33n", "CHG_ACN")
C("C23", "10n/50V", "CHG_VIN", note="Maks 10nF+1nF setelah RAC")
C("C24", "1n/50V", "CHG_VIN")
# power stage
P("Q1", "Q_NMOS", "30V N-FET", {"1": "CHG_HIDRV1", "3": "CHG_VIN", "2": "CHG_SW1"},
  pos=(213.36, 76.2), note="Buck HS. Contoh: CSD17578Q3A / setara 30V <10mOhm")
P("Q2", "Q_NMOS", "30V N-FET", {"1": "CHG_LODRV1", "3": "CHG_SW1", "2": "GND"}, pos=(213.36, 111.76),
  note="Buck LS")
P("Q3", "Q_NMOS", "30V N-FET", {"1": "CHG_LODRV2", "3": "CHG_SW2", "2": "GND"}, pos=(271.78, 111.76),
  note="Boost LS")
P("Q4", "Q_NMOS", "30V N-FET", {"1": "CHG_HIDRV2", "3": "VSYS", "2": "CHG_SW2"}, pos=(271.78, 76.2),
  note="Boost HS")
P("L1", "L", "2.2u", {"1": "CHG_SW1", "2": "CHG_SW2"}, note="Isat >10A. Contoh: XAL7070-222 / setara")
C("C25", "47n/25V", "CHG_BTST1", "CHG_SW1")
C("C26", "47n/25V", "CHG_BTST2", "CHG_SW2")
C("C27", "3.3u/10V", "CHG_REGN", fp="C0603")
R("R14", "10R", "CHG_REGN", "CHG_VDDA")
C("C28", "1u/10V", "CHG_VDDA")
for i in range(7):
    C(f"C{30 + i}", "10u/25V", "VSYS", fp="C0805", note="Min 7x10uF dekat Q3/Q4")
C("C37", "22u/25V", "VSYS", fp="C1206")
C("C38", "22u/25V", "VSYS", fp="C1206")
# BATFET + charge sense
P("Q5", "Q_PMOS", "-30V P-FET", {"1": "CHG_BATDRV", "2": "VSYS", "3": "CHG_BATP"}, pos=(332.74, 76.2),
  note="BATFET P-ch. S=VSYS. Contoh: AONR21357 / setara -30V")
R("R15", "10m 1%", "CHG_BATP", "PACK_P", fp="R1206", note="RSR charge current sense")
R("R16", "10R", "CHG_BATP", "CHG_SRP_F")
R("R17", "10R", "PACK_P", "CHG_SRN_F")
C("C39", "100n", "CHG_SRP_F", "CHG_SRN_F")
C("C40", "100n", "CHG_SRN_F")
C("C41", "10u/25V", "PACK_P", fp="C0805", note=">=20uF setelah RSR")
C("C42", "10u/25V", "PACK_P", fp="C0805")
# setting pins
R("R18", "383k", "CHG_REGN", "CHG_ILIM", note="ILIM_HIZ ~2.19V -> IDPM ~3A (batas hardware)")
R("R19", "220k", "CHG_ILIM", "GND")
R("R20", "137k", "CHG_IADPT", "GND", note="137k untuk L=2.2uH")
C("C43", "100p", "CHG_IADPT")
C("C44", "100p", "CHG_IBAT")
R("R21", "30.1k", "CHG_PSYS", "GND")
R("R22", "40.2k", "CHG_COMP1", "CHG_COMP1_RC", note="Kompensasi: VERIFIKASI vs EVM BQ25713")
C("C45", "1800p", "CHG_COMP1_RC")
C("C46", "33p", "CHG_COMP1")
R("R23", "10k", "CHG_COMP2", "CHG_COMP2_RC")
C("C47", "680p", "CHG_COMP2_RC")
C("C48", "15p", "CHG_COMP2")
R("R24", "100k", "OTG_EN", "GND", note="Default OTG mati")
# DIP jumlah cell: SW1 pos 1-4 = pilih CELL_BATPRESZ (one-hot), pos 5-7 = short VC BQ40Z50
R("R25", "30k 1%", "CHG_VDDA", "CELLSEL_1S", note="25% VDDA -> 1S")
R("R26", "15k 1%", "CHG_VDDA", "CELLSEL_2S", note="40% -> 2S")
R("R27", "8.2k 1%", "CHG_VDDA", "CELLSEL_3S", note="55% -> 3S")
R("R28", "3.3k 1%", "CHG_VDDA", "CELLSEL_4S", note="75% -> 4S")
R("R29", "10k 1%", "CELL_BATPRESZ", "GND", note="Semua OFF -> 0% = baterai dianggap tidak ada (charge mati)")
P("SW1", "SW_DIP_x08", "CELL CONFIG", {
    "1": "CELLSEL_1S", "16": "CELL_BATPRESZ",
    "2": "CELLSEL_2S", "15": "CELL_BATPRESZ",
    "3": "CELLSEL_3S", "14": "CELL_BATPRESZ",
    "4": "CELLSEL_4S", "13": "CELL_BATPRESZ",
    "5": "BMS_VC4", "12": "BMS_VC3",
    "6": "BMS_VC3", "11": "BMS_VC2",
    "7": "BMS_VC2", "10": "BMS_VC1",
    "8": NC, "9": NC},
  fp=FP["DIP8"], pos=(381.0, 175.26))
R("R30", "100k", "CELL_BATPRESZ", "CELL_SENSE", note="Readback DIP ke ADC MCU")
R("R31", "100k", "CELL_SENSE", "GND")
C("C49", "10n", "CELL_SENSE")
P("FLG3", "PWR_FLAG", "PWR_FLAG", {"1": "VSYS"})
P("FLG4", "PWR_FLAG", "PWR_FLAG", {"1": "PACK_P"})
NOTE("CHARGER BQ25713 (NVDC)\n"
     "- VBUS_SYS -> RAC 10m -> buck-boost (Q1-Q4, L1) -> VSYS. BATFET Q5 (P-ch) VSYS <-> baterai.\n"
     "- Arus charge default = 0 A: baterai TIDAK diisi sampai MCU menulis ChargeCurrent via I2C (0x6B).\n"
     "- ILIM_HIZ membatasi arus input ~3A secara hardware.\n"
     "- CELL_BATPRESZ juga menentukan SYSOVP (1S=5V, 2S=12V, 3-4S=19.5V) -> harus SESUAI jumlah cell asli.\n\n"
     "SW1 CELL CONFIG (set saat baterai dilepas, dibaca saat boot):\n"
     "  Cell | pos1 pos2 pos3 pos4 | pos5 pos6 pos7\n"
     "  1S   |  ON  off  off  off  |  ON   ON   ON\n"
     "  2S   |  off  ON  off  off  |  ON   ON  off\n"
     "  3S   |  off off  ON   off  |  ON  off  off\n"
     "  4S   |  off off  off  ON   | off  off  off\n"
     "  pos1-4 HANYA satu yang ON. pos5-7 men-short pin VC BQ40Z50 yang tidak dipakai.\n"
     "  MCU mengecek: CELL_SENSE (ADC) vs register BQ25713 vs tegangan per-cell BQ40Z50. Tidak cocok -> FAULT.")

# ============================================================================
# SHEET 3 : Battery pack + BQ40Z50-R2
# ============================================================================
sheet("bms", "Baterai 1-4S + BMS (BQ40Z50-R2)", "battery_bms.kicad_sch")
use("bms")
P("U4", "BQ40Z50-R2", "BQ40Z50RSMR-R2", {
    "32": "BATT_P", "26": "BMS_FETMID", "27": "BMS_PACK", "1": "BMS_PBI",
    "2": "BMS_VC4", "3": "BMS_VC3", "4": "BMS_VC2", "5": "BMS_VC1",
    "8": "BMS_SRP", "6": "BMS_SRN",
    "10": "BMS_TS1", "11": "BMS_TS2", "12": "BATT_N", "13": "BATT_N",
    "31": "BMS_CHG", "28": "BMS_DSG", "30": NC, "25": "BATT_N",
    "18": "BMS_SMBD", "19": "BMS_SMBC", "15": "BATT_N", "16": "BATT_N", "17": "BATT_N",
    "20": NC, "21": NC, "22": NC, "23": "BATT_N", "24": "BATT_N",
    "7": NC, "14": NC, "29": NC, "9": "BATT_N", "33": "BATT_N"},
  pos=(149.86, 106.68), mpn="BQ40Z50RSMR-R2")
P("J2", "Conn_01x05", "BALANCE", {"1": "BATT_N", "2": "BAL_B1", "3": "BAL_B2", "4": "BAL_B3", "5": "BAL_B4"},
  fp=FP["XH5"], pos=(30.48, 60.96), note="1=B0(-) 2=B1 3=B2 4=B3 5=B4. Untuk <4S, pin atas boleh kosong")
P("J3", "Conn_01x02", "BATTERY", {"1": "BATT_P", "2": "BATT_N"}, fp=FP["TB2"], pos=(30.48, 101.6),
  note="Kabel daya utama pack. Gunakan XT30/XT60 untuk arus besar")
P("J4", "Conn_01x02", "NTC_CELL", {"1": "BMS_TS1", "2": "BATT_N"}, fp=FP["PH2"], pos=(30.48, 132.08),
  note="NTC 10k B3435 (103AT) ditempel ke cell")
P("TH1", "Thermistor_NTC", "10k B3435", {"1": "BMS_TS2", "2": "BATT_N"}, fp=FP["R0603"],
  note="NTC di PCB, dekat MOSFET daya/induktor")
for i, (b, v) in enumerate((("BAL_B4", "BMS_VC4"), ("BAL_B3", "BMS_VC3"), ("BAL_B2", "BMS_VC2"),
                            ("BAL_B1", "BMS_VC1"))):
    R(f"R{40 + i}", "100R", b, v)
C("C50", "100n/25V", "BMS_VC4", "BMS_VC3")
C("C51", "100n/25V", "BMS_VC3", "BMS_VC2")
C("C52", "100n/25V", "BMS_VC2", "BMS_VC1")
C("C53", "100n/25V", "BMS_VC1", "BATT_N")
C("C54", "2.2u/25V", "BMS_PBI", "BATT_N", fp="C0603")
C("C55", "100n/25V", "BATT_P", "BATT_N")
R("R44", "1m 1%", "BATT_N", "GND", fp="R2512", note="Sense coulomb counter (low side), 2512 >=2W, Kelvin!")
R("R45", "100R", "BATT_N", "BMS_SRP", note="SRP di sisi cell (1N)")
R("R46", "100R", "GND", "BMS_SRN")
C("C56", "100n", "BMS_SRP", "BMS_SRN")
# FET proteksi high-side (common drain)
P("Q6", "Q_NMOS", "CHG FET 30V", {"1": "BMS_CHG", "2": "BATT_P", "3": "BMS_FETMID"}, pos=(91.44, 45.72),
  note="Contoh: CSD17308Q3 (30V, 8.2mOhm)")
P("Q7", "Q_NMOS", "DSG FET 30V", {"1": "BMS_DSG", "2": "PACK_P", "3": "BMS_FETMID"}, pos=(129.54, 45.72),
  note="Contoh: CSD17308Q3")
R("R47", "10M", "BMS_CHG", "BATT_P", note="Gate-source pulldown")
R("R48", "10M", "BMS_DSG", "PACK_P")
R("R49", "2k", "PACK_P", "BMS_PACK", note="VERIFIKASI vs EVM BQ40Z50")
R("R50", "100R", "BMS_SMBD", "I2C_SDA")
R("R51", "100R", "BMS_SMBC", "I2C_SCL")
C("C57", "100n/50V", "PACK_P", "BMS_ESD_MID", note="2 kapasitor seri PACK+ ke PACK- (ESD)")
C("C58", "100n/50V", "BMS_ESD_MID", "GND")
P("FLG5", "PWR_FLAG", "PWR_FLAG", {"1": "BATT_P"})
P("FLG6", "PWR_FLAG", "PWR_FLAG", {"1": "BATT_N"})
NOTE("BMS BQ40Z50-R2\n"
     "- Proteksi high-side: Q6 (CHG) + Q7 (DSG) common-drain. PACK_P = sisi charger/sistem.\n"
     "- Sense 1mOhm low-side: BATT_N (cell -) -> R44 -> GND sistem. VSS IC = BATT_N (sisi SRP).\n"
     "- SMBus alamat 0x0B ke bus I2C MCU (100 kHz).\n"
     "- TS1 = NTC cell (J4), TS2 = NTC PCB (TH1), TS3/TS4 tidak dipakai -> set di data flash.\n"
     "- Pin VC yang tidak dipakai di-short oleh SW1 pos5-7 (sheet charger).\n"
     "- Konfigurasi awal 1S/2S: colok USB-C dulu supaya PACK ada tegangan (lihat datasheet 9.2.1).\n"
     "- VERIFIKASI vs BQ40Z50EVM: koneksi VCC (di sini ke node tengah FET) dan R49.")

# ============================================================================
# SHEET 4 : Output buck-boost TPS55289
# ============================================================================
sheet("out", "Output terminal 1-16V (TPS55289)", "output_buckboost.kicad_sch")
use("out")
P("U5", "TPS55289", "TPS55289RYQR", {
    "7": "VSYS", "1": "BB_EN", "3": "I2C_SCL", "4": "I2C_SDA", "2": "BB_VCC", "5": "GND", "6": "BB_FSW",
    "21": "BB_VCC", "18": "BB_VCC", "17": "GND", "9": "GND",
    "8": "BB_SW1", "20": "BB_BOOT1", "10": "BB_SW2", "19": "BB_BOOT2", "11": "BB_VOUT",
    "12": "BB_VOUT", "13": "VOUT_TERM", "14": "BB_INT_N", "15": "BB_COMP", "16": "BB_CDC"},
  pos=(116.84, 93.98), mpn="TPS55289RYQR")
for i in range(3):
    C(f"C{60 + i}", "10u/25V", "VSYS", fp="C0805", note="Cin >=20uF efektif")
C("C63", "100n/50V", "VSYS", note="Dekat pin VIN")
R("R60", "100k", "BB_EN", "GND", note="Default mati")
R("R61", "49.9k 1%", "BB_FSW", "GND", note="fsw ~400kHz")
C("C64", "10u/10V", "BB_VCC", fp="C0603", note=">4.7uF")
C("C65", "100n/25V", "BB_BOOT1", "BB_SW1")
C("C66", "100n/25V", "BB_BOOT2", "BB_SW2")
P("L2", "L", "4.7u", {"1": "BB_SW1", "2": "BB_SW2"}, note="Isat >12A. XAL7070-472ME (rekomendasi datasheet)")
for i in range(4):
    C(f"C{67 + i}", "22u/25V", "BB_VOUT", fp="C1206")
C("C71", "100n/50V", "BB_VOUT")
R("R62", "10m 1%", "BB_VOUT", "VOUT_TERM", fp="R1206", note="ISP-ISN, limit 50mV/10m=5A default")
C("C72", "22u/25V", "VOUT_TERM", fp="C1206")
C("C73", "100n/50V", "VOUT_TERM")
P("D2", "D_TVS", "SMBJ18A", {"1": "VOUT_TERM", "2": "GND"}, fp=FP["SMB"])
R("R63", "10k", "+3V3", "BB_INT_N")
R("R64", "10k", "BB_COMP", "BB_COMP_RC", note="Kompensasi: HITUNG ulang (datasheet pers. 24-26)")
C("C74", "22n", "BB_COMP_RC")
C("C75", "100p", "BB_COMP")
R("R65", "DNP", "BB_CDC", "GND", dnp=True, note="Kompensasi kabel (opsional)")
R("R66", "100k", "VOUT_TERM", "VOUT_SENSE", note="16V -> 1.45V ke ADC")
R("R67", "10k", "VOUT_SENSE", "GND")
C("C76", "10n", "VOUT_SENSE")
P("J5", "Conn_01x02", "OUTPUT 1-16V", {"1": "VOUT_TERM", "2": "GND"}, fp=FP["TB2"], pos=(325.12, 93.98))
NOTE("OUTPUT TPS55289 (I2C 0x74, MODE=VCC)\n"
     "- Feedback internal (I2C). FB/INT jadi output fault -> MCU.\n"
     "- Bit OE (reg 06h) default 0: output MATI sampai MCU set tegangan + OE.\n"
     "- Saat shutdown tidak ada jalur arus balik dari terminal ke VSYS.\n"
     "- Batas arus output lewat R62 + register 02h (firmware menurunkan sesuai jumlah cell).")

# ============================================================================
# SHEET 5 : MCU + UI + 3V3
# ============================================================================
sheet("mcu", "MCU STM32G031 + DIP output + LDO 3.3V", "mcu_ui.kicad_sch")
use("mcu")
P("U6", "STM32G031G8Ux", "STM32G031G8U6", {
    "3": "+3V3", "4": "GND", "5": "NRST",
    "6": "VSYS_SENSE", "7": "CELL_SENSE", "8": "UART_TX", "9": "UART_RX", "10": "VOUT_SENSE",
    "11": "BTN_APPLY", "12": "LED_STAT", "13": "LED_FAULT", "14": "CHRG_OK", "15": "PROCHOT_N",
    "16": "OTG_EN", "17": "BB_INT_N", "18": "PD_IRQ_N", "19": "LED_CHG", "20": "SWDIO", "21": "SWCLK",
    "22": "DIP_V3", "23": "DIP_V0", "24": "DIP_V1", "25": "DIP_V2", "26": "I2C_SCL", "27": "I2C_SDA",
    "28": NC, "1": "BB_EN", "2": NC},
  fp="Package_DFN_QFN:QFN-28_4x4mm_P0.5mm", pos=(132.08, 93.98), mpn="STM32G031G8U6")
C("C80", "100n", "+3V3")
C("C81", "4.7u/10V", "+3V3", fp="C0603")
C("C82", "100n", "NRST")
R("R80", "4.7k", "+3V3", "I2C_SCL", note="Pull-up bus I2C utama (100kHz)")
R("R81", "4.7k", "+3V3", "I2C_SDA")
R("R82", "10k", "+3V3", "CHRG_OK")
R("R83", "10k", "+3V3", "PROCHOT_N")
R("R84", "100k", "VSYS", "VSYS_SENSE", note="19.5V -> 2.54V")
R("R85", "15k", "VSYS_SENSE", "GND")
C("C83", "10n", "VSYS_SENSE")
for i, (net, col) in enumerate((("LED_STAT", "hijau"), ("LED_CHG", "biru"), ("LED_FAULT", "merah"))):
    R(f"R{86 + i}", "1k", net, f"{net}_A")
    P(f"D{3 + i}", "LED", col, {"2": f"{net}_A", "1": "GND"}, fp=FP["LED"])
P("SW2", "SW_DIP_x04", "VOUT SELECT", {
    "1": "DIP_V0", "8": "GND", "2": "DIP_V1", "7": "GND", "3": "DIP_V2", "6": "GND", "4": "DIP_V3", "5": "GND"},
  fp=FP["DIP4"], pos=(236.22, 60.96), note="Pull-up internal MCU. ON = 0")
P("SW3", "SW_Push", "APPLY", {"1": "BTN_APPLY", "2": "GND"}, fp=FP["BTN"])
C("C84", "100n", "BTN_APPLY")
P("U7", "NCP718xSN330", "NCP718BSN330T1G", {"1": "VSYS", "3": "VSYS", "5": "+3V3", "4": NC, "2": "GND"},
  fp=FP["SOT235"], pos=(236.22, 116.84), note="VSYS max 19.5V (SYSOVP) < 24V input maks")
C("C85", "1u/25V", "VSYS", fp="C0603")
C("C86", "1u/10V", "+3V3", fp="C0603")
P("J6", "Conn_01x05", "SWD", {"1": "+3V3", "2": "SWDIO", "3": "SWCLK", "4": "NRST", "5": "GND"},
  fp=FP["HDR5"], pos=(30.48, 60.96))
P("J7", "Conn_01x03", "UART", {"1": "UART_TX", "2": "UART_RX", "3": "GND"}, fp=FP["HDR3"],
  pos=(30.48, 99.06))
P("FLG7", "PWR_FLAG", "PWR_FLAG", {"1": "GND"})
NOTE("MCU STM32G031G8U6\n"
     "- I2C1 (PB6/PB7) 100kHz: BQ25713 0x6B, BQ40Z50 0x0B, TPS55289 0x74, TPS25750 0x20.\n"
     "- SW2 VOUT SELECT 4 bit (DIP_V0..V3, aktif-low) -> tabel 16 preset di firmware.\n"
     "- SW3 APPLY: tegangan baru diterapkan hanya setelah tombol ditekan.\n"
     "- Pin 18/19 dipakai sebagai PA9/PA10 (default, tanpa remap).\n"
     "- PC15, PB8 cadangan.")

# ----------------------------------------------------------------------------
# validasi netlist
# ----------------------------------------------------------------------------


def validate():
    errs = []
    refs = set()
    netsheets = defaultdict(set)
    netconn = defaultdict(list)
    for sk, sh in SHEETS.items():
        for p in sh["parts"]:
            if p.ref in refs:
                errs.append(f"ref ganda {p.ref}")
            refs.add(p.ref)
            sym = SYMS[p.sym]
            symnums = {pin.num for pin in sym.pins}
            for n in p.pins:
                if n not in symnums:
                    errs.append(f"{p.ref}: pin {n} tidak ada di simbol {p.sym}")
            for n in symnums:
                if n not in p.pins:
                    errs.append(f"{p.ref}: pin {n} ({p.sym}) belum diberi net")
            for n, net in p.pins.items():
                if net:
                    netsheets[net].add(sk)
                    netconn[net].append(f"{p.ref}.{n}")
    for net, c in netconn.items():
        if len(c) < 2:
            errs.append(f"net {net} hanya 1 koneksi: {c}")
    return errs, netsheets, netconn


# ----------------------------------------------------------------------------
# penulisan schematic
# ----------------------------------------------------------------------------
ROOT_UUID = uid("root")
PAPER = {"A4": (297, 210), "A3": (420, 297), "A2": (594, 420)}
POWER_SYMS = {"GND", "+3V3"}


def outward(ang):
    # lib angle -> arah luar di koordinat schematic (y ke bawah)
    return {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[ang]


def label_angle(d):
    return {(-1, 0): 180, (1, 0): 0, (0, -1): 90, (0, 1): 270}[d]


def write_sheet(sk, sh, sheet_uuid, global_nets, title_comment=""):
    W, H = PAPER[sh["paper"]]
    items = []
    pwr_count = [0]
    path = f"/{ROOT_UUID}/{sheet_uuid}"
    used_syms = set()

    # --- penempatan otomatis untuk part tanpa pos (grid pasif) -------------
    placed = [p for p in sh["parts"] if p.pos]
    auto = [p for p in sh["parts"] if not p.pos]
    # area grid: di bawah IC
    maxy = max([p.pos[1] for p in placed] + [40])
    x0, pitch_x = 30.48, 12.7
    cols = int((W - x0 - 140) // pitch_x)  # sisakan ruang title block
    row_h = 60.96
    y0 = H - 25.4 - 30.48 - ((len(auto) - 1) // cols) * row_h
    # pastikan grid tidak menabrak IC: kalau tabrakan, pakai mulai di bawah IC
    y_ic_bottom = 0
    for p in placed:
        s = SYMS[p.sym]
        ymin = min(pin.y for pin in s.pins) if s.pins else 0
        y_ic_bottom = max(y_ic_bottom, p.pos[1] - ymin + 8)
    y0 = max(y0, y_ic_bottom + 30.48)
    for i, p in enumerate(auto):
        c, r = i % cols, i // cols
        p.pos = (x0 + c * pitch_x, y0 + r * row_h)
    need_h = max(p.pos[1] for p in sh["parts"]) + 40
    if need_h > H:
        raise SystemExit(f"Sheet {sk}: tidak muat di {sh['paper']} (butuh {need_h:.0f} mm)")

    for p in sh["parts"]:
        s = SYMS[p.sym]
        used_syms.add(p.sym)
        X, Y = p.pos
        X, Y = round(X / 1.27) * 1.27, round(Y / 1.27) * 1.27
        su = uid(sk, p.ref)
        two = len(s.pins) == 2 and p.sym not in ("Conn_01x02",)
        if s.power or p.sym == "PWR_FLAG":
            two = False
        props = []
        if two:
            props.append(("Reference", p.ref, X + 2.54, Y - 1.27, 0, "left", False))
            props.append(("Value", p.value, X + 2.54, Y + 1.27, 0, "left", False))
        else:
            rx, ry, _ = s.ref_at
            vx, vy, _ = s.val_at
            props.append(("Reference", p.ref, X + rx, Y - ry, 0, "left", False))
            props.append(("Value", p.value, X + vx, Y - vy, 0, "left", False))
        props.append(("Footprint", p.fp or s.footprint, X, Y, 0, None, True))
        props.append(("Datasheet", s.datasheet, X, Y, 0, None, True))
        if p.mpn:
            props.append(("MPN", p.mpn, X, Y, 0, None, True))
        if p.note:
            props.append(("Catatan", p.note, X, Y, 0, None, True))
        ptxt = []
        for (k, v, px, py, pa, just, hide) in props:
            eff = "(effects (font (size 1.27 1.27))"
            if just:
                eff += f" (justify {just})"
            if hide:
                eff += " hide"
            eff += ")"
            ptxt.append(f"    (property {q(k)} {q(v)} (at {g(px)} {g(py)} {pa}) {eff})")
        pins_txt = "\n".join(f"    (pin {q(pin.num)} (uuid {q(uid(sk, p.ref, 'pin', pin.num))}))" for pin in s.pins)
        dnp = "yes" if p.dnp else "no"
        bom = "no" if p.sym == "PWR_FLAG" else "yes"
        ref_inst = p.ref if p.sym != "PWR_FLAG" else "#" + p.ref
        if p.sym == "PWR_FLAG":
            ptxt[0] = ptxt[0].replace(q(p.ref), q("#" + p.ref)).replace("(justify left))", "(justify left) hide)")
        items.append(
            f"  (symbol (lib_id {q(LIB + ':' + p.sym)}) (at {g(X)} {g(Y)} 0) (unit 1)\n"
            f"    (in_bom {bom}) (on_board {bom}) (dnp {dnp})\n"
            f"    (uuid {q(su)})\n" + "\n".join(ptxt) + "\n" + pins_txt + "\n"
            f"    (instances (project {q(PROJECT)} (path {q('/' + ROOT_UUID + '/' + sheet_uuid)} "
            f"(reference {q(ref_inst)}) (unit 1))))\n  )")

        # koneksi tiap pin: stub + label / simbol power / no_connect
        done_pts = set()
        for pin in s.pins:
            net = p.pins.get(pin.num)
            px, py = X + pin.x, Y - pin.y
            key = (round(px, 2), round(py, 2))
            if key in done_pts:
                continue  # pin bertumpuk (stacked)
            done_pts.add(key)
            if net is None:
                items.append(f"  (no_connect (at {g(px)} {g(py)}) (uuid {q(uid(sk, p.ref, 'nc', pin.num))}))")
                continue
            if p.sym == "PWR_FLAG" or s.power:
                # langsung label di pin flag (dengan stub ke bawah)
                d = (0, 1)
            else:
                d = outward(pin.ang)
            sl = 2.54
            ex, ey = px + d[0] * sl, py + d[1] * sl
            items.append(f"  (wire (pts (xy {g(px)} {g(py)}) (xy {g(ex)} {g(ey)})) "
                         f"(stroke (width 0) (type default)) (uuid {q(uid(sk, p.ref, 'w', pin.num))}))")
            if net in POWER_SYMS:
                pwr_count[0] += 1
                pref = f"#PWR{sk.upper()}{pwr_count[0]:03d}"
                if net == "GND":
                    rot = {(0, 1): 0, (1, 0): 90, (-1, 0): 270, (0, -1): 180}[d]
                else:
                    rot = {(0, -1): 0, (0, 1): 180, (-1, 0): 90, (1, 0): 270}[d]
                used_syms.add(net)
                pu = uid(sk, p.ref, "pwr", pin.num)
                vy = 5.08 if net == "GND" else -5.08
                vxo, vyo = (0, vy) if rot in (0, 180) else (0, 0)
                items.append(
                    f"  (symbol (lib_id {q(LIB + ':' + net)}) (at {g(ex)} {g(ey)} {rot}) (unit 1)\n"
                    f"    (in_bom yes) (on_board yes) (dnp no)\n    (uuid {q(pu)})\n"
                    f"    (property \"Reference\" {q(pref)} (at {g(ex)} {g(ey)} 0) {FONT_H})\n"
                    f"    (property \"Value\" {q(net)} (at {g(ex + vxo)} {g(ey + vyo)} 0) {FONT_H})\n"
                    f"    (property \"Footprint\" \"\" (at {g(ex)} {g(ey)} 0) {FONT_H})\n"
                    f"    (property \"Datasheet\" \"\" (at {g(ex)} {g(ey)} 0) {FONT_H})\n"
                    f"    (pin \"1\" (uuid {q(uid(pu, 'p'))}))\n"
                    f"    (instances (project {q(PROJECT)} (path {q(path)} (reference {q(pref)}) (unit 1))))\n  )")
            else:
                la = label_angle(d)
                lu = uid(sk, p.ref, "lbl", pin.num)
                if net in global_nets:
                    just = "left" if la in (0, 90) else "right"
                    items.append(
                        f"  (global_label {q(net)} (shape bidirectional) (at {g(ex)} {g(ey)} {la}) (fields_autoplaced)\n"
                        f"    (effects (font (size 1.27 1.27)) (justify {just}))\n    (uuid {q(lu)})\n"
                        f"    (property \"Intersheetrefs\" \"${{INTERSHEET_REFS}}\" (at {g(ex)} {g(ey)} 0) {FONT_H})\n  )")
                else:
                    just = "left bottom" if la in (0, 90) else "right bottom"
                    items.append(
                        f"  (label {q(net)} (at {g(ex)} {g(ey)} {la}) (fields_autoplaced)\n"
                        f"    (effects (font (size 1.27 1.27)) (justify {just}))\n    (uuid {q(lu)})\n  )")

    # catatan
    for i, t in enumerate(sh["notes"]):
        items.append(f"  (text {q(t)} (at {g(W - 190)} {g(22.86 + i * 60)} 0)\n"
                     f"    (effects (font (size 1.524 1.524)) (justify left top))\n"
                     f"    (uuid {q(uid(sk, 'note', i))})\n  )")

    libsyms = "\n".join("    " + SYMS[n].body(LIB + ":").replace("\n", "\n    ") for n in sorted(used_syms))
    tb = (f"  (title_block\n    (title {q(sh['title'])})\n    (date \"2026-11-24\")\n    (rev \"0.1\")\n"
          f"    (company \"BMS 1-4S USB-C PD\")\n    (comment 1 \"Draft - cek daftar VERIFIKASI di README sebelum layout\")\n  )")
    txt = (f"(kicad_sch (version 20230121) (generator eeschema)\n\n  (uuid {q(sheet_uuid)})\n\n"
           f"  (paper {q(sh['paper'])})\n\n{tb}\n\n  (lib_symbols\n{libsyms}\n  )\n\n" + "\n".join(items) + "\n)\n")
    with open(os.path.join(OUT_DIR, sh["file"]), "w") as f:
        f.write(txt)


def write_root(sheet_uuids):
    items = []
    x, y = 30.48, 40.64
    for i, (sk, sh) in enumerate(SHEETS.items()):
        su = sheet_uuids[sk]
        sx, sy = x + (i % 3) * 120.65, y + (i // 3) * 63.5
        items.append(
            f"  (sheet (at {g(sx)} {g(sy)}) (size 101.6 38.1) (fields_autoplaced)\n"
            f"    (stroke (width 0.1524) (type solid))\n    (fill (color 0 0 0 0.0000))\n"
            f"    (uuid {q(su)})\n"
            f"    (property \"Sheetname\" {q(sh['title'])} (at {g(sx)} {g(sy - 0.71)} 0)\n"
            f"      (effects (font (size 1.27 1.27)) (justify left bottom)))\n"
            f"    (property \"Sheetfile\" {q(sh['file'])} (at {g(sx)} {g(sy + 38.1 + 0.59)} 0)\n"
            f"      (effects (font (size 1.27 1.27)) (justify left top)))\n"
            f"    (instances (project {q(PROJECT)} (path {q('/' + ROOT_UUID)} (page {q(str(i + 2))}))))\n  )")
    blk = ("BMS 1-4S Li-ion + USB-C PD (DRP) + output terminal 1-16V\n\n"
           "Alur daya:\n"
           "  USB-C -> TPS25750D (PD) -> VBUS_SYS -> BQ25713 (buck-boost) -> VSYS\n"
           "  VSYS <-> BATFET <-> PACK_P <-> BQ40Z50 (FET proteksi) <-> cell 1-4S\n"
           "  VSYS -> TPS55289 -> terminal 1-16V (DIP 4 bit + tombol APPLY)\n"
           "  VSYS -> NCP718 -> +3V3 (MCU STM32G031, TPS25750)\n"
           "  OTG: BQ25713 -> VBUS_SYS -> TPS25750 -> USB-C (PD source)\n\n"
           "Bus I2C MCU: BQ25713 0x6B | BQ40Z50 0x0B | TPS55289 0x74 | TPS25750 0x20\n"
           "Bus I2C TPS25750 (terpisah): EEPROM 24LC256 0x50\n\n"
           "Status: DRAFT v0.1 - lihat README.md bagian VERIFIKASI sebelum layout PCB.")
    items.append(f"  (text {q(blk)} (at 30.48 182.88 0)\n    (effects (font (size 2 2)) (justify left top))\n"
                 f"    (uuid {q(uid('root', 'note'))})\n  )")
    tb = ("  (title_block\n    (title \"BMS 1-4S + USB-C PD + Output 1-16V\")\n    (date \"2026-11-24\")\n"
          "    (rev \"0.1\")\n    (company \"BMS 1-4S USB-C PD\")\n"
          "    (comment 1 \"Dibuat oleh tools/gen_schematic.py - edit generator, lalu generate ulang\")\n  )")
    txt = (f"(kicad_sch (version 20230121) (generator eeschema)\n\n  (uuid {q(ROOT_UUID)})\n\n"
           f"  (paper \"A3\")\n\n{tb}\n\n  (lib_symbols\n  )\n\n" + "\n".join(items) +
           "\n\n  (sheet_instances\n    (path \"/\" (page \"1\"))\n  )\n)\n")
    with open(os.path.join(OUT_DIR, PROJECT + ".kicad_sch"), "w") as f:
        f.write(txt)


def write_lib():
    body = "\n".join("  " + s.body().replace("\n", "\n  ") for s in SYMS.values())
    with open(os.path.join(OUT_DIR, PROJECT + ".kicad_sym"), "w") as f:
        f.write(f"(kicad_symbol_lib (version 20220914) (generator kicad_symbol_editor)\n{body}\n)\n")
    with open(os.path.join(OUT_DIR, "sym-lib-table"), "w") as f:
        f.write('(sym_lib_table\n  (version 7)\n  (lib (name "bms")(type "KiCad")(uri "${KIPRJMOD}/bms.kicad_sym")'
                '(options "")(descr "Simbol proyek BMS 1-4S"))\n)\n')


def write_pro():
    import json
    pro = {
        "board": {"design_settings": {}},
        "boards": [],
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "meta": {"filename": PROJECT + ".kicad_pro", "version": 1},
        "net_settings": {"classes": [{"name": "Default", "clearance": 0.2, "track_width": 0.25,
                                      "via_diameter": 0.8, "via_drill": 0.4, "wire_width": 6,
                                      "bus_width": 12, "line_style": 0, "schematic_color": "rgba(0, 0, 0, 0.000)",
                                      "pcb_color": "rgba(0, 0, 0, 0.000)", "diff_pair_gap": 0.25,
                                      "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2,
                                      "microvia_diameter": 0.3, "microvia_drill": 0.1}],
                         "meta": {"version": 3}},
        "pcbnew": {"last_paths": {}, "page_layout_descr_file": ""},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": [[ROOT_UUID, ""]] + [[uid("sheet", k), v["title"]] for k, v in SHEETS.items()],
        "text_variables": {},
    }
    with open(os.path.join(OUT_DIR, PROJECT + ".kicad_pro"), "w") as f:
        json.dump(pro, f, indent=2)
        f.write("\n")


def write_netlist_report(netconn, netsheets):
    lines = ["# Netlist (dihasilkan otomatis oleh gen_schematic.py)", "",
             "| Net | Sheet | Koneksi |", "|---|---|---|"]
    for net in sorted(netconn):
        lines.append(f"| `{net}` | {', '.join(sorted(netsheets[net]))} | {' '.join(sorted(netconn[net]))} |")
    with open(os.path.join(OUT_DIR, "..", "docs", "netlist.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


def write_bom():
    rows = defaultdict(list)
    for sk, sh in SHEETS.items():
        for p in sh["parts"]:
            if p.sym == "PWR_FLAG":
                continue
            key = (p.sym, p.value, p.fp or SYMS[p.sym].footprint, p.dnp)
            rows[key].append(p.ref)
    import re

    def nat(r):
        m = re.match(r"([A-Z]+)(\d+)", r)
        return (m.group(1), int(m.group(2))) if m else (r, 0)
    out = ["Jumlah,Referensi,Value,Simbol,Footprint,DNP"]
    for (sym, val, fp, dnp), refs in sorted(rows.items(), key=lambda kv: nat(sorted(kv[1], key=nat)[0])):
        refs = sorted(refs, key=nat)
        out.append(f"{len(refs)},\"{' '.join(refs)}\",\"{val}\",{sym},\"{fp}\",{'DNP' if dnp else ''}")
    with open(os.path.join(OUT_DIR, "..", "docs", "bom.csv"), "w") as f:
        f.write("\n".join(out) + "\n")


def main():
    errs, netsheets, netconn = validate()
    if errs:
        print("VALIDASI GAGAL:")
        for e in errs:
            print("  -", e)
        raise SystemExit(1)
    os.makedirs(OUT_DIR, exist_ok=True)
    global_nets = {n for n, s in netsheets.items() if len(s) > 1}
    sheet_uuids = {k: uid("sheet", k) for k in SHEETS}
    for k, sh in SHEETS.items():
        write_sheet(k, sh, sheet_uuids[k], global_nets)
    write_root(sheet_uuids)
    write_lib()
    write_pro()
    write_netlist_report(netconn, netsheets)
    write_bom()
    nparts = sum(len([p for p in s["parts"] if p.sym != "PWR_FLAG"]) for s in SHEETS.values())
    print(f"OK: {len(SHEETS)} sheet, {nparts} komponen, {len(netconn)} net "
          f"({len(global_nets)} lintas sheet)")


if __name__ == "__main__":
    main()
