"""Menyusun dokumen hasil: isi baru dicetak dengan gaya dokumen contoh."""

import re
from copy import deepcopy
from io import BytesIO

from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from .classify import (
    ALPHA_HEAD_RE, ALPHA_LOW_HEAD_RE, BAB_RE, BULLET_RE, NUM_HEAD_RE, NUMLIST_RE, ROMAN_HEAD_RE,
    STOPWORDS, UNNUMBERED_RE, list_kind)
from .reader import CONTROL_RE, Seg
from .notes import Footnotes
from .roles import resolve
from .template import LABEL_RES, analyze, norm_heading

R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
LEVEL = {"bab": 0, "h1": 1, "h2": 2, "h3": 3}


TBLPR_ORDER = ["tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize",
               "tblStyleColBandSize", "tblW", "jc", "tblCellSpacing", "tblInd", "tblBorders", "shd",
               "tblLayout", "tblCellMar", "tblLook", "tblCaption", "tblDescription", "tblPrChange"]
TCPR_ORDER = ["cnfStyle", "tcW", "gridSpan", "hMerge", "vMerge", "tcBorders", "shd", "noWrap", "tcMar",
              "textDirection", "tcFitText", "vAlign", "hideMark", "headers", "cellIns", "cellDel",
              "cellMerge", "tcPrChange"]


def insert_ordered(parent, child, order):
    """Sisipkan `child` ke `parent` mengikuti urutan elemen skema OOXML (menggantikan yang sama)."""
    name = child.tag.split("}")[1]
    for old in parent.findall(child.tag):
        parent.remove(old)
    later = order[order.index(name) + 1:] if name in order else []
    for el in parent:
        if el.tag.split("}")[-1] in later:
            el.addprevious(child)
            return child
    parent.append(child)
    return child


