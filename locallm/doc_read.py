"""doc_read.py: a person's document as text for `dawnr cite` and `dawnr extract`, page by page, or a sentence saying
why it cannot be read (2026-10-05).

    from locallm import doc_read
    pages, how = doc_read.read(path)      # [(page number or None, text)], "pdf, 3 pages" / "docx" / "text (cp1252)"

Text in any encoding that can be proved, saved web pages, Word documents and EPUB books are read by
locallm/ingest.py (read_any: it either decodes a file properly or refuses in a sentence; the standard library
only). A PDF is read with poppler's `pdftotext` when the machine has it: a separate program, in reading order,
UTF-8, a form feed between pages (pdftotext(1)), so a quote can be shown with its page. A PDF with no text layer
(a scan) and a machine without pdftotext are each refused with what to do. Layout models and OCR (Docling,
arXiv:2408.09869) are what a scan or a table needs and are not carried here. Research receipt 30c2874d17c6.

Reading a PDF runs pdftotext on a file somebody else wrote, with a time limit and nothing else; that is the risk of
opening the file in a viewer built on the same library, and no more.

Spreadsheets, slides, OpenDocument files and saved emails (2026-10-05) are read here with the standard library
only, each the way its own format says:

  .xlsx .xlsm   a sheet a page, a row a line, cells separated by tabs. A cell holds its value as last calculated
                (a formula never calculated is shown as the formula); a number whose style is a date is shown as
                the date, by openpyxl's rule for which number formats are dates (styles/numbers.py: the built-in
                ids 14 to 22 and 45 to 47, and any custom format with d, m, y, h or s outside quotes and brackets;
                MIT; receipt 1fca2dbce60c). Without that rule 2 October 2024 reads as 45567
  .pptx         a slide a page, in the presentation's own order (not the files' names), a paragraph a line, then the
                speaker's notes
  .odt .ods .odp  OpenDocument's content.xml: paragraphs, headings and lists; a table's rows as tab-separated
                lines; a sheet or a slide a page. A cell repeated a million times to fill the sheet is read once
  .eml          who, to whom, when, the subject, and the plain-text body (the HTML one when there is no other);
                attachments are named and not opened

What these do not do: charts, pictures, comments and tracked changes are left out; a merged cell is its first
cell; a sheet's hidden rows are read like any others. Entity expansion inside the XML is not defended against
beyond what the installed Expat does (ingest.py says the same of a Word file).
"""
from __future__ import annotations

import datetime
import email
import email.policy
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ingest  # noqa: E402

PDF_SECONDS = 120
MIN_PDF_TEXT = 20              # characters that are not spaces, below which a PDF is taken to have no text layer
PART_BYTES = 48 * 1024 * 1024  # one part of an archive, unpacked
SHEET_ROWS = 50_000            # rows of one sheet that are read; the rest are counted and said
CELL_REPEAT = 64               # how often a cell or a row that says "repeat me N times" is repeated when it is not empty


class Unreadable(Exception):
    """The document cannot be read as text; the message says why and what to do."""


