import shutil
from io import BytesIO

import pytest
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Cm

from cetakan.reader import parse_docx, parse_text
from cetakan.render import Renderer, render, title_case
from cetakan.reader import Seg
from cetakan.template import analyze

from fixtures import SAMPLE_TEXT, journal_template, messy_docx, rich_docx, thesis_template

WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"


def run(template, content):
    data, warnings = render(template, content)
    return Document(BytesIO(data)), warnings


def avail(template):
    return set(analyze(Document(BytesIO(template))).styles)


def paras(doc):
    return [p for p in doc.paragraphs if p.text.strip()]


def find(doc, text):
    return next(p for p in doc.paragraphs if p.text.startswith(text))


# ---------------------------------------------------------------------------
# pembelajaran dari contoh
# ---------------------------------------------------------------------------
def test_thesis_template_roles():
    prof = analyze(Document(BytesIO(thesis_template())))
    roles = {p["text"][:20]: p["role"] for p in prof.paragraphs}
    assert roles["BAB I"] == "bab"
    assert roles["PENDAHULUAN"] == "bab_nama"
    assert roles["1.1 Latar Belakang"] == "h1"
    assert roles["1.1.1 Konteks Peneli"] == "h2"
    assert roles["Gambar 1.1 Kerangka "] == "keterangan_gambar"
    assert roles["DAFTAR PUSTAKA"] == "bab"
    assert roles["Creswell, J. W. (201"] == "pustaka"
    assert prof.bab_mode == "split"
    assert prof.breaks["bab"] is True
    assert prof.gaps[("bab_nama", "h1")][0] == 1
    assert prof.styles["h1"].spec == ("d", 2, "")
    assert prof.page["left"] == 4.0


def test_journal_template_roles():
    prof = analyze(Document(BytesIO(journal_template())))
    roles = {p["text"][:12]: p["role"] for p in prof.paragraphs}
    assert roles["Pengaruh Lit"] == "judul"
    assert roles["Ani Lestari¹"] == "penulis"
    assert roles["Penelitian i"] == "abstrak"
    assert roles["Kata kunci: "] == "kata_kunci"
    assert roles["Pendahuluan"] == "h1"
    assert roles["Kajian Teori"] == "h2"
    assert roles["Tabel 1. Sta"] == "keterangan_tabel"
    assert prof.styles["h1"].auto_num
    assert prof.styles["kata_kunci"].label_rPr is not None


# ---------------------------------------------------------------------------
# teks mentah → skripsi
# ---------------------------------------------------------------------------
def test_text_into_thesis_formatting():
    t = thesis_template()
    doc, warnings = run(t, parse_text(SAMPLE_TEXT, available=avail(t)))
    assert warnings == []
    texts = [p.text for p in paras(doc)]
    assert texts[:4] == ["BAB II", "TINJAUAN PUSTAKA", "2.1 Landasan Teori",
                         texts[3]]
    body = find(doc, "Teori penerimaan")
    assert body.alignment == 3  # rata kiri-kanan
    assert round(body.paragraph_format.first_line_indent.cm, 2) == 1.25
    assert body.runs[0].font.name == "Times New Roman" and body.runs[0].font.size.pt == 12
    # *Davis* tetap miring
    assert any(r.text == "Davis" and r.font.italic for r in find(doc, "Model ini").runs)
    # satu baris kosong setelah nama bab, seperti contoh
    ps = doc.paragraphs
    k = [p.text for p in ps].index("TINJAUAN PUSTAKA")
    assert ps[k + 1].text == "" and ps[k + 2].text.startswith("2.1")
    # daftar pustaka di halaman baru dengan indentasi gantung
    assert find(doc, "DAFTAR PUSTAKA").paragraph_format.page_break_before
    ref = find(doc, "Davis, F. D.")
    assert round(ref.paragraph_format.first_line_indent.cm, 2) == -1.0
    # label keterangan tebal, sisanya tidak
    cap = find(doc, "Gambar 2.1")
    assert cap.runs[0].font.bold and not cap.runs[-1].font.bold
    # butir daftar manual: "1.<tab>"
    assert find(doc, "1.\tKecepatan").text == "1.\tKecepatan kerja meningkat."


