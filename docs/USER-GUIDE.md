# Using Dawnr

Use Dawnr from your terminal to understand a repository, work on code, or
generate functions with tests and proof checks. The models run locally.

## Install

You need Git, Python 3.10 or newer, and Linux, macOS, or Windows through WSL2.
The first installation downloads several gigabytes of models and tools;
running the installer again reuses completed downloads.

```bash
git clone https://github.com/trestoncuzzort/dawnr
cd dawnr
./install.sh
export PATH="$HOME/.local/bin:$PATH"
dawnr doctor
```

The installer prints the exact command path, so you can use it immediately
even when `dawnr` is not on your `PATH`. Add the export line to your shell's
startup file if you want it available in future terminals.

On Ubuntu or Debian, install any prerequisites the installer reports, then
rerun it. A typical command is:

```bash
sudo apt install libgomp1 unzip bubblewrap
```

Models normally live in `~/.local/share/dawnr`. Choose another disk with
`./install.sh --home "/path/to/model storage"`; the installed command remembers
that location. `./install.sh --build cpu` selects CPU inference. Read all
installer options with `./install.sh --help`.

The installer includes Dafny where supported. Additional provers are available
through the [proof-engine setup guide](../t/README.md).

## Try a repository task

Open a terminal in the project you want to work on:

```bash
cd /path/to/your/project
dawnr do "Explain this project's structure and where its tests live" --read-only
```

The model starts automatically. Its first load can take a few minutes. You do
not need to start a separate server or select a model.

Run `dawnr` for an interactive session, or use `dawnr do "TASK"` for one task
that returns to your shell. For example:

```bash
dawnr do "Add a test for empty input in the parser"
```

Proposed changes appear for review before they are applied. In an interactive
session, `/undo` restores the last recorded change. `--read-only` allows file
reading and explanations while preventing edits and command execution.

## Generate a checked function

Give the function's intended behavior and concrete examples:

```bash
dawnr ask "Write a function that returns the larger of two integers." \
  --test "assert larger(3, 5) == 5" \
  --test "assert larger(-2, -1) == -1" \
  --save-python larger.py --certificate larger.cert.json
dawnr check larger.cert.json
```

`ask` checks candidate code against the examples, examines its specification,
and runs available provers. It may take several minutes and may return a
reason it could not establish an answer. `check` replays the saved evidence
without generating another answer. Results name the checks that actually ran.

A proof covers the program's stated specification and assumptions. Read those
alongside the examples to decide whether they describe the behavior you need.

For existing code, start with `dawnr help verify`. For a specification you
already wrote, use `dawnr help prove`.

## Get help and recover

`dawnr --help` and `dawnr help COMMAND` work without starting models. From a
fresh source checkout, `./bin/dawnr --help` works before installation too.

| What happened | Next step |
|---|---|
| `dawnr: command not found` | Run the full command path printed by the installer, or add `~/.local/bin` to `PATH`. |
| Setup is incomplete or a model is missing | Run `./install.sh` from the checkout again, then `dawnr doctor`. For a custom model directory, repeat the same `--home` option. |
| A download stopped | Rerun the same install command. Partial downloads resume and completed files are checked before reuse. |
| A model takes too long to load | Read the log path printed by the command. Run `dawnr doctor` to check the server and model files. |
| GPU startup fails | Run `DAWNR_GPU_LAYERS=0 dawnr do "Explain this project" --read-only` to try CPU inference. |
| The sandbox cannot run | Follow the diagnostic from `dawnr doctor`. Commands that need sandboxing stop until it works. |
| You want to unload the models | Run `dawnr serve stop`. The next task starts them again. |

## More workflows

- `dawnr cite "QUESTION" FILE` answers with quotations from a document.
- `dawnr calc "QUESTION WITH NUMBERS"` checks a numerical answer against separately evaluated workings.
- `dawnr ui` opens the local browser interface.
- `dawnr mcp` exposes the checks to an MCP client.

The assistant starts offline. `--online` enables its web tools for a session.
See [privacy](../PRIVACY.md), the [command reference](COMMANDS.md), and the
[assistant's tool boundaries](../DAWNR-AGENT.md) for details.

Training scripts and older research interfaces are documented in the
[historical harness guide](HISTORICAL-HARNESS-GUIDE.md). They are not needed
to install or use the current terminal application.
