# Privacy

dawnr runs on your machine. This page says what it keeps, where, what leaves the machine, and how to erase it.
It was written on 2026-10-06 from the code as it is; the repository's history dates every change to it.

## What dawnr is

Software you install and run yourself (`install.sh`, `bin/dawnr`). There is no account, no sign-in, no server of
the project's that it talks to, and no telemetry: dawnr reports nothing about its use, its errors or you to anyone.

## What leaves this machine

Nothing, by default. The three exceptions are each something you choose:

- **`install.sh`** downloads llama.cpp, the model files, Dafny and the PDF reader from their publishers, each checked
  against a published SHA-256 ([NOTICE](NOTICE)). Those publishers see the download request, as with any download.
- **`--online`** (the assistant) lets the model fetch pages you ask about; that request goes to that site. The network
  is off by default ([docs/USER-GUIDE.md](docs/USER-GUIDE.md), "The network: off by default").
- **A hosted writer** (`dawnr serve api` with `DAWNR_WRITER_MODEL` set): what you ask for a function is sent to that
  service and what comes back is checked here. The page says so in its header whenever it applies. Without that
  setting, nothing is sent.

## What it keeps on this machine

| what | where | why | erased by |
|---|---|---|---|
| the model files, llama.cpp, the provers, the PDF reader, the install settings | the data folder `DAWNR_HOME` (default `~/.local/share/dawnr`): `models/`, `llama.cpp/`, `provers/`, `downloads/`, `pylib/`, `env`, and the `llama.cpp.tmp/`, `cudart.tmp/` and `pylib.tmp/` an install that stopped part way leaves | to run | `dawnr forget --all`, or deleting the folder |
| the `dawnr` command: the paths of this checkout and of `DAWNR_HOME`, nothing else | `~/.local/bin/dawnr` (install.sh's `BIN_DIR`) | so that `dawnr` runs from any folder, and says to run install.sh again after `forget --all` | deleting the file |
| the model servers' logs and process ids, the API token, the file that opens the page in your browser | `DAWNR_HOME/run` | to run, and so that only your browser can open the page | `dawnr forget` |
| the assistant's journal: every change it made to a file, and the bytes it replaced; its plan log (`plans.jsonl`): for each plan, the tool and arguments of every call, except that a text longer than 200 characters (a file's contents, an edit's texts) is kept only as its length and SHA-256, and only the newest 200 plans are kept, the oldest being dropped as each new one is added; and an empty `.lock` file, which two sessions sharing the folder use to take turns writing | the state folder: `~/.local/state/dawnr-agent` on Linux, `~/Library/Application Support/dawnr-agent` on macOS, `%LOCALAPPDATA%\dawnr-agent` on Windows, or the folder given with `--state` | so that each change can be undone, and a run that went wrong can be followed afterwards ([DAWNR-AGENT.md](DAWNR-AGENT.md)) | `dawnr forget`; a folder given with `--state` while it holds nothing else (see Erasing) |
| the folders given with `--state` | `DAWNR_HOME/state-folders`, one path a line, written when the assistant starts with `--state` and `DAWNR_HOME` is set, as the `dawnr` command sets it | so that `dawnr forget` can find a folder it does not know by name | `dawnr forget` |
| the page's and the API's jobs: the text and files you gave, what the model wrote, the certificate | `DAWNR_HOME/jobs`; the newest 200 finished jobs are kept and the oldest erased first; `DELETE /v1/jobs/ID` erases one now | so that the page can show the result and you can replay it | `dawnr forget`, or `DELETE` |
| the page's session token | your browser's session storage for that tab; gone when the tab closes | so that the page can talk to the API | closing the tab |
| copies of a program being checked, which the provers and the sandbox are handed | the system's temporary folder (`$TMPDIR`, else `/tmp`), each removed when its check ends, except: a check that is killed leaves its folder; the Dafny adapter leaves the copy it hands Dafny (`t_src_*.dfy`: `t/verifiers/dafny.py` never removes it); replaying an observation certificate leaves its folder (`obs-*`: `t/obs_certificate.py` never removes it) | so that a prover reads a private copy, not a file that can change while it reads | deleting them; not `dawnr forget`, which cannot tell them from the same files of another run of the provers |

The page sets no cookies and stores nothing else in the browser. The API server writes no request log. The files you
point the assistant at are read in place; the only copies kept are the journal's undo record, the plan log's texts of 200
characters or fewer (an edit's text is often a line of a file), and the jobs above. The document reader and the sandbox
work on copies inside the state folder (`doc/`, `sh/`), removed when the read or the command ends.

The window in `locallm/` (`locallm/home.py`, started by `locallm/start-linux.sh` and its siblings, never by the
`dawnr` command) keeps two more things once a person turns them on, in the per-user data folder: on Linux
`$XDG_DATA_HOME/dawnr`, else `~/.local/share/dawnr`, the folder install.sh also uses for `DAWNR_HOME`. Each reply,
with the conversation it answered and the person's marks on it, and the adapters learned from them, are in
`people/` (`DAWNR_PEOPLE_DIR` moves it; `locallm/dawnr_learning/feedback.py`); what its chat remembers of a person is
in `memory/` (`DAWNR_DATA_DIR` moves it; `locallm/dawnr_memory/store.py`). `dawnr forget` leaves both, with `--all` too;
`python3 locallm/dawnr_learning forget-all NAME --yes` and
`python3 locallm/dawnr_memory --person NAME forget-everything --yes` erase them, one person at a time.

## What runs beside dawnr, and whether it talks to the network

| component | licence | from | network |
|---|---|---|---|
| llama.cpp's server (`llama-server`) | MIT | its publisher's release, by SHA-256 | listens on 127.0.0.1 only; fetches nothing |
| the model files (dawnr v5 and the base) | Apache-2.0 (see `release/`) | their publishers, by SHA-256 | none |
| the PDF reader (pypdfium2 over PDFium) | BSD-3-Clause or Apache-2.0; PDFium BSD-3-Clause | its publisher, by SHA-256 | none |
| Dafny | MIT | its publisher, by SHA-256 | none when run by dawnr |
| the other provers (Verus, Lean, Rocq, Frama-C, GNATprove, F*) | each its own | installed by you, if at all | none when run by dawnr |
| bubblewrap (the sandbox) | LGPL-2.0 | your distribution | none; it is what keeps commands off the network |
| Python and its standard library | PSF | your distribution | nothing beyond the three exceptions above |

dawnr has no analytics, crash reporter, update checker or other software that calls home, and adds none of its own.

## Children

dawnr collects no personal data from anyone, so it collects none from children, and it is not directed at them.
Whoever installs it on a shared machine controls the folders above.

## Erasing

`dawnr forget` erases the default state folder, the jobs, the run folder, and each folder recorded in
`DAWNR_HOME/state-folders`, then that record. A folder given with `--state` is recorded there when the assistant
starts with it from the `dawnr` command, before anything is written into it; one given to `locallm/dawnr_cli.py` run
by hand, without `DAWNR_HOME`, is not recorded. A recorded folder is erased only while it is a real folder at that
path, reached through no link, other than `/`, the home folder or `DAWNR_HOME`, and holding nothing but what the
assistant writes into a state folder: `journal.jsonl` and `backups/` (the journal), `plans.jsonl` (its plans, with
`.plans.jsonl.XXXXXXXX.tmp`, the shortened copy that trimming it leaves behind if the computer stops midway),
`.lock` (an empty file that two sessions sharing one state folder use to take turns writing, so that neither loses
the other's lines), and `doc/`, `sh/` and `sh-hidden/` (the document reader's and the sandbox's scratch). Any other is
named and left whole,
as `kept PATH: it does not look like a dawnr state folder`: a folder you also keep your own files in keeps the
journal too, so erase those names in it yourself. `dawnr forget --all` also erases the models and everything
`install.sh` fetched, with what an install that stopped part way left; run `install.sh` again to use dawnr after
that. Neither erases the `dawnr` command, the copies left in the temporary folder, or the window's records; each is
listed above with what erases it. The project holds
nothing about you that could be erased on request: there is no account or record on the project's side. If you
believe otherwise, write through the route in [SECURITY.md](SECURITY.md).

## The project's own data

The training rows and the measurements in this repository come from synthetic tasks (`locallm/dawnr_families`) and
from public corpora ([NOTICE](NOTICE)); they hold no data about anyone who uses dawnr. The factory refuses a row
that holds this machine's own names (`dawnr_factory.identifiers`).
