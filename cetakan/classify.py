"""Mengenali peran setiap paragraf (judul, bab, subjudul, paragraf, daftar, ...).

Dipakai untuk dokumen contoh maupun tulisan masukan. Tanpa AI: hanya pola teks,
nama gaya, dan ciri format (tebal, ukuran, perataan, penomoran).
"""

import re
from collections import Counter
from dataclasses import dataclass, field

ROMAN = r"[IVXLC]+"
BAB_RE = re.compile(rf"^(?i:bab)\s+({ROMAN}|\d{{1,2}})\b\s*[.:\-–—]?\s*(.*)$", re.S)
BAB_ONLY_RE = re.compile(rf"^(?i:bab)\s+({ROMAN}|\d{{1,2}})\s*[.:]?\s*$")

_SECTIONS = (
    r"DAFTAR\s+PUSTAKA|DAFTAR\s+REFERENSI|REFERENSI|REFERENCES?|BIBLIOGRAPHY|BIBLIOGRAFI|"
    r"KEPUSTAKAAN|RUJUKAN|ABSTRAK|ABSTRACT|INTISARI|RINGKASAN|SUMMARY|KATA\s+PENGANTAR|"
    r"PRAKATA|DAFTAR\s+ISI|DAFTAR\s+TABEL|DAFTAR\s+GAMBAR|DAFTAR\s+LAMPIRAN|LAMPIRAN|"
    r"PENDAHULUAN|INTRODUCTION|LATAR\s+BELAKANG|METODE(?:\s+PENELITIAN)?|METODOLOGI(?:\s+PENELITIAN)?|"
    r"METHODS?|METHODOLOGY|MATERIALS?\s+AND\s+METHODS|BAHAN\s+DAN\s+METODE|"
    r"HASIL(?:\s+DAN\s+PEMBAHASAN)?|PEMBAHASAN|RESULTS?(?:\s+AND\s+DISCUSSIONS?)?|DISCUSSIONS?|"
    r"KESIMPULAN(?:\s+DAN\s+SARAN)?|SIMPULAN(?:\s+DAN\s+SARAN)?|SARAN|CONCLUSIONS?|PENUTUP|"
    r"TINJAUAN\s+PUSTAKA|LANDASAN\s+TEORI|KAJIAN\s+PUSTAKA|KAJIAN\s+TEORI|"
    r"UCAPAN\s+TERIMA\s+KASIH|ACKNOWLEDGE?MENTS?")
MAJOR_RE = re.compile(rf"^(?:(?:\d{{1,2}}|{ROMAN}|[A-Z])\.?\s+)?({_SECTIONS})\s*:?$", re.I)
ABSTRACT_HEAD_RE = re.compile(r"^(ABSTRAK|ABSTRACT|INTISARI|RINGKASAN|SUMMARY)\s*:?$", re.I)
TOC_HEAD_RE = re.compile(r"^DAFTAR\s+(ISI|GAMBAR|TABEL|LAMPIRAN|RUMUS|PERSAMAAN|BAGAN|GRAFIK)\s*:?$", re.I)
MONO_FONTS = ("courier", "consolas", "mono", "menlo", "lucida console", "monaco", "source code")
REFS_HEAD_RE = re.compile(
    r"^(?:(?:\d{1,2}|[IVX]+)\.?\s+)?(DAFTAR\s+PUSTAKA|DAFTAR\s+REFERENSI|REFERENSI|REFERENCES?|"
    r"BIBLIOGRAPHY|BIBLIOGRAFI|KEPUSTAKAAN|RUJUKAN)\s*:?$", re.I)
# Bagian depan/belakang yang tidak pernah diberi nomor bab/subbab.
UNNUMBERED_RE = re.compile(
    r"^(DAFTAR\s+.+|REFERENSI|REFERENCES?|BIBLIOGRAPHY|BIBLIOGRAFI|KEPUSTAKAAN|RUJUKAN|ABSTRAK|"
    r"ABSTRACT|INTISARI|RINGKASAN|SUMMARY|KATA\s+PENGANTAR|PRAKATA|LAMPIRAN.*|UCAPAN\s+TERIMA\s+KASIH|"
    r"ACKNOWLEDGE?MENTS?|HALAMAN\s+.*|LEMBAR\s+.*|PERNYATAAN.*|MOTTO.*|PERSEMBAHAN|RIWAYAT\s+HIDUP|"
    r"BIODATA.*)\s*:?$", re.I)

