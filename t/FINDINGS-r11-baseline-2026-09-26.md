# The r11 baseline, scored: nine seeds of round 9's recipe pass 0 of the clean 200 in eight seeds and 2 in one

Measured 2026-09-26 on the desktop, from the answer sets graded on 2026-09-21
(`t/out/spec-experiment/locallm-r11-*`: 232 raw answers each, one kernels.md
row per well-formed task, every option identical: temperature 0, top_k 20,
1,200 tokens, seed 1). The lab's copies of these sets never had their tables;
the desktop's are the record. r11 is what r12 is judged against (plan section E).

    python3 t/score_heldout.py --split t/out/loop/split-v5.json --outcomes r11-outcomes.json locallm-r11-s1 ... locallm-r11-s9 locallm-r9 locallm-r9-seed7 locallm-r9-seed42
    python3 t/compare_arms.py --outcomes r11-outcomes.json --arm r11=... --arm r9=... --metric tests-pass

| arm | well formed (232) | tests pass (232) | clean (232) | well formed (200) | tests pass (200) | clean (200) |
|---|---:|---:|---:|---:|---:|---:|
| r11 s1 | 125 | 3 | 3 | 107 | 0 | 0 |
| r11 s2 | 128 | 3 | 2 | 106 | 0 | 0 |
| r11 s3 | 127 | 2 | 2 | 104 | 0 | 0 |
| r11 s4 | 102 | 5 | 5 | 86 | 0 | 0 |
| r11 s5 | 107 | 4 | 3 | 89 | 0 | 0 |
| r11 s6 | 98 | 3 | 2 | 83 | 0 | 0 |
| r11 s7 | 133 | 3 | 3 | 111 | 0 | 0 |
| r11 s8 | 121 | 7 | 5 | 99 | **2** | 1 |
| r11 s9 | 120 | 3 | 3 | 99 | 0 | 0 |
| r11 rerun (same seed as s1, GPU noise) | 110 | 2 | 2 | 90 | 0 | 0 |
| r11 soup A, soup B | 110, 120 | 4, 4 | 3, 3 | 89, 101 | 0, 0 | 0, 0 |
| r9 (seeds 1337, 7, 42) | 114, 106, 101 | 2, 2, 3 | 2, 1, 3 | 96, 91, 81 | 0, 0, 1 | 0, 0, 1 |
| Phi-4-mini (eval2) | 12 | 6 | 3 | 8 | 5 | 2 |

Over the nine seeds, tests passed on the clean 200: mean 0.22, range 0-2 (seed 8
passed problems 45 and 541); clean: mean 0.11. The Wilson 95% interval of 0 of
200 is [0, 3.77] percent, of 2 of 200 [0.55, 7.14]. Dodge's expected best of nine
seeds is 1.31 problems, so a single seed reaching 2 is what nine draws of this
recipe produce, not a signal. Against the r9 family (three seeds, mean 0.33):
exact permutation one-sided p = 0.45, P(r9 > r11) = 0.59 with a bootstrap
interval [0.39, 0.89], verdict INCONCLUSIVE, as it should be for the same recipe.

On all 232, every seed's clean answers sit on the 32 problems its corpus already
answered (2 to 5 per seed); no seed's specification checks have run, so the
"clean, spec checked" column is 0 with "spec unchecked" carrying them.

What r12 has to show: a seed mean above 0.22 tests passed on the clean 200, over
ten seeds, with the registered rule of section E applied once. Anything at or
under 2 in a single seed is inside what this recipe already draws.
