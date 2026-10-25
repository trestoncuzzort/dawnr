# t/ carries a pinned copy of the t proof engine

The t language lives in its own repository, [t-proof-engine](https://github.com/trestoncuzzort/t-proof-engine),
split out of this one on 2026-10-06 with its history. That covers the parser and checker, the seven lowerings,
the kernel adapters, the twin harness, the matrix runner, the tasks, the twins and the documents. This directory
carries a copy of that engine beside dawnr's own pipeline scripts, which still live here.

Pinned commit: `d13d11d01f8f50687ef645d60aa08c870d664b84` (t-proof-engine, 2026-10-10)

The Frama-C adapter, its review/control tests, and their October 18 evidence
are imported from engine commit `5828ed07aaba864a4dc4ae06ab20a4a01a5d686b`.
This is a per-file update; the base pin above has not been changed to imply
a full synchronization. The repair landed in the engine first. It restores
the four seven-kernel controls while retaining the tested negative checks;
see [the measurement](PREDICT-2026-10-18-framac-controls.md).

The certificate-negation change in `lower_framac.py` is imported from upstream merge
`d1b57dc640512a81ff58c084a4e2f976c7d5c474` ([PR 1](https://github.com/trestoncuzzort/t-language/pull/1),
2026-10-25). Only that reviewed diff is applied to dawnr's existing lowering. Its new regression test,
registration and evidence are copied from the merged revision. The base pin and earlier adapter import
remain as recorded above; this is not a full engine synchronization. The upstream native controls passed
and its 114-task Frama-C column was unchanged. See the
[import receipt](../release/evidence/framac-certificate-import-2026-10-25.json) and
[measurement](PREDICT-2026-10-25-framac-certificate-binding.md).
Candidate comparison requires refreshed dawnr baseline and specification controls using this evaluator.

- **Engine changes land in t-proof-engine first.** Then `bash t/sync_engine.sh` brings them here and moves the
  pin above. It overwrites every file the engine tracks under `t/` and deletes the ones it dropped.
- **dawnr owns `t/requirements.txt`**, although the engine has a file of the same name. dawnr's pipeline needs
  `datasets`, and the engine needs nothing outside the standard library.
- **Everything else in `t/` that the engine does not track belongs to dawnr.** That covers the training loop, the
  spec check, preflight, the lab scripts and the corpora tools.
- **Next:** dawnr's pipeline moves out of `t/`, and `t/` becomes a git submodule of t-proof-engine, which replaces
  this copy.
