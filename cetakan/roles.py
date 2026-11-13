"""Peran (role) paragraf yang dikenali dan urutan cadangannya."""

ROLES = {
    "judul": "Judul dokumen",
    "penulis": "Penulis / identitas",
    "bab": "Judul bab",
    "bab_nama": "Nama bab",
    "h1": "Subjudul 1",
    "h2": "Subjudul 2",
    "h3": "Subjudul 3",
    "paragraf": "Paragraf isi",
    "abstrak": "Abstrak",
    "kata_kunci": "Kata kunci",
    "daftar": "Butir daftar",
    "lanjutan": "Lanjutan butir daftar",
    "kutipan": "Kutipan panjang",
    "gambar": "Gambar",
    "keterangan_gambar": "Keterangan gambar",
    "keterangan_tabel": "Keterangan tabel",
    "pustaka": "Daftar pustaka",
    "kode": "Kode program",
    "tabel": "Tabel",
    "abaikan": "Abaikan",
}

HEADINGS = ("bab", "bab_nama", "h1", "h2", "h3")

# Jika contoh tidak punya gaya untuk suatu peran, pakai gaya peran berikut.
FALLBACK = {
    "judul": ["bab", "h1"],
    "penulis": ["paragraf"],
    "bab": ["h1", "judul"],
    "bab_nama": ["bab", "h1"],
    "h1": ["bab", "judul"],
    "h2": ["h1", "bab"],
    "h3": ["h2", "h1", "bab"],
    "abstrak": ["paragraf"],
    "kata_kunci": ["abstrak", "paragraf"],
    "daftar": ["paragraf"],
    "lanjutan": ["paragraf"],
    "kutipan": ["paragraf"],
    "gambar": ["keterangan_gambar", "paragraf"],
    "keterangan_gambar": ["keterangan_tabel", "paragraf"],
    "keterangan_tabel": ["keterangan_gambar", "paragraf"],
    "pustaka": ["paragraf"],
    "kode": ["paragraf"],
}


def resolve(role, available):
    """Peran yang gayanya benar-benar dipakai untuk `role`."""
    if role in available:
        return role
    for alt in FALLBACK.get(role, []):
        if alt in available:
            return alt
    return "paragraf" if "paragraf" in available else None