def roman(n):
    vals = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
            (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


def from_roman(s):
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    total = 0
    for a, b in zip(s, s[1:] + " "):
        v = vals.get(a, 0)
        total += -v if vals.get(b, 0) > v else v
    return total


def letter(n, upper=True):
    s = chr(ord("A") + (max(n, 1) - 1) % 26)
    return s if upper else s.lower()


# ---------------------------------------------------------------------------
# operasi pada daftar Seg
# ---------------------------------------------------------------------------
def seg_text(segs):
    return "".join(s.text for s in segs if not s.special)


def cut(segs, n):
    """Buang n karakter pertama dari teks segs."""
    out = []
    for s in segs:
        if n > 0 and not s.special:
            take = min(n, len(s.text))
            n -= take
            rest = s.text[take:]
            if rest:
                out.append(Seg(rest, s.b, s.i, s.u, s.sup, s.sub))
        else:
            out.append(s)
    while out and not out[0].special and not out[0].text.strip():
        out.pop(0)
    if out and not out[0].special:
        f = out[0]
        out[0] = Seg(f.text.lstrip(), f.b, f.i, f.u, f.sup, f.sub)
    return out


def split_at(segs, n):
    left, right = [], []
    for s in segs:
        if s.special or n <= 0:
            (left if n > 0 else right).append(s)
            continue
        if len(s.text) <= n:
            left.append(s)
            n -= len(s.text)
        else:
            left.append(Seg(s.text[:n], s.b, s.i, s.u, s.sup, s.sub))
            right.append(Seg(s.text[n:], s.b, s.i, s.u, s.sup, s.sub))
            n = 0
    return left, right


def upper(segs):
    return [s if s.special else Seg(s.text.upper(), s.b, s.i, s.u, s.sup, s.sub) for s in segs]


def title_case(segs):
    """HURUF KAPITAL SEMUA → Huruf Awal Kapital (kata tugas tetap kecil)."""
    out, first = [], True
    for s in segs:
        if s.special:
            out.append(s)
            continue
        parts = re.split(r"(\s+)", s.text)
        for k, w in enumerate(parts):
            if not w.strip():
                continue
            low = w.lower()
            if (not first and low.strip("()[],.;:") in STOPWORDS) or re.search(r"\d", w):
                parts[k] = low if not re.search(r"\d", w) else w
            else:
                parts[k] = re.sub(r"[^\W\d_]", lambda m: m.group(0).upper(), low, count=1)
            first = False
        out.append(Seg("".join(parts), s.b, s.i, s.u, s.sup, s.sub))
    return out


def apply_case(rs, segs):
    if rs is None:
        return segs
    if rs.upper:
        return upper(segs)
    text = seg_text(segs)
    if getattr(rs, "title", False) and any(c.isalpha() for c in text) and text == text.upper():
        return title_case(segs)
    return segs


def strip_number(segs):
    """Buang nomor manual di awal judul. Kembalikan (segs, angka-angka atau None)."""
    t = seg_text(segs).lstrip()
    lead = len(seg_text(segs)) - len(t)
    m = BAB_RE.match(t)
    if m and m.group(2).strip():
        g = m.group(1)
        return cut(segs, lead + m.start(2)), [int(g) if g.isdigit() else from_roman(g)]
    m = NUM_HEAD_RE.match(t)
    if m:
        return cut(segs, lead + m.start(3)), [int(x) if x.isdigit() else from_roman(x)
                                              for x in m.group(1).split(".")]
    m = ROMAN_HEAD_RE.match(t)
    if m:
        return cut(segs, lead + m.start(2)), [from_roman(m.group(1))]
    for rx in (ALPHA_HEAD_RE, ALPHA_LOW_HEAD_RE):
        m = rx.match(t)
        if m:
            return cut(segs, lead + m.start(2)), [ord(m.group(1).upper()) - 64]
    return segs, None


def strip_marker(segs):
    t = seg_text(segs).lstrip()
    lead = len(seg_text(segs)) - len(t)
    m = BULLET_RE.match(t) or NUMLIST_RE.match(t)
    if m:
        return cut(segs, lead + m.start(2)), m.group(1)
    return segs, None


# ---------------------------------------------------------------------------
class Renderer:
    def __init__(self, template_bytes, overrides=None):
        self.doc = Document(BytesIO(template_bytes))
        self.profile = analyze(self.doc, overrides)
        self.available = set(self.profile.styles)
        self.body = self.doc.element.body
        self.warnings = set()
        self.counters = [0, 0, 0, 0]
        self.docpr_id = max([int(e.get("id", 0)) for e in self.body.iter(f"{{{WP_NS}}}docPr")
                             if str(e.get("id", "0")).isdigit()] + [0]) + 1000
        self._num_part = None
        self.used_nums = set()
        self.first = True
        self.prev_role = None
        self.cur = None
        self.ctx = None       # judul terakhir (bab/h1/h2/h3) untuk gaya bergantung konteks
        self.origin = {}      # elemen keluaran → (indeks blok naskah, peran gaya)
        ref = next((r for r in self.body.iter(qn("w:r")) if r.find(qn("w:footnoteReference")) is not None), None)
        ref_rpr = ref.find(qn("w:rPr")) if ref is not None else None
        para = self.profile.styles.get("paragraf")
        self.notes = Footnotes(self.doc, deepcopy(ref_rpr) if ref_rpr is not None else None,
                               para.rPr if para is not None else None)

    # ---- dasar ---------------------------------------------------------
    def clear(self):
        for ch in list(self.body):
            if ch.tag != qn("w:sectPr"):
                self.body.remove(ch)
        # komentar dari contoh tidak ikut
        for rid, rel in list(self.doc.part.rels.items()):
            if rel.reltype == RT.COMMENTS:
                self.doc.part.drop_rel(rid)

    def append(self, el):
        sect = self.body.find(qn("w:sectPr"))
        if sect is not None:
            sect.addprevious(el)
        else:
            self.body.append(el)

    def spacing(self, role):
        if self.prev_role is not None:
            n, sp = self.gap(self.prev_role, role)
            for _ in range(n):
                if sp is not None:
                    self.append(deepcopy(sp))
                else:
                    p = OxmlElement("w:p")
                    st = self.profile.styles.get("paragraf")
                    if st is not None and st.pPr is not None:
                        p.append(deepcopy(st.pPr))
                    self.append(p)
        self.prev_role = role

    def gap(self, a, b):
        g = self.profile.gaps
        if (a, b) in g:
            return g[(a, b)]
        cands = [v for (x, y), v in g.items() if y == b]
        if cands and b not in ("paragraf", "abstrak", "pustaka", "daftar"):
            return max(cands, key=lambda v: sum(1 for c in cands if c[0] == v[0]))
        cands = [v for (x, y), v in g.items() if x == a]
        if cands:
            return max(cands, key=lambda v: sum(1 for c in cands if c[0] == v[0]))
        return (0, None)

    # ---- paragraf -------------------------------------------------------
    def para(self, rs, segs, role, page_break=None, num_off=False, num_override=None):
        p = OxmlElement("w:p")
        if rs is not None and rs.pPr is not None:
            p.append(deepcopy(rs.pPr))
        para = Paragraph(p, self.doc._body)
        if page_break is None:
            page_break = self.profile.breaks.get(role, False)
        if page_break and not self.first and not para.paragraph_format.page_break_before:
            para.paragraph_format.page_break_before = True
        if num_off or num_override:
            numPr = p.get_or_add_pPr().get_or_add_numPr()
            if num_override:
                numPr.get_or_add_ilvl().val = num_override[1]
                numPr.get_or_add_numId().val = int(num_override[0])
            else:
                numPr.get_or_add_numId().val = 0
        label = []
        if rs is not None and rs.label_rPr is not None:
            text = seg_text(segs)
            for rx in LABEL_RES:
                m = rx.match(text)
                if m:
                    label, segs = split_at(segs, m.end())
                    break
        self.write_runs(p, label, rs.label_rPr if rs else None)
        self.write_runs(p, segs, rs.rPr if rs else None)
        self.spacing(role)
        self.append(p)
        self.origin[p] = (self.cur, role)
        self.first = False
        return p

    def write_runs(self, p, segs, rPr):
        for s in segs:
            if s.xml is not None:
                el = self.import_xml(s.xml)
                if el is not None:
                    p.append(el)
                continue
            if s.note is not None:
                p.append(self.notes.add(s.note, self.write_runs))
                continue
            if not s.text:
                continue
            r = OxmlElement("w:r")
            if rPr is not None:
                r.append(deepcopy(rPr))
            p.append(r)
            run = Run(r, None)
            run.text = CONTROL_RE.sub("", s.text)
            if s.b:
                run.font.bold = True
            if s.i:
                run.font.italic = True
            if s.u:
                run.font.underline = True
            if s.sup:
                run.font.superscript = True
            elif s.sub:
                run.font.subscript = True

    def import_xml(self, el):
        """Salin run gambar / persamaan dari dokumen sumber, termasuk berkas gambarnya."""
        el = deepcopy(el)
        src = getattr(self, "source", None)
        for node in el.iter():
            for attr in list(node.attrib):
                if not attr.startswith(f"{{{R_NS}}}"):
                    continue
                rid = node.get(attr)
                rel = src.part.rels.get(rid) if src is not None else None
                if rel is None or rel.is_external or rel.reltype != RT.IMAGE:
                    self.warnings.add("Objek selain gambar (grafik/objek tertanam) tidak dapat disalin.")
                    return None
                new_rid, _ = self.doc.part.get_or_add_image(BytesIO(rel.target_part.blob))
                node.set(attr, new_rid)
        for dp in el.iter(f"{{{WP_NS}}}docPr"):
            self.docpr_id += 1
            dp.set("id", str(self.docpr_id))
        return el

    # ---- gaya ----------------------------------------------------------
    def style(self, role):
        r = resolve(role, self.available)
        ctx_rs = self.profile.ctx_styles.get((r, self.ctx)) if r else None
        if ctx_rs is not None:
            return ctx_rs, r
        return (self.profile.styles.get(r) if r else None), (r or role)

    def numbering(self):
        if self._num_part is None:
            self._num_part = self.doc.part.numbering_part.element
        return self._num_part

    def restart_num(self, num):
        """numId baru (abstrak sama) yang mulai lagi dari 1."""
        try:
            numbering = self.numbering()
        except Exception:
            return None
        old = next((n for n in numbering.findall(qn("w:num"))
                    if n.get(qn("w:numId")) == str(num[0])), None)
        if old is None:
            return None
        new = numbering.add_num(int(old.find(qn("w:abstractNumId")).get(qn("w:val"))))
        new.add_lvlOverride(ilvl=num[1]).add_startOverride(1)
        return (new.numId, num[1])

    # ---- judul bernomor -------------------------------------------------
    def heading(self, block, role, segs):
        key = norm_heading(seg_text(segs))
        exact = self.profile.exact.get(key)
        if exact is not None and exact.role == "bab_nama":
            exact = None    # nama bab dicetak lewat bab(), bersama baris "BAB n"
        if exact is not None and exact.role != resolve(role, self.available) \
                and not UNNUMBERED_RE.match(seg_text(segs).strip()):
            # judul bernama sama tetapi beda tingkat (mis. subbab "Latar Belakang" vs bab
            # "LATAR BELAKANG"): tingkat naskah dipertahankan
            exact = None
        rs, used = (exact, exact.role) if exact else self.style(role)
        if role == "bab" or used == "bab":
            return self.bab(block, segs, rs, used, key)
        segs, nums = strip_number(segs)
        if exact is not None:
            unnumbered = not (exact.spec or exact.auto_num)
        else:
            unnumbered = bool(UNNUMBERED_RE.match(seg_text(segs).strip()))
        lvl = LEVEL.get(used, LEVEL.get(role, 1))
        num_off = False
        prefix = ""
        if unnumbered:
            num_off = bool(rs and rs.auto_num)
        else:
            if nums:
                start = max(0, lvl - len(nums) + 1)
                for j, v in enumerate(nums[-(lvl + 1):]):
                    self.counters[start + j] = v
            else:
                self.counters[lvl] += 1
            for j in range(lvl + 1, 4):
                self.counters[j] = 0
            if rs is not None and not rs.auto_num and rs.spec:
                spec = rs.spec
                c = self.counters
                if spec[0] == "d":
                    parts = [str(max(c[j], 1)) for j in range(max(0, lvl - spec[1] + 1), lvl + 1)]
                    if len(spec) > 3 and spec[3]:
                        parts[0] = roman(int(parts[0]))     # I.1, II.2.1
                    prefix = ".".join(parts) + spec[2]
                elif spec[0] == "R":
                    prefix = roman(c[lvl]) + "."
                elif spec[0] == "A":
                    prefix = letter(c[lvl]) + "."
                elif spec[0] == "a":
                    prefix = letter(c[lvl], False) + spec[1]
        segs = apply_case(rs, segs)
        if prefix:
            segs = [Seg(prefix + rs.sep)] + segs
        self.para(rs, segs, used, num_off=num_off)

    def bab(self, block, segs, rs, used, key):
        mode = self.profile.bab_mode
        t = seg_text(segs).strip()
        m = BAB_RE.match(t)
        num = None
        if m:
            g = m.group(1)
            num = int(g) if g.isdigit() else from_roman(g)
            segs = cut(segs, len(seg_text(segs)) - len(seg_text(segs).lstrip()) + m.start(2))
        name = segs if seg_text(segs).strip() else None
        if name is None and block.next_name is not None:
            name = block.next_name
        if "bab" not in self.available:
            # contoh tanpa bab (mis. jurnal): bab naskah menjadi subjudul tingkat 1
            if name is None:
                return
            if num:
                self.counters[1] = num - 1
            return self.heading(block, "h1", name)
        unnumbered = num is None and bool(UNNUMBERED_RE.match(t))
        if not unnumbered:
            self.counters[0] = num if num else self.counters[0] + 1
            self.counters[1:] = [0, 0, 0]
            num = self.counters[0]
        name_rs, _ = self.style("bab_nama") if "bab_nama" in self.available else (rs, used)
        if name is not None:
            name = apply_case(name_rs if name_rs is not None else rs, name)
        roman_style = True
        for b in self.profile.paragraphs:
            if b["role"] == "bab":
                mm = BAB_RE.match(b["text"])
                if mm:
                    roman_style = not mm.group(1).isdigit()
                    break
        label = f"BAB {roman(num) if roman_style else num}" if num else None
        if mode == "plain":
            self.para(rs, name or [Seg(label or "")], used)
        elif mode == "auto" or used != "bab":
            self.para(rs, name or [Seg(label or "")], used, num_off=unnumbered and bool(rs and rs.auto_num))
        elif unnumbered or label is None:
            self.para(rs, name or [], used)
        elif mode == "merged":
            self.para(rs, [Seg(label + "\n")] + (name or []), used)
        elif mode == "inline":
            self.para(rs, [Seg(label + self.profile.bab_sep)] + (name or []), used)
        else:
            self.para(rs, [Seg(label)], used)
            if name:
                self.para(name_rs, name, "bab_nama")

    # ---- daftar ----------------------------------------------------------
    def list_item(self, block, segs, state):
        kind = list_kind(block.item)
        rs = self.profile.ctx_lists.get((kind, self.ctx)) or self.profile.lists.get(kind)
        variant = rs is None
        if rs is None:
            rs = next(iter(self.profile.lists.values()), None) or self.style("daftar")[0]
        segs, marker = strip_marker(segs)
        if state.get("kind") != kind:
            state.clear()
            state.update(kind=kind, n=0, num=None)
        state["n"] += 1
        override = None
        if rs is not None and rs.auto_num:
            # contoh hanya punya daftar berbutir (atau hanya bernomor): pakai indentasinya,
            # tetapi buat definisi penomoran baru dengan jenis yang sesuai naskah
            base = self.list_variant(rs.num, kind) if variant else rs.num
            if base is not None and (kind == "number" or variant):
                if state["num"] is None:
                    if base[0] in self.used_nums and kind == "number":
                        state["num"] = self.restart_num(base)
                    else:
                        state["num"] = base
                        self.used_nums.add(base[0])
                override = state["num"]
            ilvl = block.item.num[1] if block.item.num else 0
            if ilvl and override:
                override = (override[0], ilvl)
        else:
            mk = rs.marker if rs is not None and rs.marker else None
            if kind == "number":
                if not mk or BULLET_RE.match(mk + " "):
                    mk = "1."
                n = state["n"]
                if re.match(r"^\(?\d", mk):
                    mk = re.sub(r"\d+", str(n), mk, count=1)
                elif re.match(r"^\(?[a-z]", mk):
                    mk = re.sub(r"[a-z]", letter(n, False), mk, count=1)
                elif re.match(r"^\(?[A-Z]", mk):
                    mk = re.sub(r"[A-Z]", letter(n), mk, count=1)
            elif not mk or not BULLET_RE.match(mk + " "):
                mk = marker if marker and BULLET_RE.match(marker + " ") else "•"
            sep = rs.sep if rs is not None and rs.marker else "\t" if rs is not None and (
                rs.summary.get("first_line") or 0) < 0 else " "
            segs = [Seg(mk + sep)] + segs
        self.para(rs, segs, "daftar", num_override=override)

    def list_variant(self, num, kind):
        """numId baru yang meniru definisi `num` tetapi berjenis bullet/angka."""
        key = (num, kind)
        cache = self.__dict__.setdefault("_variants", {})
        if key in cache:
            return cache[key]
        try:
            numbering = self.numbering()
        except Exception:
            return None
        old = next((n for n in numbering.findall(qn("w:num")) if n.get(qn("w:numId")) == str(num[0])), None)
        if old is None:
            return None
        aid = old.find(qn("w:abstractNumId")).get(qn("w:val"))
        absn = next((a for a in numbering.findall(qn("w:abstractNum"))
                     if a.get(qn("w:abstractNumId")) == aid), None)
        if absn is None:
            return None
        new_abs = deepcopy(absn)
        ids = [int(a.get(qn("w:abstractNumId"))) for a in numbering.findall(qn("w:abstractNum"))]
        new_id = max(ids + [0]) + 1
        new_abs.set(qn("w:abstractNumId"), str(new_id))
        for tag in ("w:nsid", "w:tmpl", "w:numStyleLink", "w:styleLink"):
            for x in new_abs.findall(qn(tag)):
                new_abs.remove(x)
        for lvl in new_abs.findall(qn("w:lvl")):
            n = int(lvl.get(qn("w:ilvl"), "0"))
            fmt, txt = lvl.find(qn("w:numFmt")), lvl.find(qn("w:lvlText"))
            if fmt is None or txt is None:
                continue
            if kind == "number":
                fmt.set(qn("w:val"), ("decimal", "lowerLetter", "lowerRoman")[n % 3])
                txt.set(qn("w:val"), f"%{n + 1}.")
                rpr = lvl.find(qn("w:rPr"))
                if rpr is not None:
                    lvl.remove(rpr)
            else:
                fmt.set(qn("w:val"), "bullet")
                txt.set(qn("w:val"), "•–◦"[n % 3])
        numbering.findall(qn("w:abstractNum"))[-1].addnext(new_abs)
        new = numbering.add_num(new_id)
        cache[key] = (new.numId, num[1])
        return cache[key]

    # ---- tabel -----------------------------------------------------------
    def table(self, block):
        tp = self.profile.table
        self.spacing("tabel")
        if block.tbl is not None:
            tbl = self.import_table(block)
        else:
            tbl = self.text_table(block.rows)
        if tp.get("tblPr") is not None:
            old = tbl.find(qn("w:tblPr"))
            new = deepcopy(tp["tblPr"])
            if old is not None:
                old.addprevious(new)
                tbl.remove(old)
            else:
                tbl.insert(0, new)
        self.append(tbl)
        self.origin[tbl] = (self.cur, "tabel")
        self.first = False

    def _fill_cell(self, tc, paras_segs, head):
        tp = self.profile.table
        rs = tp.get("head" if head else "body") or self.style("paragraf")[0]
        for p in tc.findall(qn("w:p")):
            tc.remove(p)
        extra = tp.get(("head" if head else "body") + "_tc")
        if extra:
            tcPr = tc.get_or_add_tcPr() if hasattr(tc, "get_or_add_tcPr") else tc.find(qn("w:tcPr"))
            if tcPr is not None:
                for c in extra:
                    insert_ordered(tcPr, deepcopy(c), TCPR_ORDER)
        for segs in paras_segs or [[]]:
            saved = self.append
            self.append = tc.append
            prev, first = self.prev_role, self.first
            self.prev_role, self.first = None, True
            self.para(rs, segs, "tabel", page_break=False)
            self.prev_role, self.first = prev, first
            self.append = saved

    def ensure_style(self, sid):
        """Salin definisi gaya `sid` (beserta induknya) dari naskah bila contoh tidak memilikinya."""
        styles = self.doc.styles.element
        have = {x.get(qn("w:styleId")) for x in styles.findall(qn("w:style"))}
        src = getattr(self, "source", None)
        while sid and sid not in have and src is not None:
            el = next((x for x in src.styles.element.findall(qn("w:style"))
                       if x.get(qn("w:styleId")) == sid), None)
            if el is None:
                return False
            styles.append(deepcopy(el))
            have.add(sid)
            based = el.find(qn("w:basedOn"))
            sid = based.get(qn("w:val")) if based is not None else None
        return True

    def import_table(self, block):
        tbl = deepcopy(block.tbl)
        if self.profile.table.get("tblPr") is None:
            tblPr = tbl.find(qn("w:tblPr"))
            ts = tblPr.find(qn("w:tblStyle")) if tblPr is not None else None
            ok = ts is not None and self.ensure_style(ts.get(qn("w:val")))
            borders = tblPr is not None and tblPr.find(qn("w:tblBorders")) is not None
            if not ok and not borders and tblPr is not None:
                if ts is not None:
                    tblPr.remove(ts)
                insert_ordered(tblPr, self.grid_borders(), TBLPR_ORDER)
        for r, tr in enumerate(tbl.findall(qn("w:tr"))):
            for c, tc in enumerate(tr.findall(qn("w:tc"))):
                try:
                    content = block.cells[r][c]
                except IndexError:
                    content = []
                for nested in tc.findall(qn("w:tbl")):
                    tc.remove(nested)
                self._fill_cell(tc, content, r == 0)
        return tbl

    @staticmethod
    def grid_borders():
        borders = OxmlElement("w:tblBorders")
        for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
            b = OxmlElement(f"w:{side}")
            b.set(qn("w:val"), "single")
            b.set(qn("w:sz"), "4")
            b.set(qn("w:space"), "0")
            b.set(qn("w:color"), "000000")
            borders.append(b)
        return borders

    def text_table(self, rows):
        ncols = max(len(r) for r in rows)
        t = self.doc.add_table(rows=len(rows), cols=ncols)
        tbl = t._tbl
        tbl.getparent().remove(tbl)
        if self.profile.table.get("tblPr") is None:
            insert_ordered(tbl.tblPr, self.grid_borders(), TBLPR_ORDER)
        for r, row in enumerate(rows):
            for c in range(ncols):
                tc = t.cell(r, c)._tc
                self._fill_cell(tc, [row[c]] if c < len(row) else [[]], r == 0)
        return tbl

    # ---- utama -----------------------------------------------------------
    def render(self, content):
        self.source = content.source
        self.warnings.update(content.warnings)
        self.clear()
        order = [i for i, b in enumerate(content.blocks) if b.role != "abaikan"]
        blocks = [content.blocks[i] for i in order]
        # gabungkan "BAB I" + nama bab berikutnya
        for b in blocks:
            b.next_name = None
        skip = set()
        for k, b in enumerate(blocks):
            if b.role == "bab" and k + 1 < len(blocks) and blocks[k + 1].role == "bab_nama":
                m = BAB_RE.match(b.text.strip())
                if m and not m.group(2).strip():
                    b.next_name = blocks[k + 1].segs
                    skip.add(k + 1)
        list_state = {}
        title = None
        # naskah ber-BAB pada contoh tanpa bab: turunkan subjudul satu tingkat
        shift = "bab" not in self.available and any(b.role in ("bab", "bab_nama") for b in blocks)
        for k, b in enumerate(blocks):
            if k in skip:
                continue
            self.cur = order[k]
            role = b.role or "paragraf"
            if role != "daftar":
                list_state = {}
            if b.kind == "table":
                self.table(b)
                continue
            segs = [s for s in b.segs]
            if seg_text(segs).strip() == "" and not any(s.special for s in segs):
                continue
            if role == "judul" and title is None:
                title = seg_text(segs).strip()
            if shift:
                role = {"h1": "h2", "h2": "h3"}.get(role, role)
            if role in ("bab", "bab_nama", "h1", "h2", "h3"):
                self.ctx = "bab" if role in ("bab", "bab_nama") else role
                if role == "bab_nama":
                    rs, used = self.style("bab_nama")
                    self.para(rs, apply_case(rs, segs), used)
                else:
                    self.heading(b, role, segs)
            elif role == "daftar":
                self.list_item(b, segs, list_state)
            else:
                rs, used = self.style(role)
                self.para(rs, apply_case(rs, segs), used)
        if title:
            self.doc.core_properties.title = title[:250]
        return self.save()

    def save(self):
        self.notes.flush()
        out = BytesIO()
        self.doc.save(out)
        return out.getvalue()


def render(template_bytes, content, overrides=None):
    r = Renderer(template_bytes, overrides)
    data = r.render(content)
    return data, sorted(r.warnings)