def test_heading_numbers_are_generated_and_synced():
    t = thesis_template()
    text = "BAB III\nMETODE PENELITIAN\n\n## Desain Penelitian\nIsi paragraf yang cukup panjang untuk dikenali sebagai paragraf isi oleh mesin ini.\n" \
           "### Populasi\nIsi paragraf yang cukup panjang untuk dikenali sebagai paragraf isi oleh mesin ini.\n" \
           "## Teknik Analisis\nIsi paragraf yang cukup panjang untuk dikenali sebagai paragraf isi oleh mesin ini."
    doc, _ = run(t, parse_text(text, available=avail(t)))
    texts = [p.text for p in paras(doc)]
    assert "3.1 Desain Penelitian" in texts
    assert "3.1.1 Populasi" in texts
    assert "3.2 Teknik Analisis" in texts


def test_inline_bab_and_case():
    t = thesis_template()
    doc, _ = run(t, parse_text("BAB IV Hasil dan Pembahasan\n4.1 Hasil\nParagraf isi yang cukup panjang agar dikenali mesin sebagai paragraf isi biasa.", available=avail(t)))
    texts = [p.text for p in paras(doc)]
    assert texts[:3] == ["BAB IV", "HASIL DAN PEMBAHASAN", "4.1 Hasil"]


# ---------------------------------------------------------------------------
# docx berantakan → skripsi
# ---------------------------------------------------------------------------
def test_messy_docx_into_thesis():
    t = thesis_template()
    doc, _ = run(t, parse_docx(messy_docx(), avail(t)))
    texts = [p.text for p in paras(doc)]
    assert texts[:2] == ["BAB I", "PENDAHULUAN"]
    assert "1.1 Latar Belakang" in texts
    body = find(doc, "Penelitian ini")
    assert all(r.font.name == "Times New Roman" for r in body.runs)
    assert any(r.text == "mixed methods" and r.font.italic for r in body.runs)
    assert find(doc, "1.\tResponden").text.endswith("daring.")
    assert find(doc, "2.\tData")
    assert find(doc, "DAFTAR PUSTAKA").paragraph_format.page_break_before


# ---------------------------------------------------------------------------
# jurnal: penomoran otomatis Word
# ---------------------------------------------------------------------------
def test_text_into_journal_auto_numbering():
    t = journal_template()
    doc, _ = run(t, parse_text(SAMPLE_TEXT, available=avail(t)))
    h = find(doc, "Tinjauan Pustaka")       # huruf besar → Huruf Awal Kapital seperti contoh
    assert h.style.name == "Heading 1"
    sub = find(doc, "Landasan Teori")       # nomor manual "2.1" dibuang, Word yang menomori
    assert sub.style.name == "Heading 2"
    items = [p for p in doc.paragraphs if p.text.startswith(("Kecepatan", "Kualitas"))]
    num_ids = {p._p.pPr.numPr.numId.val for p in items}
    assert len(num_ids) == 1 and len(items) == 2
    # definisi penomoran baru bertipe angka, bukan bullet
    numbering = doc.part.numbering_part.element
    nid = num_ids.pop()
    num = next(n for n in numbering.findall(qn("w:num")) if n.numId == nid)
    aid = num.find(qn("w:abstractNumId")).get(qn("w:val"))
    absn = next(a for a in numbering.findall(qn("w:abstractNum")) if a.get(qn("w:abstractNumId")) == aid)
    assert absn.find(f"{qn('w:lvl')}/{qn('w:numFmt')}").get(qn("w:val")) == "decimal"


