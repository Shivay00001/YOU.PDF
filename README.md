# YOU.PDF

A real PDF toolkit API: upload PDFs to extract text, read metadata, merge
documents, or split out page ranges.

## Run

```bash
pip install -r requirements.txt
uvicorn app:app --port 8001
```

## Endpoints

- `POST /info` — multipart `file` → page count, metadata, size
- `POST /extract` — multipart `file`, optional form field `pages` (`"1-2,3"`)
  → text per page
- `POST /merge` — multipart `files` (2+) → merged PDF download
- `POST /split` — multipart `file` + form field `ranges` (`"1-2,3"`) →
  PDF containing those pages in the given order
- `GET /health`

## Test

```bash
pytest -q
```

## Notes

Encrypted PDFs are rejected with a clear 400. Text extraction quality depends
on the PDF itself (scanned-image PDFs have no extractable text layer).