CAPTION_RE = re.compile(
    r"^(Gambar|Tabel|Figure|Fig\.|Table|Grafik|Diagram|Bagan|Skema|Foto|Ilustrasi|Lampiran)\s*"
    r"([0-9IVX]+(?:[.\-][0-9]+)*)\s*([.:\-–—|])?\s*(.*)$", re.I | re.S)
KEYWORD_RE = re.compile(r"^(Kata[\s-]*[Kk]unci|Keywords?|Key\s+words|Index\s+Terms)\s*[:：—–\-]", re.I)
# Entri daftar isi / daftar tabel: teks, tab atau titik-titik, lalu nomor halaman.
TOC_LINE_RE = re.compile(r"^\S.{1,200}?(\t[\s.·…_\-]*|[.·…_]{4,}\s*)([0-9]{1,4}|[ivxlcdm]{1,7})\s*$", re.I | re.S)
ABS_INLINE_RE = re.compile(r"^(Abstrak|Abstract|Intisari)\s*[:.—–\-]\s*\S", re.I)

# 1.1 / 2.3.1 / juga I.1 / II.2.1 (nomor bab Romawi diikuti subnomor)
NUM_HEAD_RE = re.compile(r"^((?:\d{1,2}|[IVXLC]{1,6}(?=\.\d))(?:\.\d{1,2}){0,4})(\.?)\s+(\S.*)$", re.S)
ROMAN_HEAD_RE = re.compile(rf"^({ROMAN})\.\s+(\S.*)$", re.S)
ALPHA_HEAD_RE = re.compile(r"^([A-Z])\.\s+(\S.*)$", re.S)
ALPHA_LOW_HEAD_RE = re.compile(r"^([a-z])[.)]\s+(\S.*)$", re.S)
BULLET_RE = re.compile(r"^([-•*▪◦–·●○■□➢►✓→])\s+(.*)$", re.S)
NUMLIST_RE = re.compile(r"^(\d{1,2}[.)]|[a-z][.)]|\(\d{1,2}\)|\([a-z]\))\s+(.*)$", re.S)

STOPWORDS = {
    "dan", "di", "ke", "dari", "yang", "untuk", "pada", "dengan", "terhadap", "dalam", "atau",
    "serta", "oleh", "sebagai", "antara", "melalui", "tentang", "of", "and", "the", "in", "on",
    "for", "to", "a", "an", "at", "by", "with", "from", "vs", "versus",
}


@dataclass
class Item:
    text: str = ""
    props: dict | None = None          # None untuk teks polos (tanpa info format)
    style_name: str = ""
    has_drawing: bool = False
    num: tuple | None = None           # (numId, ilvl) penomoran otomatis Word
    num_fmt: str | None = None         # 'bullet', 'decimal', ...
    forced: str | None = None          # peran dipaksa (mis. dari penanda Markdown)
    forced_level: int | None = None    # tingkat judul dari '#', '##', ...
    extra: dict = field(default_factory=dict)

    @property
    def empty(self):
        return not self.text.strip() and not self.has_drawing


def words(t):
    return len(t.split())


def is_titleish(t):
    toks = [w for w in re.findall(r"[^\W\d_][\w'’\-]*", t)]
    sig = [w for w in toks if w.lower() not in STOPWORDS]
    if not sig:
        return False
    if t.upper() == t:
        return True
    return sum(1 for w in sig if w[0].isupper()) / len(sig) >= 0.8


def list_kind(item):
    """'bullet' / 'number' untuk butir daftar."""
    if item.num_fmt:
        return "bullet" if item.num_fmt == "bullet" else "number"
    return "bullet" if BULLET_RE.match(item.text.strip()) else "number"


