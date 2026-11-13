"""Pratinjau cepat: dokumen hasil diubah menjadi JSON yang dirender browser."""

from collections import defaultdict

from docx.oxml.ns import qn

from .reader import para_text
from .render import letter, roman
from .styles import StyleResolver, summary


def _fmt_num(n, fmt):
    if fmt == "upperRoman":
        return roman(n)
    if fmt == "lowerRoman":
        return roman(n).lower()
    if fmt == "upperLetter":
        return letter(n)
    if fmt == "lowerLetter":
        return letter(n, False)
    if fmt == "bullet":
        return "•"
    if fmt == "none":
        return ""
    return str(n)


class _Numberer:
    """Meniru penomoran otomatis Word secukupnya untuk pratinjau."""

    def __init__(self, res):
        self.res = res
        self.count = defaultdict(lambda: [0] * 9)

    def label(self, num):
        num_id, ilvl = num
        info = self.res._numbering
        if not info:
            return ""
        aid = info["nums"].get(str(num_id))
        levels = info["abstract"].get(aid, {})
        if not levels:
            return ""
        c = self.count[aid]
        c[ilvl] += 1
        for j in range(ilvl + 1, 9):
            c[j] = 0
        fmt, text = levels.get(ilvl, ("decimal", "%1."))
        if fmt == "bullet":
            return "•"
        out = text
        for j in range(ilvl + 1):
            f = levels.get(j, ("decimal", ""))[0]
            out = out.replace(f"%{j + 1}", _fmt_num(max(c[j], 1), f))
        return out


def _runs(p, res, base):
    out = []
    for r in p.iter(qn("w:r")):
        txt = []
        for ch in r:
            if ch.tag == qn("w:t"):
                txt.append(ch.text or "")
            elif ch.tag == qn("w:tab"):
                txt.append("\t")
            elif ch.tag == qn("w:br") and ch.get(qn("w:type")) not in ("page", "column"):
                txt.append("\n")
            elif ch.tag in (qn("w:drawing"), qn("w:pict")):
                out.append({"media": True})
        if txt:
            pr = res.run_props(base, r)
            out.append({"t": "".join(txt), "b": bool(pr.get("bold")), "i": bool(pr.get("italic")),
                        "u": bool(pr.get("underline")), "caps": bool(pr.get("caps")),
                        "sup": pr.get("vert") == "superscript", "sub": pr.get("vert") == "subscript",
                        "size": pr.get("size"), "font": pr.get("font")})
    return out


def build(renderer):
    doc = renderer.doc
    res = StyleResolver(doc)
    numberer = _Numberer(res)
    items = []
    for el in doc.element.body:
        src, role = renderer.origin.get(el, (None, None))
        if el.tag == qn("w:p"):
            props = res.para_props(el)
            base = res.para_base(el)
            entry = {"b": src, "role": role, "style": summary(props),
                     "page_break": bool(base.get("page_break_before")),
                     "runs": _runs(el, res, base)}
            entry["empty"] = not para_text(el).strip() and not any(r.get("media") for r in entry["runs"])
            num = base.get("num")
            if num and not entry["empty"]:
                entry["label"] = numberer.label(num)
            items.append(entry)
        elif el.tag == qn("w:tbl"):
            rows = []
            for tr in el.findall(qn("w:tr")):
                rows.append([" ".join(para_text(p) for p in tc.findall(qn("w:p"))) for tc in tr.findall(qn("w:tc"))])
            first = el.find(f".//{qn('w:p')}")
            style = summary(res.para_props(first)) if first is not None else {}
            items.append({"b": src, "role": "tabel", "table": rows, "style": style})
    return {"page": renderer.profile.page, "items": items, "warnings": sorted(renderer.warnings)}
