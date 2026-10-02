# Seatbelt policies from OpenAI's Codex CLI

`seatbelt_base_policy.sbpl` and `seatbelt_read_only_platform_defaults.sbpl` are copied unchanged from
github.com/openai/codex, `codex-rs/sandboxing/src/`, commit 4dd51f4a5f2037f8aa322fe7807315e6530a4ec8 (Apache License 2.0, `LICENSE` here).
`t/py_sandbox.py` runs model-written Python on macOS under `/usr/bin/sandbox-exec` with these two policies
followed by its own few lines (read the job folder and the Python install, write only a private temporary folder).
Codex's base policy denies by default and grants no network access.
