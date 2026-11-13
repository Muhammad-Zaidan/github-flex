"""Server web Cetakan (FastAPI)."""

import copy
import hashlib
import json
import os
import re
import threading
from collections import OrderedDict
from io import BytesIO
from urllib.parse import quote

from docx import Document
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__
from .export import FORMATS, ExportError, available, convert
from .reader import parse_docx, parse_text
from .preview import build as build_preview
from .render import Renderer
from .roles import ROLES
from .template import analyze, describe

STATIC = os.path.join(os.path.dirname(__file__), "static")
MAX_UPLOAD = 40 * 1024 * 1024
DOCX_MAGIC = b"PK\x03\x04"


class LRU:
    def __init__(self, size):
        self.size, self.data, self.lock = size, OrderedDict(), threading.Lock()

    def put(self, key, value):
        with self.lock:
            self.data[key] = value
            self.data.move_to_end(key)
            while len(self.data) > self.size:
                self.data.popitem(last=False)

    def get(self, key):
        with self.lock:
            if key not in self.data:
                return None
            self.data.move_to_end(key)
            return self.data[key]


templates = LRU(64)   # id → bytes
contents = LRU(64)    # id → Content

app = FastAPI(title="Cetakan", version=__version__)


def _read_docx(upload: UploadFile, what):
    data = upload.file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, f"Berkas {what} terlalu besar (maksimal 40 MB).")
    if not data.startswith(DOCX_MAGIC):
        name = (upload.filename or "").lower()
        hint = " Simpan dulu sebagai .docx di Word (File → Save As)." if name.endswith((".doc", ".pdf", ".odt")) else ""
        raise HTTPException(400, f"Berkas {what} harus berformat .docx.{hint}")
    return data


def _template(tid):
    data = templates.get(tid)
    if data is None:
        raise HTTPException(404, "Contoh format sudah kedaluwarsa di server. Unggah ulang berkas contoh.")
    return data


def _overrides(raw):
    return {int(k): v for k, v in (raw or {}).items() if v in ROLES}


@app.get("/api/info")
def info():
    return {"version": __version__, "roles": ROLES,
            "formats": {k: {"label": v[0], "available": available().get(k, False)} for k, v in FORMATS.items()}}


@app.post("/api/template")
def upload_template(file: UploadFile = File(...)):
    data = _read_docx(file, "contoh")
    tid = hashlib.sha1(data).hexdigest()[:16]
    try:
        prof = analyze(Document(BytesIO(data)))
    except Exception as e:  # berkas rusak / bukan dokumen Word
        raise HTTPException(400, f"Berkas contoh tidak dapat dibaca: {e}")
    templates.put(tid, data)
    return {"template_id": tid, "name": file.filename, **describe(prof)}


class TemplateRoles(BaseModel):
    overrides: dict = {}


@app.post("/api/template/{tid}/roles")
def template_roles(tid: str, body: TemplateRoles):
    data = _template(tid)
    prof = analyze(Document(BytesIO(data)), _overrides(body.overrides))
    return {"template_id": tid, **describe(prof)}


def _block_json(i, b):
    out = {"i": i, "kind": b.kind, "role": b.role, "auto": b.auto_role}
    if b.kind == "table":
        if b.rows is not None:
            rows = [["".join(s.text for s in c) for c in r] for r in b.rows]
        else:
            rows = [[" ".join("".join(s.text for s in p) for p in c) for c in r] for r in (b.cells or [])]
        out["rows"] = [r[:12] for r in rows[:60]]
        out["text"] = f"Tabel {len(rows)} baris"
    else:
        out["segs"] = [{"media": True} if s.xml is not None else
                       {"t": "*", "sup": True, "note": " ".join("".join(x.text for x in ps) for ps in s.note)}
                       if s.note is not None else
                       {"t": s.text, "b": s.b, "i": s.i, "u": s.u, "sup": s.sup, "sub": s.sub}
                       for s in b.segs]
        out["text"] = b.text
    return out


