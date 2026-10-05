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


# ---- spreadsheets, slides, OpenDocument and email (2026-10-05). The first test of each format is a file written
# here part by part, so that what is read is known exactly; the last test of the file reads what LibreOffice itself
# writes, where it is installed.

def archive(path, parts: dict):
    with zipfile.ZipFile(path, "w") as z:
        for name, text in parts.items():
            z.writestr(name, text)
    return path


S = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
RELS = 'xmlns="http://schemas.openxmlformats.org/package/2006/relationships"'


def test_a_spreadsheet_is_read_sheet_by_sheet_with_dates_as_dates_and_values_as_last_calculated(tmp_path):
    book = archive(tmp_path / "budget.xlsx", {
        "xl/workbook.xml": f'<workbook {S}><sheets><sheet name="Budget" sheetId="1" r:id="rId2"/><sheet name="Old" sheetId="2" state="hidden" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": f'<Relationships {RELS}><Relationship Id="rId1" Type="x/worksheet" Target="worksheets/sheet1.xml"/>'
                                      f'<Relationship Id="rId2" Type="x/worksheet" Target="/xl/worksheets/sheet2.xml"/></Relationships>',
        "xl/sharedStrings.xml": f'<sst {S}><si><t>Item</t></si><si><r><t>Tra</t></r><r><t>in</t></r><rPh><t>ignored</t></rPh></si><si><t>When</t></si></sst>',
        "xl/styles.xml": f'<styleSheet {S}><numFmts><numFmt numFmtId="164" formatCode="[$-409]d\\ mmm\\ yyyy;@"/><numFmt numFmtId="165" formatCode="0.0 &quot;days&quot;"/></numFmts>'
                         f'<cellXfs><xf numFmtId="0"/><xf numFmtId="14"/><xf numFmtId="164"/><xf numFmtId="165"/><xf numFmtId="20"/></cellXfs></styleSheet>',
        "xl/worksheets/sheet2.xml": f'<worksheet {S}><sheetData>'
                                    '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>2</v></c><c r="D1" t="inlineStr"><is><t>Cost</t></is></c></row>'
                                    '<row r="2"><c r="A2" t="s"><v>1</v></c><c r="B2" s="1"><v>45567</v></c><c r="D2"><v>48.5</v></c></row>'
                                    '<row r="3"><c r="A3" t="str"><f>A2&amp;"!"</f><v>Train!</v></c><c r="B3" s="2"><v>45568.75</v></c><c r="D3" s="3"><v>3</v></c></row>'
                                    '<row r="4"><c r="A4" t="b"><v>1</v></c><c r="B4" s="4"><v>0.5</v></c><c r="D4"><f>SUM(D2:D3)</f></c><c r="E4"><v>0.30000000000000004</v></c></row>'
                                    '<row r="5"></row></sheetData></worksheet>',
        "xl/worksheets/sheet1.xml": f'<worksheet {S}><sheetData><row r="1"><c r="A1"><v>7</v></c></row></sheetData></worksheet>'})
    pages, how = doc_read.read(book)
    assert how == "xlsx, 2 sheets" and [n for n, _ in pages] == [1, 2]
    assert pages[0][1].split("\n") == ["Sheet: Budget", "Item\tWhen\t\tCost", "Train\t2024-10-02\t\t48.5", "Train!\t2024-10-03 18:00:00\t\t3",
                                       "TRUE\t12:00:00\t\t=SUM(D2:D3)\t0.3"]
    assert pages[1][1] == "Sheet: Old (hidden)\n7"
    empty = archive(tmp_path / "empty.xlsx", {"xl/workbook.xml": f'<workbook {S}><sheets><sheet name="A" sheetId="1" r:id="rId1"/></sheets></workbook>',
                                                "xl/_rels/workbook.xml.rels": f'<Relationships {RELS}><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
                                                "xl/worksheets/sheet1.xml": f'<worksheet {S}><sheetData/></worksheet>'})
    with pytest.raises(doc_read.Unreadable, match="none of its sheets has a value"):
        doc_read.read(empty)
    (tmp_path / "broken.xlsx").write_bytes(b"PK\x03\x04 not really")
    with pytest.raises(doc_read.Unreadable, match="could not be opened as a spreadsheet"):
        doc_read.read(tmp_path / "broken.xlsx")
    old = archive(tmp_path / "mac.xlsx", {"xl/workbook.xml": f'<workbook {S}><workbookPr date1904="1"/><sheets><sheet name="A" sheetId="1" r:id="rId1"/></sheets></workbook>',
                                            "xl/_rels/workbook.xml.rels": f'<Relationships {RELS}><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
                                            "xl/styles.xml": f'<styleSheet {S}><cellXfs><xf numFmtId="14"/></cellXfs></styleSheet>',
                                            "xl/worksheets/sheet1.xml": f'<worksheet {S}><sheetData><row><c s="0"><v>1</v></c></row></sheetData></worksheet>'})
    assert doc_read.read(old)[0][0][1] == "Sheet: A\n1904-01-02"


