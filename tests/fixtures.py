"""Dokumen contoh sintetis untuk pengujian."""

from io import BytesIO

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Cm, Pt


def _fmt(p, size=12, bold=False, italic=False, align=None, first=None, left=None, hanging=None,
         before=0, after=0, line=1.5, font="Times New Roman"):
    pf = p.paragraph_format
    pf.space_before, pf.space_after = Pt(before), Pt(after)
    pf.line_spacing = line
    if align is not None:
        p.alignment = align
    if first is not None:
        pf.first_line_indent = Cm(first)
    if left is not None:
        pf.left_indent = Cm(left)
    if hanging is not None:
        pf.left_indent = Cm(hanging)
        pf.first_line_indent = Cm(-hanging)
    for r in p.runs:
        r.font.name, r.font.size, r.font.bold, r.font.italic = font, Pt(size), bold, italic
    return p


def thesis_template():
    """Skripsi: BAB I / PENDAHULUAN terpisah, subbab 1.1, format langsung (tanpa gaya Heading)."""
    d = Document()
    s = d.sections[0]
    s.page_width, s.page_height = Cm(21), Cm(29.7)
    s.left_margin, s.top_margin, s.right_margin, s.bottom_margin = Cm(4), Cm(4), Cm(3), Cm(3)
    C = WD_ALIGN_PARAGRAPH.CENTER
    J = WD_ALIGN_PARAGRAPH.JUSTIFY

    def bab(num, name, first=False):
        p = d.add_paragraph()
        if not first:
            p.add_run().add_break(WD_BREAK.PAGE)
        p.add_run(f"BAB {num}")
        _fmt(p, 14, True, align=C, line=1.0)
        _fmt(d.add_paragraph(name), 14, True, align=C, line=1.0)
        d.add_paragraph()  # satu baris kosong setelah nama bab

    bab("I", "PENDAHULUAN", first=True)
    _fmt(d.add_paragraph("1.1 Latar Belakang"), 12, True, line=1.5)
    for _ in range(2):
        _fmt(d.add_paragraph("Paragraf isi ditulis rata kiri-kanan dengan huruf Times New Roman 12 "
                             "dan spasi satu setengah serta menjorok satu seperempat sentimeter."),
             align=J, first=1.25)
    _fmt(d.add_paragraph("1.1.1 Konteks Penelitian"), 12, True, italic=True)
    _fmt(d.add_paragraph("Isi subbab tingkat dua juga memakai format paragraf isi yang sama persis "
                         "dengan paragraf lain di seluruh dokumen ini."), align=J, first=1.25)
    _fmt(d.add_paragraph("1.2 Rumusan Masalah"), 12, True)
    _fmt(d.add_paragraph("Rumusan masalah dalam penelitian ini dijabarkan sebagai berikut dengan "
                         "beberapa butir pertanyaan penelitian."), align=J, first=1.25)
    for t in ("1.\tBagaimana pengaruh A terhadap B?", "2.\tBagaimana pengaruh C terhadap B?"):
        _fmt(d.add_paragraph(t), align=J, hanging=0.75)
    p = d.add_paragraph()
    r = p.add_run("Gambar 1.1")
    r.bold = True
    p.add_run(" Kerangka berpikir penelitian")
    _fmt(p, 11, align=C, line=1.0, before=6, after=12)
    p.runs[0].font.bold = True
    t = d.add_table(rows=2, cols=2)
    t.style = "Table Grid"
    t.cell(0, 0).text, t.cell(0, 1).text = "Variabel", "Indikator"
    t.cell(1, 0).text, t.cell(1, 1).text = "X", "Y"
    bab("V", "PENUTUP")
    _fmt(d.add_paragraph("5.1 Kesimpulan"), 12, True)
    _fmt(d.add_paragraph("Kesimpulan penelitian ditulis secara ringkas dan jelas dalam bentuk paragraf "
                         "yang menjawab rumusan masalah penelitian."), align=J, first=1.25)
    p = d.add_paragraph()
    p.add_run().add_break(WD_BREAK.PAGE)
    p.add_run("DAFTAR PUSTAKA")
    _fmt(p, 14, True, align=C, line=1.0)
    d.add_paragraph()
    for ref in ("Creswell, J. W. (2014). Research Design. Thousand Oaks: Sage Publications.",
                "Sugiyono. (2019). Metode Penelitian Kuantitatif. Bandung: Alfabeta."):
        _fmt(d.add_paragraph(ref), align=J, hanging=1.0, line=1.0, after=12)
    buf = BytesIO()
    d.save(buf)
    return buf.getvalue()


def messy_docx():
    """Naskah berantakan: font campur, Heading bawaan, daftar, tebal & miring sebagian."""
    d = Document()
    d.add_heading("Pendahuluan", level=1)
    p = d.add_paragraph("Penelitian ini menggunakan pendekatan ")
    p.add_run("mixed methods").italic = True
    p.add_run(" untuk menguji hipotesis tentang adopsi teknologi di sekolah menengah atas di Indonesia.")
    for r in p.runs:
        r.font.name, r.font.size = "Arial", Pt(10)
    d.add_paragraph()
    d.add_paragraph()
    d.add_heading("Latar Belakang", level=2)
    d.add_paragraph("Teknologi pendidikan berkembang pesat dalam satu dekade terakhir sehingga sekolah "
                    "harus menyesuaikan diri dengan cepat terhadap perubahan tersebut.")
    d.add_paragraph("Responden mengisi kuesioner daring.", style="List Number")
    d.add_paragraph("Data dianalisis dengan regresi linear.", style="List Number")
    d.add_heading("Daftar Pustaka", level=1)
    d.add_paragraph("Davis, F. D. (1989). Perceived usefulness. MIS Quarterly, 13(3), 319–340.")
    buf = BytesIO()
    d.save(buf)
    return buf.getvalue()


SAMPLE_TEXT = """BAB II
TINJAUAN PUSTAKA

2.1 Landasan Teori
Teori penerimaan teknologi menjelaskan bagaimana pengguna menerima dan memakai sebuah teknologi baru dalam pekerjaan sehari-hari mereka.
Model ini dikembangkan oleh *Davis* pada tahun 1989 dan telah diuji pada banyak konteks penelitian.

2.1.1 Persepsi Kegunaan
Persepsi kegunaan adalah tingkat keyakinan seseorang bahwa memakai sistem tertentu akan meningkatkan kinerjanya.

Indikator yang digunakan dalam penelitian ini adalah sebagai berikut.
1. Kecepatan kerja meningkat.
2. Kualitas hasil kerja meningkat.

Gambar 2.1 Model penerimaan teknologi

DAFTAR PUSTAKA
Davis, F. D. (1989). Perceived usefulness, perceived ease of use, and user acceptance. MIS Quarterly, 13(3), 319–340.
Venkatesh, V. (2003). User acceptance of information technology. MIS Quarterly, 27(3), 425–478.
"""
