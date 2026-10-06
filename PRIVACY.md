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
| the model files, llama.cpp, the provers, the PDF reader, the install settings | the data folder `DAWNR_HOME` (default `~/.local/share/dawnr`): `models/`, `llama.cpp/`, `provers/`, `downloads/`, `pylib/`, `env` | to run | `dawnr forget --all`, or deleting the folder |
| the model servers' logs and process ids, the API token, the file that opens the page in your browser | `DAWNR_HOME/run` | to run, and so that only your browser can open the page | `dawnr forget` |
| the assistant's journal: every change it made to a file, and the bytes it replaced | the state folder: `~/.local/state/dawnr-agent` on Linux, `~/Library/Application Support/dawnr-agent` on macOS, `%LOCALAPPDATA%\dawnr-agent` on Windows, or the folder given with `--state` | so that each change can be undone ([DAWNR-AGENT.md](DAWNR-AGENT.md)) | `dawnr forget` |
| the page's and the API's jobs: the text and files you gave, what the model wrote, the certificate | `DAWNR_HOME/jobs`; the newest 200 finished jobs are kept and the oldest erased first; `DELETE /v1/jobs/ID` erases one now | so that the page can show the result and you can replay it | `dawnr forget`, or `DELETE` |
| the page's session token | your browser's session storage for that tab; gone when the tab closes | so that the page can talk to the API | closing the tab |

The page sets no cookies and stores nothing else in the browser. The API server writes no request log. The files you
point the assistant at are read in place; the only copies are the journal's undo record and the jobs above.

## Children

dawnr collects no personal data from anyone, so it collects none from children, and it is not directed at them.
Whoever installs it on a shared machine controls the folders above.

## Erasing

`dawnr forget` erases the journal and state, the jobs and the run folder. `dawnr forget --all` also erases the
models and everything `install.sh` fetched; run `install.sh` again to use dawnr after that. The project holds
nothing about you that could be erased on request: there is no account or record on the project's side. If you
believe otherwise, write through the route in [SECURITY.md](SECURITY.md).

## The project's own data

The training rows and the measurements in this repository come from synthetic tasks (`locallm/dawnr_families`) and
from public corpora ([NOTICE](NOTICE)); they hold no data about anyone who uses dawnr. The factory refuses a row
that holds this machine's own names (`dawnr_factory.identifiers`).
