"""Mempelajari "cetakan" dari satu dokumen contoh: gaya tiap peran, jarak, pemisah halaman."""

import re
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass, field

from docx.oxml.ns import qn
from lxml import etree

from .classify import (
    ALPHA_HEAD_RE, ALPHA_LOW_HEAD_RE, BAB_ONLY_RE, BAB_RE, BULLET_RE, CAPTION_RE,
    KEYWORD_RE, NUM_HEAD_RE, NUMLIST_RE, ROMAN_HEAD_RE, classify, is_titleish, list_kind)
from .reader import para_item, para_text
from .roles import HEADINGS, ROLES
from .styles import StyleResolver, summary

LABEL_RES = [
    KEYWORD_RE,
    re.compile(CAPTION_RE.pattern.replace(r"\s*(.*)$", r""), re.I),
    re.compile(r"^(Abstrak|Abstract|Intisari)\s*[:.—–\-]", re.I),
]
RSID = re.compile(r"\{[^}]+\}rsid\w*")


def _clean(el):
    """Salinan elemen tanpa atribut rsid dan riwayat revisi."""
    el = deepcopy(el)
    for node in el.iter():
        for a in [a for a in node.attrib if RSID.match(a)]:
            del node.attrib[a]
    for tag in ("w:pPrChange", "w:rPrChange", "w:sectPr"):
        for x in el.findall(f".//{qn(tag)}") + ([el] if el.tag == qn(tag) else []):
            if x is not el:
                x.getparent().remove(x)
    return el


def _sig(el):
    return etree.tostring(_clean(el)) if el is not None else b""


def norm_heading(text):
    t = text.strip()
    for rx in (BAB_RE,):
        m = rx.match(t)
        if m and m.group(2).strip():
            t = m.group(2)
    t = re.sub(r"^(\d{1,2}(\.\d{1,2})*\.?|[IVXLC]+\.|[A-Za-z][.)])\s+", "", t)
    return re.sub(r"[\W_]+", " ", t).strip().upper()


@dataclass
class RoleStyle:
    role: str
    pPr: object = None
    rPr: object = None
    label_rPr: object = None
    upper: bool = False
    title: bool = False           # contoh memakai Huruf Awal Kapital
    auto_num: bool = False
    num: tuple = None             # (numId, ilvl) bila bernomor otomatis
    num_fmt: str = None
    spec: tuple = None            # format nomor manual, mis. ('d', 2, '') atau ('A',)
    sep: str = " "                # pemisah nomor manual dan teks
    marker: str = None            # penanda daftar manual, mis. '1.' / '•'
    sample: str = ""
    summary: dict = field(default_factory=dict)
    index: int = None             # indeks paragraf contoh


@dataclass
class Profile:
    styles: dict
    lists: dict
    exact: dict
    gaps: dict
    breaks: dict
    bab_mode: str
    bab_sep: str
    table: dict
    page: dict
    paragraphs: list
    roles: list


def _text_runs(p):
    """[(rPr, teks)] untuk run-run berteks pada paragraf."""
    out = []
    for r in p.iter(qn("w:r")):
        txt = "".join((t.text or "") if t.tag == qn("w:t") else "\t"
                      for t in r if t.tag in (qn("w:t"), qn("w:tab")))
        if txt:
            out.append((r.find(qn("w:rPr")), txt))
    return out


def _manual_spec(role, text):
    t = text.lstrip()
    if role == "bab":
        return None
    m = NUM_HEAD_RE.match(t)
    if m:
        return ("d", m.group(1).count(".") + 1, m.group(2)), re.match(r"^\S+(\s+)", t).group(1)
    for rx, key in ((ROMAN_HEAD_RE, "R"), (ALPHA_HEAD_RE, "A")):
        if rx.match(t):
            return (key,), re.match(r"^\S+(\s+)", t).group(1)
    m = ALPHA_LOW_HEAD_RE.match(t)
    if m:
        return ("a", t[1]), re.match(r"^\S+(\s+)", t).group(1)
    return None, " "


