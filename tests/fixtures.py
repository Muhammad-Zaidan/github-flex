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


def _add_heading_numbering(doc):
    """Penomoran bertingkat otomatis (1., 1.1.) yang ditautkan ke Heading 1 & 2."""
    from docx.oxml import parse_xml
    numbering = doc.part.numbering_part.element
    W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    absn = parse_xml(f"""<w:abstractNum {W} w:abstractNumId="90">
      <w:multiLevelType w:val="multilevel"/>
      <w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:pStyle w:val="Heading1"/>
        <w:lvlText w:val="%1."/><w:lvlJc w:val="left"/></w:lvl>
      <w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:pStyle w:val="Heading2"/>
        <w:lvlText w:val="%1.%2."/><w:lvlJc w:val="left"/></w:lvl>
    </w:abstractNum>""")
    first_num = numbering.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}num")
    if first_num is not None:
        first_num.addprevious(absn)
    else:
        numbering.append(absn)
    num = numbering.add_num(90)
    for sid, lvl in (("Heading 1", 0), ("Heading 2", 1)):
        st = doc.styles[sid]
        numPr = st.element.get_or_add_pPr().get_or_add_numPr()
        numPr.get_or_add_ilvl().val = lvl
        numPr.get_or_add_numId().val = num.numId


def journal_template():
    """Jurnal: gaya Title, abstrak miring, kata kunci berlabel tebal, Heading bernomor otomatis."""
    d = Document()
    s = d.sections[0]
    s.page_width, s.page_height = Cm(21), Cm(29.7)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(s, side, Cm(2.5))
    normal = d.styles["Normal"]
    normal.font.name, normal.font.size = "Cambria", Pt(10)
    normal.paragraph_format.first_line_indent = Cm(0.75)
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    for sid, size in (("Heading 1", 11), ("Heading 2", 10)):
        st = d.styles[sid]
        st.font.name, st.font.size, st.font.bold, st.font.italic = "Cambria", Pt(size), True, sid == "Heading 2"
        st.font.color.rgb = None
        st.paragraph_format.space_before, st.paragraph_format.space_after = Pt(12), Pt(6)
        st.paragraph_format.first_line_indent = Cm(0)
    _add_heading_numbering(d)
    t = d.add_paragraph("Pengaruh Literasi Digital terhadap Kinerja Guru", style="Title")
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in t.runs:
        r.font.size, r.font.name = Pt(16), "Cambria"
    for line in ("Ani Lestari¹, Budi Santoso²", "¹Universitas Contoh, ²Institut Teladan"):
        p = d.add_paragraph(line)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.first_line_indent = Cm(0)
    h = d.add_paragraph()
    h.add_run("Abstrak").bold = True
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    h.paragraph_format.first_line_indent = Cm(0)
    h.paragraph_format.space_before = Pt(12)
    a = d.add_paragraph("Penelitian ini bertujuan mengetahui pengaruh literasi digital terhadap kinerja guru "
                        "sekolah dasar di tiga kabupaten dengan pendekatan kuantitatif dan survei daring.")
    a.paragraph_format.left_indent = a.paragraph_format.right_indent = Cm(1)
    a.paragraph_format.first_line_indent = Cm(0)
    for r in a.runs:
        r.italic = True
    k = d.add_paragraph()
    k.add_run("Kata kunci:").bold = True
    k.add_run(" literasi digital; kinerja guru; sekolah dasar")
    k.paragraph_format.left_indent = k.paragraph_format.right_indent = Cm(1)
    k.paragraph_format.first_line_indent = Cm(0)
    d.add_paragraph("Pendahuluan", style="Heading 1")
    for _ in range(2):
        d.add_paragraph("Paragraf isi jurnal memakai Cambria sepuluh poin rata kiri kanan dengan "
                        "indentasi baris pertama tujuh setengah milimeter tanpa jarak antarparagraf.")
    d.add_paragraph("Kajian Teori", style="Heading 2")
    d.add_paragraph("Penjelasan teori ditulis dalam paragraf biasa yang panjangnya cukup untuk dikenali "
                    "sebagai paragraf isi oleh mesin pengenal struktur dokumen.")
    for t in ("Butir pertama daftar.", "Butir kedua daftar."):
        d.add_paragraph(t, style="List Bullet")
    d.add_paragraph("Metode", style="Heading 1")
    d.add_paragraph("Metode penelitian dijelaskan secara rinci agar dapat direplikasi oleh peneliti lain "
                    "pada konteks yang berbeda di kemudian hari.")
    d.add_paragraph("Tabel 1. Statistik deskriptif", style="Caption")
    d.add_paragraph("Daftar Pustaka", style="Heading 1")
    for ref in ("Ng, W. (2012). Can we teach digital natives digital literacy? Computers & Education, 59(3), 1065–1078.",
                "Gilster, P. (1997). Digital literacy. New York: Wiley."):
        p = d.add_paragraph(ref)
        p.paragraph_format.left_indent = Cm(0.75)
        p.paragraph_format.first_line_indent = Cm(-0.75)
    buf = BytesIO()
    d.save(buf)
    return buf.getvalue()


def _png():
    import struct
    import zlib
    raw = b"".join(b"\x00" + b"\x30\x80\x60" * 40 for _ in range(30))
    def chunk(t, data):
        return struct.pack(">I", len(data)) + t + data + struct.pack(">I", zlib.crc32(t + data) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 40, 30, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def rich_docx():
    """Naskah dengan gambar, tabel, persamaan, dan sitasi superskrip."""
    from docx.oxml import parse_xml
    d = Document()
    d.add_paragraph("Judul Naskah Percobaan Yang Cukup Panjang")
    d.add_paragraph("Pendahuluan", style="Heading 1")
    p = d.add_paragraph("Air (H")
    r = p.add_run("2")
    r.font.subscript = True
    p.add_run("O) adalah pelarut universal yang banyak dipakai dalam penelitian laboratorium kimia.")
    r = p.add_run("1")
    r.font.superscript = True
    d.add_paragraph().add_run().add_picture(BytesIO(_png()), width=Cm(4))
    d.add_paragraph("Gambar 1. Contoh gambar penelitian")
    d.add_paragraph("Tabel 1. Data hasil pengukuran")
    t = d.add_table(rows=3, cols=2)
    for i, row in enumerate((("Sampel", "Nilai"), ("A", "1,2"), ("B", "3,4"))):
        for j, v in enumerate(row):
            t.cell(i, j).text = v
    m = d.add_paragraph("Persamaan energi: ")
    M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
    m._p.append(parse_xml(f'<m:oMath xmlns:m="{M}"><m:r><m:t>E=mc</m:t></m:r></m:oMath>'))
    m.add_run(" berlaku umum dalam fisika modern dan banyak dipakai sebagai contoh rumus.")
    buf = BytesIO()
    d.save(buf)
    return buf.getvalue()