@app.post("/api/content")
def upload_content(text: str = Form(""), merge_lines: bool = Form(False), template_id: str = Form(""),
                   file: UploadFile | None = File(None)):
    avail = None
    if template_id and templates.get(template_id) is not None:
        avail = set(analyze(Document(BytesIO(templates.get(template_id)))).styles)
    if file is not None and file.filename:
        data = _read_docx(file, "naskah")
        try:
            content = parse_docx(data, available=avail)
        except Exception as e:
            raise HTTPException(400, f"Berkas naskah tidak dapat dibaca: {e}")
        key = hashlib.sha1(data + (template_id or "").encode()).hexdigest()[:16]
    else:
        if not text.strip():
            raise HTTPException(400, "Naskah masih kosong.")
        content = parse_text(text, merge_lines=merge_lines, available=avail)
        key = hashlib.sha1(f"{merge_lines}|{template_id}|{text}".encode()).hexdigest()[:16]
    contents.put(key, content)
    return {"content_id": key, "warnings": content.warnings,
            "blocks": [_block_json(i, b) for i, b in enumerate(content.blocks)]}


class GenerateRequest(BaseModel):
    template_id: str
    content_id: str
    format: str = "docx"
    template_overrides: dict = {}
    roles: dict = {}
    filename: str | None = None
    inline: bool = False


def _filename(name, content):
    if not name:
        title = next((b.text for b in content.blocks if b.role in ("judul", "bab_nama", "bab")), "")
        name = title or "hasil-cetakan"
    name = re.sub(r"[^\w\- ]+", "", name, flags=re.U).strip()[:80] or "hasil-cetakan"
    return re.sub(r"\s+", "-", name)


def _render(req):
    data = _template(req.template_id)
    content = contents.get(req.content_id)
    if content is None:
        raise HTTPException(404, "Naskah sudah kedaluwarsa di server. Proses ulang naskahnya.")
    work = copy.copy(content)
    work.blocks = [copy.copy(b) for b in content.blocks]
    for k, r in _overrides(req.roles).items():
        if 0 <= k < len(work.blocks) and work.blocks[k].kind == "p":
            work.blocks[k].role = r
    renderer = Renderer(data, _overrides(req.template_overrides))
    docx_bytes = renderer.render(work)
    return renderer, docx_bytes, work


@app.post("/api/preview")
def preview(req: GenerateRequest):
    renderer, _, _ = _render(req)
    return build_preview(renderer)


@app.post("/api/generate")
def generate(req: GenerateRequest):
    if req.format not in FORMATS:
        raise HTTPException(400, "Format keluaran tidak dikenal.")
    renderer, docx_bytes, work = _render(req)
    warnings = sorted(renderer.warnings)
    try:
        out = convert(docx_bytes, req.format)
    except ExportError as e:
        raise HTTPException(503, str(e))
    name = f"{_filename(req.filename, work)}.{req.format}"
    disp = "inline" if req.inline else "attachment"
    headers = {
        "Content-Disposition": f"{disp}; filename=\"{quote(name)}\"; filename*=UTF-8''{quote(name)}",
        "X-Cetakan-Warnings": quote(json.dumps(warnings)),
        "Access-Control-Expose-Headers": "X-Cetakan-Warnings, Content-Disposition",
        "Cache-Control": "no-store",
    }
    return Response(out, media_type=FORMATS[req.format][1], headers=headers)


@app.exception_handler(HTTPException)
def http_error(_, exc):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC), name="static")


def main():
    import argparse

    import uvicorn
    ap = argparse.ArgumentParser(description="Jalankan web app Cetakan.")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--buka", action="store_true", help="buka browser otomatis")
    a = ap.parse_args()
    url = f"http://{'127.0.0.1' if a.host in ('0.0.0.0', '::') else a.host}:{a.port}"
    print(f"Cetakan berjalan di {url}  (tekan Ctrl+C untuk berhenti)")
    if a.buka:
        import threading
        import webbrowser
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