def test_keyword_label_and_abstract():
    t = journal_template()
    text = ("Judul Tulisan Saya Tentang Sesuatu\nNama Penulis\n\nABSTRAK\n"
            "Ini adalah isi abstrak yang cukup panjang untuk dikenali sebagai paragraf abstrak oleh mesin.\n"
            "Kata kunci: satu; dua; tiga\n\n# Pendahuluan\n"
            "Isi paragraf pendahuluan yang cukup panjang untuk dikenali sebagai paragraf isi oleh mesin.")
    c = parse_text(text, available=avail(t))
    assert [b.role for b in c.blocks] == ["judul", "penulis", "h1", "abstrak", "kata_kunci", "h1", "paragraf"]
    doc, _ = run(t, c)
    kw = find(doc, "Kata kunci")
    assert kw.runs[0].font.bold and not kw.runs[-1].font.bold
    abs_p = find(doc, "Ini adalah isi abstrak")
    assert abs_p.runs[0].font.italic
    assert round(abs_p.paragraph_format.left_indent.cm, 1) == 1.0
    assert find(doc, "Judul Tulisan").style.name == "Title"
    # "Abstrak" memakai gaya persis paragraf "Abstrak" di contoh (tengah, bukan Heading 1 bernomor)
    ah = find(doc, "Abstrak")
    assert ah.alignment == 1 and ah.style.name != "Heading 1"


# ---------------------------------------------------------------------------
# gambar, tabel, persamaan
# ---------------------------------------------------------------------------
def test_rich_content_is_preserved():
    t = journal_template()
    doc, warnings = run(t, parse_docx(rich_docx(), avail(t)))
    body = doc.element.body
    assert len(list(body.iter(f"{WP}inline"))) == 1
    assert any(p.partname.endswith(".png") for p in doc.part.package.parts)
    assert len(list(body.iter(f"{M}oMath"))) == 1
    assert len(doc.tables) == 1
    tblPr = doc.tables[0]._tbl.tblPr
    assert tblPr.find(qn("w:tblBorders")) is not None or tblPr.find(qn("w:tblStyle")) is not None
    sub = find(doc, "Air (H")
    assert any(r.text == "2" and r.font.subscript for r in sub.runs)
    assert any(r.text == "1" and r.font.superscript for r in sub.runs)
    ids = [e.get("id") for e in body.iter(f"{WP}docPr")]
    assert len(ids) == len(set(ids))


def test_text_tables():
    t = thesis_template()
    text = "Tabel 1.1 Data\nNama\tNilai\nA\t1\nB\t2\n\n| x | y |\n|---|---|\n| 1 | 2 |"
    doc, _ = run(t, parse_text(text, available=avail(t)))
    assert len(doc.tables) == 2
    assert [c.text for c in doc.tables[0].rows[1].cells] == ["A", "1"]
    assert [c.text for c in doc.tables[1].rows[1].cells] == ["1", "2"]
    # gaya tabel contoh (Table Grid) dipakai
    assert doc.tables[0].style.name == "Table Grid"


# ---------------------------------------------------------------------------
# koreksi peran
# ---------------------------------------------------------------------------
def test_role_overrides():
    t = thesis_template()
    c = parse_text("Paragraf pertama yang cukup panjang untuk dikenali sebagai paragraf isi oleh mesin.\nCatatan penting", available=avail(t))
    c.blocks[1].role = "kutipan"
    c.blocks[0].role = "abaikan"
    doc, _ = run(t, c)
    assert [p.text for p in paras(doc)] == ["Catatan penting"]
    # koreksi pada contoh: jadikan paragraf isi contoh sebagai kutipan → gaya kutipan ada
    r = Renderer(t, {4: "kutipan"})
    assert "kutipan" in r.profile.styles


def test_title_case():
    assert title_case([Seg("METODE DAN HASIL PENELITIAN")])[0].text == "Metode dan Hasil Penelitian"


def test_merge_lines_from_pdf():
    c = parse_text("Ini kalimat yang ter-\nputus dari PDF dan\nberlanjut di baris berikutnya.\n\n1.1 Judul Baru", merge_lines=True)
    assert c.blocks[0].text == "Ini kalimat yang terputus dari PDF dan berlanjut di baris berikutnya."
    assert c.blocks[1].role == "h2"   # tanpa bab, "1.1" adalah tingkat dua


def test_list_detection_vs_heading():
    c = parse_text("Langkah penelitian:\n1. Observasi\n2. Wawancara\n3. Dokumentasi")
    assert [b.role for b in c.blocks][1:] == ["daftar", "daftar", "daftar"]


