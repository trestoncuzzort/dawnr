# dawnr releases

Releases are numbered dawnr MAJOR.MINOR.PATCH and published as GitHub releases tagged vMAJOR.MINOR.PATCH. `dawnr
version` prints the release a checkout is. `install.sh` installs the model of the latest release by default;
`./install.sh --release v6.0.0` installs one release's model, and `--model FILE` uses a local file.

Every release carries `dawnr.sha256`, the model manifest: one line per model file, its SHA-256 and either its name in
the same release or the URL where an earlier release of this repository published it. A release that keeps its model
therefore lists the earlier files instead of uploading the same weights again. The installer checks every file
against its SHA-256 before it switches models, keeps the installed model if anything fails, and removes the files only
the replaced manifest listed once the new model is complete.

## Status, 24 October 2026

**dawnr 6.0.0** (tag `v6.0.0`) is the current release. Its model is the October 5 model, byte for byte, under version
names ([card](MODEL-CARD-dawnr-6.0.md)); what is new is the application at that tag, the version it carries, the
installer, and the correction of the October 22 to 23 readings ([CORRECTIONS.md](../CORRECTIONS.md)). The 6.1.0
candidate is in training on the October 5 model's own audited rows plus strictly checked specifications and repair
examples ([registration](../t/PREDICT-2026-10-24-release-6.1-candidate-a.md)).

## How a model enters a release

Only by the protocol of [the 6.0 plan](../internal/RELEASE-6.0-PLAN.md), section 3: two training seeds and three
decodes each, read paired per problem against the released model on the 206 unleaked development problems (more
problems up than down, permutation p at or below 0.05); the ceiling instrument's gate precision at least 0.70; at
least 27 of the 33 given specifications proved by all seven kernels; the held-out 182 read once, after the others
decide, and not below the released model's 17 and 12; and the model running as smoothly as the released one on the
laptop the release is checked on. A mean is never a verdict. A release that does not change the model says so.

MAJOR changes what a person must do differently (file names, commands); MINOR adds a model or a capability; PATCH
fixes.

## History

From 2026-10-05 to 2026-10-24 downloads came from one rolling channel (tag `rolling`) whose model files were named
`dawnr-student-*`, the model now carried by 6.0.0. That channel stays published for the records that cite it;
`./install.sh --model https://github.com/trestoncuzzort/dawnr/releases/download/rolling` still reads it.

To update a checkout:

```bash
git pull --ff-only
./install.sh
dawnr version
dawnr doctor
```

Repeat `--home DIR` when reinstalling into a custom model directory. The installed command remembers that directory
between uses.