def _heading_kind(it, t, base_size):
    """Jenis penomoran judul (untuk menentukan tingkat), atau None."""
    p = it.props
    n = words(t)
    if n > 18 or len(t) > 160:
        return None
    ends = t.rstrip()[-1:] in ".,;" if t else False
    fmt_strong = bool(p) and (p.get("bold") or (p.get("size") or 0) >= base_size + 1
                              or p.get("align") == "center" or p.get("outline") is not None)
    m = NUM_HEAD_RE.match(t)
    if m:
        depth = m.group(1).count(".") + 1
        rest = m.group(3)
        if depth >= 2 and not ends and (p is None or fmt_strong or n <= 12):
            return ("d", depth)
        if depth == 1 and not ends and (fmt_strong or (p is None and is_titleish(rest) and n <= 10)):
            return ("d", 1)
        return None
    for rx, key in ((ROMAN_HEAD_RE, "R"), (ALPHA_HEAD_RE, "A")):
        m = rx.match(t)
        if m and not ends and (fmt_strong or (p is None and is_titleish(m.group(2)) and n <= 10)):
            return (key,)
    m = ALPHA_LOW_HEAD_RE.match(t)
    if m and not ends and (fmt_strong or (p is None and is_titleish(m.group(2)) and n <= 8)):
        return ("a",)
    if it.num and p and p.get("bold") and not ends and n <= 12:
        return ("n", it.num[1])
    return None