# ---------------------------------------------------------------------------
# server & ekspor
# ---------------------------------------------------------------------------
@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from cetakan.server import app
    return TestClient(app)


def test_api_flow(client):
    t = thesis_template()
    r = client.post("/api/template", files={"file": ("contoh.docx", t)})
    assert r.status_code == 200, r.text
    tid = r.json()["template_id"]
    assert "bab" in r.json()["roles"]
    r = client.post("/api/content", data={"text": SAMPLE_TEXT, "template_id": tid})
    cid = r.json()["content_id"]
    blocks = r.json()["blocks"]
    assert blocks[0]["role"] == "bab"
    r = client.post("/api/preview", json={"template_id": tid, "content_id": cid})
    items = r.json()["items"]
    assert items[0]["runs"][0]["t"] == "BAB II"
    assert any(i.get("page_break") for i in items)
    r = client.post("/api/generate", json={"template_id": tid, "content_id": cid, "format": "docx",
                                           "roles": {"3": "kutipan"}})
    assert r.status_code == 200
    assert "BAB-II.docx" in r.headers["content-disposition"]
    doc = Document(BytesIO(r.content))
    assert doc.paragraphs[0].text == "BAB II"
    r = client.post(f"/api/template/{tid}/roles", json={"overrides": {"4": "kutipan"}})
    assert "kutipan" in r.json()["roles"]


def test_api_rejects_non_docx(client):
    r = client.post("/api/template", files={"file": ("contoh.pdf", b"%PDF-1.4 ...")})
    assert r.status_code == 400
    assert "docx" in r.json()["detail"]


@pytest.mark.skipif(not shutil.which("soffice"), reason="LibreOffice tidak terpasang")
def test_export_pdf():
    from cetakan.export import convert
    t = thesis_template()
    data, _ = render(t, parse_text(SAMPLE_TEXT, available=avail(t)))
    pdf = convert(data, "pdf")
    assert pdf.startswith(b"%PDF")


@pytest.mark.skipif(not shutil.which("pandoc"), reason="Pandoc tidak terpasang")
def test_export_markdown():
    from cetakan.export import convert
    t = thesis_template()
    data, _ = render(t, parse_text(SAMPLE_TEXT, available=avail(t)))
    md = convert(data, "md").decode()
    assert "TINJAUAN PUSTAKA" in md and "*Davis*" in md


# ---------------------------------------------------------------------------
# catatan kaki
# ---------------------------------------------------------------------------
FN_TEXT = ("BAB I\nPENDAHULUAN\n1.1 Latar Belakang\nHukum adat diakui konstitusi[^1] dan dihormati negara "
           "sebagai bagian dari **sistem hukum nasional[^2]** yang hidup.\n\n"
           "[^1]: Pasal 18B ayat (2) UUD 1945.\n[^2]: Soepomo, *Bab-Bab tentang Hukum Adat*, hlm. 3.")


def _footnotes(doc):
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    from docx.oxml import parse_xml
    part = next(r.target_part for r in doc.part.rels.values() if r.reltype == RT.FOOTNOTES)
    root = parse_xml(part.blob)
    return [n for n in root.findall(qn("w:footnote")) if n.get(qn("w:type")) is None]


def test_footnotes_from_text_and_roundtrip():
    t = thesis_template()
    doc, _ = run(t, parse_text(FN_TEXT, available=avail(t)))
    notes = _footnotes(doc)
    assert ["".join(x.text for x in n.iter(qn("w:t"))).strip() for n in notes] == \
        ["Pasal 18B ayat (2) UUD 1945.", "Soepomo, Bab-Bab tentang Hukum Adat, hlm. 3."]
    refs = list(doc.element.body.iter(qn("w:footnoteReference")))
    assert [r.get(qn("w:id")) for r in refs] == [n.get(qn("w:id")) for n in notes]
    # isi catatan: 10 pt, miring tetap miring
    assert any(r.find(qn("w:rPr")) is not None and r.find(qn("w:rPr")).find(qn("w:i")) is not None
               for r in notes[1].iter(qn("w:r")))
    # naskah .docx bercatatan kaki dibaca ulang tanpa kehilangan catatan
    buf = BytesIO()
    doc.save(buf)
    doc2, warnings = run(t, parse_docx(buf.getvalue(), avail(t)))
    assert len(_footnotes(doc2)) == 2 and warnings == []


