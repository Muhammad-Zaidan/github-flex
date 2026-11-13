"""Membaca tulisan masukan (teks polos atau .docx berantakan) menjadi blok-blok."""

import re
from dataclasses import dataclass, field
from io import BytesIO

from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import parse_xml
from docx.oxml.ns import qn

from .classify import BULLET_RE, NUMLIST_RE, Item, classify
from .styles import StyleResolver

M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
INLINE_RE = re.compile(r"\*\*(.+?)\*\*|\*([^*\s](?:[^*]*?[^*\s])?)\*|\[\^([^\]\s]+)\]|\^([^^\s]+)\^|~([^~\s]+)~")
NOTE_DEF_RE = re.compile(r"^\[\^([^\]\s]+)\]:\s*(.*)$")
MD_HEAD_RE = re.compile(r"^(#{1,6})\s+(.*)$")
PIPE_SEP_RE = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$")


@dataclass
class Seg:
    text: str = ""
    b: bool = False
    i: bool = False
    u: bool = False
    sup: bool = False
    sub: bool = False
    xml: object = None      # elemen run berisi gambar, atau persamaan (m:oMath)
    note: list = None       # catatan kaki: daftar paragraf, tiap paragraf daftar Seg

    @property
    def special(self):
        return self.xml is not None or self.note is not None


@dataclass
class Block:
    kind: str = "p"                     # 'p' atau 'table'
    segs: list = field(default_factory=list)
    item: Item = field(default_factory=Item)
    rows: list = None                   # tabel teks: [[ [Seg], ...], ...]
    tbl: object = None                  # tabel docx asli (elemen w:tbl)
    cells: list = None                  # isi tiap sel tbl: [[ [ [Seg] per paragraf ] ]]
    role: str = None
    auto_role: str = None

    @property
    def text(self):
        return "".join(s.text for s in self.segs)


@dataclass
class Content:
    blocks: list
    source: object = None               # Document sumber (untuk relasi gambar)
    warnings: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# teks polos
# ---------------------------------------------------------------------------
def inline(text, notes=None):
    """Teks dengan penanda **tebal**, *miring*, ^atas^, ~bawah~, [^1] → daftar Seg."""
    segs, pos = [], 0
    for m in INLINE_RE.finditer(text):
        b, i, ref, sup, sub = m.groups()
        if ref is not None and (notes is None or ref not in notes):
            continue
        if m.start() > pos:
            segs.append(Seg(text[pos:m.start()]))
        if ref is not None:
            segs.append(Seg(note=[inline(notes[ref])]))
        elif b is not None:
            segs.extend(s if s.special else Seg(s.text, b=True, i=s.i, sup=s.sup, sub=s.sub)
                        for s in inline(b, notes))
        elif i is not None:
            segs.append(Seg(i, i=True))
        elif sup is not None:
            segs.append(Seg(sup, sup=True))
        else:
            segs.append(Seg(sub, sub=True))
        pos = m.end()
    if pos < len(text):
        segs.append(Seg(text[pos:]))
    return segs


def _starts_block(line):
    from .classify import BAB_RE, BULLET_RE, CAPTION_RE, NUMLIST_RE, NUM_HEAD_RE
    s = line.strip()
    return bool(MD_HEAD_RE.match(s) or BAB_RE.match(s) or BULLET_RE.match(s) or NUMLIST_RE.match(s)
                or NUM_HEAD_RE.match(s) or CAPTION_RE.match(s) or s.startswith(("|", ">")))


def _split_cells(line):
    if "\t" in line:
        return [c.strip() for c in line.split("\t")]
    return [c.strip() for c in line.strip().strip("|").split("|")]


CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ufffe\uffff]")