def test_slides_are_read_in_the_presentations_order_with_the_speakers_notes(tmp_path):
    P = 'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    slide = lambda *paras: f'<p:sld {P}><p:cSld><p:spTree><p:sp><p:txBody>' + "".join(f"<a:p>{p}</a:p>" for p in paras) + '</p:txBody></p:sp></p:spTree></p:cSld></p:sld>'
    deck = archive(tmp_path / "talk.pptx", {
        "ppt/presentation.xml": f'<p:presentation {P}><p:sldIdLst><p:sldId id="256" r:id="rId3"/><p:sldId id="257" r:id="rId2"/></p:sldIdLst></p:presentation>',
        "ppt/_rels/presentation.xml.rels": f'<Relationships {RELS}><Relationship Id="rId2" Type="x/slide" Target="slides/slide1.xml"/><Relationship Id="rId3" Type="x/slide" Target="slides/slide2.xml"/></Relationships>',
        "ppt/slides/slide2.xml": slide("<a:r><a:t>Plan for </a:t></a:r><a:r><a:t>2027</a:t></a:r>", "<a:r><a:t>Two lines</a:t></a:r><a:br/><a:r><a:t>in one</a:t></a:r>", ""),
        "ppt/slides/slide1.xml": slide("<a:r><a:t>Costs</a:t></a:r>"),
        "ppt/slides/_rels/slide2.xml.rels": f'<Relationships {RELS}><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide" Target="../notesSlides/notesSlide1.xml"/></Relationships>',
        "ppt/notesSlides/notesSlide1.xml": slide("<a:r><a:t>Say the date twice.</a:t></a:r>", "<a:fld><a:t>1</a:t></a:fld>")})
    pages, how = doc_read.read(deck)
    assert how == "pptx, 2 slides"
    assert pages == [(1, "Plan for 2027\nTwo lines in one\nNotes:\nSay the date twice."), (2, "Costs")]


ODF = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
       'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"')


def test_opendocument_text_sheets_and_slides_are_read_from_their_content(tmp_path):
    cell = lambda text, more="": f"<table:table-cell{more}><text:p>{text}</text:p></table:table-cell>" if text else f"<table:table-cell{more}/>"
    letter = archive(tmp_path / "letter.odt", {"content.xml": f'<office:document-content {ODF}><office:body><office:text>'
        '<text:tracked-changes><text:p>deleted long ago</text:p></text:tracked-changes>'
        '<text:h>Lease</text:h><text:p>The rent is<text:s text:c="2"/>900<text:tab/>a month<text:note><text:p>a footnote</text:p></text:note>.</text:p>'
        '<text:list><text:list-item><text:p>First <text:span>of the</text:span> month</text:p></text:list-item></text:list>'
        f'<table:table><table:table-row>{cell("Room")}{cell("Size")}</table:table-row><table:table-row>{cell("Kitchen")}{cell("12")}</table:table-row></table:table>'
        '</office:text></office:body></office:document-content>'})
    assert doc_read.read(letter) == ([(None, "Lease\nThe rent is  900 a month.\nFirst of the month\nRoom\tSize\nKitchen\t12")], "odt")
    rep = lambda n: f' table:number-columns-repeated="{n}"'
    sheet = archive(tmp_path / "rooms.ods", {"content.xml": f'<office:document-content {ODF}><office:body><office:spreadsheet>'
        f'<table:table table:name="Rooms"><table:table-row>{cell("Room")}{cell("", rep(2))}{cell("Size")}{cell("", rep(16380))}</table:table-row>'
        f'<table:table-row table:number-rows-repeated="2">{cell("x", rep(3))}</table:table-row>'
        f'<table:table-row table:number-rows-repeated="1048570">{cell("", rep(16384))}</table:table-row></table:table>'
        f'<table:table table:name="Empty"><table:table-row>{cell("")}</table:table-row></table:table>'
        '</office:spreadsheet></office:body></office:document-content>'})
    pages, how = doc_read.read(sheet)
    assert how == "ods, 2 sheets" and pages == [(1, "Sheet: Rooms\nRoom\t\t\tSize\nx\tx\tx\nx\tx\tx"), (2, "Sheet: Empty\n")]
    deck = archive(tmp_path / "talk.odp", {"content.xml": f'<office:document-content {ODF}><office:body><office:presentation>'
        '<draw:page><draw:frame><draw:text-box><text:p>Plan</text:p><text:p/></draw:text-box></draw:frame></draw:page>'
        '<draw:page><draw:frame><draw:text-box><text:list><text:list-item><text:p>Costs</text:p></text:list-item></text:list></draw:text-box></draw:frame></draw:page>'
        '<draw:page/></office:presentation></office:body></office:document-content>'})
    assert doc_read.read(deck) == ([(1, "Plan"), (2, "Costs"), (3, "(no text on this slide)")], "odp, 3 slides")
    with pytest.raises(doc_read.Unreadable, match="content part is missing"):
        doc_read.read(archive(tmp_path / "bare.odt", {"mimetype": "application/vnd.oasis.opendocument.text"}))


