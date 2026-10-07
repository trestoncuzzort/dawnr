# t/ carries a pinned copy of the t proof engine

The t language lives in its own repository, [t-proof-engine](https://github.com/trestoncuzzort/t-proof-engine),
split out of this one on 2026-10-06 with its history. That covers the parser and checker, the seven lowerings,
the kernel adapters, the twin harness, the matrix runner, the tasks, the twins and the documents. This directory
carries a copy of that engine beside dawnr's own pipeline scripts, which still live here.

Pinned commit: `fc2f91f660dc0f441d11dd93a77ad82257162c95` (t-proof-engine, 2026-10-07)

- **Engine changes land in t-proof-engine first.** Then `bash t/sync_engine.sh` brings them here and moves the
  pin above. It overwrites every file the engine tracks under `t/` and deletes the ones it dropped.
- **dawnr owns `t/requirements.txt`**, although the engine has a file of the same name. dawnr's pipeline needs
  `datasets`, and the engine needs nothing outside the standard library.
- **Everything else in `t/` that the engine does not track belongs to dawnr.** That covers the training loop, the
  spec check, preflight, the lab scripts and the corpora tools.
- **Next:** dawnr's pipeline moves out of `t/`, and `t/` becomes a git submodule of t-proof-engine, which replaces
  this copy.