def test_footnote_style_learned_from_template():
    t = thesis_template()
    first, _ = render(t, parse_text(FN_TEXT, available=avail(t)))
    # ubah gaya catatan kaki di "contoh": rata kiri, 9 pt, pemisah tab
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    d = Document(BytesIO(first))
    part = next(r.target_part for r in d.part.rels.values() if r.reltype == RT.FOOTNOTES)
    xml = part.blob.decode().replace('<w:jc w:val="both"/>', '<w:jc w:val="left"/>').replace('w:val="20"', 'w:val="18"')
    part._blob = xml.encode()
    buf = BytesIO()
    d.save(buf)
    doc, _ = run(buf.getvalue(), parse_text("Isi[^a] paragraf yang cukup panjang supaya dikenali sebagai paragraf isi oleh mesin.\n[^a]: Catatan.", available=None))
    note = _footnotes(doc)[0]
    assert note.find(f".//{qn('w:jc')}").get(qn("w:val")) == "left"
    assert note.find(f".//{qn('w:sz')}").get(qn("w:val")) == "18"


# ---------------------------------------------------------------------------
# keabsahan urutan elemen OOXML (Word menolak urutan yang salah)
# ---------------------------------------------------------------------------
ORDER = {
    "pPr": "pStyle keepNext keepLines pageBreakBefore framePr widowControl numPr suppressLineNumbers pBdr shd "
           "tabs suppressAutoHyphens kinsoku wordWrap overflowPunct topLinePunct autoSpaceDE autoSpaceDN bidi "
           "adjustRightInd snapToGrid spacing ind contextualSpacing mirrorIndents suppressOverlap jc "
           "textDirection textAlignment textboxTightWrap outlineLvl divId cnfStyle rPr sectPr pPrChange",
    "rPr": "rStyle rFonts b bCs i iCs caps smallCaps strike dstrike outline shadow emboss imprint noProof "
           "snapToGrid vanish webHidden color spacing w kern position sz szCs highlight u effect bdr shd "
           "fitText vertAlign rtl cs em lang eastAsianLayout specVanish oMath",
    "tblPr": "tblStyle tblpPr tblOverlap bidiVisual tblStyleRowBandSize tblStyleColBandSize tblW jc "
             "tblCellSpacing tblInd tblBorders shd tblLayout tblCellMar tblLook tblCaption tblDescription",
    "tcPr": "cnfStyle tcW gridSpan hMerge vMerge tcBorders shd noWrap tcMar textDirection tcFitText vAlign "
            "hideMark",
}


def assert_schema_order(root):
    for tag, seq in ORDER.items():
        order = {n: k for k, n in enumerate(seq.split())}
        for el in root.iter(qn(f"w:{tag}")):
            names = [c.tag.split("}")[1] for c in el if c.tag.split("}")[1] in order]
            idx = [order[n] for n in names]
            assert idx == sorted(idx) and len(set(names)) == len(names), (tag, names)


@pytest.mark.parametrize("make", [
    lambda: run(thesis_template(), parse_text(SAMPLE_TEXT + "\nNama\tNilai\nA\t1", available=avail(thesis_template()))),
    lambda: run(journal_template(), parse_text(SAMPLE_TEXT, available=avail(journal_template()))),
    lambda: run(journal_template(), parse_docx(rich_docx(), avail(journal_template()))),
    lambda: run(thesis_template(), parse_docx(messy_docx(), avail(thesis_template()))),
    lambda: run(thesis_template(), parse_text(FN_TEXT)),
])
def test_output_is_schema_ordered(make):
    doc, _ = make()
    assert_schema_order(doc.element)
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    from docx.oxml import parse_xml
    for rel in doc.part.rels.values():
        if rel.reltype in (RT.FOOTNOTES, RT.NUMBERING, RT.STYLES):
            assert_schema_order(parse_xml(rel.target_part.blob) if not hasattr(rel.target_part, "element")
                                else rel.target_part.element)