def parse_text(text, merge_lines=False, available=None):
    text = CONTROL_RE.sub("", text.replace("\u2028", "\n").replace("\u2029", "\n"))
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    notes = {}
    for k, line in enumerate(lines):
        m = NOTE_DEF_RE.match(line.strip())
        if m:
            notes[m.group(1)] = m.group(2).strip()
            lines[k] = ""
    raw = []          # (jenis, isi)
    k = 0
    fence = False
    while k < len(lines):
        line = lines[k].rstrip()
        s = line.strip()
        if s.startswith("```"):
            fence = not fence
            k += 1
            continue
        if fence:                           # kode program: spasi awal dipertahankan
            raw.append(("code", line or "\u00a0"))
            k += 1
            continue
        if not s:
            raw.append(("blank", None))
            k += 1
            continue
        # tabel: baris ber-tab (tempelan dari Word/Excel) atau tabel pipa Markdown
        is_tab = "\t" in s
        is_pipe = s.startswith("|") and s.endswith("|") and s.count("|") >= 3
        if is_tab or is_pipe:
            j = k
            rows = []
            while j < len(lines):
                t = lines[j].strip()
                if is_tab and "\t" in t:
                    rows.append(_split_cells(lines[j].strip("\n")))
                elif is_pipe and t.startswith("|") and t.count("|") >= 2:
                    if not PIPE_SEP_RE.match(t):
                        rows.append(_split_cells(t))
                else:
                    break
                j += 1
            if len(rows) >= 2:
                width = max(len(r) for r in rows)
                rows = [r + [""] * (width - len(r)) for r in rows]
                raw.append(("table", rows))
                k = j
                continue
        if merge_lines and raw and raw[-1][0] == "p" and not _starts_block(s):
            prev = raw[-1][1]
            if prev.endswith("-") and s[:1].islower():
                raw[-1] = ("p", prev[:-1] + s)
            else:
                raw[-1] = ("p", prev + " " + s)
        elif line[:1] == "\t" or line[:2] == "  " and raw and raw[-1][0] in ("p", "lanjut") and (
                raw[-1][0] == "lanjut" or BULLET_RE.match(raw[-1][1]) or NUMLIST_RE.match(raw[-1][1])):
            raw.append(("lanjut", s))       # baris menjorok setelah butir: lanjutan butir
        else:
            raw.append(("p", s))
        k += 1

    blocks = []
    for kind, val in raw:
        if kind == "blank":
            continue
        if kind == "code":
            blocks.append(Block(segs=[Seg(val)], item=Item(text=val, forced="kode")))
            continue
        if kind == "table":
            rows = [[inline(c, notes) for c in r] for r in val]
            blocks.append(Block(kind="table", rows=rows, role="tabel", auto_role="tabel",
                                item=Item(text=" | ".join(val[0]), forced="tabel")))
            continue
        item = Item(text=val, forced="lanjutan" if kind == "lanjut" else None)
        body = val
        m = MD_HEAD_RE.match(val)
        if m:
            body = m.group(2).strip()
            item = Item(text=body, forced="heading", forced_level=len(m.group(1)))
        elif val.startswith(">"):
            body = val.lstrip("> ").strip()
            item = Item(text=body, forced="kutipan")
        segs = inline(body, notes)
        item.text = "".join(sg.text for sg in segs)
        blocks.append(Block(segs=segs, item=item))
    warnings = _classify_blocks(blocks, available)
    return Content(blocks=blocks, warnings=warnings)


def _classify_blocks(blocks, available):
    paras = [b for b in blocks if b.kind == "p"]
    roles = classify([b.item for b in paras], available)
    roles = align_levels([b.item for b in paras], roles, available)
    for b, r in zip(paras, roles):
        b.role = b.auto_role = r or "paragraf"
    toc = sum(1 for b in paras if b.item.extra.get("toc"))
    if toc:
        return [f"{toc} baris daftar isi/daftar tabel dilewati; buat ulang daftar isi di Word "
                "(References → Table of Contents)."]
    return []


