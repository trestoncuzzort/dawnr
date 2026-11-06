# PX4: bugs in ordinary flight, 2026-11-06

PX4's maintainers have said what they want from this repository's findings: "Some of these PRs are good bug fixes, others are pointless edge cases", and "Before opening the PR ask your AI 'Is this even worth doing?'" ([#29151](https://github.com/PX4/PX4-Autopilot/pull/29151)). Of the findings in [FLIGHT-FINDINGS-REAL.md](FLIGHT-FINDINGS-REAL.md), several needed a malformed message or an out-of-range parameter, and that is the kind they meant.

So this looks somewhere else: **what goes wrong when nothing unusual is asked of the vehicle.** A sanitizer report during PX4's own flight tests, or in a long flight with ordinary settings, cannot be an edge case by construction. Each is read and then checked by a native case in this gate before it counts.

Prior art: PX4's CI already flies SIH under ASan on `quadx`, TSan on `hex` and UBSan on `xvert` (`.github/workflows/sitl_tests.yml`), and UBSan's non-fatal reports fail nothing there. Long flights and the other vehicle and sanitizer pairs are not in that matrix. PX4's own `clang-tidy` job uses a narrower list of checks than the one here. `lv_map` in [the scaffold's measurement](PREDICT-2026-11-05-native-scaffold.md) is the shape to look for: an overflow on ordinary values, and one that needs a long time to show up is still ordinary.

## What runs

At PX4 `bf59c29e8b`, on one throwaway 16-core VM:

1. `test/mavsdk_tests/configs/sih-sitl.json`, PX4's own flight tests, once each under UBSan, ASan and TSan.
2. Long flights in SIH with ordinary settings, past the 32-bit microsecond wraps at 35.8 and 71.6 minutes.
3. `clang-tidy` with `bugprone-misplaced-widening-cast`, `bugprone-integer-division` and `clang-analyzer-*` over PX4's own sources.

A finding is reported only when all of this holds: **it happens on values or settings a user would really have**, it has a consequence someone would notice, it is not already fixed or being worked on upstream, and a native case or a PX4 unit test shows it failing before a fix and passing after. Nothing goes upstream from here without the owner's say on that item.

## Predictions, written before any flight

| # | prediction | falsified by |
|---|---|---|
| X1 | UBSan reports at least one distinct location in PX4's own code during its own flight tests | none |
| X2 | ASan reports nothing in PX4's own code, since CI already runs it on `quadx` | any report |
| X3 | TSan reports at least one race not in PX4's suppression file | none |
| X4 | Long flights change nothing visible at the wraps: at most a sanitizer report, and no failsafe, reset or stop that a shorter flight lacks | any such change |
| X5 | At most 1 in 4 distinct sanitizer reports survives reading as something worth proposing | more than 1 in 4 |
| X6 | At most 1 in 10 `clang-tidy` reports read survives | more than 1 in 10 |
| X7 | This finds at most 3 things worth a pull request, since PX4 has been read closely here once already and has an active fuzzing and sanitizer setup | more than 3 |

## Results

To be filled in by the runs, with the failures left in.
