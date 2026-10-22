# Dawnr rolling release

[Rolling](https://github.com/trestoncuzzort/dawnr/releases/tag/rolling) is the
single release channel. The installer follows its model manifest, downloads
the listed files, and checks each SHA-256 before using it. Reinstalling
refreshes the manifest and reuses unchanged model files.

The current model remains [v5](MODEL-CARD-student-v5.md). The candidates since
it (v6, v7, v8) did not separate from v5 under the measured noise of the
development panel and none is promoted; v9 is in training under the two-seed,
three-decode protocol of 22 October 2026 (see the README's model status). Historical model names identify measured artifacts, not separate
release channels.

To update an existing checkout:

```bash
git pull --ff-only
./install.sh
dawnr doctor
```

Repeat `--home DIR` when reinstalling into a custom model directory. The
installed command remembers that directory between uses.

When a new model qualifies, publish its versioned files and checksums before
replacing `dawnr-student.sha256`. Keep the v5 baseline files and its separate
manifest in the same rolling release while they are needed to reproduce the
comparison. A partial download or checksum failure must leave the previous
installation configuration in place.

Application changes and model qualification are recorded separately. Update
the rolling tag and notes to the tested application revision; do not describe
an unevaluated model as the released default.
