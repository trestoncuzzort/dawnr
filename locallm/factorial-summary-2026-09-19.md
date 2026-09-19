# Latent and execution supervision: factorial result

Held-out splits scored: eval_pattern, eval_depth. Seeds complete: 3/3.

| seed | arm | correct | tasks | percent | malformed | wrong | other |
|---|---|---:|---:|---:|---:|---:|---:|
| 1337 | baseline | 2 | 102 | 2.0% | 1 | 99 | 0 |
| 1337 | latent | 1 | 102 | 1.0% | 2 | 99 | 0 |
| 1337 | execution | 3 | 102 | 2.9% | 0 | 98 | 1 |
| 1337 | combined | 4 | 102 | 3.9% | 2 | 96 | 0 |
| 7 | baseline | 2 | 102 | 2.0% | 0 | 100 | 0 |
| 7 | latent | 3 | 102 | 2.9% | 19 | 80 | 0 |
| 7 | execution | 7 | 102 | 6.9% | 0 | 95 | 0 |
| 7 | combined | 1 | 102 | 1.0% | 0 | 101 | 0 |
| 42 | baseline | 2 | 102 | 2.0% | 0 | 100 | 0 |
| 42 | latent | 9 | 102 | 8.8% | 1 | 92 | 0 |
| 42 | execution | 2 | 102 | 2.0% | 0 | 100 | 0 |
| 42 | combined | 2 | 102 | 2.0% | 3 | 97 | 0 |

| seed | latent − baseline | execution − baseline | combined − baseline | interaction |
|---|---:|---:|---:|---:|
| 1337 | -1.0 | +1.0 | +2.0 | +2.0 |
| 7 | +1.0 | +4.9 | -1.0 | -6.9 |
| 42 | +6.9 | +0.0 | +0.0 | -6.9 |

Registered predictions:

- combined beats baseline by at least 5 points in every seed: **falsified** at seed(s) 1337, 7, 42
- the paired combined difference is positive in every seed: **falsified** at seed(s) 7, 42
- the interaction is positive in every seed: **falsified** at seed(s) 7, 42

Malformed, timed-out, over-budget and contract-altering answers are counted as failures in every cell. These are generated-task scores: no seven-verifier, twin or specification-agreement evidence is claimed here.
