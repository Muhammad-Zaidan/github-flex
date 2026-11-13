"""Menghitung properti format efektif (gaya + format langsung) sebuah paragraf."""

from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import qn
from lxml import etree

ALIGN = {
    "left": "left", "start": "left", "center": "center", "right": "right", "end": "right",
    "both": "justify", "distribute": "justify", "lowKashida": "justify",
    "mediumKashida": "justify", "highKashida": "justify", "thaiDistribute": "justify",
}
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def on(el):
    """Nilai elemen toggle OOXML (<w:b/>, <w:i w:val="0"/> ...)."""
    if el is None:
        return None
    return el.get(qn("w:val")) not in ("0", "false", "off", "none")


def _num(el, attr):
    v = el.get(qn(attr)) if el is not None else None
    try:
        return int(float(v)) if v is not None else None
    except ValueError:
        return None


class StyleResolver:
    def __init__(self, document):
        self.document = document
        root = document.styles.element
        self.styles = {}
        for s in root.findall(qn("w:style")):
            name = s.find(qn("w:name"))
            based = s.find(qn("w:basedOn"))
            sid = s.get(qn("w:styleId"))
            self.styles[sid] = {
                "type": s.get(qn("w:type")),
                "name": name.get(qn("w:val")) if name is not None else sid,
                "based": based.get(qn("w:val")) if based is not None else None,
                "pPr": s.find(qn("w:pPr")),
                "rPr": s.find(qn("w:rPr")),
                "default": s.get(qn("w:default")) in ("1", "true"),
            }
        self.default_para = next(
            (k for k, s in self.styles.items() if s["type"] == "paragraph" and s["default"]), None)
        dd = root.find(qn("w:docDefaults"))
        self.def_ppr = dd.find(f"{qn('w:pPrDefault')}/{qn('w:pPr')}") if dd is not None else None
        self.def_rpr = dd.find(f"{qn('w:rPrDefault')}/{qn('w:rPr')}") if dd is not None else None
        self.theme = self._theme_fonts()
        self._cache = {}
        self._numbering = self._load_numbering()

    # ---- tema & penomoran -------------------------------------------------
    def _theme_fonts(self):
        fonts = {"major": None, "minor": None}
        for rel in self.document.part.rels.values():
            if rel.reltype == RT.THEME and not rel.is_external:
                try:
                    root = etree.fromstring(rel.target_part.blob)
                except etree.XMLSyntaxError:
                    break
                for key in fonts:
                    el = root.find(f".//{{{A_NS}}}{key}Font/{{{A_NS}}}latin")
                    if el is not None:
                        fonts[key] = el.get("typeface")
        return fonts

    def _load_numbering(self):
        try:
            numbering = self.document.part.numbering_part.element
        except (NotImplementedError, KeyError, AttributeError):
            return None
        abstract = {}
        for a in numbering.findall(qn("w:abstractNum")):
            lvls = {}
            for lvl in a.findall(qn("w:lvl")):
                fmt = lvl.find(qn("w:numFmt"))
                txt = lvl.find(qn("w:lvlText"))
                lvls[_num(lvl, "w:ilvl") or 0] = (
                    fmt.get(qn("w:val")) if fmt is not None else "decimal",
                    txt.get(qn("w:val")) if txt is not None else "")
            abstract[a.get(qn("w:abstractNumId"))] = lvls
        nums = {}
        for n in numbering.findall(qn("w:num")):
            aid = n.find(qn("w:abstractNumId"))
            if aid is not None:
                nums[n.get(qn("w:numId"))] = aid.get(qn("w:val"))
        return {"abstract": abstract, "nums": nums}

    def num_info(self, num_id, ilvl=0):
        """(abstractNumId, numFmt, lvlText) untuk sebuah numId, atau None."""
        if not self._numbering or num_id in (None, "0"):
            return None
        aid = self._numbering["nums"].get(str(num_id))
        if aid is None:
            return None
        fmt, text = self._numbering["abstract"].get(aid, {}).get(ilvl or 0, ("decimal", ""))
        return aid, fmt, text

    # ---- gaya -------------------------------------------------------------
    def chain(self, sid):
        out, seen = [], set()
        while sid and sid in self.styles and sid not in seen:
            seen.add(sid)
            out.append(sid)
            sid = self.styles[sid]["based"]
        return out[::-1]

    def style_name(self, sid):
        s = self.styles.get(sid)
        return s["name"] if s else (sid or "")

    def style_props(self, sid):
        if sid in self._cache:
            return self._cache[sid]
        props = {}
        self.apply_ppr(props, self.def_ppr)
        self.apply_rpr(props, self.def_rpr)
        for s in self.chain(sid):
            self.apply_ppr(props, self.styles[s]["pPr"])
            self.apply_rpr(props, self.styles[s]["rPr"])
        self._cache[sid] = props
        return props

    def para_style_id(self, p):
        pPr = p.find(qn("w:pPr"))
        ps = pPr.find(qn("w:pStyle")) if pPr is not None else None
        return ps.get(qn("w:val")) if ps is not None else self.default_para

    def para_base(self, p):
        """Properti paragraf tanpa format karakter dari run."""
        sid = self.para_style_id(p)
        props = dict(self.style_props(sid))
        self.apply_ppr(props, p.find(qn("w:pPr")))
        props["style_id"] = sid
        props["style_name"] = self.style_name(sid)
        return props

    def run_props(self, base, r):
        props = dict(base)
        rPr = r.find(qn("w:rPr"))
        if rPr is not None:
            rs = rPr.find(qn("w:rStyle"))
            if rs is not None:
                for s in self.chain(rs.get(qn("w:val"))):
                    self.apply_rpr(props, self.styles[s]["rPr"])
            self.apply_rpr(props, rPr)
        return props

    def para_props(self, p):
        """Properti efektif paragraf, termasuk karakter dari run teks pertama."""
        base = self.para_base(p)
        for r in p.iter(qn("w:r")):
            if r.find(qn("w:t")) is not None and "".join(t.text or "" for t in r.findall(qn("w:t"))).strip():
                return self.run_props(base, r)
        return base

    # ---- penerapan properti ------------------------------------------------
    def apply_ppr(self, props, pPr):
        if pPr is None:
            return
        jc = pPr.find(qn("w:jc"))
        if jc is not None:
            props["align"] = ALIGN.get(jc.get(qn("w:val")), "left")
        ind = pPr.find(qn("w:ind"))
        if ind is not None:
            for attr, key in (("w:left", "ind_left"), ("w:start", "ind_left"),
                              ("w:right", "ind_right"), ("w:end", "ind_right")):
                v = _num(ind, attr)
                if v is not None:
                    props[key] = v / 567
            fl, hg = _num(ind, "w:firstLine"), _num(ind, "w:hanging")
            if hg is not None:
                props["first_line"] = -hg / 567
            elif fl is not None:
                props["first_line"] = fl / 567
        sp = pPr.find(qn("w:spacing"))
        if sp is not None:
            for attr, key in (("w:before", "before"), ("w:after", "after")):
                v = _num(sp, attr)
                if v is not None:
                    props[key] = v / 20
            line = _num(sp, "w:line")
            if line is not None:
                rule = sp.get(qn("w:lineRule")) or "auto"
                if rule == "auto":
                    props["line_mult"], props["line_pt"] = line / 240, None
                else:
                    props["line_mult"], props["line_pt"] = None, line / 20
        ol = pPr.find(qn("w:outlineLvl"))
        if ol is not None:
            props["outline"] = _num(ol, "w:val")
        numPr = pPr.find(qn("w:numPr"))
        if numPr is not None:
            nid = numPr.find(qn("w:numId"))
            lvl = numPr.find(qn("w:ilvl"))
            nid = nid.get(qn("w:val")) if nid is not None else props.get("num", (None, 0))[0]
            props["num"] = (nid, _num(lvl, "w:val") or 0) if nid not in (None, "0") else None
        for tag, key in (("w:pageBreakBefore", "page_break_before"), ("w:keepNext", "keep_next")):
            v = on(pPr.find(qn(tag)))
            if v is not None:
                props[key] = v

    def apply_rpr(self, props, rPr):
        if rPr is None:
            return
        rf = rPr.find(qn("w:rFonts"))
        if rf is not None:
            font = rf.get(qn("w:ascii")) or rf.get(qn("w:hAnsi"))
            theme = rf.get(qn("w:asciiTheme")) or rf.get(qn("w:hAnsiTheme"))
            if theme and not font:
                font = self.theme.get("major" if theme.startswith("major") else "minor")
            if font:
                props["font"] = font
        sz = rPr.find(qn("w:sz"))
        if sz is not None and _num(sz, "w:val"):
            props["size"] = _num(sz, "w:val") / 2
        for tag, key in (("w:b", "bold"), ("w:i", "italic"), ("w:caps", "caps"),
                         ("w:smallCaps", "small_caps"), ("w:u", "underline")):
            v = on(rPr.find(qn(tag)))
            if v is not None:
                props[key] = v
        color = rPr.find(qn("w:color"))
        if color is not None and color.get(qn("w:val")) not in (None, "auto"):
            props["color"] = color.get(qn("w:val"))
        va = rPr.find(qn("w:vertAlign"))
        if va is not None:
            props["vert"] = va.get(qn("w:val"))


def summary(props):
    """Ringkasan properti untuk pratinjau di browser (satuan pt dan cm)."""
    keys = ("font", "size", "bold", "italic", "caps", "small_caps", "underline", "color",
            "align", "ind_left", "ind_right", "first_line", "before", "after",
            "line_mult", "line_pt")
    out = {k: props.get(k) for k in keys}
    out["size"] = out["size"] or 11
    out["align"] = out["align"] or "left"
    for k in ("ind_left", "ind_right", "first_line", "before", "after", "line_mult", "line_pt"):
        if isinstance(out[k], float):
            out[k] = round(out[k], 2)
    return out