def _role_style(role, p, res, item, texts):
    pPr = p.find(qn("w:pPr"))
    pPr = _clean(pPr) if pPr is not None else None
    runs = _text_runs(p)
    full = "".join(t for _, t in runs)
    rPr = label_rPr = None
    first = next(((r, t) for r, t in runs if t.strip()), None)
    if first:
        rPr = first[0]
        for rx in LABEL_RES:
            m = rx.match(full.lstrip())
            if not m:
                continue
            end = len(full) - len(full.lstrip()) + m.end()
            while end < len(full) and full[end].isspace():
                end += 1
            pos, after, found = 0, None, False
            for r, t in runs:
                if pos <= end < pos + len(t):
                    after, found = r, True
                    break
                pos += len(t)
            if found and _sig(after) != _sig(first[0]):
                label_rPr, rPr = first[0], after
            break
    props = res.para_props(p)
    rs = RoleStyle(
        role=role, pPr=pPr,
        rPr=_clean(rPr) if rPr is not None else None,
        label_rPr=_clean(label_rPr) if label_rPr is not None else None,
        upper=all(any(c.isalpha() for c in t) and t == t.upper() for t in texts) and bool(texts),
        sample=item.text.strip()[:200], summary=summary(props))
    if props.get("num"):
        rs.auto_num, rs.num = True, props["num"]
        info = res.num_info(*props["num"])
        rs.num_fmt = info[1] if info else None
    elif role in ("h1", "h2", "h3"):
        rs.spec, rs.sep = _manual_spec(role, item.text)
    if role == "daftar" and not rs.auto_num:
        t = item.text.lstrip()
        m = BULLET_RE.match(t) or NUMLIST_RE.match(t)
        if m:
            rs.marker = m.group(1)
            rs.sep = re.match(r"^\S+(\s+)", t).group(1)
    letters = [t for t in texts if any(c.isalpha() for c in t)]
    rs.title = (not rs.upper and len(letters) > 0 and role in HEADINGS + ("judul",)
                and all(is_titleish(t) and t != t.upper() for t in letters))
    rs.summary["upper"] = rs.upper
    rs.summary["auto_num"] = rs.auto_num
    return rs


def _breaks_in(p):
    """(pecah halaman sebelum teks, pecah setelah teks) dalam paragraf."""
    before = after = False
    seen_text = False
    for el in p.iter(qn("w:t"), qn("w:br"), qn("w:drawing")):
        if el.tag == qn("w:br"):
            if el.get(qn("w:type")) == "page":
                if seen_text:
                    after = True
                else:
                    before = True
        elif el.tag == qn("w:drawing") or (el.text or "").strip():
            seen_text = True
    pPr = p.find(qn("w:pPr"))
    if pPr is not None:
        sect = pPr.find(qn("w:sectPr"))
        if sect is not None:
            typ = sect.find(qn("w:type"))
            if typ is None or typ.get(qn("w:val")) in ("nextPage", "oddPage", "evenPage"):
                after = True
    return before, after


def _page(doc):
    sect = doc.element.body.find(qn("w:sectPr"))
    out = {"width": 21.0, "height": 29.7, "top": 2.54, "bottom": 2.54, "left": 2.54, "right": 2.54}
    if sect is None:
        return out
    sz, mar = sect.find(qn("w:pgSz")), sect.find(qn("w:pgMar"))
    for el, attrs in ((sz, (("w:w", "width"), ("w:h", "height"))),
                      (mar, (("w:top", "top"), ("w:bottom", "bottom"), ("w:left", "left"),
                             ("w:right", "right")))):
        if el is None:
            continue
        for a, k in attrs:
            v = el.get(qn(a))
            if v:
                out[k] = round(abs(int(float(v))) / 567, 2)
    return out


