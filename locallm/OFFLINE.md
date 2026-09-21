# Offline audit: does locallm work off a stick with no internet? 2026-09-20

The claim under test is the one `home.py` is measured against: *somebody anywhere boots this off a
USB stick, points it at whatever text they care about, and has a model training.* A stick has no
network. So: what in the shipped program opens a socket, what starts it, and what happens when
there is nothing to open a socket to.

**Answer, short: the window is offline-safe. Setup is not.** Once `.venv` exists, opening the
window and training a model reaches the network zero times, and every download is behind a named
button that says it downloads. `INSTALL.bat` cannot work offline at all, because it installs
PyTorch from `download.pytorch.org` with pip. That is the only real offline blocker found, and it
is a packaging problem, not a defect in the window.

This is a negative result. It is written down because "we looked and it is fine" is worth exactly
as much as the audit that would have found the opposite, and because two of the three things this
audit was sent to confirm turned out not to be true.

## 1. How this was measured, not reasoned about

Three instruments, in order of how much they are worth:

**A recording probe.** The window was constructed against the real display with
`socket.getaddrinfo`, `socket.socket.connect`, `socket.create_connection`, `subprocess.run` and
`subprocess.Popen` wrapped to record every call, then left idle for 12 seconds so the `after()`
timers and the background threads had several passes each. Idle, because the question is what the
window does when nobody has asked it for anything. Both configurations below were recorded (the
GUI decides between them from `t/lab-workstation.conf`, which is gitignored and is on no stick):

