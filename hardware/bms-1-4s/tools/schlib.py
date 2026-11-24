"""
Mesin kecil untuk menulis skematik KiCad 7 (format 20230121) dari Python.

Isi:
  * definisi simbol (pasif, MOSFET, konektor, DIP, IC kustom, simbol power)
  * kelas Sheet: menaruh komponen, menggambar wire, label, simbol power,
    hierarchical label, kotak blok, teks; junction ditambahkan otomatis
  * penulis file .kicad_sch / .kicad_sym

Koordinat yang dipakai di Sheet adalah koordinat layar KiCad (mm, sumbu Y ke
bawah). Semua titik sebaiknya kelipatan 1.27 mm (grid 50 mil).
"""
import uuid as _uuid
from collections import OrderedDict, defaultdict

G = 2.54
_NS = _uuid.UUID("6f1c2a52-6a0b-4b8e-9d3f-2b5b1a9c0e11")


def uid(*parts):
    return str(_uuid.uuid5(_NS, "/".join(str(p) for p in parts)))


def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def g(v):
    v = round(v * 100) / 100.0
    s = ("%.2f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def snap(v, step=1.27):
    return round(v / step) * step


FONT = "(effects (font (size 1.27 1.27)))"
FONT_H = "(effects (font (size 1.27 1.27)) hide)"


# ============================================================================
# Simbol
# ============================================================================
class Pin:
    def __init__(self, num, name, etype, x, y, ang, length=G, hidden=False):
        self.num, self.name, self.etype = num, name, etype
        self.x, self.y, self.ang, self.length, self.hidden = x, y, ang, length, hidden


class Sym:
    def __init__(self, name, ref, pins, graphics, desc="", power=False, hide_pin_numbers=False,
                 hide_pin_names=False, pin_name_offset=1.016, datasheet="~", footprint="", kind="ic"):
        self.name, self.ref, self.pins, self.graphics = name, ref, pins, graphics
        self.desc, self.power, self.kind = desc, power, kind
        self.hide_pin_numbers, self.hide_pin_names = hide_pin_numbers, hide_pin_names
        self.pin_name_offset = pin_name_offset
        self.datasheet, self.footprint = datasheet, footprint
        self.box = None  # (x1, y1, x2, y2) koordinat lib, untuk IC

    def pin(self, num):
        for p in self.pins:
            if p.num == num:
                return p
        raise KeyError(f"{self.name}: pin {num}")

    def body(self, prefix=""):
        out = [f"(symbol {q(prefix + self.name)}"]
        if self.power:
            out.append(" (power)")
        if self.hide_pin_numbers:
            out.append(" (pin_numbers hide)")
        out.append(f" (pin_names (offset {g(self.pin_name_offset)})" + (" hide)" if self.hide_pin_names else ")"))
        out.append(" (in_bom yes) (on_board yes)\n")
        out.append(f"  (property \"Reference\" {q(self.ref)} (at 0 0 0) {FONT_H if self.power else FONT})\n")
        out.append(f"  (property \"Value\" {q(self.name)} (at 0 0 0) {FONT})\n")
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
        out.append("  )\n)")
        return "".join(out)


def rect(x1, y1, x2, y2, fill="background", w=0.254):
    return (f"(rectangle (start {g(x1)} {g(y1)}) (end {g(x2)} {g(y2)}) "
            f"(stroke (width {g(w)}) (type default)) (fill (type {fill})))")


def poly(pts, w=0.254, fill="none"):
    p = " ".join(f"(xy {g(x)} {g(y)})" for x, y in pts)
    return f"(polyline (pts {p}) (stroke (width {g(w)}) (type default)) (fill (type {fill})))"


def circle(x, y, r, w=0.254, fill="none"):
    return (f"(circle (center {g(x)} {g(y)}) (radius {g(r)}) (stroke (width {g(w)}) (type default)) "
            f"(fill (type {fill})))")


SYMS = OrderedDict()


def add(s):
    SYMS[s.name] = s
    return s


def ic_symbol(name, ref, left, right, desc="", datasheet="~", footprint="", min_w=None, top=None, bottom=None):
    """
    left/right: daftar (nama, [nomor...], tipe) atau None (baris kosong), urut dari atas.
    Nomor pertama tampil, sisanya pin tersembunyi bertumpuk di titik yang sama.
    """
    nrows = max(len(left), len(right))
    maxl = max([len(e[0]) for e in left if e] + [1])
    maxr = max([len(e[0]) for e in right if e] + [1])
    w = (maxl + maxr) * 1.27 + 4 * G
    if min_w:
        w = max(w, min_w)
    w = round(w / (2 * G) + 0.4999) * (2 * G)
    h = (nrows + 1) * G
    ytop = round((h / 2) / G) * G
    pins = []
    for side, lst in (("L", left), ("R", right)):
        for i, e in enumerate(lst):
            if not e:
                continue
            pname, nums, et = e
            y = ytop - (i + 1) * G
            x, ang = (-w / 2 - G, 0) if side == "L" else (w / 2 + G, 180)
            for k, n in enumerate(nums):
                pins.append(Pin(n, pname, et, x, y, ang, G, hidden=(k > 0)))
    ybot = ytop - (nrows + 1) * G
    s = Sym(name, ref, pins, [rect(-w / 2, ytop, w / 2, ybot)], desc=desc, datasheet=datasheet,
            footprint=footprint, kind="ic")
    s.box = (-w / 2, ytop, w / 2, ybot)
    return s


def two_pin(name, ref, graphics, names=("~", "~"), desc="", kind="2pin"):
    p = [Pin("1", names[0], "passive", 0, 3.81, 270, 1.27), Pin("2", names[1], "passive", 0, -3.81, 90, 1.27)]
    return Sym(name, ref, p, graphics, desc=desc, hide_pin_numbers=True, hide_pin_names=True,
               pin_name_offset=0, kind=kind)


# --- pasif -----------------------------------------------------------------
add(two_pin("R", "R", [rect(-1.016, 2.54, 1.016, -2.54, fill="none")], desc="Resistor"))
add(two_pin("C", "C", [poly([(-2.032, 0.762), (2.032, 0.762)], 0.508),
                       poly([(-2.032, -0.762), (2.032, -0.762)], 0.508),
                       poly([(0, 2.54), (0, 0.762)]), poly([(0, -2.54), (0, -0.762)])], desc="Kapasitor"))
add(two_pin("L", "L", [
    "(arc (start 0 2.54) (mid 0.6323 1.905) (end 0 1.27) (stroke (width 0) (type default)) (fill (type none)))",
    "(arc (start 0 1.27) (mid 0.6323 0.635) (end 0 0) (stroke (width 0) (type default)) (fill (type none)))",
    "(arc (start 0 0) (mid 0.6323 -0.635) (end 0 -1.27) (stroke (width 0) (type default)) (fill (type none)))",
    "(arc (start 0 -1.27) (mid 0.6323 -1.905) (end 0 -2.54) (stroke (width 0) (type default)) (fill (type none)))"],
    desc="Induktor"))
add(two_pin("Thermistor_NTC", "TH", [rect(-1.016, 2.54, 1.016, -2.54, fill="none"),
                                     poly([(-1.905, -2.54), (-1.905, -1.905), (1.905, 1.905), (1.905, 2.54)], 0)],
            desc="Thermistor NTC"))
# Dioda/LED: pin 1 = K (atas), pin 2 = A (bawah) -> panah menunjuk ke atas
_tri = poly([(0, 1.27), (-1.27, -1.27), (1.27, -1.27), (0, 1.27)], 0.254)
add(two_pin("D_TVS", "D", [poly([(-1.27, 1.27), (1.27, 1.27)], 0.254), poly([(-1.27, 1.27), (-1.778, 1.778)], 0.254),
                           poly([(1.27, 1.27), (1.778, 0.762)], 0.254), _tri,
                           poly([(0, 2.54), (0, 1.27)]), poly([(0, -2.54), (0, -1.27)])],
            names=("K", "A"), desc="TVS unidirectional (1=K, 2=A)"))
add(two_pin("LED", "D", [poly([(-1.27, 1.27), (1.27, 1.27)], 0.254), _tri,
                         poly([(0, 2.54), (0, 1.27)]), poly([(0, -2.54), (0, -1.27)]),
                         poly([(1.778, 0.508), (2.794, 1.524)]), poly([(1.778, -0.508), (2.794, 0.508)])],
            names=("K", "A"), desc="LED (1=K, 2=A)"))
add(two_pin("SW_Push", "SW", [circle(0, 2.032, 0.508), circle(0, -2.032, 0.508),
                              poly([(-1.27, 1.524), (-1.27, -1.524)], 0.254), poly([(-1.778, 0), (-2.54, 0)], 0.254)],
            desc="Push button"))


def fet(name, pch=False):
    arrow = [(0.254, 0), (1.27, 0.508), (1.27, -0.508), (0.254, 0)] if not pch else \
            [(1.524, 0), (0.508, 0.508), (0.508, -0.508), (1.524, 0)]
    gr = [poly([(-0.254, 1.905), (-0.254, -1.905)], 0.254), poly([(0.254, 2.286), (0.254, 1.27)], 0.254),
          poly([(0.254, 0.508), (0.254, -0.508)], 0.254), poly([(0.254, -1.27), (0.254, -2.286)], 0.254),
          poly([(0.254, 1.778), (2.54, 1.778), (2.54, 2.54)]), poly([(0.254, -1.778), (2.54, -1.778), (2.54, -2.54)]),
          poly([(0.254, 0), (2.54, 0), (2.54, -1.778)]), poly(arrow, 0, "outline"), poly([(-2.54, 0), (-0.254, 0)]),
          circle(1.27, 0, 2.794, 0.254)]
    p = [Pin("1", "G", "input", -5.08, 0, 0, 2.54), Pin("2", "S", "passive", 2.54, -5.08, 90, 2.54),
         Pin("3", "D", "passive", 2.54, 5.08, 270, 2.54)]
    return Sym(name, "Q", p, gr, desc=("P" if pch else "N") + "-channel MOSFET (1=G, 2=S, 3=D)",
               hide_pin_names=True, pin_name_offset=0, kind="fet")


add(fet("Q_NMOS"))
add(fet("Q_PMOS", pch=True))


def conn(name, n):
    """Konektor: pin di kiri (connection point x=-5.08), pin 1 paling atas."""
    top = snap((n - 1) * G / 2, G)
    pins = [Pin(str(i + 1), f"Pin_{i + 1}", "passive", -5.08, top - i * G, 0, 3.81) for i in range(n)]
    s = Sym(name, "J", pins, [rect(-1.27, top + 1.27, 1.27, top - (n - 1) * G - 1.27)], desc=f"Konektor 1x{n:02d}",
            hide_pin_names=True, kind="conn")
    s.box = (-1.27, top + 1.27, 1.27, top - (n - 1) * G - 1.27)
    return s


for _n in (2, 3, 5):
    add(conn(f"Conn_01x{_n:02d}", _n))


def dip(name, n):
    """Saklar k: pin kiri = k, pin kanan = 2n+1-k (sesuai footprint DIP KiCad)."""
    top = snap((n - 1) * G / 2, G)
    pins, gr = [], [rect(-3.81, top + 1.905, 3.81, top - (n - 1) * G - 1.905)]
    for k in range(1, n + 1):
        y = top - (k - 1) * G
        pins.append(Pin(str(k), "~", "passive", -7.62, y, 0, 3.81))
        pins.append(Pin(str(2 * n + 1 - k), "~", "passive", 7.62, y, 180, 3.81))
        gr += [circle(-2.032, y, 0.508), circle(2.032, y, 0.508), poly([(-1.524, y + 0.127), (2.032, y + 1.016)], 0)]
    s = Sym(name, "SW", pins, gr, desc=f"DIP switch {n} posisi", hide_pin_names=True, kind="dip")
    s.box = (-3.81, top + 1.905, 3.81, top - (n - 1) * G - 1.905)
    return s


add(dip("SW_DIP_x04", 4))


def power_sym(name, style):
    """style 'rail' (panah/bar ke atas) atau 'gnd' (segitiga ke bawah)."""
    if style == "gnd":
        gr = [poly([(0, 0), (0, -1.27), (1.27, -1.27), (0, -2.54), (-1.27, -1.27), (0, -1.27)])]
        ang = 270
    elif style == "gnd2":  # ground domain lain (garis bertingkat)
        gr = [poly([(0, 0), (0, -1.27)]), poly([(-1.524, -1.27), (1.524, -1.27)]),
              poly([(-1.016, -1.778), (1.016, -1.778)]), poly([(-0.508, -2.286), (0.508, -2.286)])]
        ang = 270
    else:
        gr = [poly([(0, 0), (0, 1.27)]), poly([(-1.27, 1.27), (1.27, 1.27)], 0.254)]
        ang = 90
    return Sym(name, "#PWR", [Pin("1", name, "power_in", 0, 0, ang, 0, hidden=True)], gr, power=True,
               desc=f"Net power global {name}", hide_pin_numbers=True, pin_name_offset=0, kind="power_" + style)


for _n, _s in (("GND", "gnd"), ("BATT-", "gnd2"), ("+3V3", "rail"), ("VSYS", "rail"), ("VBUS_SYS", "rail"),
               ("PACK+", "rail"), ("BATT+", "rail")):
    add(power_sym(_n, _s))
add(Sym("PWR_FLAG", "#FLG", [Pin("1", "pwr", "power_out", 0, 0, 90, 0)],
        [poly([(0, 0), (0, 1.27), (-1.016, 1.905), (0, 2.54), (1.016, 1.905), (0, 1.27)])],
        power=True, desc="Penanda sumber daya untuk ERC", hide_pin_numbers=True, hide_pin_names=True,
        pin_name_offset=0, kind="flag"))


# ============================================================================
# Part & Sheet
# ============================================================================
ROT = {0: lambda x, y: (x, y), 90: lambda x, y: (y, -x), 180: lambda x, y: (-x, -y), 270: lambda x, y: (-y, x)}


class Part:
    def __init__(self, sheet, ref, sym, value, x, y, rot, mirror, pins, fp, dnp, note, mpn, ref_at, val_at,
                 hide_value):
        self.sheet, self.ref, self.sym, self.value = sheet, ref, SYMS[sym], value
        self.symname = sym
        self.x, self.y, self.rot, self.mirror = x, y, rot, mirror
        self.pins, self.fp, self.dnp, self.note, self.mpn = pins, fp, dnp, note, mpn
        self.ref_at, self.val_at, self.hide_value = ref_at, val_at, hide_value

    def off(self, lx, ly):
        sx, sy = lx, -ly
        if self.mirror:
            sx = -sx
        return ROT[self.rot](sx, sy)

    def p(self, num):
        pn = self.sym.pin(str(num))
        dx, dy = self.off(pn.x, pn.y)
        return (round(self.x + dx, 2), round(self.y + dy, 2))

    def bbox(self):
        """Kotak body di koordinat layar (untuk penempatan teks)."""
        if self.sym.box:
            x1, y1, x2, y2 = self.sym.box
        else:
            x1, y1, x2, y2 = -2.54, 2.54, 2.54, -2.54
        a = self.off(x1, y1)
        b = self.off(x2, y2)
        return (self.x + min(a[0], b[0]), self.y + min(a[1], b[1]), self.x + max(a[0], b[0]), self.y + max(a[1], b[1]))


class Sheet:
    def __init__(self, key, title, fname, paper="A3", refbase=0):
        self.key, self.title, self.file, self.paper = key, title, fname, paper
        self.parts, self.wires, self.labels, self.hlabels, self.powers = [], [], [], [], []
        self.ncs, self.texts, self.boxes = [], [], []
        self.refbase = refbase
        self._pwr = 0

    # ---- komponen -----------------------------------------------------------
    def part(self, ref, sym, value, x, y, pins, rot=0, mirror=False, fp="", dnp=False, note="", mpn="",
             ref_at=None, val_at=None, hide_value=False):
        p = Part(self, ref, sym, value, snap(x), snap(y), rot, mirror, {str(k): v for k, v in pins.items()},
                 fp, dnp, note, mpn, ref_at, val_at, hide_value)
        self.parts.append(p)
        return p

    def vert(self, ref, sym, value, top, nets, **kw):
        """Komponen 2-pin vertikal, pin 1 di titik `top`."""
        return self.part(ref, sym, value, top[0], top[1] + 3.81, {"1": nets[0], "2": nets[1]}, **kw)

    def horiz(self, ref, sym, value, left, nets, **kw):
        """Komponen 2-pin horizontal, pin 1 di titik `left` (rot 90)."""
        return self.part(ref, sym, value, left[0] + 3.81, left[1], {"1": nets[0], "2": nets[1]}, rot=90, **kw)

    def shunt(self, ref, sym, value, node, net, gnd="GND", **kw):
        """Komponen vertikal dari node (di atas) ke ground (di bawah)."""
        p = self.vert(ref, sym, value, node, (net, gnd), **kw)
        self.pwr(gnd, p.p(2))
        return p

    # ---- gambar -------------------------------------------------------------
    def w(self, *pts):
        pts = [(round(x, 2), round(y, 2)) for x, y in pts]
        for a, b in zip(pts, pts[1:]):
            if a != b:
                self.wires.append((a, b))

    def wh(self, a, b):
        """Wire L: horizontal dulu lalu vertikal."""
        self.w(a, (b[0], a[1]), b)

    def wv(self, a, b):
        """Wire L: vertikal dulu lalu horizontal."""
        self.w(a, (a[0], b[1]), b)

    def pwr(self, name, pt, d=None):
        """Simbol power. d = arah simbol: 'up','down','left','right' (default rail=up, ground=down)."""
        s = SYMS[name]
        isg = s.kind.startswith("power_gnd")
        if d is None:
            d = "down" if isg else "up"
        if isg:
            rot = {"down": 0, "up": 180, "right": 90, "left": 270}[d]
        else:
            rot = {"up": 0, "down": 180, "left": 90, "right": 270}[d]
        self.powers.append((name, (round(pt[0], 2), round(pt[1], 2)), rot, d))

    def flag(self, pt, net):
        self.part(f"#FLG{self.key}{len(self.parts)}", "PWR_FLAG", "PWR_FLAG", pt[0], pt[1], {"1": net},
                  hide_value=True)

    def label(self, name, pt, d="right"):
        """Label lokal di ujung wire; d = arah teks."""
        self.labels.append((name, (round(pt[0], 2), round(pt[1], 2)), d))

    def hlabel(self, name, pt, d="right", shape="bidirectional"):
        self.hlabels.append((name, (round(pt[0], 2), round(pt[1], 2)), d, shape))

    def nc(self, pt):
        self.ncs.append((round(pt[0], 2), round(pt[1], 2)))

    def text(self, s, x, y, size=1.27, bold=False):
        self.texts.append((s, x, y, size, bold))

    def box(self, x1, y1, x2, y2, title):
        self.boxes.append((x1, y1, x2, y2, title))

    # ---- tulis --------------------------------------------------------------
    def _junctions(self):
        cnt = defaultdict(int)
        pins = set()
        for p in self.parts:
            seen = set()
            for pn in p.sym.pins:
                pt = p.p(pn.num)
                if pt not in seen:
                    seen.add(pt)
                    pins.add(pt)
                    cnt[pt] += 1
        for name, pt, rot, d in self.powers:
            cnt[pt] += 1
        for a, b in self.wires:
            cnt[a] += 1
            cnt[b] += 1
        cands = set(cnt)
        js = []
        for pt in cands:
            c = cnt[pt]
            for a, b in self.wires:
                if pt in (a, b):
                    continue
                if a[0] == b[0] == pt[0] and min(a[1], b[1]) < pt[1] < max(a[1], b[1]):
                    c += 2
                elif a[1] == b[1] == pt[1] and min(a[0], b[0]) < pt[0] < max(a[0], b[0]):
                    c += 2
            if c >= 3:
                js.append(pt)
        return sorted(js)

    def render(self, project, root_uuid, sheet_uuid, lib):
        it = []
        path = f"/{root_uuid}/{sheet_uuid}" if sheet_uuid != root_uuid else f"/{root_uuid}"
        used = set()
        for p in self.parts:
            used.add(p.symname)
            it.append(self._sym_inst(p, project, path, lib))
        for i, (name, pt, rot, d) in enumerate(self.powers):
            used.add(name)
            it.append(self._pwr_inst(i, name, pt, rot, d, project, path, lib))
        for i, (a, b) in enumerate(self.wires):
            it.append(f"  (wire (pts (xy {g(a[0])} {g(a[1])}) (xy {g(b[0])} {g(b[1])})) "
                      f"(stroke (width 0) (type default)) (uuid {q(uid(self.key, 'w', i, a, b))}))")
        for pt in self._junctions():
            it.append(f"  (junction (at {g(pt[0])} {g(pt[1])}) (diameter 0) (color 0 0 0 0) "
                      f"(uuid {q(uid(self.key, 'j', pt))}))")
        for pt in self.ncs:
            it.append(f"  (no_connect (at {g(pt[0])} {g(pt[1])}) (uuid {q(uid(self.key, 'nc', pt))}))")
        ang = {"right": 0, "up": 90, "left": 180, "down": 270}
        for i, (name, pt, d) in enumerate(self.labels):
            just = "left bottom" if d in ("right", "up") else "right bottom"
            it.append(f"  (label {q(name)} (at {g(pt[0])} {g(pt[1])} {ang[d]}) (fields_autoplaced)\n"
                      f"    (effects (font (size 1.27 1.27)) (justify {just}))\n"
                      f"    (uuid {q(uid(self.key, 'lbl', i, name))})\n  )")
        for i, (name, pt, d, shape) in enumerate(self.hlabels):
            just = "left" if d in ("right", "up") else "right"
            it.append(f"  (hierarchical_label {q(name)} (shape {shape}) (at {g(pt[0])} {g(pt[1])} {ang[d]}) "
                      f"(fields_autoplaced)\n    (effects (font (size 1.27 1.27)) (justify {just}))\n"
                      f"    (uuid {q(uid(self.key, 'hl', i, name))})\n  )")
        for i, (x1, y1, x2, y2, title) in enumerate(self.boxes):
            it.append(f"  (rectangle (start {g(x1)} {g(y1)}) (end {g(x2)} {g(y2)})\n"
                      f"    (stroke (width 0.254) (type dash) (color 0 0 194 1)) (fill (type none))\n"
                      f"    (uuid {q(uid(self.key, 'box', i))})\n  )")
            it.append(f"  (text {q(title)} (at {g(x1 + 1.27)} {g(y1 + 1.27)} 0)\n"
                      f"    (effects (font (size 2.032 2.032) (thickness 0.4064) bold (color 0 0 194 1)) "
                      f"(justify left top))\n    (uuid {q(uid(self.key, 'boxt', i))})\n  )")
        for i, (s, x, y, size, bold) in enumerate(self.texts):
            b = " (thickness 0.3048) bold" if bold else ""
            it.append(f"  (text {q(s)} (at {g(x)} {g(y)} 0)\n"
                      f"    (effects (font (size {g(size)} {g(size)}){b}) (justify left top))\n"
                      f"    (uuid {q(uid(self.key, 'txt', i))})\n  )")
        return it, used

    def _sym_inst(self, p, project, path, lib):
        s = p.sym
        X, Y = p.x, p.y
        x1, y1, x2, y2 = p.bbox()
        kind = s.kind
        if p.ref_at:
            r = p.ref_at
        elif kind == "2pin" and p.rot in (0, 180):
            r = (X + 2.54, Y - 1.27, "left")
        elif kind == "2pin":
            r = (X, Y - 2.54, None)
        elif kind == "fet":
            r = (x2 + 1.27, Y - 1.27, "left")
        else:
            r = (x1, y1 - 1.27, "left")
        if p.val_at:
            v = p.val_at
        elif kind == "2pin" and p.rot in (0, 180):
            v = (X + 2.54, Y + 1.27, "left")
        elif kind == "2pin":
            v = (X, Y + 2.54, None)
        elif kind == "fet":
            v = (x2 + 1.27, Y + 1.27, "left")
        else:
            v = (x1, y2 + 1.27, "left")

        def prop(k, val, at, hide=False):
            x, y, j = at
            eff = "(effects (font (size 1.27 1.27))"
            if j:
                eff += f" (justify {j})"
            if hide:
                eff += " hide"
            return f"    (property {q(k)} {q(val)} (at {g(x)} {g(y)} 0) {eff}))"
        isflag = p.symname == "PWR_FLAG"
        props = [prop("Reference", p.ref, r, hide=isflag), prop("Value", p.value, v, hide=p.hide_value or isflag),
                 prop("Footprint", p.fp or s.footprint, (X, Y, None), True),
                 prop("Datasheet", s.datasheet, (X, Y, None), True)]
        if p.mpn:
            props.append(prop("MPN", p.mpn, (X, Y, None), True))
        if p.note:
            props.append(prop("Catatan", p.note, (X, Y, None), True))
        pins = "\n".join(f"    (pin {q(pn.num)} (uuid {q(uid(self.key, p.ref, 'pin', pn.num))}))" for pn in s.pins)
        mir = " (mirror y)" if p.mirror else ""
        bom = "no" if isflag else "yes"
        return (f"  (symbol (lib_id {q(lib + ':' + p.symname)}) (at {g(X)} {g(Y)} {p.rot}){mir} (unit 1)\n"
                f"    (in_bom {bom}) (on_board {bom}) (dnp {'yes' if p.dnp else 'no'})\n"
                f"    (uuid {q(uid(self.key, p.ref))})\n" + "\n".join(props) + "\n" + pins + "\n"
                f"    (instances (project {q(project)} (path {q(path)} (reference {q(p.ref)}) (unit 1))))\n  )")

    def _pwr_inst(self, i, name, pt, rot, d, project, path, lib):
        self._pwr += 1
        ref = f"#PWR{self.refbase + self._pwr:04d}"
        x, y = pt
        isg = SYMS[name].kind.startswith("power_gnd")
        off = {"up": (0, -3.175, None), "down": (0, 4.445, None), "left": (-3.175, 0, "right"),
               "right": (3.175, 0, "left")}[d]
        hide = name == "GND"
        eff = "(effects (font (size 1.27 1.27))" + (f" (justify {off[2]})" if off[2] else "") + \
              (" hide" if hide else "") + ")"
        return (f"  (symbol (lib_id {q(lib + ':' + name)}) (at {g(x)} {g(y)} {rot}) (unit 1)\n"
                f"    (in_bom yes) (on_board yes) (dnp no)\n    (uuid {q(uid(self.key, 'pwr', i, name, pt))})\n"
                f"    (property \"Reference\" {q(ref)} (at {g(x)} {g(y)} 0) {FONT_H})\n"
                f"    (property \"Value\" {q(name)} (at {g(x + off[0])} {g(y + off[1])} 0) {eff})\n"
                f"    (property \"Footprint\" \"\" (at {g(x)} {g(y)} 0) {FONT_H})\n"
                f"    (property \"Datasheet\" \"\" (at {g(x)} {g(y)} 0) {FONT_H})\n"
                f"    (pin \"1\" (uuid {q(uid(self.key, 'pwrpin', i, name, pt))}))\n"
                f"    (instances (project {q(project)} (path {q(path)} (reference {q(ref)}) (unit 1))))\n  )")


def sheet_file(sheet, project, root_uuid, sheet_uuid, lib, title_block, extra=""):
    it, used = sheet.render(project, root_uuid, sheet_uuid, lib)
    libsyms = "\n".join("    " + SYMS[n].body(lib + ":").replace("\n", "\n    ") for n in sorted(used))
    return (f"(kicad_sch (version 20230121) (generator eeschema)\n\n  (uuid {q(sheet_uuid)})\n\n"
            f"  (paper {q(sheet.paper)})\n\n{title_block}\n\n  (lib_symbols\n{libsyms}\n  )\n\n"
            + "\n".join(it) + "\n" + extra + ")\n")