def _pdf(path: Path) -> tuple[list[tuple[int | None, str]], str]:
    tool = shutil.which("pdftotext")
    if tool is None:
        raise Unreadable(f"“{path.name}” is a PDF, and this machine has no pdftotext to read it with. Install poppler "
                         f"(Linux: `sudo apt install poppler-utils`; macOS: `brew install poppler`), or save the document as text")
    try:
        p = subprocess.run([tool, "-enc", "UTF-8", "-q", str(path), "-"], capture_output=True, timeout=PDF_SECONDS, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        raise Unreadable(f"“{path.name}” took pdftotext more than {PDF_SECONDS} s to read") from None
    if p.returncode != 0:
        raise Unreadable(f"pdftotext could not read “{path.name}” ({p.stderr.decode('utf-8', 'replace').strip()[:160] or 'no message'})")
    pages = [(n, text) for n, text in enumerate(p.stdout.decode("utf-8", "replace").split("\f"), 1) if text.strip()]
    if sum(len("".join(text.split())) for _n, text in pages) < MIN_PDF_TEXT:
        raise Unreadable(f"“{path.name}” is a PDF with no text in it, most likely a scan; reading one needs character "
                         f"recognition, which is not built in. Run it through an OCR tool first")
    return pages, f"pdf, {len(pages)} page{'s' if len(pages) != 1 else ''}"


# ------------------------------------------------------------- archives of XML --

_S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_RELS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_OT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
_OTB = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
_OO = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
_OD = "{urn:oasis:names:tc:opendocument:xmlns:drawing:1.0}"
# openpyxl/styles/numbers.py: the built-in formats that are dates or times, and how a custom one is told
_DATE_IDS = set(range(14, 23)) | {45, 46, 47}
_NOT_FORMAT = re.compile(r'".*?"|\[(?!hh?\]|mm?\]|ss?\])[^\]]*\]')


def _is_date_format(code: str) -> bool:
    return re.search(r"(?<![_\\])[dmhysDMHYS]", _NOT_FORMAT.sub("", (code or "").split(";")[0])) is not None


def _open(path: Path, what: str) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        raise Unreadable(f"“{path.name}” could not be opened as {what}: the archive inside it is damaged") from None


def _part(zf: zipfile.ZipFile, name: str):
    data = ingest._zip_read(zf, name.lstrip("/"), PART_BYTES)
    return ingest._xml(data) if data else None


def _targets(zf: zipfile.ZipFile, rels: str, base: str) -> dict:
    """{relationship id: (type, member name)} of a part's relationships file."""
    root, out = _part(zf, rels), {}
    for rel in (root.iter(_RELS + "Relationship") if root is not None else []):
        target = rel.get("Target") or ""
        parts: list = []
        for piece in (target if target.startswith("/") else base + target).split("/"):
            if piece == "..":
                parts = parts[:-1]
            elif piece and piece != ".":
                parts.append(piece)
        out[rel.get("Id")] = (rel.get("Type") or "", "/".join(parts))
    return out


def _serial(value: float, epoch_1904: bool, code: str) -> str:
    """A spreadsheet's day number as the date, the time or both that its format shows."""
    days = int(value)
    base = datetime.datetime(1904, 1, 1) if epoch_1904 else datetime.datetime(1899, 12, 30 if days > 59 else 31)
    moment = base + datetime.timedelta(days=days, seconds=round((value - days) * 86400))
    shown = _NOT_FORMAT.sub("", code.split(";")[0]).lower()
    has_date, has_time = any(ch in shown for ch in "dy"), any(ch in shown for ch in "hs")
    if has_time and not has_date and days == 0:
        return moment.strftime("%H:%M:%S")
    return moment.strftime("%Y-%m-%d %H:%M:%S") if has_time or value != days else moment.strftime("%Y-%m-%d")


def _column(ref: str) -> int:
    n = 0
    for ch in ref:
        if not ch.isalpha():
            break
        n = n * 26 + ord(ch.upper()) - 64
    return n - 1


def _rows_text(rows: list) -> str:
    return "\n".join("\t".join(cell.replace("\t", " ").replace("\n", " ") for cell in row).rstrip("\t") for row in rows)


def _xlsx(path: Path) -> tuple[list, str]:
    with _open(path, "a spreadsheet") as zf:
        book = _part(zf, "xl/workbook.xml")
        if book is None:
            raise Unreadable(f"“{path.name}” is a spreadsheet whose workbook part is missing or unreadable")
        targets = _targets(zf, "xl/_rels/workbook.xml.rels", "xl/")
        pr = book.find(_S + "workbookPr")
        epoch_1904 = pr is not None and pr.get("date1904") in ("1", "true")
        shared = _part(zf, "xl/sharedStrings.xml")
        strings = []
        for si in (shared.iter(_S + "si") if shared is not None else []):      # a string, or runs of one; not its phonetic guide
            strings.append("".join(t.text or "" for node in si if node.tag != _S + "rPh" for t in ([node] if node.tag == _S + "t" else node.iter(_S + "t"))))
        styles = _part(zf, "xl/styles.xml")
        codes = {int(f.get("numFmtId")): f.get("formatCode") or "" for f in (styles.iter(_S + "numFmt") if styles is not None else [])
                 if (f.get("numFmtId") or "").isdigit()}
        xfs = styles.find(_S + "cellXfs") if styles is not None else None
        formats = [int(xf.get("numFmtId") or 0) for xf in (xfs if xfs is not None else [])]
        date_code = {i: codes.get(f, "yyyy-mm-dd" if f in (14, 15, 16, 17) else "h:mm:ss" if f in (18, 19, 20, 21, 45, 46, 47) else "yyyy-mm-dd h:mm")
                     for i, f in enumerate(formats) if f in _DATE_IDS or _is_date_format(codes.get(f, ""))}
        pages, valued = [], 0
        for number, sheet in enumerate(book.iter(_S + "sheet"), 1):
            root = _part(zf, targets.get(sheet.get(_REL + "id"), ("", ""))[1]) if sheet.get(_REL + "id") in targets else None
            rows, more = [], 0
            for row in (root.iter(_S + "row") if root is not None else []):
                cells: dict = {}
                for c in row.findall(_S + "c"):
                    kind, v, f = c.get("t"), c.find(_S + "v"), c.find(_S + "f")
                    text = v.text if v is not None and v.text is not None else ""
                    if kind == "s":
                        text = strings[int(text)] if text.isdigit() and int(text) < len(strings) else ""
                    elif kind == "inlineStr":
                        text = "".join(t.text or "" for t in c.iter(_S + "t"))
                    elif kind == "b":
                        text = "TRUE" if text == "1" else "FALSE"
                    elif kind in (None, "n") and text:
                        try:
                            number_value = float(text)
                            style = int(c.get("s") or 0)
                            text = _serial(number_value, epoch_1904, date_code[style]) if style in date_code else (
                                text if re.fullmatch(r"-?\d+", text) else f"{number_value:.15g}")
                        except (ValueError, OverflowError):
                            pass
                    if not text and f is not None and f.text:
                        text = "=" + f.text
                    if text:
                        cells[_column(c.get("r") or "") if c.get("r") else len(cells)] = text
                if cells:
                    if len(rows) >= SHEET_ROWS:
                        more += 1
                    else:
                        rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
            head = f"Sheet: {sheet.get('name') or number}" + (" (hidden)" if sheet.get("state") in ("hidden", "veryHidden") else "")
            pages.append((number, head + "\n" + _rows_text(rows) + (f"\n[{more} more rows not read]" if more else "")))
            valued += len(rows)
    if not valued:
        raise Unreadable(f"“{path.name}” opened, but none of its sheets has a value in it")
    return pages, f"xlsx, {len(pages)} sheet{'s' if len(pages) != 1 else ''}"


def _drawing_text(root) -> list:
    """The paragraphs of a slide or a notes page, a line each; a line break inside one is a space."""
    lines = []
    for para in (root.iter(_A + "p") if root is not None else []):
        text = "".join((node.text or "") if node.tag == _A + "t" else " " if node.tag in (_A + "br", _A + "tab") else "" for node in para.iter())
        if text.strip():
            lines.append(text.strip())
    return lines


def _pptx(path: Path) -> tuple[list, str]:
    with _open(path, "a presentation") as zf:
        show = _part(zf, "ppt/presentation.xml")
        if show is None:
            raise Unreadable(f"“{path.name}” is a presentation whose main part is missing or unreadable")
        targets = _targets(zf, "ppt/_rels/presentation.xml.rels", "ppt/")
        pages = []
        for number, slide in enumerate(show.iter(_P + "sldId"), 1):
            member = targets.get(slide.get(_REL + "id"), ("", ""))[1]
            lines = _drawing_text(_part(zf, member)) if member else []
            folder, _, name = member.rpartition("/")
            notes = next((m for kind, m in _targets(zf, f"{folder}/_rels/{name}.rels", folder + "/").values() if kind.endswith("/notesSlide")), "")
            said = [line for line in _drawing_text(_part(zf, notes)) if not line.isdigit()] if notes else []     # not the slide number
            pages.append((number, "\n".join(lines + (["Notes:"] + said if said else [])) or "(no text on this slide)"))
    if not pages:
        raise Unreadable(f"“{path.name}” opened, but it has no slides")
    return pages, f"pptx, {len(pages)} slide{'s' if len(pages) != 1 else ''}"


def _odf_text(node) -> str:
    """The characters of an OpenDocument paragraph: its text, with the elements that stand for spaces, tabs and
    line breaks; a note or a comment anchored in it is left out."""
    if node.tag in (_OO + "annotation", _OT + "note", _OT + "tracked-changes"):
        return node.tail or ""
    text = node.text or ""
    if node.tag == _OT + "s":
        text = " " * int(node.get(_OT + "c") or 1)
    elif node.tag in (_OT + "tab", _OT + "line-break"):
        text = " "
    return text + "".join(_odf_text(child) for child in node) + (node.tail or "")


def _odf_table(table) -> list:
    rows = []
    for row in table.iter(_OTB + "table-row"):
        cells = []
        for cell in row:
            if cell.tag not in (_OTB + "table-cell", _OTB + "covered-table-cell"):
                continue
            text = " ".join(_odf_text(par).strip() for par in cell.iter(_OT + "p")).strip()
            # an empty cell keeps its place however often it is repeated (the trailing ones are dropped below)
            cells += [text] * min(int(cell.get(_OTB + "number-columns-repeated") or 1), CELL_REPEAT if text else 1024)
        while cells and not cells[-1]:
            cells.pop()
        if cells:
            rows += [cells] * min(int(row.get(_OTB + "number-rows-repeated") or 1), CELL_REPEAT)
    return rows


def _odf_block(node, lines: list) -> None:
    for child in node:
        if child.tag in (_OT + "p", _OT + "h"):
            text = _odf_text(child)[:-len(child.tail)] if child.tail else _odf_text(child)
            lines.append(text.strip())
        elif child.tag == _OTB + "table":
            lines.append(_rows_text(_odf_table(child)))
        elif child.tag == _OT + "tracked-changes":
            continue
        else:
            _odf_block(child, lines)                            # a list, a section, a frame: whatever holds paragraphs


def _odf(path: Path) -> tuple[list, str]:
    kind = path.suffix.lower().lstrip(".")
    with _open(path, "an OpenDocument file") as zf:
        root = _part(zf, "content.xml")
    body = root.find(_OO + "body") if root is not None else None
    if body is None:
        raise Unreadable(f"“{path.name}” is an OpenDocument file whose content part is missing or unreadable")
    pages: list = []
    sheets = list(body.iter(_OTB + "table")) if kind == "ods" else []
    slides = list(body.iter(_OD + "page")) if kind == "odp" else []
    for number, table in enumerate(sheets, 1):
        pages.append((number, f"Sheet: {table.get(_OTB + 'name') or number}\n" + _rows_text(_odf_table(table)[:SHEET_ROWS])))
    for number, slide in enumerate(slides, 1):
        lines: list = []
        _odf_block(slide, lines)
        pages.append((number, "\n".join(line for line in lines if line) or "(no text on this slide)"))
    if not sheets and not slides:
        lines = []
        _odf_block(body, lines)
        text = "\n".join(lines).strip()
        pages = [(None, text)] if text else []
    if not any(text.strip() and (kind != "ods" or text.count("\n") and text.split("\n", 1)[1].strip()) for _n, text in pages):
        raise Unreadable(f"“{path.name}” opened, but there are no words in it")
    count = f", {len(pages)} {'sheet' if kind == 'ods' else 'slide'}{'s' if len(pages) != 1 else ''}" if kind in ("ods", "odp") else ""
    return pages, kind + count


def _eml(path: Path) -> tuple[list, str]:
    try:
        with path.open("rb") as f:
            message = email.message_from_binary_file(f, policy=email.policy.default)
    except (OSError, email.errors.MessageError) as error:
        raise Unreadable(f"“{path.name}” could not be read as an email ({type(error).__name__})") from None
    body = message.get_body(preferencelist=("plain", "html"))
    try:
        text = body.get_content() if body is not None else ""
    except (LookupError, UnicodeError, ValueError):
        text = ""
    if body is not None and body.get_content_type() == "text/html":
        text = ingest._html_text(text.encode("utf-8")).text or ""
    named = [part.get_filename() for part in message.iter_attachments() if part.get_filename()]
    head = [f"{name}: {message[name]}" for name in ("From", "To", "Cc", "Date", "Subject") if message[name]]
    if not head:
        raise Unreadable(f"“{path.name}” does not read as an email: it has no sender, recipient, date or subject")
    return [(None, "\n".join(head) + "\n\n" + text.strip() + ("\n\nAttachments (not opened): " + ", ".join(named) if named else ""))], "email"


BY_SUFFIX = {".xlsx": _xlsx, ".xlsm": _xlsx, ".pptx": _pptx, ".odt": _odf, ".ods": _odf, ".odp": _odf, ".eml": _eml}


def read(path) -> tuple[list[tuple[int | None, str]], str]:
    """([(page number or None, text)], how it was read). Unreadable with a sentence a person can act on."""
    path = Path(path)
    try:
        head = path.open("rb").read(1024)
    except OSError as error:
        raise Unreadable(f"“{path.name}” cannot be opened ({error.strerror})") from None
    if b"%PDF-" in head:
        return _pdf(path)
    if path.suffix.lower() in BY_SUFFIX:
        return BY_SUFFIX[path.suffix.lower()](path)
    r = ingest.read_any(path)
    if r.text is None:
        raise Unreadable(r.say.why.rstrip("."))
    return [(None, r.text)], r.kind + (f" ({r.encoding})" if r.encoding and r.kind == "text" else "")
