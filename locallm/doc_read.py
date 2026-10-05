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
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ingest  # noqa: E402

PDF_SECONDS = 120
MIN_PDF_TEXT = 20              # characters that are not spaces, below which a PDF is taken to have no text layer


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


def read(path) -> tuple[list[tuple[int | None, str]], str]:
    """([(page number or None, text)], how it was read). Unreadable with a sentence a person can act on."""
    path = Path(path)
    try:
        head = path.open("rb").read(1024)
    except OSError as error:
        raise Unreadable(f"“{path.name}” cannot be opened ({error.strerror})") from None
    if b"%PDF-" in head:
        return _pdf(path)
    r = ingest.read_any(path)
    if r.text is None:
        raise Unreadable(r.say.why.rstrip("."))
    return [(None, r.text)], r.kind + (f" ({r.encoding})" if r.encoding and r.kind == "text" else "")
