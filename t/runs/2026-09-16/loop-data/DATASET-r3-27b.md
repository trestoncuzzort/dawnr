# The loop dataset -- --from-samples round (r3-27b)

Built by `loop_dataset.py --from-samples` from 2 sample tag(s): `qwen3.8-27b-fp8`, `qwen3.8-27b-fp8-v3`. The reward now includes the problem's own MBPP tests: a positive passes every test and verifies with a refuted twin in at least 7 of 7 kernels. Graded over the fixed split `out/loop/split-v3.json` (pool 649: 417 train, 232 eval); only train-split positives produce pairs, the eval-split rows below measure the sampler, not training data.

## Pairs per source (after merging --include and deduplicating)

| source | pairs |
|---|---:|
| samples | 115 |
| **total (merged, deduped)** | **115** |

Samples pairs before merge: 115. Include pairs read (`none given`): 0. `sft-r3-27b.jsonl`: 47 distinct positives.

## Negatives per kind (samples source only)

| kind | pairs |
|---|---:|
| malformed | 1 |
| tests-fail-verified | 2 |
| twin:boundary-swap | 4 |
| twin:collapse-if | 15 |
| twin:collapse-if#1 | 3 |
| twin:compare-flip | 4 |
| twin:negate-cond | 12 |
| twin:off-by-one | 29 |
| twin:off-by-one#1 | 30 |
| twin:off-by-one#2 | 1 |
| twin:wrong-constant | 1 |
| twin:wrong-constant#1 | 1 |
| twin:wrong-var | 6 |
| twin:wrong-var#1 | 6 |

## Pairs per twin operator (base tag, `#k` rungs folded together, all merged pairs)

| operator | pairs |
|---|---:|
| boundary-swap | 4 |
| collapse-if | 18 |
| compare-flip | 4 |
| negate-cond | 12 |
| off-by-one | 60 |
| wrong-constant | 2 |
| wrong-var | 12 |

## Histogram: tests pass x kernel count, over train-split well-formed samples

Deduplicated by printed t text across the K tags (step 1's dedup rule); this is the bar (`--min-kernels`, currently 7) that step 2 checks against.

| tests | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pass | 96 | 6 | 7 | 12 | 11 | 5 | 11 | 56 | 204 |
| fail/other | 43 | 2 | 1 | 1 | 2 | 3 | 4 | 5 | 61 |

## pass@K, over the fixed split

| split | problems | with a well-formed sample | with a tests-passing sample | with a positive |
|---|---:|---:|---:|---:|
| train | 417 | 223 | 173 | 47 |
| eval | 232 | 128 | 92 | 16 |

Eval-split rows are a measurement of the sampler: no eval-split problem contributes a pair.

370 train-split problem(s) had at least one sample but no positive at the bar: 5, 7, 9, 11, 14, 15, 16, 19, 21, 22, 25, 27, 29, 30, 33, 36, 41, 42, 43, 44, 46, 48, 54, 55, 57, 58, 61, 62, 67, 69, 71, 76, 77, 79, 83, 84, 90, 92, 93, 99, 100, 101, 102, 107, 109, 113, 118, 121, 123, 127, 128, 131, 133, 134, 142, 146, 148, 150, 152, 155, 159, 162, 165, 166, 168, 170, 172, 173, 178, 181, 183, 186, 188, 191, 192, 199, 200, 202, 204, 207, 209, 210, 211, 217, 218, 223, 225, 226, 229, 236, 238, 240, 242, 244, 249, 251, 254, 256, 260, 270, 274, 281, 284, 285, 286, 288, 291, 292, 296, 303, 311, 315, 319, 320, 321, 323, 326, 327, 328, 331, 335, 336, 337, 338, 340, 346, 348, 349, 350, 352, 359, 360, 364, 365, 371, 372, 377, 378, 382, 384, 386, 388, 392, 396, 403, 406, 407, 412, 416, 426, 427, 430, 433, 434, 435, 437, 439, 448, 449, 450, 451, 455, 456, 459, 461, 466, 468, 471, 476, 477, 478, 480, 481, 485, 491, 495, 496, 500, 501, 504, 505, 507, 508, 511, 517, 520, 522, 523, 525, 526, 529, 532, 537, 539, 540, 543, 547, 549, 554, 555, 557, 558, 563, 564, 567, 570, 572, 573, 576, 577, 578, 586, 588, 589, 594, 595, 598, 600, 602, 603, 608, 610, 619, 620, 621, 624, 627, 628, 632, 634, 635, 637, 639, 640, 641, 643, 646, 647, 648, 649, 655, 657, 659, 661, 664, 666, 667, 668, 671, 673, 674, 676, 677, 678, 681, 684, 685, 689, 690, 693, 697, 700, 702, 707, 708, 714, 718, 724, 725, 727, 730, 735, 737, 739, 743, 745, 747, 749, 752, 754, 756, 759, 760, 762, 764, 767, 770, 771, 772, 774, 777, 781, 784, 787, 790, 794, 797, 799, 801, 803, 806, 807, 810, 812, 815, 817, 818, 820, 823, 824, 825, 829, 832, 836, 838, 841, 843, 845, 847, 848, 850, 852, 854, 855, 861, 863, 864, 868, 870, 871, 874, 879, 880, 881, 883, 884, 890, 892, 895, 897, 898, 901, 905, 907, 909, 910, 913, 915, 917, 918, 923, 926, 930, 932, 933, 934, 940, 943, 944, 950, 952, 955, 956, 958, 960, 964, 965, 967, 968, 971

## Regenerating this dataset

```
python3 loop_dataset.py --from-samples qwen3.8-27b-fp8 qwen3.8-27b-fp8-v3 --split out/loop/split-v3.json --min-kernels 7 --out-suffix r3-27b
```

