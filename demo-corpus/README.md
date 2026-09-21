# A folder to drag into locallm

Seven files that answer one question: what happens when a person points this at
whatever they actually have, rather than at a tidy `.txt`.

| File | What it is | What locallm does |
|---|---|---|
| `01-plain-utf8.txt` | ordinary text | reads it, 13,800 characters |
| `02-windows-notepad-utf16.txt` | **the same text**, saved the way Windows Notepad saves it | reads it, **13,800 characters**, and says "utf-16 (BOM)" |
| `03-accented-cp1252.txt` | a letter with accents in a legacy Western encoding | reads it, every accent intact |
| `04-arabic.txt` | Arabic | reads it |
| `05-chinese.txt` | Chinese | reads it |
| `06-word-document.docx` | a real Word document | reads it, using the standard library and no new dependency |
| `07-refused.pdf` | a PDF | **refuses it**, and says why in a sentence |

Files 01 and 02 are the point. They hold the same text and differ only in how it
was saved. Until 2026-09-21 the second arrived as 4,960 characters of which 2,560
were NUL, because it was decoded as UTF-8 with `errors="ignore"` and the
interleaved zero bytes were silently dropped. Nothing said so; you simply got a
worse model. Now both produce the identical string.

`07-refused.pdf` is here because a refusal is a feature. A PDF stores instructions
for placing glyphs rather than characters, and it used to be accepted as prose
and contribute 576 characters of printer commands to the model's permanent
vocabulary.

To see all seven judged at once, without opening the window:

```
cd locallm && python3 -c "
import ingest, pathlib
for f in sorted(pathlib.Path('../demo-corpus').iterdir()):
    if f.suffix == '.md': continue
    g = ingest.read_any(f)
    print(f'{f.name:34s} {g.say.mark} {g.say.word:<18} {g.encoding or g.kind:<16} {len(g.text or \"\"):>6} chars')
"
```