def align_levels(items, roles, available):
    """Samakan hierarki judul naskah dengan contoh.

    Contoh skripsi punya BAB, naskah tidak (mis. Heading 1 "Pendahuluan"): naikkan
    setiap tingkat satu langkah, h1 → bab, h2 → h1, dst. Tidak dilakukan bila judul
    tingkat satu naskah sudah bernomor bertingkat seperti "1.1".
    """
    if not available or "bab" not in available or any(r in ("bab", "bab_nama") for r in roles):
        return roles
    h1 = [it.text.strip() for it, r in zip(items, roles) if r == "h1"]
    if not h1 or any(re.match(r"^\d{1,2}\.\d", t) for t in h1):
        return roles
    shift = {"h1": "bab", "h2": "h1", "h3": "h2"}
    return [shift.get(r, r) for r in roles]


# ---------------------------------------------------------------------------
# .docx
# ---------------------------------------------------------------------------
def _run_segs(r, res, base, out, warnings, notes=None):
    props = res.run_props(base, r)
    fmt = dict(b=bool(props.get("bold")), i=bool(props.get("italic")),
               u=bool(props.get("underline")), sup=props.get("vert") == "superscript",
               sub=props.get("vert") == "subscript")
    buf = []

    def flush():
        if buf:
            out.append(Seg("".join(buf), **fmt))
            buf.clear()

    for ch in r:
        tag = ch.tag
        if tag == qn("w:t"):
            buf.append(ch.text or "")
        elif tag == qn("w:tab") or tag == qn("w:ptab"):
            buf.append("\t")
        elif tag in (qn("w:br"), qn("w:cr")):
            if ch.get(qn("w:type")) not in ("page", "column"):
                buf.append("\n")
        elif tag == qn("w:noBreakHyphen"):
            buf.append("‑")
        elif tag == qn("w:softHyphen"):
            pass
        elif tag == qn("w:sym"):
            code = ch.get(qn("w:char"))
            try:
                buf.append(chr(int(code, 16) - 0xF000 if int(code, 16) >= 0xF000 else int(code, 16)))
            except (TypeError, ValueError):
                pass
        elif tag in (qn("w:drawing"), qn("w:pict"), qn("w:object")):
            flush()
            out.append(Seg(xml=r))
            return
        elif tag in (qn("w:footnoteReference"), qn("w:endnoteReference")):
            kind = "foot" if tag == qn("w:footnoteReference") else "end"
            note = (notes or {}).get((kind, ch.get(qn("w:id"))))
            if note is None:
                continue
            if kind == "end":
                warnings.add("Catatan akhir (endnote) diubah menjadi catatan kaki.")
            flush()
            paras = [_para_segs(np_, res, warnings) for np_ in note.findall(qn("w:p"))]
            if paras and paras[0] and not paras[0][0].special:
                f = paras[0][0]
                paras[0][0] = Seg(f.text.lstrip(), f.b, f.i, f.u, f.sup, f.sub)
            out.append(Seg(note=[ps for ps in paras if "".join(x.text for x in ps).strip()] or [[]]))
    flush()


def _para_segs(p, res, warnings, notes=None):
    base = res.para_base(p)
    out = []

    def walk(el):
        for ch in el:
            tag = ch.tag
            if tag == qn("w:r"):
                _run_segs(ch, res, base, out, warnings, notes)
            elif tag in (qn("w:hyperlink"), qn("w:smartTag"), qn("w:ins"), qn("w:fldSimple"),
                         qn("w:customXml"), qn("w:moveTo")):
                walk(ch)
            elif tag == qn("w:sdt"):
                c = ch.find(qn("w:sdtContent"))
                if c is not None:
                    walk(c)
            elif tag in (f"{{{M_NS}}}oMath", f"{{{M_NS}}}oMathPara"):
                out.append(Seg(xml=ch))
    walk(p)
    # tebal/miring yang menutupi seluruh paragraf adalah format paragraf, bukan penekanan
    text_segs = [s for s in out if not s.special and s.text.strip()]
    for attr in ("b", "i", "u"):
        if text_segs and all(getattr(s, attr) for s in text_segs):
            for s in out:
                setattr(s, attr, False)
    merged = []
    for s in out:
        if merged and not s.special and not merged[-1].special and \
                (s.b, s.i, s.u, s.sup, s.sub) == (merged[-1].b, merged[-1].i, merged[-1].u,
                                                 merged[-1].sup, merged[-1].sub):
            merged[-1] = Seg(merged[-1].text + s.text, s.b, s.i, s.u, s.sup, s.sub)
        else:
            merged.append(s)
    return merged


