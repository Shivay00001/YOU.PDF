"""Real end-to-end tests: build a real 3-page PDF, then extract/split/merge it."""
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app import app

client = TestClient(app)


def make_pdf(pages_text):
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setTitle("Test Document")
    c.setAuthor("YOU.PDF tests")
    for t in pages_text:
        c.drawString(100, 700, t)
        c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture()
def three_page():
    return make_pdf(["Alpha page one", "Beta page two", "Gamma page three"])


def test_info(three_page):
    r = client.post("/info", files={"file": ("doc.pdf", three_page, "application/pdf")})
    assert r.status_code == 200
    body = r.json()
    assert body["pages"] == 3
    assert body["metadata"]["title"] == "Test Document"


def test_extract_all(three_page):
    r = client.post("/extract", files={"file": ("doc.pdf", three_page, "application/pdf")})
    assert r.status_code == 200
    body = r.json()
    assert body["pages_extracted"] == 3
    assert "Alpha page one" in body["content"][0]["text"]
    assert "Gamma page three" in body["content"][2]["text"]


def test_extract_range(three_page):
    r = client.post(
        "/extract",
        files={"file": ("doc.pdf", three_page, "application/pdf")},
        data={"pages": "2-3"},
    )
    assert r.status_code == 200
    assert [c["page"] for c in r.json()["content"]] == [2, 3]


def test_merge(three_page):
    two_page = make_pdf(["One", "Two"])
    r = client.post(
        "/merge",
        files=[
            ("files", ("a.pdf", three_page, "application/pdf")),
            ("files", ("b.pdf", two_page, "application/pdf")),
        ],
    )
    assert r.status_code == 200
    merged = PdfReader(BytesIO(r.content))
    assert len(merged.pages) == 5
    assert "Alpha page one" in merged.pages[0].extract_text()
    assert "Two" in merged.pages[4].extract_text()


def test_split(three_page):
    r = client.post(
        "/split",
        files={"file": ("doc.pdf", three_page, "application/pdf")},
        data={"ranges": "2-3"},
    )
    assert r.status_code == 200
    out = PdfReader(BytesIO(r.content))
    assert len(out.pages) == 2
    assert "Beta page two" in out.pages[0].extract_text()


def test_split_reorder(three_page):
    r = client.post(
        "/split",
        files={"file": ("doc.pdf", three_page, "application/pdf")},
        data={"ranges": "3,1"},
    )
    assert r.status_code == 200
    out = PdfReader(BytesIO(r.content))
    assert len(out.pages) == 2
    assert "Gamma page three" in out.pages[0].extract_text()
    assert "Alpha page one" in out.pages[1].extract_text()


def test_bad_range_rejected(three_page):
    r = client.post(
        "/split",
        files={"file": ("doc.pdf", three_page, "application/pdf")},
        data={"ranges": "1-9"},
    )
    assert r.status_code == 400


def test_health():
    assert client.get("/health").json() == {"status": "ok", "service": "YOU.PDF"}