def classify(items, available=None):
    """Kembalikan daftar peran (None untuk paragraf kosong)."""
    n = len(items)
    roles = [None] * n
    kinds = [None] * n
    sizes = [it.props.get("size") for it in items
             if it.props and words(it.text) >= 25 and it.props.get("size")]
    base_size = Counter(sizes).most_common(1)[0][0] if sizes else 11
    inds = [round(it.props.get("ind_left") or 0, 1) for it in items
            if it.props and words(it.text) >= 25]
    base_ind = Counter(inds).most_common(1)[0][0] if inds else 0
    has_bab = any(BAB_RE.match(it.text.strip()) and words(it.text) <= 14 for it in items)

    # --- tahap 1: ciri masing-masing paragraf --------------------------------
    for k, it in enumerate(items):
        if it.empty:
            continue
        t = it.text.strip()
        nw = words(t)
        p = it.props or {}
        sn = (it.style_name or "").lower()
        if it.forced:
            roles[k] = it.forced
            if it.forced_level is not None:
                kinds[k] = ("md", it.forced_level)
            continue
        if (sn.startswith(("toc", "table of figures", "daftar isi")) or TOC_LINE_RE.match(t)) and nw <= 30:
            roles[k] = "abaikan"
            it.extra["toc"] = True
            continue
        if it.props and any(f in (it.props.get("font") or "").lower() for f in MONO_FONTS):
            roles[k] = "kode"
            continue
        if it.has_drawing and nw <= 4:
            roles[k] = "gambar"
            continue
        m = BAB_RE.match(t)
        if m and nw <= 14 and not t.endswith("."):
            roles[k] = "bab"
            continue
        m = CAPTION_RE.match(t)
        if m and nw <= 45 and (m.group(3) or (m.group(4)[:1].isupper())):
            roles[k] = "keterangan_tabel" if m.group(1).lower() in ("tabel", "table") else "keterangan_gambar"
            continue
        if KEYWORD_RE.match(t):
            roles[k] = "kata_kunci"
            continue
        if ABS_INLINE_RE.match(t) and nw > 8:
            roles[k] = "abstrak"
            continue
        hm = re.match(r"^(?:heading|judul)\s*([1-9])$", sn)
        if hm or (p.get("outline") is not None and p["outline"] < 6 and nw <= 18):
            lvl = int(hm.group(1)) if hm else p["outline"] + 1
            roles[k], kinds[k] = "heading", ("s", lvl)
            continue
        if MAJOR_RE.match(t) and nw <= 6:
            roles[k], kinds[k] = "heading", ("major",)
            continue
        if sn in ("title", "judul"):
            roles[k] = "judul"
            continue
        if sn in ("subtitle", "subjudul"):
            roles[k] = "penulis"
            continue
        if "caption" in sn or "keterangan" in sn:
            roles[k] = "keterangan_tabel" if t.lower().startswith(("tabel", "table")) else "keterangan_gambar"
            continue
        if "bibliograph" in sn or "pustaka" in sn:
            roles[k] = "pustaka"
            continue
        if "quote" in sn or "kutipan" in sn:
            roles[k] = "kutipan"
            continue
        hk = _heading_kind(it, t, base_size)
        if hk:
            roles[k], kinds[k] = "heading", hk
            continue
        if BULLET_RE.match(t) or NUMLIST_RE.match(t) or it.num or "list" in sn:
            roles[k] = "daftar"
            continue
        if it.props:
            whole_bold = p.get("bold") and nw <= 15 and not t.endswith((".", ",", ";"))
            bigger = (p.get("size") or 0) >= base_size + 1.5 and nw <= 20
            if whole_bold or bigger:
                roles[k], kinds[k] = "heading", ("b",)
                continue
            if (nw >= 15 and (p.get("ind_left") or 0) >= base_ind + 0.9
                    and (p.get("ind_right") or 0) > 0.2):
                roles[k] = "kutipan"
                continue
        roles[k] = "paragraf"

    order = [k for k in range(n) if roles[k] is not None]

    pos_of = {k: i for i, k in enumerate(order)}

    def nxt(k):
        pos = pos_of[k]
        return order[pos + 1] if pos + 1 < len(order) else None

    # --- tahap 2: judul tanpa format di teks polos ---------------------------
    for k in order:
        it = items[k]
        if roles[k] != "paragraf" or it.props is not None:
            continue
        t = it.text.strip()
        nk = nxt(k)
        if (words(t) <= 10 and t[-1:] not in ".,;:" and is_titleish(t) and nk is not None
                and roles[nk] == "paragraf" and words(items[nk].text) > 15):
            roles[k], kinds[k] = "heading", ("b",)

    # --- tahap 3: butir berurutan dengan pola sama = daftar, bukan judul -----
    as_list = set()
    for a, b in zip(order, order[1:]):
        ka, kb = kinds[a], kinds[b]
        if (roles[a] == roles[b] == "heading" and ka == kb and ka and ka[0] in ("d", "A", "a", "R")
                and (ka[0] != "d" or ka[1] == 1)):
            pa, pb = items[a].props, items[b].props
            if not (pa and pa.get("bold")) and not (pb and pb.get("bold")):
                as_list.update((a, b))
    for k in as_list:
        roles[k], kinds[k] = "daftar", None

    # --- tahap 4: bagian depan (judul + penulis) -----------------------------
    allow_title = available is None or "judul" in available
    if order and allow_title:
        k0 = order[0]
        it = items[k0]
        t = it.text.strip()
        p = it.props
        looks = words(t) <= 35 and not t.endswith((".", ":"))
        if p is not None:
            nk = nxt(k0)
            before_heading = nk is not None and roles[nk] == "heading" and words(t) <= 20
            looks = looks and (p.get("align") == "center" or p.get("bold") or before_heading
                               or (p.get("size") or 0) >= base_size + 2)
        if roles[k0] in ("paragraf", "heading") and looks and (kinds[k0] in (None, ("b",))):
            roles[k0], kinds[k0] = "judul", None
        if roles[k0] == "judul":
            for k in order[1:]:
                if roles[k] not in ("paragraf", "heading") or kinds[k] not in (None, ("b",)):
                    break
                if words(items[k].text) > 30 or items[k].text.strip().endswith("."):
                    break
                roles[k], kinds[k] = "penulis", None

    # --- tahap 5: nama bab setelah "BAB I" -----------------------------------
    for k in order:
        if roles[k] == "bab" and BAB_ONLY_RE.match(items[k].text.strip()):
            nk = nxt(k)
            if nk is not None and roles[nk] in ("heading", "paragraf") and words(items[nk].text) <= 14 \
                    and not items[nk].text.strip().endswith("."):
                roles[nk], kinds[nk] = "bab_nama", None

    # --- tahap 6: tingkat judul ---------------------------------------------
    # Gaya Heading N dan nomor 1.1 / 1.1.1 memberi tingkat mutlak; jenis lain
    # (I., A., a., tebal) diberi tingkat menurut urutan kemunculannya.
    s_levels = [kinds[k][1] for k in order if roles[k] == "heading" and kinds[k] and kinds[k][0] == "s"]
    s_off = min(s_levels) - 1 if s_levels else 0
    has_alpha = any(kinds[k] == ("A",) for k in order)
    seen = []
    for k in order:
        kd = kinds[k]
        if roles[k] == "heading" and kd and kd[0] not in ("major", "md", "s", "d") and kd not in seen:
            seen.append(kd)
    # urutkan jenis bertingkat yang sejenis menurut kedalamannya
    for prefix in ("n",):
        idx = [i for i, kd in enumerate(seen) if kd[0] == prefix]
        vals = sorted((seen[i] for i in idx), key=lambda kd: kd[1])
        for i, kd in zip(idx, vals):
            seen[i] = kd
    md_levels = [r for r in ("bab", "h1", "h2", "h3") if available is None or r in available] or ["h1"]
    for k in order:
        kd = kinds[k]
        if roles[k] != "heading" and not (kd and kd[0] == "md"):
            continue
        if kd[0] == "md":
            roles[k] = md_levels[min(kd[1], len(md_levels)) - 1]
            continue
        if kd[0] == "major":
            roles[k] = "bab" if has_bab else "h1"
            continue
        if kd[0] == "s":
            lvl = kd[1] - s_off
        elif kd[0] == "d":
            lvl = kd[1] + 1 if (has_bab and has_alpha) else (max(1, kd[1] - 1) if has_bab else kd[1])
        else:
            lvl = seen.index(kd) + 1
        roles[k] = f"h{min(max(lvl, 1), 3)}"

    # --- tahap 6b: judul setingkat bab tanpa nomor ---------------------------
    # Judul di tengah yang hurufnya lebih besar dari isi (mis. "LATAR BELAKANG" pada
    # proposal) setara bab, walau tidak diawali "BAB I".
    for k in order:
        p = items[k].props
        if p is None or roles[k] not in ("h1", "h2", "h3"):
            continue
        if p.get("align") == "center" and (p.get("size") or 0) >= base_size + 1 \
                and words(items[k].text) <= 10:
            roles[k] = "bab"

    # --- tahap 6c: paragraf lanjutan di dalam butir daftar --------------------
    # Paragraf yang menjorok sejajar teks butir di atasnya (tanpa menjorok baris
    # pertama) adalah lanjutan butir, bukan paragraf isi biasa.
    prev_role = prev_left = None
    for k in order:
        it = items[k]
        p = it.props
        if roles[k] == "paragraf" and prev_role in ("daftar", "lanjutan") and p is not None \
                and (p.get("ind_left") or 0) >= base_ind + 0.4 and (p.get("first_line") or 0) <= 0.05 \
                and (prev_left is None or (p.get("ind_left") or 0) >= prev_left - 0.15):
            roles[k] = "lanjutan"
        prev_role = roles[k]
        if roles[k] == "daftar" and p is not None:
            prev_left = p.get("ind_left") or 0

    # --- tahap 7: konteks bagian (abstrak, daftar pustaka) -------------------
    section = None
    for k in order:
        t = items[k].text.strip()
        r = roles[k]
        if section == "toc" and r not in ("bab", "bab_nama", "judul"):
            roles[k] = "abaikan"        # isi daftar isi/gambar/tabel (termasuk entri terlipat)
            continue
        if r in ("bab", "bab_nama", "h1", "h2", "h3", "judul"):
            section = ("abs" if ABSTRACT_HEAD_RE.match(t) else
                       "toc" if TOC_HEAD_RE.match(t) else
                       "ref" if REFS_HEAD_RE.match(t) else None)
            continue
        if r == "kata_kunci":
            section = None
        elif section == "abs" and r in ("paragraf", "kutipan"):
            roles[k] = "abstrak"
        elif section == "ref" and r in ("paragraf", "daftar"):
            roles[k] = "pustaka"
    return roles