def analyze(doc, overrides=None):
    """Pelajari cetakan dari `doc` (python-docx Document). `overrides`: {indeks: peran}."""
    res = StyleResolver(doc)
    body = doc.element.body
    seq = []           # ('p', el, item) | ('tbl', el)
    for el in body:
        if el.tag == qn("w:p"):
            seq.append(("p", el, para_item(el, res)))
        elif el.tag == qn("w:tbl"):
            seq.append(("tbl", el, None))
    paras = [s for s in seq if s[0] == "p"]
    roles = classify([s[2] for s in paras])
    for k, r in (overrides or {}).items():
        k = int(k)
        if 0 <= k < len(roles) and r in ROLES and roles[k] is not None:
            roles[k] = r
    role_of = {id(s[1]): r for s, r in zip(paras, roles)}

    # --- gaya per peran: pilih paragraf contoh yang formatnya paling umum ---
    by_role = defaultdict(list)
    for idx, (s, r) in enumerate(zip(paras, roles)):
        if r and r not in ("abaikan", "tabel"):
            by_role[r].append(idx)
    styles, lists, exact = {}, {}, {}

    def pick(idxs):
        sigs = [(_sig(paras[i][1].find(qn("w:pPr"))),
                 _sig(next((r for r, t in _text_runs(paras[i][1]) if t.strip()), None))) for i in idxs]
        best = Counter(sigs).most_common(1)[0][0]
        return idxs[sigs.index(best)]

    for r, idxs in by_role.items():
        texts = [paras[i][2].text.strip() for i in idxs]
        if r == "daftar":
            groups = defaultdict(list)
            for i in idxs:
                groups[list_kind(paras[i][2])].append(i)
            for kind, g in groups.items():
                i = pick(g)
                lists[kind] = _role_style(r, paras[i][1], res, paras[i][2], [])
                lists[kind].index = i
            i = pick(idxs)
        else:
            i = pick(idxs)
        rs = _role_style(r, paras[i][1], res, paras[i][2], texts)
        rs.index = i
        styles[r] = rs
        if r in HEADINGS + ("judul",):
            for j in idxs:
                key = norm_heading(paras[j][2].text)
                if key and len(key.split()) <= 8 and key not in exact:
                    e = _role_style(r, paras[j][1], res, paras[j][2], [paras[j][2].text.strip()])
                    e.index = j
                    exact[key] = e

    # --- jarak (paragraf kosong) & pemisah halaman antarperan ----------------
    gaps = defaultdict(list)
    breaks = defaultdict(list)
    prev, empties, spacer, pending_break = None, 0, None, False
    for kind, el, item in seq:
        if kind == "tbl":
            role = "tabel"
        else:
            b_before, b_after = _breaks_in(el)
            if item.empty:
                if b_before or b_after:
                    pending_break, empties, spacer = True, 0, None
                else:
                    empties += 1
                    if spacer is None:
                        spacer = el
                continue
            role = role_of.get(id(el))
            if role == "abaikan":
                continue
            ppr_break = res.para_base(el).get("page_break_before")
            pending_break = pending_break or b_before or bool(ppr_break)
        if prev is not None:
            gaps[(prev, role)].append((empties, spacer))
            breaks[role].append(pending_break)
        prev, empties, spacer = role, 0, None
        pending_break = kind == "p" and _breaks_in(el)[1]

    gap_table = {}
    for key, vals in gaps.items():
        n = Counter(v[0] for v in vals).most_common(1)[0][0]
        sp = next((v[1] for v in vals if v[0] == n and v[1] is not None), None)
        gap_table[key] = (n, _spacer(sp) if sp is not None else None)
    brk = {r: sum(v) / len(v) >= 0.5 for r, v in breaks.items() if v}
    if "bab" in styles and "bab" not in brk:
        brk["bab"] = True   # bab skripsi/tesis lazimnya selalu di halaman baru

    # --- gaya bab ------------------------------------------------------------
    bab_mode, bab_sep = None, " "
    if "bab" in styles:
        bab_mode = "auto" if styles["bab"].auto_num else "split"
        for idx in by_role["bab"]:
            el, item = paras[idx][1], paras[idx][2]
            full = para_text(el).strip()
            m = BAB_RE.match(full)
            if not m:
                continue
            if "\n" in full:
                bab_mode = "merged"
            elif BAB_ONLY_RE.match(full):
                bab_mode = "split"
            else:
                bab_mode = "inline"
                bab_sep = full[m.end(1):m.start(2)] or " "
            break

    # --- tabel ---------------------------------------------------------------
    table = {}
    tbl = next((s[1] for s in seq if s[0] == "tbl"), None)
    if tbl is not None:
        table["tblPr"] = _clean(tbl.find(qn("w:tblPr")))
        rows = tbl.findall(qn("w:tr"))
        for key, tr in (("head", rows[0] if rows else None), ("body", rows[1] if len(rows) > 1 else None)):
            if tr is None:
                continue
            tc = tr.find(qn("w:tc"))
            p = tc.find(qn("w:p")) if tc is not None else None
            if p is not None:
                it = para_item(p, res)
                table[key] = _role_style("tabel", p, res, it, [])
            tcPr = tc.find(qn("w:tcPr")) if tc is not None else None
            if tcPr is not None:
                keep = [deepcopy(c) for c in tcPr if c.tag in (qn("w:tcBorders"), qn("w:shd"), qn("w:vAlign"))]
                table[key + "_tc"] = keep
            trPr = tr.find(qn("w:trPr"))
            if trPr is not None:
                table[key + "_tr"] = _clean(trPr)
        table["head"] = table.get("head") or table.get("body")
        table["body"] = table.get("body") or table.get("head")

    listing = []
    for idx, (s, r) in enumerate(zip(paras, roles)):
        if r is None:
            continue
        listing.append({"i": idx, "text": s[2].text.strip()[:220] or "[gambar]", "role": r})
    return Profile(styles=styles, lists=lists, exact=exact, gaps=gap_table, breaks=brk,
                   bab_mode=bab_mode, bab_sep=bab_sep, table=table, page=_page(doc),
                   paragraphs=listing, roles=roles)


def _spacer(p):
    sp = _clean(p)
    for ch in list(sp):
        if ch.tag != qn("w:pPr"):
            sp.remove(ch)
    return sp


def describe(profile):
    """Ringkasan cetakan untuk antarmuka."""
    out = {}
    for r, rs in profile.styles.items():
        out[r] = {"label": ROLES[r], "sample": rs.sample, "style": rs.summary,
                  "page_break": profile.breaks.get(r, False), "index": rs.index}
    return {"roles": out, "page": profile.page, "bab_mode": profile.bab_mode,
            "paragraphs": profile.paragraphs, "has_table": bool(profile.table)}
