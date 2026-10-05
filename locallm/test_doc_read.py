"""doc_read.py: a person's document as text for cite and extract. Read properly or refused in a sentence: a legacy
encoding, a saved web page, a Word document, a PDF with pages (through pdftotext), a PDF with no text in it."""
import shutil
import zipfile

import pytest

from locallm import cite_docs, doc_read, extract_docs

needs_pdftotext = pytest.mark.skipif(shutil.which("pdftotext") is None, reason="pdftotext (poppler) is not installed")


def pdf(pages: list[list[str]]) -> bytes:
    """A small PDF with one text line per string, a page per list; offsets computed, so any reader takes it."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for lines in pages:
        text = "BT /F1 12 Tf 72 720 Td 16 TL " + " ".join(
            "(" + l.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ") Tj T*" for l in lines) + " ET"
        objects.append(f"<< /Length {len(text)} >>\nstream\n{text}\nendstream")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {len(objects)} 0 R "
                       f"/Resources << /Font << /F1 3 0 R >> >> >>")
        kids.append(len(objects))
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>"
    out, offsets = b"%PDF-1.4\n", []
    for n, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    return out + f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()


def docx(paragraphs: list[str]) -> bytes:
    import io
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" '
                   'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                   'Target="word/document.xml"/></Relationships>')
        z.writestr("word/document.xml", '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                   f"<w:body>{body}</w:body></w:document>")
    return buf.getvalue()


def test_text_in_a_legacy_encoding_a_web_page_and_a_word_document_are_read_as_what_they_say(tmp_path):
    (tmp_path / "letter.txt").write_bytes("Le café coûte 3 euros. Payez avant le 3 mars.".encode("cp1252"))
    pages, how = doc_read.read(tmp_path / "letter.txt")
    assert pages == [(None, "Le café coûte 3 euros. Payez avant le 3 mars.")] and how.startswith("text (")
    (tmp_path / "page.html").write_text("<html><body><h1>Invoice 2291</h1><p>The total due is $5.</p><script>var x = 1;</script></body></html>")
    pages, how = doc_read.read(tmp_path / "page.html")
    assert "The total due is $5." in pages[0][1] and "var x" not in pages[0][1] and how == "html"
    (tmp_path / "terms.docx").write_bytes(docx(["Late payments carry interest of 1.5% a month.", "Questions go to accounts."]))
    pages, how = doc_read.read(tmp_path / "terms.docx")
    assert "interest of 1.5% a month" in pages[0][1] and how == "docx"


@needs_pdftotext
def test_a_pdf_is_read_page_by_page_and_a_quote_is_shown_with_its_page(tmp_path):
    f = tmp_path / "invoice.pdf"
    f.write_bytes(pdf([["Invoice 2291 from Harbor Supply.", "Billed to Northlight Marine."],
                       ["The total due is $1,250.00, payable by March 3, 2026."]]))
    pages, how = doc_read.read(f)
    assert [n for n, _text in pages] == [1, 2] and how == "pdf, 2 pages" and "total due is $1,250.00" in pages[1][1]
    sentences = extract_docs.located([f])
    total = next(s for s in sentences if "total due" in s["text"])
    assert total["page"] == 2 and total["file"] == "invoice.pdf"
    post = lambda url, body: {"choices": [{"message": {"content": f"S{sentences.index(total) + 1}: 1,250.00"}}]}
    rows = extract_docs.extract("h:1", [extract_docs.read_field("total(number): the amount due")], sentences, post)
    assert rows[0]["value"] == 1250.0 and rows[0]["page"] == 2
    assert "(invoice.pdf, page 2, sentence" in extract_docs.render(rows)
    assert [p["title"] for p in cite_docs.passages([f])] == ["invoice.pdf, page 1, part 1", "invoice.pdf, page 2, part 1"]


@needs_pdftotext
def test_a_pdf_with_no_text_in_it_is_refused_as_a_scan(tmp_path):
    f = tmp_path / "scan.pdf"
    f.write_bytes(pdf([[]]))
    with pytest.raises(doc_read.Unreadable, match="no text in it, most likely a scan"):
        doc_read.read(f)


def test_without_pdftotext_a_pdf_is_refused_with_how_to_get_it(tmp_path, monkeypatch):
    f = tmp_path / "invoice.pdf"
    f.write_bytes(pdf([["The total due is $5."]]))
    monkeypatch.setattr(doc_read.shutil, "which", lambda name: None)
    with pytest.raises(doc_read.Unreadable, match="no pdftotext to read it with. Install poppler"):
        doc_read.read(f)


def test_what_cannot_be_read_stops_the_command_with_the_sentence(tmp_path, capsys):
    f = tmp_path / "notes.rtf"
    f.write_bytes(rb"{\rtf1\ansi Hello}")
    with pytest.raises(doc_read.Unreadable):
        doc_read.read(f)
    assert extract_docs.main(["--host", "h:1", "--field", "a: b", str(f)]) == 2 and capsys.readouterr().err.startswith("extract: ")
    assert cite_docs.main(["--host", "h:1", "What?", str(f)]) == 2 and capsys.readouterr().err.startswith("cite: ")
    with pytest.raises(doc_read.Unreadable, match="cannot be opened"):
        doc_read.read(tmp_path / "absent.txt")