def test_a_saved_email_is_its_headers_and_its_text_and_an_attachment_is_named_not_opened(tmp_path):
    from email.message import EmailMessage
    message = EmailMessage()
    message["From"], message["To"], message["Subject"], message["Date"] = "Ana <ana@example.org>", "bo@example.org", "Door code", "Mon, 05 Oct 2026 09:00:00 +0000"
    message.set_content("The code is 4417.\nDo not share it.\n")
    message.add_attachment(b"%PDF-1.4 secret", maintype="application", subtype="pdf", filename="plan.pdf")
    (tmp_path / "code.eml").write_bytes(message.as_bytes())
    pages, how = doc_read.read(tmp_path / "code.eml")
    assert how == "email" and pages[0][0] is None
    assert pages[0][1] == ("From: Ana <ana@example.org>\nTo: bo@example.org\nDate: Mon, 05 Oct 2026 09:00:00 +0000\nSubject: Door code\n\n"
                           "The code is 4417.\nDo not share it.\n\nAttachments (not opened): plan.pdf")
    page = EmailMessage()
    page["Subject"] = "Only HTML"
    page.set_content("<html><body><p>Moved to <b>Thursday</b>.</p><script>ignored()</script></body></html>", subtype="html")
    (tmp_path / "html.eml").write_bytes(page.as_bytes())
    assert doc_read.read(tmp_path / "html.eml")[0][0][1] == "Subject: Only HTML\n\nMoved to Thursday."
    (tmp_path / "none.eml").write_text("just some words, no headers\n")
    with pytest.raises(doc_read.Unreadable, match="does not read as an email"):
        doc_read.read(tmp_path / "none.eml")


@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice is not installed")
def test_what_libreoffice_itself_writes_is_read(tmp_path):
    """The files above were written here by hand; these are written by the program most people's files come from."""
    import subprocess

    def convert(source, to):
        got = subprocess.run(["soffice", "--headless", f"-env:UserInstallation=file://{tmp_path}/profile", "--convert-to", to, "--outdir", str(tmp_path), str(source)],
                             capture_output=True, timeout=180)
        made = tmp_path / (source.stem + "." + to.split(":")[0])
        if not made.is_file():
            pytest.skip(f"soffice did not write {made.name}: {got.stderr.decode('utf-8', 'replace')[-200:]}")
        return made
    (tmp_path / "trips.csv").write_text("Item,When,Cost\nTrain,2024-10-02,48.50\nHotel,2024-10-03,131\nTotal,,=SUM(C2:C3)\n")
    for kind in ("xlsx", "ods"):
        pages, how = doc_read.read(convert(tmp_path / "trips.csv", kind))
        rows = pages[0][1].split("\n")
        assert how == f"{kind}, 1 sheet" and rows[0].startswith("Sheet: ") and rows[1] == "Item\tWhen\tCost", (kind, rows)
        assert rows[2].split("\t")[0] == "Train" and rows[2].split("\t")[1] in ("2024-10-02", "10/02/24", "10/02/2024") and rows[2].split("\t")[2] in ("48.5", "48.50"), (kind, rows)
        assert rows[4].split("\t")[0] == "Total" and rows[4].split("\t")[-1] in ("179.5", "179.50"), (kind, rows)
    (tmp_path / "lease.txt").write_text("Lease\n\nThe rent is 900 a month.\nIt is due on the first day.\n")
    pages, how = doc_read.read(convert(tmp_path / "lease.txt", "odt"))
    assert how == "odt" and "The rent is 900 a month." in pages[0][1].split("\n") and pages[0][1].startswith("Lease")
    (tmp_path / "talk.fodp").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" '
        'xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0" office:version="1.3" office:mimetype="application/vnd.oasis.opendocument.presentation">'
        '<office:body><office:presentation>'
        '<draw:page draw:name="one"><draw:frame svg:width="10cm" svg:height="3cm" svg:x="1cm" svg:y="1cm"><draw:text-box><text:p>Plan for 2027</text:p></draw:text-box></draw:frame></draw:page>'
        '<draw:page draw:name="two"><draw:frame svg:width="10cm" svg:height="3cm" svg:x="1cm" svg:y="1cm"><draw:text-box><text:p>Costs fell</text:p></draw:text-box></draw:frame></draw:page>'
        '</office:presentation></office:body></office:document>')
    for kind in ("pptx", "odp"):
        pages, how = doc_read.read(convert(tmp_path / "talk.fodp", kind))
        assert how == f"{kind}, 2 slides" and "Plan for 2027" in pages[0][1] and "Costs fell" in pages[1][1], (kind, pages)
