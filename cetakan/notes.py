"""Catatan kaki: gaya dipelajari dari contoh (bila ada), isi dari naskah."""

from copy import deepcopy

from docx.opc.constants import CONTENT_TYPE as CT
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.packuri import PackURI
from docx.opc.part import Part, XmlPart
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Pt
from lxml import etree

EMPTY = (f'<w:footnotes {nsdecls("w", "r")}>'
         '<w:footnote w:type="separator" w:id="-1"><w:p><w:pPr><w:spacing w:after="0" w:line="240" '
         'w:lineRule="auto"/></w:pPr><w:r><w:separator/></w:r></w:p></w:footnote>'
         '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:pPr><w:spacing w:after="0" '
         'w:line="240" w:lineRule="auto"/></w:pPr><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>'
         '</w:footnotes>')


def _style_id(doc, *names):
    for s in doc.styles.element.findall(qn("w:style")):
        n = s.find(qn("w:name"))
        if n is not None and n.get(qn("w:val"), "").lower() in names:
            return s.get(qn("w:styleId"))
    return None


def _clean(el):
    el = deepcopy(el)
    for x in el.findall(qn("w:rPrChange")) + el.findall(qn("w:pPrChange")):
        el.remove(x)
    return el


class Footnotes:
    def __init__(self, doc, body_rpr, para_rpr):
        """`body_rpr`: rPr penanda catatan di badan teks contoh (atau None)."""
        self.doc = doc
        self.part = None
        self.root = None
        self.body_rpr = body_rpr
        self.para_rpr = para_rpr
        self.texts = {}
        for rel in doc.part.rels.values():
            if rel.reltype == RT.FOOTNOTES and not rel.is_external:
                self.part = rel.target_part
        self.ppr = self.ref_rpr = self.text_rpr = None
        self.sep = " "
        if self.part is not None:
            self.root = parse_xml(self.part.blob)
            normal = [n for n in self.root.findall(qn("w:footnote"))
                      if n.get(qn("w:type")) in (None, "normal")]
            for n in normal:
                if self.ppr is None:
                    self._learn(n)
                self.root.remove(n)
        self.next_id = max([int(n.get(qn("w:id"))) for n in self.root.findall(qn("w:footnote"))]
                           + [0]) + 1 if self.root is not None else 1

    def _learn(self, note):
        p = note.find(qn("w:p"))
        if p is None:
            return
        pPr = p.find(qn("w:pPr"))
        self.ppr = _clean(pPr) if pPr is not None else OxmlElement("w:pPr")
        runs = p.findall(qn("w:r"))
        for k, r in enumerate(runs):
            if r.find(qn("w:footnoteRef")) is not None:
                rp = r.find(qn("w:rPr"))
                self.ref_rpr = _clean(rp) if rp is not None else None
                if k + 1 < len(runs):
                    t = "".join(x.text or "" for x in runs[k + 1].findall(qn("w:t")))
                    tab = runs[k + 1].find(qn("w:tab")) is not None
                    if tab:
                        self.sep = "\t"
                    elif t and not t.strip():
                        self.sep = t
            elif self.text_rpr is None and "".join(x.text or "" for x in r.findall(qn("w:t"))).strip():
                rp = r.find(qn("w:rPr"))
                self.text_rpr = _clean(rp) if rp is not None else OxmlElement("w:rPr")

    def _ensure(self):
        if self.root is not None and self.part is not None:
            return
        self.root = parse_xml(EMPTY)
        self.part = Part(PackURI("/word/footnotes.xml"), CT.WML_FOOTNOTES, b"", self.doc.part.package)
        self.doc.part.relate_to(self.part, RT.FOOTNOTES)

    def _defaults(self):
        if self.ppr is None:
            self.ppr = OxmlElement("w:pPr")
            sid = _style_id(self.doc, "footnote text")
            if sid:
                ps = OxmlElement("w:pStyle")
                ps.set(qn("w:val"), sid)
                self.ppr.append(ps)
            else:
                sp = OxmlElement("w:spacing")
                sp.set(qn("w:after"), "0")
                sp.set(qn("w:line"), "240")
                sp.set(qn("w:lineRule"), "auto")
                self.ppr.append(sp)
                jc = OxmlElement("w:jc")
                jc.set(qn("w:val"), "both")
                self.ppr.append(jc)
        if self.text_rpr is None:
            if _style_id(self.doc, "footnote text"):
                self.text_rpr = OxmlElement("w:rPr")
            else:
                self.text_rpr = deepcopy(self.para_rpr) if self.para_rpr is not None else OxmlElement("w:rPr")
                for x in self.text_rpr.findall(qn("w:szCs")):
                    self.text_rpr.remove(x)
                self.text_rpr.sz_val = Pt(10)
        if self.ref_rpr is None:
            self.ref_rpr = self.reference_rpr()

    def reference_rpr(self):
        """rPr untuk angka penanda catatan."""
        if self.body_rpr is not None:
            return deepcopy(self.body_rpr)
        rpr = OxmlElement("w:rPr")
        sid = _style_id(self.doc, "footnote reference")
        if sid:
            rs = OxmlElement("w:rStyle")
            rs.set(qn("w:val"), sid)
            rpr.append(rs)
        else:
            va = OxmlElement("w:vertAlign")
            va.set(qn("w:val"), "superscript")
            rpr.append(va)
        return rpr

    def add(self, paragraphs, make_runs):
        """Tambah satu catatan; `make_runs(p, segs, rPr)` menulis run teks. Kembalikan run penanda."""
        self._ensure()
        self._defaults()
        nid = self.next_id
        self.next_id += 1
        note = OxmlElement("w:footnote")
        note.set(qn("w:id"), str(nid))
        texts = []
        for k, segs in enumerate(paragraphs or [[]]):
            p = OxmlElement("w:p")
            p.append(deepcopy(self.ppr))
            if k == 0:
                r = OxmlElement("w:r")
                r.append(deepcopy(self.ref_rpr))
                r.append(OxmlElement("w:footnoteRef"))
                p.append(r)
                r = OxmlElement("w:r")
                r.append(deepcopy(self.text_rpr))
                if self.sep == "\t":
                    r.append(OxmlElement("w:tab"))
                else:
                    t = OxmlElement("w:t")
                    t.text = self.sep
                    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                    r.append(t)
                p.append(r)
            make_runs(p, [s for s in segs if s.xml is None and s.note is None], self.text_rpr)
            texts.append("".join(s.text for s in segs if s.note is None))
            note.append(p)
        self.root.append(note)
        self.texts[str(nid)] = " ".join(texts).strip()
        ref = OxmlElement("w:r")
        ref.append(self.reference_rpr() if self.body_rpr is not None else deepcopy(self.ref_rpr))
        fr = OxmlElement("w:footnoteReference")
        fr.set(qn("w:id"), str(nid))
        ref.append(fr)
        return ref

    def flush(self):
        if self.root is None or self.part is None:
            return
        data = etree.tostring(self.root, xml_declaration=True, encoding="UTF-8", standalone=True)
        if isinstance(self.part, XmlPart):
            self.part._element = parse_xml(data)
        else:
            self.part._blob = data