| configuration | Python sockets opened | subprocesses started | of those, network |
|---|---:|---:|---|
| `T_LAB` set (the operator's desktop) | **0** | 6 | 6 × `ssh` to the lab, from `watch_lab` |
| no `T_LAB` (a stick) | **0** | 130 | **0** -- one loopback `curl`, the rest local `test`/`ls` |

Zero Python-level socket calls in both. Every network touch the window makes on its own is a
subprocess, which is why recording only `socket` would have missed all of it.

**`verify_claims.py`.** It already scans all 71 `locallm/*.py` files for network imports and calls
and for anything that could send bytes out. Its verdict stands: no `POST`, no mail, no socket
write anywhere, downloader included. Its other network check currently FAILS, and section 4 is
about why that failure is wrong.

**Two timed failure probes**, for what "no network" actually costs (section 5).

## 2. Every network touch point in the shipped program

Reachable means: a stick user can get there from the window. "Asks first" means the control that
starts it says, in the words on screen, that it downloads.

| file:line | what it reaches | what triggers it | asks first | Tk thread |
|---|---|---|---|---|
| `get_corpus.py:142` (`urlopen`, `timeout=420`) | `huggingface.co` TinyStories (`:69-70`), 20 `gutenberg.org` books (`:82-83`) -- plain text, never weights | `home.py:1171` "Get text to practise on…" → dialog → **Download**; or `studio.py:859` "Get better text…" → same | yes: "Downloaded once and kept... Only plain text is fetched" | **no** -- `home.py:1299` / `studio.py:1308` run it on a daemon thread |
| `install.py:139` (`pip index versions torch`, `timeout=180`) | `download.pytorch.org/whl/cu121` or `/whl/cpu` (`:44-45`) | `INSTALL.bat` only | yes -- it is setup | n/a, no GUI |
| `install.py:164` (`pip install`, **no timeout**) | the same index | `INSTALL.bat` only | yes | n/a |
| `t/lab.py:2019` (`ssh ... t/lab_status.py`) | the address in `t/lab-workstation.conf` | `watch_lab`, started at `t/lab.py:961`, **every 5 s, unprompted** -- only when `T_LAB` is set | the page says "Connecting to lab workstation…" and "updates every 5 seconds" | **no** -- own thread, `ConnectTimeout=5`, `timeout=25` |
| `t/lab.py:2293` (`bash t/lab_gpu.sh status` → `ssh`) | same | `lab_gpu_watch`, started at `t/lab.py:2236`, every 20 s, unprompted -- only when `T_LAB` is **not** set, so `lab_gpu.sh:17` exits on `${T_LAB:?}` and no ssh happens | n/a | **no** -- own thread, `timeout=60` |
| `t/lab.py:2551` (the done-when checks) | loopback `:11434` via `curl` (`t/steps.json:39`); four bare `ssh` checks (`t/steps.json:327,335,375,399`) | `check_steps`, started at `t/lab.py:2193`, every 3 s, unprompted | n/a | **no** -- own thread |
| `t/lab.py:2277` (`bash t/lab_gpu.sh <verb>` → `ssh`) | same | the **Start / Stop / Fetch answers** buttons on the AI page | yes, by name | **no** -- own thread |
| `t/lab.py:2480` (`Popen bash -lc <step>`) | everything in section 3 | one **Run** button per step on Collect data | yes -- each step's own text says what it fetches and how big | **no** -- `Popen`, never waited on |

Nothing else in `locallm/` opens a socket. `check_my_computer.py:149` only *prints* `pip install
torch` for the user to run. `data.py:298,332` only name pip in an error message. `preflight.py:615`
loads tokenizers with `local_files_only=True` and says so.

**No network call anywhere runs on the Tk thread.** That was the failure mode most worth looking
for, because Tcl/Tk is single-threaded and "event handlers must respond quickly, otherwise they
will block other events from being processed" (docs.python.org/3/library/tkinter.html) -- a
420-second `urlopen` in a button callback would freeze the whole window, repaint included, for
seven minutes with no cursor and no cancel. Both download buttons were written the other way
round: the dialog is built on the Tk thread, `get_corpus.main()` runs on a daemon thread, and the
result comes back through the page's queue. Every poll loop is likewise a thread, and their
docstrings say so (`t/lab.py:2011`: "no Tk calls or pipeline commands in this thread").

## 3. The pipeline, which is not part of the offline claim

These are reached only by pressing **Run** on a Collect data step, or from a terminal. Listed so
the audit is complete, not because a stick user meets them -- every one of them needs the lab
workstation, a GPU, or `ollama`, and the step's own text on screen says so.

| file:line | what it fetches |
|---|---|
| `t/steps.json:30` | `curl -fsSL https://ollama.com/install.sh \| sh` (step "Install Ollama", asks for a password in a terminal) |
| `t/steps.json:14` | `pip install transformers peft trl datasets accelerate bitsandbytes safetensors` |
| `t/steps.json:46,78` | `ollama pull qwen2.5-coder:14b`, `ollama pull deepseek-coder-v2:16b` ("About 9 GB") |
| `t/steps.json:278` | `ssh ... git fetch -q origin && git reset --hard origin/main` on the lab |
| `t/steps.json:318,326,334,342,366,374,398` | `ssh` + `rsync` to the lab, one per pipeline stage |
| `t/spec_experiment.py:832,845,853` | `urlopen` to an OpenAI-shaped server or ollama's `/api/chat`, `/api/show` -- a host the caller names |
| `t/loop_train.py:144,151-152,372,509`; `t/loop_generate.py:579,590-591,611` | Hugging Face `from_pretrained` / `hf_hub_download`: this is where **weights** are downloaded |
| `t/bedrock_generate.py:319-322` | `boto3` to AWS Bedrock, CLI only, never wired to a button |
| `t/lab_gpu.sh:18`, `t/grade_lab.sh:34` | `ssh -o BatchMode=yes -o ConnectTimeout=10`, and `rsync` at `t/lab_gpu.sh:111,146` |
| `t/out/research-review-2026-09-19/fetch_followup.py:29-35` | arXiv PDFs. A one-off archiving script under `t/out/`, in no import path |
| `t/runs/2026-09-16/scripts/ollama_shim.py:50-53` | an HTTP proxy. A recorded run artifact, in no import path |

## 4. `build_source_corpus.py:19` does not fetch anything

This audit was told that `get_corpus.py` and `build_source_corpus.py` "around line 19" are known
to fetch. The first is true. **The second is false**, and the line is exact enough that the belief
clearly came from somewhere. It did:

    locallm/build_source_corpus.py:19:  from urllib.parse import quote

`urllib.parse` is string manipulation with no socket in it -- it exists "to break Uniform Resource
Locator (URL) strings up in components... and to combine the components back into a URL string"
(docs.python.org/3/library/urllib.parse.html). `quote` is used once, at
`build_source_corpus.py:180`, to percent-encode a path into a `blob/<revision>/<path>` attribution
URL that is written into `provenance.jsonl` and never requested. The file's `git` calls
(`:53,138,141,144,148,298`) are `rev-parse`, `remote get-url`, `diff` and `ls-files` against
**already-cloned local checkouts**: inspection of a pinned working tree, no `clone`, no `fetch`,
no `pull`. Its own docstring is accurate: "Reads source as text; never imports or executes it."

Where the belief came from is `verify_claims.py:154`, whose network pattern is

    ^\s*(?:import|from)\s+(?:requests|urllib|socket|httpx|aiohttp|smtplib|ftplib|http)\b

so `from urllib.parse import quote` matches on the bare `urllib`, and the run reports

    [FAIL] only get_corpus.py touches the network   network use outside the downloader: ['build_source_corpus.py:19']

That check has therefore been red on a false positive, and a red safety check that everyone knows
to ignore is worth less than no check: it is now one of four failures in a run of nineteen, and the
other three are unrelated documentation drift. This matters more than the wrong line number,
because the comment above `DOWNLOADER` at `verify_claims.py:127` is explicit that the scanner's
first version flagged itself and that "the fix is a more precise pattern, not an exemption" -- and
the same mistake is now sitting in the scanner a second time, in the other direction. Fixing it is
recommendation 1; it is outside this audit's mandate, which was the window.

## 5. What happens with nothing to connect to

Measured on this machine rather than assumed. The `timeout` passed to `urlopen` "specifies a
timeout in seconds for blocking operations like the connection attempt"
(docs.python.org/3/library/urllib.request.html) -- it is per operation, not a deadline for the
download, and it only bites when a connection *hangs* rather than being refused.

| condition | what happens | how long |
|---|---|---|
| no DNS (what "no internet" normally is) | `URLError: [Errno -2] Name or service not known`, each URL skipped by `get_corpus.py:200`, then `get_corpus.py:208` raises `SystemExit("nothing downloaded - check your internet connection")` | **0.01 s** |
| a black hole: routable address, no answer to SYN | `URLError: timed out` after the full `timeout` | scaled probe: 8.01 s at `timeout=8`, so **420 s** per URL as shipped -- and `books` is 20 URLs, so up to **2.3 hours** |
| no `t/lab-workstation.conf` (every stick) | `. t/lab-workstation.conf` fails, `&&` short-circuits, the four `ssh` done-checks never run | 0.10 s, no socket |
| `lab_gpu.sh` with no `T_LAB` | `lab_gpu.sh: line 17: T_LAB: set T_LAB=...`, exits before `ssh` | immediate |

So the common case fails fast and says the right thing. The black-hole case does not, but it
cannot freeze the window -- it is on a daemon thread. What it does instead is leave the page saying
"Downloading 200 MB..." for up to two hours with no progress, no error and no way to stop it. That
is recommendation 3.

The `ssh` done-checks deserve a note because they look worse than they are. `t/steps.json:327,335,
375,399` run a bare `ssh` with neither `BatchMode=yes` nor `ConnectTimeout`, from
`t/lab.py:2551`'s `subprocess.run(...)`, which passes **no `timeout=`** either, in a loop that
repeats every 3 seconds. Without `BatchMode`, "user interaction such as password prompts and host
key confirmation requests" stays enabled (man.openbsd.org/ssh_config), and a prompt on inherited
stdin waits forever; without `ConnectTimeout` an unreachable host falls back to "the default system
TCP timeout". A hang there would stall all 50 done-checks behind it and freeze every progress bar
on Collect data with nothing on screen saying why -- the window would stay alive and stop telling
the truth, which is the failure this repository dislikes most.

**It is nevertheless unreachable today, and the reason is worth writing down so it is not broken by
accident.** `lab_target()` (`t/lab.py:451`) returns a target exactly when `T_LAB` is set or
`t/lab-workstation.conf` names one; `build_collect` (`t/lab.py:2112-2114`) returns early in that
case and never starts `check_steps`. So the ssh checks run only when there is no `T_LAB` -- which
is the case in which `. t/lab-workstation.conf` fails and they make no connection. The two
conditions are exclusive, and that is an accident of two unrelated decisions, not a guard. One
configuration does slip between them: a conf whose `T_LAB` contains whitespace or begins with `-`,
which `lab_target:464` rejects for safety while the shell sources it happily. That is
recommendation 2.

## 6. Is the window offline-safe today?

Plainly, in the three cases that matter:

1. **A stick with `.venv` already on it, no internet.** Yes. Zero network calls, measured: the
   window opens, Home builds, a corpus is loaded from a file, training runs, the included model
   answers. The only two buttons that would reach the network are named for it and are the only
   things that fail.
2. **A stick with no `.venv`, no internet.** No, and not fixably from here: `INSTALL.bat` needs
   `download.pytorch.org`. Nothing in the window is at fault and nothing in the window pretends
   otherwise -- `home.py`'s cards say in words which parts cannot work without torch, which is why
   the page still opens and explains itself on a machine that has never installed anything.
3. **The operator's own desktop, `T_LAB` set.** The window makes 6 `ssh` connections in its first
   12 seconds with nobody touching it. Called for by remote mode, announced on the page, bounded
   at 5 s connect and 25 s total, off the Tk thread -- an announced consequence of writing a
   private config file, not an unasked-for call. No change proposed.

**No defect of the kind this audit was permitted to fix was found, so no code was changed.** No
network call is reachable from the window without a control that says it downloads, and no network
call runs on the Tk thread.

## 7. What would have to change

In the order that the size of the lie each one tells divided by its cost puts them.

1. **Make `verify_claims.py`'s network scan distinguish `urllib.parse` from `urllib.request`** --
   match `urllib.request`, `urllib.error` and bare `urllib`, not `urllib.parse`, and likewise
   `http.client`/`http.server` rather than `http`. Adding a `build_source_corpus.py` exemption
   instead would be the mistake the comment at `verify_claims.py:127` was written to prevent. One
   regex, and the claim "only `get_corpus.py` touches the network" becomes true and green, which is
   the whole point of having it.
2. **Bound the automatic done-checks.** `t/lab.py:2551` should pass a `timeout=` and treat
   `TimeoutExpired` as "not done yet" and carry on, rather than letting it reach the existing
   `except (OSError, SubprocessError)` arm, which kills the polling thread for good. The four
   `ssh` checks in `t/steps.json` should carry `-o BatchMode=yes -o ConnectTimeout=5`, as
   `t/lab_gpu.sh:18` and `t/grade_lab.sh:34` already do. Not reachable today, per section 5, but
   held shut by a coincidence rather than by a decision.
3. **Give the corpus download a deadline and a Cancel.** A per-URL `timeout=420` with no overall
   budget can leave "Downloading..." on screen for hours behind a black-holed connection. A total
   budget, and a stop flag the dialog can set, would turn that into a sentence the user can read.
   The 420 s is itself measured and correct (`get_corpus.py:137-141`: 169 s just to complete one
   TLS handshake, then 4.36 MB/s) -- the missing piece is the ceiling, not a smaller timeout.
4. **Ship an offline install path.** A `wheels/` folder on the stick and `pip install
   --no-index --find-links wheels`, chosen per platform, is what would make claim 2 above true.
   This is the one item that changes what locallm can promise, and the one that is real work:
   a CPU-only torch wheel is on the order of 200 MB and the wheel set is per OS and per Python
   version, so it is a release-engineering decision, not a patch.
5. **Say the state of play in `README.md`.** It already says `get_corpus.py` is "The one file here
   that opens a network connection", which is true of `locallm/` and is the strongest sentence in
   this audit. What it does not say is that the window makes no network call at all, that setup
   needs internet once, or that `app.py` opens `t/lab.py`, which reaches further. One paragraph,
   and a reader can answer the stick question without this file.

## Sources

- docs.python.org/3/library/urllib.request.html -- what `urlopen`'s `timeout` covers
- docs.python.org/3/library/urllib.parse.html -- that `urllib.parse` is string work only
- docs.python.org/3/library/tkinter.html -- Tk's single-threaded event loop, and why a slow
  callback blocks every other event
- man.openbsd.org/ssh_config -- `BatchMode`, `ConnectTimeout`
- docs.python.org/3/library/subprocess.html -- `timeout=`, `TimeoutExpired`, and that a missing
  program raises rather than exiting non-zero (the reason `HOST_CAN_RUN_STEPS` exists at
  `t/lab.py:99`)
