# Dawnr rolling release

[Rolling](https://github.com/trestoncuzzort/dawnr/releases/tag/rolling) is the
single release channel. The installer follows its model manifest, downloads
the listed files, and checks each SHA-256 before using it. Reinstalling
refreshes the manifest and reuses unchanged model files.

## Status, 23 October 2026

The released model is dawnr v5 (the artifact is named `dawnr-student-v5`; its
[model card](MODEL-CARD-student-v5.md) carries the measurements). Nothing has
been promoted since: v6 corrective, v7 and v8 were each trained from changed
data and read against v5 on the 95-problem development panel, and the week of
22 October showed that the panel's own noise is as large as the differences
they showed. Decoded three times, v5 ends fully clean on 6, 4 and 6 of 95
(all seven kernels 3, 2, 3); trained again from its exact rows with only the
seed changed, 4, 5, 4 (2, 1, 1). On the 240-problem panel (the 95 plus the
wider reader's 145) v5 reads 31, 29, 30 clean and its seed-2 twin 22, 25, 22.
v8, the last candidate before the protocol change, reads 4, 4, 5 on the 95
against v5's 6, 4, 6: not separable (sign test p 0.63).

From v9 on, a model qualifies for this channel only by the protocol of
[the variance record](../t/PREDICT-2026-10-22-seed-variance.md): trained on two
seeds, decoded three times each, read paired per problem on the 240-problem
panel against v5's six decodes (both seeds, mean 26.5 clean), with the
ceiling instrument's gate precision and the held-out 182 read beside it. A
mean is never a verdict. v9 (v5's rows plus self-distilled specifications kept
at a 90% strength floor) finished training on 22 October; its ceiling reading
is in [its record](../t/PREDICT-2026-10-22-v9-strict-rows.md) and its seed-2
twin is training. Historical model names identify measured artifacts, not
separate release channels.

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
