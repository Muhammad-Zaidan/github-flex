"""Membaca PDF (hasil Word/LibreOffice) dan menyusunnya ulang menjadi .docx.

Tata letak PDF (posisi baris, huruf, ukuran, jarak) diterjemahkan kembali menjadi
paragraf ber-format langsung: perataan, menjorok, spasi baris, jarak sebelum/sesudah,
pemisah halaman, margin, dan ukuran kertas. Tabel menjadi tabel Word; gambar, diagram
vektor, dan persamaan disalin sebagai gambar. Hasilnya dipakai sebagai dokumen contoh
maupun naskah oleh mesin Cetakan yang sama.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from io import BytesIO
from statistics import median

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from docx.table import _Cell

CM = 72 / 2.54           # pt per cm
LINE_FACTOR = {"times new roman": 1.15, "arial": 1.15, "calibri": 1.22, "cambria": 1.172,
               "georgia": 1.136, "garamond": 1.12, "book antiqua": 1.17, "tahoma": 1.207,
               "verdana": 1.215, "bookman old style": 1.17, "century": 1.2}
MARKER_RE = re.compile(r"^(\d{1,2}[.)]|[a-zA-Z][.)]|\(\d{1,2}\)|\([a-z]\)|\[\d{1,3}\]|[•●▪◦■□➢►\-–])\s")
BAB_LINE_RE = re.compile(r"^BAB\s+([IVXLC]+|\d{1,2})\s*$")
PAGENUM_RE = re.compile(r"^\s*([0-9]{1,4}|[ivxlcdm]{1,7})\s*$", re.I)
BULLET_FONTS = ("symbol", "wingdings")


def font_name(raw):
    name = raw.split("+")[-1]
    name = re.split(r"[-,]", name)[0]
    name = re.sub(r"(PSMT|PS|MT|Std|Pro)$", "", name)
    name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).strip()
    # font pengganti yang ukurannya setara (PDF dari LibreOffice) dikembalikan ke aslinya
    return {"Arial MT": "Arial", "Liberation Serif": "Times New Roman", "Liberation Sans": "Arial",
            "Liberation Mono": "Courier New", "Carlito": "Calibri", "Caladea": "Cambria",
            "Tinos": "Times New Roman", "Arimo": "Arial", "Cousine": "Courier New"}.get(name, name) or raw


def line_factor(font):
    return LINE_FACTOR.get((font or "").lower(), 1.17)


def snap_indent(pt):
    """Indentasi (pt) dibulatkan seperti nilai yang lazim diketik di Word (cm)."""
    cm = pt / CM
    q = round(cm * 4) / 4
    cm = q if abs(cm - q) <= 0.06 else round(cm * 20) / 20
    return cm * CM


def snap_space(pt):
    s = round(pt)
    q = 6 * round(s / 6)
    return q if abs(s - q) <= 1.5 else s


def snap(v, choices, tol):
    for c in choices:
        if abs(v - c) <= tol * max(c, 1e-6):
            return c
    return v


# ---------------------------------------------------------------------------
@dataclass
class Span:
    text: str
    font: str
    size: float
    bold: bool
    italic: bool
    sup: bool = False
    sub: bool = False
    math: bool = False
    oy: float = 0             # garis dasar span


@dataclass
class Line:
    page: int
    x0: float
    x1: float
    y0: float
    y1: float
    base: float
    spans: list

    @property
    def text(self):
        return "".join(s.text for s in self.spans).strip()

    @property
    def main(self):
        """Span yang paling banyak hurufnya (penentu ukuran dan huruf baris)."""
        return max((s for s in self.spans if s.text.strip()), key=lambda s: len(s.text.strip()),
                   default=self.spans[0])

    @property
    def size(self):
        return round(self.main.size * 2) / 2

    @property
    def bold(self):
        letters = [s for s in self.spans if re.search(r"\w", s.text)]
        return bool(letters) and all(s.bold for s in letters)

    @property
    def is_math(self):
        chars = sum(len(s.text.strip()) for s in self.spans)
        return chars > 0 and sum(len(s.text.strip()) for s in self.spans if s.math) / chars > 0.5


@dataclass
class Para:
    lines: list = field(default_factory=list)
    kind: str = "p"             # p | table | image
    rows: list = None
    image: bytes = None
    img_w: float = 0
    img_h: float = 0
    align: str = "left"
    left: float = 0
    first: float = 0
    right: float = 0
    line_mult: float = None
    before: float = 0
    after: float = 0
    page_break: bool = False
    page: int = 0
    y0: float = 0
    y1: float = 0
    bold_head: bool = False
    widths: list = None
    fill: str = None


# ---------------------------------------------------------------------------
def _lines(page, pno):
    out = []
    d = page.get_text("dict", flags=0)
    for b in d["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b["lines"]:
            spans = []
            base = None
            for s in ln["spans"]:
                if not s["text"]:
                    continue
                f = s["font"]
                low = f.lower()
                if base is None and s["text"].strip():
                    base = s["origin"][1]
                spans.append(Span(
                    text=s["text"], font=font_name(f), size=s["size"],
                    bold=bool(s["flags"] & 16) or "bold" in low or "black" in low,
                    italic=bool(s["flags"] & 2) or "italic" in low or "oblique" in low,
                    math="math" in low, oy=s["origin"][1]))
            if not spans or not "".join(s.text for s in spans).strip():
                continue
            x0 = next(s["origin"][0] for s in ln["spans"] if s["text"].strip())
            x1 = ln["bbox"][2]
            # buang lebar spasi di akhir baris
            last = ln["spans"][-1]
            trail = len(last["text"]) - len(last["text"].rstrip())
            if trail and last["text"].strip():
                x1 -= (last["bbox"][2] - last["bbox"][0]) / max(len(last["text"]), 1) * trail
            elif not last["text"].strip() and len(ln["spans"]) > 1:
                x1 = ln["spans"][-2]["bbox"][2]
            out.append(Line(pno, x0, x1, ln["bbox"][1], ln["bbox"][3], base or ln["bbox"][3], spans))
    # gabungkan potongan yang sebaris (tab, nomor rujukan, dsb.)
    out.sort(key=lambda l: (round(l.base), l.x0))
    raw = [Line(l.page, l.x0, l.x1, l.y0, l.y1, l.base, list(l.spans)) for l in out]
    merged = []
    for ln in out:
        prev = merged[-1] if merged else None
        if prev and abs(prev.base - ln.base) < 2.5 and ln.x0 >= prev.x1 - 1:
            gap = ln.x0 - prev.x1
            # tab hanya untuk jarak lebar atau setelah label pendek ("[1]", "gm"); jarak
            # lebar di kalimat rata kiri-kanan tetap spasi biasa
            label = len(prev.text) <= 5 or re.match(r"^(\[\d{1,3}\]|\(?\d{1,3}[.)]?|[a-zA-Z][.)])$", prev.text)
            tab = gap > prev.size * 6 or (bool(label) and gap > prev.size * 0.9)
            sep = "\t" if tab else ("" if prev.spans[-1].text.endswith(" ") else " ")
            if sep == "\t":
                prev.spans[-1].text = prev.spans[-1].text.rstrip() or prev.spans[-1].text
            if sep:
                prev.spans.append(Span(sep, prev.spans[-1].font, prev.spans[-1].size, False, False))
            prev.spans.extend(ln.spans)
            prev.x1, prev.y0, prev.y1 = ln.x1, min(prev.y0, ln.y0), max(prev.y1, ln.y1)
        elif prev and abs(prev.base - ln.base) < 2.5 and ln.x1 <= prev.x0 + 1:
            ln.spans.append(Span("\t", ln.spans[-1].font, ln.spans[-1].size, False, False))
            prev.spans[:0] = ln.spans
            prev.x0 = ln.x0
        else:
            merged.append(ln)
    # superskrip/subskrip dari posisi garis dasar span yang lebih kecil
    for ln in merged:
        main = ln.main
        for s in ln.spans:
            if s is main or not s.text.strip() or s.size >= main.size * 0.85 or s.math:
                continue
            if s.oy < main.oy - 1:
                s.sup = True
            elif s.oy > main.oy + 0.5:
                s.sub = True
    return merged, raw


def _segments(drawings):
    hs, vs = [], []
    for dr in drawings:
        for it in dr["items"]:
            if it[0] == "l":
                a, b = it[1], it[2]
                if abs(a.y - b.y) < 1:
                    hs.append([min(a.x, b.x), max(a.x, b.x), (a.y + b.y) / 2])
                elif abs(a.x - b.x) < 1:
                    vs.append([min(a.y, b.y), max(a.y, b.y), (a.x + b.x) / 2])
            elif it[0] == "re":
                r = it[1]
                if r.height < 2.5 and r.width > 2:
                    hs.append([r.x0, r.x1, (r.y0 + r.y1) / 2])
                elif r.width < 2.5 and r.height > 2:
                    vs.append([r.y0, r.y1, (r.x0 + r.x1) / 2])
                elif r.width > 2 and r.height > 2 and not dr.get("fill"):
                    hs += [[r.x0, r.x1, r.y0], [r.x0, r.x1, r.y1]]
                    vs += [[r.y0, r.y1, r.x0], [r.y0, r.y1, r.x1]]
    return hs, vs


def _coverage(segs, at, lo, hi, tol=1.6):
    """Panjang gabungan segmen pada garis `at` di antara lo..hi."""
    parts = sorted((max(a, lo), min(b, hi)) for a, b, c in segs if abs(c - at) <= tol and b > lo and a < hi)
    total, end = 0, lo
    for a, b in parts:
        if b > end:
            total += b - max(a, end)
            end = b
    return total


def _cluster(vals, tol=1.6):
    out = []
    for v in sorted(vals):
        if out and v - out[-1][-1] <= tol:
            out[-1].append(v)
        else:
            out.append([v])
    return [sum(c) / len(c) for c in out]


def _tables(drawings, raw):
    """Tabel dari garis batas sel: [(bbox, rows, header_bold)]."""
    hs, vs = _segments(drawings)
    if len(hs) < 3 or len(vs) < 3:
        return []
    segs = [("h", h) for h in hs] + [("v", v) for v in vs]
    parent = list(range(len(segs)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    hidx = [i for i, s in enumerate(segs) if s[0] == "h"]
    vidx = [i for i, s in enumerate(segs) if s[0] == "v"]
    for i in hidx:
        x0, x1, y = segs[i][1]
        for j in vidx:
            y0, y1, x = segs[j][1]
            if x0 - 1.5 <= x <= x1 + 1.5 and y0 - 1.5 <= y <= y1 + 1.5:
                parent[find(i)] = find(j)
    groups = {}
    for i in range(len(segs)):
        groups.setdefault(find(i), []).append(segs[i])
    out = []
    for g in groups.values():
        ys = _cluster([s[1][2] for s in g if s[0] == "h"])
        xs = _cluster([s[1][2] for s in g if s[0] == "v"])
        if len(ys) < 3 or len(xs) < 3:
            continue
        bbox = [xs[0], ys[0], xs[-1], ys[-1]]
        hseg = [s[1] for s in g if s[0] == "h"]
        vseg = [s[1] for s in g if s[0] == "v"]
        # bingkai luar harus utuh dan setiap garis baris/kolom cukup panjang;
        # skematik/diagram vektor tidak memenuhi ini
        width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if width < 60 or height < 20:
            continue
        cov_y = [_coverage(hseg, y, bbox[0], bbox[2]) / width for y in ys]
        cov_x = [_coverage(vseg, x, bbox[1], bbox[3]) / height for x in xs]
        if min(cov_y[0], cov_y[-1], cov_x[0], cov_x[-1]) < 0.9 or min(cov_y) < 0.3 \
                or sum(c > 0.9 for c in cov_x) < 2 or len(xs) > 16:
            continue
        rows = [["" for _ in xs[:-1]] for _ in ys[:-1]]
        bold = []
        for ln in raw:
            cx, cy = (ln.x0 + ln.x1) / 2, (ln.y0 + ln.y1) / 2
            if not (bbox[0] <= cx <= bbox[2] and bbox[1] <= cy <= bbox[3]):
                continue
            r = next(k for k in range(len(ys) - 1) if cy <= ys[k + 1] or k == len(ys) - 2)
            c = next((k for k in range(len(xs) - 1) if ln.x0 + 1 < xs[k + 1]), len(xs) - 2)
            rows[r][c] = (rows[r][c] + " " + ln.text).strip()
            if r == 0:
                bold.append(ln.bold)
        rows = [r for r in rows if any(c for c in r)]
        if len(rows) >= 2:
            fill = None
            for dr in drawings:
                r = dr["rect"]
                if dr.get("fill") and r.width > 4 and r.height > 4 and abs(r.y0 - ys[0]) < 2 \
                        and r.y1 <= ys[1] + 2 and bbox[0] - 2 <= r.x0 <= bbox[2]:
                    c = dr["fill"]
                    if c and min(c) < 0.98:
                        fill = "%02X%02X%02X" % tuple(int(v * 255) for v in c[:3])
                        break
            widths = [b - a for a, b in zip(xs, xs[1:])]
            out.append((bbox, rows, bool(bold) and all(bold), widths, fill))
    return out


def _regions(page, drawings, tables, H):
    """Daerah gambar: bitmap dan kumpulan garis/kotak vektor (diagram)."""
    rects = []
    for info in page.get_image_info():
        r = info["bbox"]
        if (r[2] - r[0]) > 8 and (r[3] - r[1]) > 8:
            rects.append(list(r))
    for dr in drawings:
        r = dr["rect"]
        if r.width < 0.5 and r.height < 0.5:
            continue
        if any(t[0] - 2 <= r.x0 and r.x1 <= t[2] + 2 and t[1] - 2 <= r.y0 and r.y1 <= t[3] + 2 for t in tables):
            continue
        rects.append([r.x0, r.y0, r.x1, r.y1])
    # gabungkan yang berdekatan
    changed = True
    while changed:
        changed = False
        out = []
        for r in rects:
            for o in out:
                if r[0] <= o[2] + 8 and o[0] <= r[2] + 8 and r[1] <= o[3] + 8 and o[1] <= r[3] + 8:
                    o[0], o[1], o[2], o[3] = min(o[0], r[0]), min(o[1], r[1]), max(o[2], r[2]), max(o[3], r[3])
                    changed = True
                    break
            else:
                out.append(list(r))
        rects = out
    return [r for r in rects if (r[2] - r[0]) > 30 and (r[3] - r[1]) > 20 and r[3] < H * 0.97]


def _inside(ln, r, pad=2):
    cx, cy = (ln.x0 + ln.x1) / 2, (ln.y0 + ln.y1) / 2
    return r[0] - pad <= cx <= r[2] + pad and r[1] - pad <= cy <= r[3] + pad


def _pixmap(page, rect, scale=2.5):
    import pymupdf
    clip = pymupdf.Rect(rect) + (-2, -2, 2, 2)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=clip, alpha=False)
    return pix.tobytes("png"), clip.width, clip.height


# ---------------------------------------------------------------------------
class PdfLayout:
    def __init__(self, data):
        import pymupdf
        self.doc = pymupdf.open(stream=data, filetype="pdf")
        if self.doc.needs_pass:
            raise ValueError("PDF terkunci kata sandi.")
        first = self.doc[0].rect
        self.W, self.H = first.width, first.height
        self.footer = None
        self.items = []        # (page, y, kind, payload)
        self._read()

    def _read(self):
        pages = []
        for pno, page in enumerate(self.doc):
            H = page.rect.height
            drawings = page.get_drawings()
            lines, raw = _lines(page, pno)
            tables = _tables(drawings, raw)
            body, foot = [], []
            for ln in lines:
                if ln.base > H * 0.9 and PAGENUM_RE.match(ln.text):
                    foot.append(ln)
                elif ln.y1 < H * 0.07 or (ln.y0 > H * 0.93 and len(ln.text) < 60):
                    continue
                else:
                    body.append(ln)
            if foot and self.footer is None and PAGENUM_RE.match(foot[0].text):
                self.footer = foot[0]
            regions = _regions(page, drawings, [t[0] for t in tables], H)
            # persamaan: baris dengan huruf Math berurutan menjadi satu gambar
            eq, cur = [], None
            for ln in body:
                if ln.is_math:
                    if cur and ln.y0 - cur[3] < ln.size * 1.2:
                        cur[0], cur[1], cur[2], cur[3] = min(cur[0], ln.x0), min(cur[1], ln.y0), \
                            max(cur[2], ln.x1), max(cur[3], ln.y1)
                    else:
                        cur = [ln.x0, ln.y0, ln.x1, ln.y1]
                        eq.append(cur)
            # nomor persamaan "(1)" di sebelah kanan ikut daerah persamaan
            for r in eq:
                for ln in body:
                    if re.match(r"^\(\d+(\.\d+)*\)$", ln.text) and r[1] - 4 <= (ln.y0 + ln.y1) / 2 <= r[3] + 4:
                        r[2] = max(r[2], ln.x1)
            regions = [r for r in regions if not any(_overlap(r, e) for e in eq)] + eq
            items = []
            for ln in body:
                if any(_inside(ln, t[0]) for t in tables) or any(_inside(ln, r) for r in regions):
                    continue
                items.append((ln.y0, "line", ln))
            for bbox, rows, head_bold, widths, fill in tables:
                items.append((bbox[1], "table", (rows, head_bold, bbox, widths, fill)))
            for r in regions:
                png, w, h = _pixmap(page, r)
                items.append((r[1], "image", (png, w, h, r)))
            items.sort(key=lambda it: it[0])
            pages.append(items)
        self.pages = pages

    # ---- metrik halaman ----------------------------------------------------
    def margins(self):
        lines = [it[2] for items in self.pages for it in items if it[1] == "line"]
        wide = [l for l in lines if l.x1 - l.x0 > self.W * 0.45]
        # tepi kiri: posisi awal baris lebar yang paling kiri dan cukup sering muncul
        # (baris pertama paragraf sering menjorok, jadi modus saja bisa keliru)
        xc = Counter(round(l.x0) for l in wide)
        top = xc.most_common(1)[0][1] if xc else 0
        L = min((x for x, n in xc.items() if n >= top * 0.25), default=72)
        R = Counter(round(l.x1) for l in wide).most_common(1)[0][0] if wide else self.W - 72
        tops, bottoms = [], []
        for items in self.pages:
            ls = [it[2] for it in items if it[1] == "line"]
            if ls:
                tops.append(round(min(l.y0 for l in ls)))
                bottoms.append(max(l.y1 for l in ls))
        T = Counter(tops).most_common(1)[0][0] if tops else 72
        B = max(bottoms) if bottoms else self.H - 72
        self.L, self.R = L, R
        cm = lambda v: snap(round(v / CM, 2), [1, 1.27, 1.5, 2, 2.5, 2.54, 3, 3.5, 4, 4.5, 5], 0.04)
        return {"left": cm(L), "right": cm(self.W - R), "top": cm(T - 1), "bottom": cm(self.H - B - 6)}

    # ---- paragraf ---------------------------------------------------------
    def paragraphs(self):
        self.margins()
        L, R = self.L, self.R
        mid = (L + R) / 2
        paras = []
        cur = None

        def centered(ln):
            return abs((ln.x0 + ln.x1) / 2 - mid) < 6 and ln.x0 > L + 12

        def full(ln):
            return ln.x1 >= R - 14

        for pno, items in enumerate(self.pages):
            for y, kind, val in items:
                if kind != "line":
                    cur = None
                    p = Para(kind=kind, page=pno, y0=y)
                    if kind == "table":
                        p.rows, p.bold_head, bbox, p.widths, p.fill = val
                        p.y1 = bbox[3]
                    else:
                        p.image, p.img_w, p.img_h, r = val
                        p.y1 = r[3]
                        c = (r[0] + r[2]) / 2
                        p.align = "center" if abs(c - mid) < 25 else ("left" if r[0] < L + 20 else "center")
                    paras.append(p)
                    continue
                ln = val
                new = cur is None
                if not new:
                    prev = cur.lines[-1]
                    if prev.page != ln.page:
                        new = not (full(prev) and abs(ln.x0 - (cur.lines[1].x0 if len(cur.lines) > 1 else L)) < 3
                                   and ln.size == prev.size and not ln.bold)
                    else:
                        same = [b.base - a.base for a, b in zip(cur.lines, cur.lines[1:]) if a.page == b.page]
                        pitch = same[-1] if same else None
                        gap = ln.base - prev.base
                        expect = pitch or ln.size * line_factor(ln.main.font) * 1.6
                        if gap > expect * 1.18 + 0.5 or gap < 0:
                            new = True
                        elif ln.size != prev.size or ln.bold != prev.bold:
                            new = True
                        elif MARKER_RE.match(ln.text) or BAB_LINE_RE.match(ln.text) \
                                or BAB_LINE_RE.match(prev.text):
                            new = True
                        elif centered(ln) and centered(prev):
                            new = False
                        elif MARKER_RE.match(cur.lines[0].text) and (
                                abs(ln.x0 - cur.lines[1].x0) < 3 if len(cur.lines) > 1
                                else ln.x0 > cur.lines[0].x0 + 2):
                            new = False     # lanjutan butir/pustaka berindentasi gantung
                        elif not full(prev):
                            new = True
                        elif len(cur.lines) == 1:
                            first = cur.lines[0]
                            new = ln.x0 > first.x0 + 2 and not MARKER_RE.match(first.text)
                        else:
                            new = abs(ln.x0 - cur.lines[1].x0) > 3
                if new:
                    cur = Para(page=pno, y0=ln.y0)
                    paras.append(cur)
                cur.lines.append(ln)
                cur.y1 = ln.y1
        self._layout(paras)
        return paras

    def _layout(self, paras):
        L, R = self.L, self.R
        mid = (L + R) / 2
        done = []
        for p in paras:
            if p.kind != "p":
                continue
            ls = p.lines
            first = ls[0]
            if len(ls) > 1:
                cont = Counter(round(l.x0) for l in ls[1:]).most_common(1)[0][0]
                p.left = max(cont - L, 0)
                p.first = first.x0 - cont
                pitches = [b.base - a.base for a, b in zip(ls, ls[1:]) if a.page == b.page]
                if pitches:
                    mult = median(pitches) / (first.size * line_factor(first.main.font))
                    p.line_mult = snap(round(mult, 2), [1.0, 1.15, 1.5, 2.0, 2.5, 3.0], 0.06)
                body = ls[:-1]
                if all(l.x1 >= R - 4 for l in body):
                    p.align = "justify"
                    p.right = 0
                elif all(abs((l.x0 + l.x1) / 2 - mid) < 6 for l in ls):
                    p.align, p.left, p.first = "center", 0, 0
                else:
                    ends = [l.x1 for l in body]
                    if ends and max(ends) - min(ends) < 4 and R - max(ends) > 10:
                        p.align = "justify"
                        p.right = R - max(ends)
                    else:
                        p.align = "left"
            else:
                if abs((first.x0 + first.x1) / 2 - mid) < 6 and first.x0 > L + 12:
                    p.align = "center"
                elif first.x1 >= R - 4 and first.x0 > L + 40:
                    p.align = "right"
                else:
                    p.align = "left"
                    p.first = max(first.x0 - L, 0)
            if len(ls) == 1 and MARKER_RE.match(first.text):
                # butir satu baris: pakai indentasi butir bertanda sebelumnya pada posisi sama
                sib = next((q for q in reversed(done) if len(q.lines) > 1
                            and MARKER_RE.match(q.lines[0].text) and abs(q.lines[0].x0 - first.x0) < 3), None)
                if sib is not None and not first.bold:
                    p.left, p.first, p.align = sib.left, sib.first, sib.align
                elif p.align == "left":
                    p.left, p.first = first.x0 - L, 0
            done.append(p)
        body = [p.line_mult for p in paras if p.kind == "p" and len(p.lines) > 2 and p.line_mult]
        default = Counter(body).most_common(1)[0][0] if body else 1.0
        # jarak antarparagraf & pemisah halaman
        prev = None
        for p in paras:
            prev_page = (prev.lines[-1].page if prev.kind == "p" else prev.page) if prev is not None else None
            if prev is not None and p.page == prev_page:
                if p.kind == "p" and prev.kind == "p":
                    nxt_line = p.lines[0]
                    gap = nxt_line.base - prev.lines[-1].base
                    if len(prev.lines) == 1 and not prev.line_mult:
                        m = gap / (prev.lines[0].size * line_factor(prev.lines[0].main.font))
                        # hanya nilai yang memang dipakai dokumen; selisih lain adalah jarak paragraf
                        sm = snap(round(m, 2), [default, 1.0], 0.04)
                        if sm != round(m, 2):
                            prev.line_mult = sm
                    height = nxt_line.size * line_factor(nxt_line.main.font) * (p.line_mult or prev.line_mult or 1)
                    extra = gap - height
                else:
                    extra = p.y0 - prev.y1 - 4
                extra = max(0, round(extra))
                if extra >= 3:
                    head = p.kind == "p" and (p.lines[0].bold or p.align == "center") and len(p.lines) <= 3
                    if head:
                        p.before = extra
                    else:
                        prev.after = extra
            elif prev is not None:
                # halaman sebelumnya berhenti jauh di atas batas bawah → pemisah halaman
                if prev.y1 < self._page_bottom() - 60:
                    p.page_break = True
            prev = p
        # paragraf yang terbelah antarhalaman sudah tergabung; spasi baris paragraf
        # satu baris diwarisi dari paragraf sejenis
        sig_mult = {}
        for p in paras:
            if p.kind == "p" and p.line_mult:
                sig_mult.setdefault(self._sig(p), []).append(p.line_mult)
        last = None
        for p in paras:
            if p.kind == "p" and not p.line_mult:
                vals = sig_mult.get(self._sig(p))
                if last is not None and last.line_mult and last.lines[0].size == p.lines[0].size \
                        and MARKER_RE.match(p.lines[0].text) and MARKER_RE.match(last.lines[0].text):
                    p.line_mult = last.line_mult
                else:
                    p.line_mult = Counter(vals).most_common(1)[0][0] if vals else default
            if p.kind == "p":
                last = p

    def _page_bottom(self):
        if not hasattr(self, "_pb"):
            bottoms = [max(it[2].y1 for it in items if it[1] == "line")
                       for items in self.pages if any(it[1] == "line" for it in items)]
            self._pb = max(bottoms) if bottoms else self.H - 72
        return self._pb

    @staticmethod
    def _sig(p):
        ln = p.lines[0]
        return (ln.size, ln.bold, p.align)


def _overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


# ---------------------------------------------------------------------------
ALIGN = {"left": WD_ALIGN_PARAGRAPH.LEFT, "center": WD_ALIGN_PARAGRAPH.CENTER,
         "right": WD_ALIGN_PARAGRAPH.RIGHT, "justify": WD_ALIGN_PARAGRAPH.JUSTIFY}


def _para_text(p):
    """Span paragraf → [(teks, span)], menyambung baris dengan spasi."""
    out = []
    for k, ln in enumerate(p.lines):
        spans = [s for s in ln.spans]
        if k:
            prev = out[-1][0] if out else ""
            if prev.endswith("-") and ln.text[:1].islower():
                pass
            elif not prev.endswith((" ", "\t")):
                out.append((" ", spans[0]))
        for s in spans:
            t = s.text
            if not out and k == 0:
                t = t.lstrip()
            out.append((t, s))
    if out:
        out[-1] = (out[-1][0].rstrip(), out[-1][1])
    return out


_CACHE = {}


def to_docx(data):
    """PDF (bytes) → .docx (bytes) yang meniru tata letaknya (hasil disimpan sementara)."""
    import hashlib
    key = hashlib.sha1(data).hexdigest()
    if key not in _CACHE:
        if len(_CACHE) >= 16:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = _to_docx(data)
    return _CACHE[key]


def _to_docx(data):
    lay = PdfLayout(data)
    margins = lay.margins()
    paras = lay.paragraphs()
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Pt(lay.W), Pt(lay.H)
    sec.left_margin, sec.right_margin = Cm(margins["left"]), Cm(margins["right"])
    sec.top_margin, sec.bottom_margin = Cm(max(margins["top"], 0.5)), Cm(max(margins["bottom"], 0.5))
    sizes = Counter(p.lines[0].size for p in paras if p.kind == "p" and len(p.lines) > 2)
    fonts = Counter(p.lines[0].main.font for p in paras if p.kind == "p" and len(p.lines) > 2)
    base_font = fonts.most_common(1)[0][0] if fonts else "Times New Roman"
    base_size = sizes.most_common(1)[0][0] if sizes else 12
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = base_font, Pt(base_size)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), base_font)
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.space_before = Pt(0)
    for p in paras:
        if p.kind == "table":
            ncols = max(len(r) for r in p.rows)
            t = doc.add_table(rows=len(p.rows), cols=ncols)
            t.style = doc.styles["Table Grid"]
            t.autofit = False
            if p.widths and len(p.widths) == ncols:
                for col, w in zip(t.columns, p.widths):
                    col.width = Pt(w)
                for tr in t._tbl.tr_lst:
                    for tc, w in zip(tr.tc_lst, p.widths):
                        tc.width = Pt(w)
            for i, (row, tr) in enumerate(zip(p.rows, t._tbl.tr_lst)):
                for j, tc in enumerate(tr.tc_lst):
                    cell = _Cell(tc, t)
                    txt = (row[j] if j < len(row) else "") or ""
                    cell.text = re.sub(r"\s*\n\s*", " ", txt).strip()
                    for par in cell.paragraphs:
                        par.paragraph_format.space_after = Pt(0)
                        par.paragraph_format.line_spacing = 1.0
                        for r in par.runs:
                            r.font.size = Pt(max(base_size - 1, 8))
                            if i == 0 and p.bold_head:
                                r.bold = True
                    if i == 0 and p.fill:
                        shd = OxmlElement("w:shd")
                        shd.set(qn("w:val"), "clear")
                        shd.set(qn("w:color"), "auto")
                        shd.set(qn("w:fill"), p.fill)
                        tc.get_or_add_tcPr().append(shd)
            continue
        para = doc.add_paragraph()
        pf = para.paragraph_format
        para.alignment = ALIGN[p.align]
        if p.page_break:
            pf.page_break_before = True
        if p.kind == "image":
            pf.line_spacing = 1.0
            run = para.add_run()
            run.add_picture(BytesIO(p.image), width=Pt(p.img_w), height=Pt(p.img_h))
            pf.space_before, pf.space_after = Pt(p.before), Pt(p.after)
            continue
        if abs(p.left) > 1:
            pf.left_indent = Pt(snap_indent(p.left))
        if abs(p.first) > 1:
            pf.first_line_indent = Pt(snap_indent(p.first))
        if p.right > 1:
            pf.right_indent = Pt(snap_indent(p.right))
        pf.space_before, pf.space_after = Pt(snap_space(p.before)), Pt(snap_space(p.after))
        if p.line_mult:
            pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
            pf.line_spacing = p.line_mult
        main = p.lines[0].main
        for text, s in _para_text(p):
            if not text:
                continue
            r = para.add_run(text)
            r.font.name = s.font if not s.math else "Cambria Math"
            r.font.size = Pt(round(s.size * 2) / 2 if not (s.sup or s.sub) else round(main.size * 2) / 2)
            r.bold = s.bold
            r.italic = s.italic
            if s.sup:
                r.font.superscript = True
            elif s.sub:
                r.font.subscript = True
    if lay.footer is not None:
        _footer_number(doc, lay)
    out = BytesIO()
    doc.save(out)
    return out.getvalue()


def _footer_number(doc, lay):
    ln = lay.footer
    para = doc.sections[0].footer.paragraphs[0]
    mid = (lay.L + lay.R) / 2
    c = (ln.x0 + ln.x1) / 2
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER if abs(c - mid) < 20 else (
        WD_ALIGN_PARAGRAPH.RIGHT if c > mid else WD_ALIGN_PARAGRAPH.LEFT)
    run = para.add_run()
    run.font.name, run.font.size = ln.main.font, Pt(ln.size)
    for kind, text in (("begin", None), (None, "PAGE"), ("separate", None), (None, None), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
            run._r.append(el)
        elif text:
            el = OxmlElement("w:instrText")
            el.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            el.text = f" {text} "
            run._r.append(el)
        else:
            t = OxmlElement("w:t")
            t.text = "1"
            run._r.append(t)
