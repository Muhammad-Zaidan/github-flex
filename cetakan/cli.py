"""Baris perintah: cetakan contoh.docx naskah.txt -o hasil.docx"""

import argparse
import os
import sys

from .export import FORMATS, ExportError, convert
from .reader import parse_docx, parse_text
from .render import Renderer
from .roles import ROLES


def _pairs(text):
    out = {}
    for part in filter(None, (text or "").split(",")):
        k, _, v = part.partition("=")
        if not k.strip().isdigit() or v.strip() not in ROLES:
            raise SystemExit(f"Format peran tidak valid: {part!r} (contoh: 3=h1). Peran: {', '.join(ROLES)}")
        out[int(k) - 1] = v.strip()
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="cetakan",
        description="Cetak naskah dengan format yang dipelajari dari satu dokumen contoh (.docx).")
    ap.add_argument("contoh", help="dokumen contoh .docx (template kampus/jurnal/tulisan orang lain)")
    ap.add_argument("naskah", help="naskah: .txt / .md (teks mentah) atau .docx (berantakan)")
    ap.add_argument("-o", "--output", help="berkas hasil; ekstensinya menentukan format "
                    f"({', '.join(FORMATS)}). Bawaan: <naskah>-cetakan.docx")
    ap.add_argument("--gabung-baris", action="store_true", help="gabungkan baris terputus (teks dari PDF)")
    ap.add_argument("--peran-contoh", metavar="N=PERAN,...", help="koreksi peran paragraf contoh, nomor mulai 1")
    ap.add_argument("--peran", metavar="N=PERAN,...", help="koreksi peran blok naskah, nomor mulai 1")
    ap.add_argument("--periksa", action="store_true", help="tampilkan hasil deteksi tanpa membuat berkas")
    a = ap.parse_args(argv)

    with open(a.contoh, "rb") as f:
        template = f.read()
    tpl_over = _pairs(a.peran_contoh)
    renderer = Renderer(template, tpl_over)
    avail = set(renderer.profile.styles)
    if a.naskah.lower().endswith(".docx"):
        with open(a.naskah, "rb") as f:
            content = parse_docx(f.read(), avail)
    else:
        with open(a.naskah, encoding="utf-8-sig") as f:
            content = parse_text(f.read(), merge_lines=a.gabung_baris, available=avail)
    for k, r in _pairs(a.peran).items():
        if 0 <= k < len(content.blocks):
            content.blocks[k].role = r

    if a.periksa:
        print("== Contoh ==")
        for p in renderer.profile.paragraphs:
            print(f"{p['i'] + 1:>4}  {p['role']:<18} {p['text'][:70]}")
        print("\n== Naskah ==")
        for i, b in enumerate(content.blocks):
            print(f"{i + 1:>4}  {b.role:<18} {b.text[:70] if b.kind == 'p' else '[tabel]'}")
        return 0

    out = a.output or os.path.splitext(a.naskah)[0] + "-cetakan.docx"
    fmt = os.path.splitext(out)[1].lstrip(".").lower() or "docx"
    if fmt not in FORMATS:
        raise SystemExit(f"Format keluaran tidak dikenal: .{fmt}")
    data = renderer.render(content)
    try:
        data = convert(data, fmt)
    except ExportError as e:
        raise SystemExit(str(e))
    with open(out, "wb") as f:
        f.write(data)
    for w in sorted(renderer.warnings):
        print("Peringatan:", w, file=sys.stderr)
    print(f"Selesai: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
