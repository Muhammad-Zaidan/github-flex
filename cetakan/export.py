"""Konversi .docx hasil ke format lain (PDF, ODT, RTF lewat LibreOffice; HTML, Markdown, LaTeX, EPUB lewat Pandoc)."""

import os
import shutil
import subprocess
import tempfile
import threading

FORMATS = {
    "docx": ("Word (.docx)", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "pdf": ("PDF", "application/pdf"),
    "odt": ("OpenDocument (.odt)", "application/vnd.oasis.opendocument.text"),
    "rtf": ("Rich Text (.rtf)", "application/rtf"),
    "html": ("HTML", "text/html; charset=utf-8"),
    "md": ("Markdown", "text/markdown; charset=utf-8"),
    "tex": ("LaTeX", "application/x-tex"),
    "epub": ("EPUB", "application/epub+zip"),
    "txt": ("Teks polos", "text/plain; charset=utf-8"),
}
OFFICE = {"pdf": "pdf", "odt": "odt", "rtf": "rtf"}
PANDOC = {"html": "html", "md": "gfm", "tex": "latex", "epub": "epub", "txt": "plain"}

_office_lock = threading.Lock()
_PROFILE = os.path.join(tempfile.gettempdir(), "cetakan-lo-profile")


def soffice():
    return shutil.which("soffice") or shutil.which("libreoffice")


def available():
    out = {"docx": True}
    has_office, has_pandoc = bool(soffice()), bool(shutil.which("pandoc"))
    for k in FORMATS:
        if k in OFFICE:
            out[k] = has_office
        elif k in PANDOC:
            out[k] = has_pandoc
    return out


class ExportError(RuntimeError):
    pass


def convert(docx_bytes, fmt):
    if fmt == "docx":
        return docx_bytes
    if fmt not in FORMATS:
        raise ExportError(f"Format tidak dikenal: {fmt}")
    with tempfile.TemporaryDirectory(prefix="cetakan-") as tmp:
        src = os.path.join(tmp, "hasil.docx")
        with open(src, "wb") as f:
            f.write(docx_bytes)
        if fmt in OFFICE:
            exe = soffice()
            if not exe:
                raise ExportError("LibreOffice tidak terpasang di server, jadi PDF/ODT/RTF tidak tersedia.")
            # LibreOffice tidak boleh dijalankan paralel dengan profil yang sama.
            with _office_lock:
                proc = subprocess.run(
                    [exe, f"-env:UserInstallation=file://{_PROFILE}", "--headless", "--norestore",
                     "--convert-to", OFFICE[fmt], "--outdir", tmp, src],
                    capture_output=True, timeout=180)
            out = os.path.join(tmp, f"hasil.{fmt}")
        else:
            if not shutil.which("pandoc"):
                raise ExportError("Pandoc tidak terpasang di server, jadi format ini tidak tersedia.")
            out = os.path.join(tmp, f"hasil.{fmt}")
            args = ["pandoc", src, "-f", "docx", "-t", PANDOC[fmt], "-o", out]
            if fmt in ("html", "tex"):
                args.append("--standalone")
            if fmt == "html":
                args += ["--embed-resources", "--metadata", "pagetitle=Hasil Cetakan"]
            proc = subprocess.run(args, capture_output=True, timeout=180, cwd=tmp)
        if not os.path.exists(out):
            msg = (proc.stderr or b"").decode(errors="replace")[-400:]
            raise ExportError(f"Konversi ke {fmt} gagal. {msg}".strip())
        with open(out, "rb") as f:
            return f.read()