def para_text(p):
    """Teks paragraf termasuk tab dan ganti baris (tanpa teks instruksi field)."""
    out = []
    for el in p.iter(qn("w:t"), qn("w:tab"), qn("w:br"), qn("w:cr")):
        if el.tag == qn("w:t"):
            out.append(el.text or "")
        elif el.tag == qn("w:tab"):
            if el.getparent().tag == qn("w:r"):
                out.append("\t")
        elif el.get(qn("w:type")) not in ("page", "column"):
            out.append("\n")
    return "".join(out)


def para_item(p, res):
    props = res.para_props(p)
    text = para_text(p)
    has_drawing = any(True for _ in p.iter(qn("w:drawing"))) or any(True for _ in p.iter(qn("w:pict")))
    num = props.get("num")
    fmt = None
    if num:
        info = res.num_info(num[0], num[1])
        fmt = info[1] if info else None
    return Item(text=text, props=props, style_name=props.get("style_name", ""),
                has_drawing=has_drawing, num=num, num_fmt=fmt)


def _is_toc(sdt):
    gal = sdt.find(f"{qn('w:sdtPr')}/{qn('w:docPartObj')}/{qn('w:docPartGallery')}")
    return gal is not None and "content" in (gal.get(qn("w:val")) or "").lower()


def _load_notes(doc):
    notes = {}
    for rel in doc.part.rels.values():
        if rel.is_external or rel.reltype not in (RT.FOOTNOTES, RT.ENDNOTES):
            continue
        kind = "foot" if rel.reltype == RT.FOOTNOTES else "end"
        try:
            root = parse_xml(rel.target_part.blob)
        except Exception:
            continue
        for n in root:
            if n.get(qn("w:type")) in (None, "normal"):
                notes[(kind, n.get(qn("w:id")))] = n
    return notes


def parse_docx(data, available=None):
    doc = Document(BytesIO(data))
    res = StyleResolver(doc)
    blocks, warnings = [], set()
    notes = _load_notes(doc)

    def visit(container):
        for el in container:
            if el.tag == qn("w:p"):
                item = para_item(el, res)
                segs = _para_segs(el, res, warnings, notes)
                if item.empty and not any(s.special for s in segs):
                    continue
                if any(s.xml is not None for s in segs) and not item.text.strip():
                    item.has_drawing = True
                blocks.append(Block(segs=segs, item=item))
            elif el.tag == qn("w:tbl"):
                cells = []
                for tr in el.findall(qn("w:tr")):
                    row = []
                    for tc in tr.findall(qn("w:tc")):
                        row.append([_para_segs(p, res, warnings, notes) for p in tc.findall(qn("w:p"))])
                    cells.append(row)
                first = " | ".join("".join(s.text for s in c[0]) if c else "" for c in cells[0]) if cells else ""
                blocks.append(Block(kind="table", tbl=el, cells=cells, role="tabel", auto_role="tabel",
                                    item=Item(text=first, forced="tabel")))
            elif el.tag == qn("w:sdt"):
                if _is_toc(el):
                    warnings.add("Daftar isi otomatis di naskah dilewati; perbarui daftar isi di Word.")
                    continue
                c = el.find(qn("w:sdtContent"))
                if c is not None:
                    visit(c)

    visit(doc.element.body)
    warnings.update(_classify_blocks(blocks, available))
    return Content(blocks=blocks, source=doc, warnings=sorted(warnings))
