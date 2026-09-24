"""YOU.PDF - a real PDF toolkit API.

Endpoints:
  POST /info      upload a PDF -> page count, metadata, size
  POST /extract   upload a PDF -> extracted text per page
  POST /merge     upload 2+ PDFs -> one merged PDF (download)
  POST /split    upload a PDF + page ranges -> split PDF(s) (download)
Run: uvicorn app:app --port 8001
"""
from io import BytesIO
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pypdf import PdfReader, PdfWriter

app = FastAPI(title="YOU.PDF", version="1.0.0")


def _read_pdf(data: bytes) -> PdfReader:
    try:
        reader = PdfReader(BytesIO(data))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Not a readable PDF: {exc}")
    if reader.is_encrypted:
        raise HTTPException(status_code=400, detail="Encrypted PDFs are not supported")
    return reader


def _parse_ranges(spec: str, n_pages: int) -> List[List[int]]:
    """Parse '1-3,5' style ranges into 1-based page number lists."""
    parts: List[List[int]] = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            a, b = chunk.split("-", 1)
            start, end = int(a.strip()), int(b.strip())
            if start < 1 or end > n_pages or start > end:
                raise HTTPException(status_code=400, detail=f"Bad range '{chunk}' for a {n_pages}-page PDF")
            parts.append(list(range(start, end + 1)))
        else:
            p = int(chunk)
            if p < 1 or p > n_pages:
                raise HTTPException(status_code=400, detail=f"Bad page '{chunk}' for a {n_pages}-page PDF")
            parts.append([p])
    if not parts:
        raise HTTPException(status_code=400, detail="No valid ranges given")
    return parts


@app.post("/info")
async def info(file: UploadFile = File(...)):
    data = await file.read()
    reader = _read_pdf(data)
    meta = reader.metadata or {}
    return {
        "filename": file.filename,
        "pages": len(reader.pages),
        "size_bytes": len(data),
        "metadata": {
            "title": meta.get("/Title"),
            "author": meta.get("/Author"),
            "creator": meta.get("/Creator"),
            "producer": meta.get("/Producer"),
            "creation_date": str(meta.get("/CreationDate")) if meta.get("/CreationDate") else None,
        },
    }


@app.post("/extract")
async def extract(file: UploadFile = File(...), pages: Optional[str] = Form(None)):
    """Extract text. Optional `pages` form field like '1-2,3' limits extraction."""
    data = await file.read()
    reader = _read_pdf(data)
    n = len(reader.pages)
    wanted = list(range(1, n + 1))
    if pages:
        wanted = [p for group in _parse_ranges(pages, n) for p in group]
    out = []
    for p in wanted:
        out.append({"page": p, "text": reader.pages[p - 1].extract_text() or ""})
    return {"filename": file.filename, "pages_extracted": len(out), "content": out}


@app.post("/merge")
async def merge(files: List[UploadFile] = File(...)):
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="Upload at least 2 PDFs to merge")
    writer = PdfWriter()
    total = 0
    for f in files:
        reader = _read_pdf(await f.read())
        for page in reader.pages:
            writer.add_page(page)
            total += 1
    buf = BytesIO()
    writer.write(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=merged.pdf"},
    )


@app.post("/split")
async def split(file: UploadFile = File(...), ranges: str = Form(...)):
    """`ranges` like '1-2,3': returns one PDF containing the listed pages in order.
    Use `mode=zip` ... (single PDF per request keeps the API honest and simple)."""
    data = await file.read()
    reader = _read_pdf(data)
    groups = _parse_ranges(ranges, len(reader.pages))
    writer = PdfWriter()
    selected = 0
    for group in groups:
        for p in group:
            writer.add_page(reader.pages[p - 1])
            selected += 1
    buf = BytesIO()
    writer.write(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=split.pdf"},
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "YOU.PDF"}
