# Keep evaluation receipts independent when reusing requests

The existing `laptop_route.sh` seeds a cache by hard-linking every JSON file except
`protocol.json`. This includes `completed.json`. The decoder writes that completion
receipt in place, so a later seeded run can overwrite the source run's receipt.

Before the reproduction, a private prediction recorded that the actual shell seeding
fragment would share the completion inode and that a destination write would change
the source. The falsifier was an unchanged source receipt. Both predicted effects
were observed in a temporary fixture; no model or server ran.

The correction copies only request records named by their SHA-256 identity, validates
that identity, and writes independent bytes atomically. Existing destination requests
are preserved. Run metadata is excluded, and the wrapper removes any legacy linked
completion receipt before a run can write it. The release driver records the seeder's
source hash alongside its other inputs.

Regression checks exercise real decoder replay without a model call, source isolation
after destination writes, preserved destination answers, malformed or renamed records,
symbolic links, and the actual wrapper's handling of a legacy linked completion receipt.
The wrapper fixture stops before server startup. Historical result counts are not
recomputed or changed; this finding concerns receipt ownership, not model quality.

The 21 focused cache, decoder and release-driver checks pass after the correction;
shell syntax and whitespace checks also pass. Full suites run in CI after the push.

The prepared candidate uses this correction before any training or evaluation starts.
Dataset, trainer, prompts, sampling and acceptance thresholds remain as registered.

Sources: `t/recipes/v6_server_route.py`, `t/recipes/release_decode_arms.py`, and
[Python file-copy semantics](https://docs.python.org/3/library/shutil.html#shutil.copyfile).
