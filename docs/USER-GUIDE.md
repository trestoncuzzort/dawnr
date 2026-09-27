# Using dawnr

This is the plain-language guide to the parts of this repository a user
touches directly: installing it, opening the desktop app, talking to a
trained model from a terminal, and configuring the harness around it (which
tools it may call, what needs your approval, and whether it can reach the
network at all). It does not cover training a model from scratch (that is
[`../locallm/README.md`](../locallm/README.md)) or the seven-prover
specification pipeline (that is [`../t/README.md`](../t/README.md)); both are
linked from wherever this guide touches them.

Every command shown below was run while writing this guide, on Python
3.11.15, Linux. Where a step needs something this session did not have (a
display for the desktop app's window, a trained checkpoint, `git lfs`), that
is said plainly, not glossed over; see "What this guide could and could not
check" at the end.

## What dawnr does and does not do yet

dawnr is a small model, trained from random weights, wrapped in a harness
that can offer it tools. Today, plainly:

- **The proof engine is real and runs on its own.** `t`, the specification
  language, lowers to seven independent provers, and `python3 t/cli.py` or
  `python3 t/grade.py` check a task without any model in the loop
  ([`../t/README.md`](../t/README.md)). This guide does not cover that half;
  it covers the model and the harness around it.
- **The model can call the checker on its own draft**, mid-answer, through
  the chat format's `t` tool, and a failing check keeps its answer from
  ending once before letting it end anyway
  ([`../DAWNR-HARNESS.md`](../DAWNR-HARNESS.md) section 3). It does not yet
  reliably fix what the checker rejects: repair conversations exist, but the
  measured effect at six fresh seeds is not yet distinguishable from seed
  noise (`../locallm/FINDINGS-repair-2026-09-26.md`).
- **The rest of the harness -- tools beyond `t`, hooks, skills, MCP, the
  network -- is built and tested, but no shipped checkpoint has been trained
  to use any of it.** The registry, the policy, the hook contract and the
  skill loader all work today and are exercised by
  `locallm/test_harness.py`; a model actually choosing to call
  `web_fetch`, load a skill, or read an MCP server's answer well is future
  work, not a measured result (`../AMBITION.md`, "dawnr's harness: reaching
  past itself").
- **The network is a tool, never a dependency.** With no configuration, the
  harness has one capability (the `t` checker) and cannot reach the network
  at all. See "The network: off by default" below for exactly what turns
  that on.
- **On learning instead of memorising, the honest number is not yet good.**
  The last baseline passed 0 of 200 clean held-out problems in eight of nine
  seeds ([`../README.md`](../README.md), "Where it stands"). Nothing in this
  guide changes that; it is about running what exists, not about what it
  gets right yet.

## Installing

The harness itself (`locallm/dawnr_harness/`) is standard-library Python
3.10 or newer and needs nothing else installed; `locallm/test_harness.py`'s
own suite is measured to pass on 3.10 and 3.14
(`../CONTRIBUTING.md`). Beyond that, what you need depends on what you want
to run:

| To run... | You also need |
|---|---|
| the harness alone (`dawnr_harness index`/`call`/`problems`), or dawnr's MCP server | nothing extra |
| the chat CLI (`chat_cli.py`), or the desktop app's Train tab | `pip install torch` (`../locallm/requirements.txt` is exactly that one line) |
| the desktop app at all (any tab) | Tk, which ships with Python on Windows and macOS; on Debian or Ubuntu install it separately: `sudo apt install python3-tk` |
| a real trained checkpoint, rather than an empty models folder | `git lfs pull` once per clone -- a plain `git clone` leaves the shipped checkpoints as LFS pointer files, not weights |

Clone the repository, then, from its root:

```bash
pip install torch          # only needed for the chat CLI or training; skip it to use the harness alone
git lfs pull                # only needed to get a real checkpoint's weights, not pointer files
```

There is no separate installer for the harness or the chat CLI: they are
plain scripts under `locallm/`. (`locallm/INSTALL.bat` and `locallm/install.py`
set up a private environment for the *trainer*, `studio.py`; see
[`../locallm/README.md`](../locallm/README.md) if that is what you want.)

## Running the desktop app

```bash
python3 locallm/app.py
```

opens one window with five tabs -- Home, Train, Proof, Collect data, AI --
built from `t/lab.py`'s shell with `locallm/studio.py`'s training surface
embedded in it (`locallm/app.py`'s own docstring explains why it is one
window and not two). Home is the tab the root [`README.md`](../README.md)
means by "talk to the included model": point it at your own text, train a
small model on it, then a "Write something" step samples from the result
with `locallm/plain_generate.py`, which needs no PyTorch and streams its
answer as it writes. Train is the same trainer `locallm/studio.py` runs on
its own, with every setting exposed; the three tabs behind Proof watch t's
seven-kernel pipeline instead, which is [`../t/README.md`](../t/README.md)'s
subject, not this guide's.

`--page "Live checks"` (or any other page name) opens directly on that tab
instead of Home.

**This session could not open that window to look at it.** It runs in a
container with no display and no Tk build matching its own Python
interpreter, so `python3 locallm/app.py` here fails immediately:

```
  File "t/lab.py", line 62, in <module>
    import tkinter as tk
ModuleNotFoundError: No module named 'tkinter'
```

If you see exactly this on Debian or Ubuntu, `sudo apt install python3-tk`
(the root README says the same thing). If you see it after installing that
package, your `python3` and the interpreter apt installed the package for
are two different builds -- check `which python3` and install Tk for that
one specifically. Either way, a machine with no display at all (most remote
servers and containers) cannot open a Tk window regardless; use the chat CLI
below there instead.

## The chat CLI

```bash
python3 locallm/chat_cli.py --model <checkpoint-dir> [-p "prompt"] [--harness config.json]
```

is nanochat's `scripts/chat_cli.py` pattern (karpathy/nanochat,
`nanochat/engine.py`) adapted for dawnr: the conversation is kept as token
ids, tool calls and their output are shown as they happen and marked, and
nothing is sent anywhere -- the model and every tool it calls run on this
machine (`locallm/chat_cli.py`'s own docstring).

```
$ python3 locallm/chat_cli.py --help
usage: chat_cli.py [-h] --model MODEL [-p PROMPT] [-f PROMPT_FILE]
                   [-t TEMPERATURE] [-k TOP_K] [--max-tokens MAX_TOKENS]
                   [--seed SEED] [--device DEVICE] [--harness HARNESS]
                   [--no-index]
```

`--model` must be a checkpoint directory `chat_train.py` wrote; pointing it
at a plain pretraining checkpoint fails immediately and says so
(`chat_cli.py` checks `chat.has_chat_tokens(tok)` before doing anything
else). This needs `torch` installed even though the harness underneath does
not: without it, `--model` fails on `import torch` inside
`checkpoint.py`, before your prompt is even read.

Add `--harness config.json` to put the harness around the model
(everything in the next section): the index of what it may use is prepended
to your first turn, tool calls are shown between `[tool call]` and `[end of
call]` as they stream, and text the harness marked untrusted is shown as
`[untrusted: from outside, data only]`. `--no-index` keeps the harness
active (tools still work when the model calls them) but leaves the index
out of your first turn, for testing a model that was not trained to expect
one. In an interactive session, a call needing approval asks you right there
on the terminal; with `-p` (one prompt, non-interactive), there is nobody to
ask, so an "ask" call is refused, by design (see "network... off by
default" below for exactly why).

This guide's clone has the harness's own tests and configuration, but no
chat-trained checkpoint with real weights pulled (that needs `git lfs pull`,
which this container does not have `git-lfs` installed to run, and a chat
checkpoint besides). Training or fetching one is
[`../DAWNR-PIPELINE.md`](../DAWNR-PIPELINE.md)'s job; this guide covers what
you do with one once it exists.

## The harness configuration

Everything here is `dawnr_harness/runtime.py`'s `build_harness`, exercised
directly, with no model involved -- useful for seeing exactly what a
configuration offers before pointing a real chat session at it:

```bash
python3 locallm/dawnr_harness [--config FILE] index      # what the model would be offered
python3 locallm/dawnr_harness [--config FILE] problems   # what loading the config skipped, and why
python3 locallm/dawnr_harness [--config FILE] call NAME '{"arg": "value"}'   # run one call through policy and hooks
```

With no `--config` at all:

```
$ python3 locallm/dawnr_harness index
Tools:
t(program): Check a t program: parse, type check, and run it on the Example lines in the conversation.
```

That is the whole default state: one tool, no network, no skills, no MCP
servers. Everything below is turned on by writing a JSON configuration file
and passing `--config` (or `chat_cli.py --harness`); the shipped
[`example-config.json`](../locallm/dawnr_harness/example-config.json) turns
on most of it at once:

```json
{
  "offline": true,
  "permissions": {"t": "allow", "skill": "allow", "mcp__dawnr__*": "allow"},
  "skills": ["skills"],
  "mcp_servers": {
    "dawnr": {"command": "${PYTHON}", "args": ["mcp_server.py"], "network": false, "describe": true}
  },
  "web": {"search": {"backend": "searxng", "url": "http://127.0.0.1:8888"}}
}
```

which, run from `locallm/` (`python3 dawnr_harness --config
dawnr_harness/example-config.json index`), offers exactly:

```
Tools:
mcp__dawnr__t_check(program, examples?): Parse, type check and run a t program on Example lines (Example: f(1, [2]) == 3); answers one verdict per line: parses, well formed, then each example's pass or failure.
skill(name, file?): Load a skill's instructions, or one file from its folder.
t(program): Check a t program: parse, type check, and run it on the Example lines in the conversation.
Skills:
cite-your-source: Before writing or changing an implementation, look for a source that already solves the problem and name it in the commit message. ...
proof-failure-triage: Read a t grading table, one real/twin cell per kernel (verified, refuted, unproved, timeout, malformed, vacuous, abstain, no-twin), ...
reading-untrusted-pages: Handle a tool result the harness marked untrusted: a fetched page, a search result, an MCP answer. ...
t-debug-with-examples: Trace a t program by hand on Example lines to find where it computes the wrong value, ...
t-repair: Repair a t program after dawnr's checker reports a failing verdict (parses no, well formed no, an example that fails, is undefined or runs out of budget). ...
t-spec-writing: Write a new t task from a plain-language problem: signature and types, then requires and ensures, then a body that satisfies them. ...
```

(one line each, the full text cut short here with `...` for space; the
table below has each one in full. `problems` on that same config prints
`none`: nothing was skipped.) `web`
is configured there but `offline` is still `true`, so `web_fetch` and
`web_search` are registered yet hidden from the index, same as if `web` were
missing entirely -- see below.

### Tools and permissions

Every tool has a default permission -- `allow`, `ask`, or `deny` -- and a
default trust (`trusted` output, or `untrusted`, meaning it is marked and
never treated as instructions; see the shipped `reading-untrusted-pages`
skill). The operator's `permissions` map overrides that: an exact tool name
wins, else the strictest glob that matches (such as `mcp__*`), else the
tool's own default. Deciding an `ask` needs someone present: `chat_cli.py`
supplies a real terminal prompt only when standard input is a TTY;
`dawnr_harness ... call` does the same. Piped or scripted input is not a
person, so an `ask` call made that way is refused every time, verified here
against a one-line config (`{"offline": false, "web": {}}`, so
`web_search` is registered and not blocked by offline first) that leaves
its permission at the tool's own default, `ask`:

```
$ printf 'y\n' | python3 dawnr_harness --config network-on.json call web_search '{"query": "test"}'
[trusted, error]
not run: web_search needs approval (the tool's default); nobody is here to approve it
```

(piping `y` did nothing; only an interactive terminal can approve an `ask`.
Against `example-config.json` specifically the same call is refused a step
earlier instead, `denied: offline: ...`, because that file leaves
`"offline": true` and only a network tool that is not blocked by offline
ever reaches the ask-with-nobody-present check at all.)
Once any untrusted text has entered the conversation, a consequential tool
that would otherwise have been auto-allowed needs approval too, so a call
that used to go straight through can suddenly start asking -- that is the
taint rule, not a bug.

### Hooks

With no `"hooks"` key, a configuration gets exactly this default
(`dawnr_harness/runtime.py`'s `DEFAULT_HOOKS`):

```json
{"PostToolUse": [{"matcher": "*", "hooks": [{"type": "builtin", "name": "t_check"}]}],
 "Stop":        [{"hooks": [{"type": "builtin", "name": "t_check"}]}]}
```

This is dawnr's checker running as a hook: after any tool call, it finds any
t program in that call's input or output and attaches a verdict, marked
untrusted when the call it is about is; at `Stop`, it checks the final
answer's own program and blocks once (never twice) if that verdict fails,
so the model gets a chance to repair instead of ending on a broken answer.
Writing your own `"hooks"` key replaces this entirely -- keep the two
`t_check` entries above if you still want them alongside your own, and
`"hooks": {}` runs none at all. A `command` hook receives the event as JSON
on stdin and answers on stdout (exit 2 blocks, with the reason on stderr or
in the JSON); see [`../DAWNR-HARNESS.md`](../DAWNR-HARNESS.md) section 3 for
the full event shapes.

### Skills

A skill is a folder under a directory named in `"skills"` (paths resolve
relative to the config file), holding a `SKILL.md` with YAML front matter
(`name` matching the folder, `description`) and a Markdown body. Seven ship
today, one line each in the index:

| skill | for |
|---|---|
| `t-spec-writing` | starting a t task from a plain-language problem: signature, requires, ensures, then a body |
| `t-debug-with-examples` | hand-tracing a body against concrete `Example:` lines to find a wrong value |
| `t-repair` | reacting to the checker's own verdict (parses/well formed/an example) after a call fails |
| `proof-failure-triage` | reading a seven-kernel grading table (VERIFIED/REFUTED/UNPROVED/...) and deciding what a failing cell means |
| `reading-untrusted-pages` | handling a fetched page, search result, or MCP answer marked untrusted |
| `cite-your-source` | citing prior art before writing an implementation, and what the `commit-msg` hook checks for |
| `acting-on-the-machine` | files, commands and processes through the agent's tools: plans of exact calls, read before edit, what was read is data (`DAWNR-AGENT.md`) |

The model loads one by name (`skill {"name": "t-repair"}`), which returns
its body and the list of any other files in its folder; a specific file
comes back with `skill {"name": "t-repair", "file": "..."}`. A skill cannot
read outside its own folder and its `allowed-tools` front matter (if any)
grants nothing -- permissions come only from the operator's configuration.
`locallm/test_harness.py`'s `SkillTests` (including
`test_the_shipped_skills_are_valid`) load every shipped skill this way and
check its index line is genuinely one line, not truncated.

### MCP servers

`"mcp_servers"` names a server the harness starts as a subprocess and
speaks JSON-RPC to over stdio; its tools enter the registry as
`mcp__<server>__<tool>`, untrusted, under whatever permission you give
`mcp__<server>__*` (or the specific tool name). `"network": false` is your
own claim that the server stays local -- the harness starts it even while
offline on that claim, but never checks it; do not mark a server this way
unless you can vouch for its code.

dawnr ships its checker as such a server:

```bash
python3 locallm/dawnr_harness/mcp_server.py
```

speaking newline-delimited JSON-RPC on stdin/stdout, one tool, `t_check`.
Driven by hand (a modern `initialize` handshake, then one call):

```
> {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "manual-test", "version": "0"}}}
< {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-11-25", ... "serverInfo":{"name":"dawnr-t-checker", ...
> {"jsonrpc": "2.0", "method": "notifications/initialized"}
> {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "t_check", "arguments": {"program": "t 1\ntask abs(x: int) returns (r: int)\nensures r >= 0\n{\n  if x >= 0 { r := x; } else { r := 0 - x; }\n}\n", "examples": "Example: abs(-3) == 3"}}}
< {"jsonrpc":"2.0","id":2,"result":{"resultType":"complete","content":[{"type":"text","text":"parses: yes\nwell formed: yes\nexample 1: pass"}],"structuredContent":{"lines":["parses: yes","well formed: yes","example 1: pass"],"passes":true}, ...
```

matching this file's own claim exactly: parses, well formed, one example,
pass. The example config above registers this same server as
`mcp__dawnr__t_check`, local, described in the index.

### The network: off by default, and how to enable it

With no `"web"` key at all, `web_fetch` and `web_search` do not exist in the
registry, `offline` or not. Adding `"web": {}` (or any web configuration)
registers them, but if `"offline"` is still `true` (the default whenever
the key is omitted), the policy denies them outright and they still do not
appear in the index -- verified here, three configurations, only the first
shows the tools:

```
{"offline": false, "web": {}}                          -> t, web_fetch, web_search
{"offline": true,  "web": {}}                          -> t only
{"web": {"search": {"backend": "searxng", "url": "..."}}}  -> t only   (offline still defaults true)
```

So enabling the network takes both: a `"web"` key (even `{}`) *and*
`"offline": false`. `web_fetch` then works with no further configuration
(default permission `ask`); `web_search` also needs `"search"` naming a
backend -- `searxng` (a self-hosted instance's keyless API), `command` (a
program that prints JSON results), or one registered in Python with
`web.register_backend` -- or it is offered but errors when actually called.
Both tools' output always comes back marked untrusted; see the
`reading-untrusted-pages` skill for what that changes about what you should
do with it, not just how it looks.

### Letting dawnr act on your machine

An `"agent"` section gives the harness files inside folders you name, commands
you list, and the process list, with a planning loop whose plans you see before
anything runs. Nothing of it exists without the section; the threat model and
every option are in `DAWNR-AGENT.md`, and the `acting-on-the-machine` skill is
how a model is told the conventions. A small configuration (paths relative to
the file):

```json
{"offline": true,
 "permissions": {"fs_write": "ask", "fs_edit": "ask"},
 "agent": {"roots": [{"name": "project", "path": "work/project", "mode": "write"}],
           "state": "agent-state"}}
```

and a plan file, the form a model's `plan` call takes:

```json
{"goal": "say hello to the world",
 "steps": [{"tool": "fs_read", "arguments": {"path": "project/readme.txt"}},
           {"tool": "fs_edit", "arguments": {"path": "project/readme.txt", "old": "world", "new": "there"}}]}
```

`python locallm/dawnr_agent --config harness.json dry-run plan.json` printed,
run here, and changed nothing:

```
plan cee1b11a7e9cee04: 2 steps (say hello to the world)
  1. fs_read {"path": "project/readme.txt"}
     allow: the tool's default
     reads project/readme.txt (12 bytes, sha256 4a1e67f2fe1d1cc7); its text enters as untrusted data
  2. fs_edit {"path": "project/readme.txt", "old": "world", "new": "there", "expect_sha256": "4a1e67f2fe1d1cc7"}
     ask: the operator's rule for fs_edit
     edits project/readme.txt (12 -> 12 bytes, old bytes kept for undo)
       --- a/project/readme.txt
       +++ b/project/readme.txt
       @@ -1,2 +1,2 @@
        hello
       -world
       +there
nothing has run yet; approving runs exactly these steps in order, stopping at the first that fails
```

`run plan.json` shows the same and asks once on a terminal; with no terminal the
read ran and the edit was refused ("nobody is here to approve it"); `run
plan.json --approve cee1b11a7e9cee04` ran both, because the plan's digest still
matched what the dry run showed, and `journal` then listed the change
(`c-... edit project/readme.txt 4a1e67f2fe1d -> d6f09840733a`) that `undo
c-...` reverts. Commands are off until you both allow `run_command` in
`"permissions"` and list the argv shapes it may run under `"commands"`; with
`"sandbox": "bwrap"` they run without network and can write only inside your
writable roots.

## Testing what is here

```bash
python3 -m unittest locallm/test_harness.py    # registry, policy, hooks, the checker hook, skills, MCP, web tools
python3 -m unittest locallm/test_harness_chat.py    # the harness's chat tokens and engine integration; needs torch
python3 -m unittest locallm/test_dawnr_agent.py    # the agent: containment, commands, plans, the loop, injection
```

The agent's suite is standard library only: 75 tests, 2 skipped by design (two
race tests that the Windows-style path walk does not claim), 6.6 seconds here;
its sandbox tests also skip on a machine where bubblewrap cannot run.

The first is standard library only and passed all 46 tests here in about 4
seconds. The second needs `torch`; without it, every test in it reports
`skipped 'needs torch'` rather than failing (also verified here, 8 skipped,
`OK`) -- that is the intended behaviour on a machine that only has the
harness, not a failure to investigate.

## What this guide could and could not check

Run directly, in this session, while writing the sections above: every
`dawnr_harness index`/`problems`/`call` example and its exact output; the
MCP server transcript; both test commands and their pass/skip counts;
`chat_cli.py --help`; the desktop app's actual failure in a display-less,
mismatched-Tk container. Not run here, and not claimed as tested: the
desktop app's window on a machine with a working display (this container
has neither a display nor a `python3` build with `tkinter`, which is an
environment gap, not something this guide changed or worked around); any
real conversation through `chat_cli.py --harness`, since that needs a
chat-trained checkpoint with its weights pulled by `git lfs`, and this
container has neither `git-lfs` installed nor one pulled. Both are ordinary
to have on a normal development machine; they are named here so nothing
above is taken on faith that was not actually run.
