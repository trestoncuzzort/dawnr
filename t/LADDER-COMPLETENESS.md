# The ladder as a completeness measurement

ROADMAP WS-19 move 6, 2026-09-11. `harness.twin_for` (the single-twin
rule) stops at the ladder's first rung with a witness; this measures
EVERY rung `harness.ladder_rungs` can build for each well-formed task,
via the interpreter only (no kernels run here), and cross-tabulates
the refuted fraction against the task's own tests (tests.json) and
its kernel verdict (kernels.md, `verified / refuted` per column).
A rung counts as refuted only when interp shows a sound kernel MUST
refute it (an invariant-drop witness, or an extensional witness that
falsifies `ensures`), the same standard `twin_for` applies before
accepting a flip.

## Column: `qwen2.5-coder-7b` (64 well-formed tasks)

| task_id | fn | rungs | refuted | fraction | tests | columns counting |
|---:|---|---:|---:|---:|---|---:|
| 5 | count_ways | 16 | 11 | 0.69 | fail | 0/7 |
| 17 | square_perimeter | 2 | 2 | 1.00 | pass | 6/7 |
| 34 | find_missing | 3 | 1 | 0.33 | requires-excluded | 0/7 |
| 35 | find_rect_num | 2 | 2 | 1.00 | pass | 6/7 |
| 52 | parallelogram_area | 2 | 2 | 1.00 | pass | 6/7 |
| 58 | opposite_Signs | 6 | 6 | 1.00 | pass | 3/7 |
| 59 | is_octagonal | 4 | 4 | 1.00 | pass | 6/7 |
| 84 | sequence | 16 | 12 | 0.75 | pass | 0/7 |
| 86 | centered_hexagonal_number | 4 | 4 | 1.00 | fail | 6/7 |
| 89 | closest_num | 2 | 2 | 1.00 | pass | 6/7 |
| 112 | perimeter | 4 | 4 | 1.00 | pass | 6/7 |
| 119 | search | 30 | 21 | 0.70 | fail | 0/7 |
| 122 | smartNumber | 17 | 15 | 0.88 | fail | 0/7 |
| 127 | multiply_int | 20 | 19 | 0.95 | pass | 6/7 |
| 135 | hexagonal_num | 4 | 4 | 1.00 | pass | 6/7 |
| 162 | sum_series | 15 | 10 | 0.67 | pass | 0/7 |
| 169 | get_pell | 18 | 14 | 0.78 | pass | 0/7 |
| 171 | perimeter_pentagon | 2 | 2 | 1.00 | pass | 6/7 |
| 176 | perimeter_triangle | 6 | 6 | 1.00 | pass | 6/7 |
| 189 | first_Missing_Positive | 43 | 29 | 0.67 | fail | 0/7 |
| 190 | count_Intgral_Points | 12 | 12 | 1.00 | fail | 6/7 |
| 195 | first | 31 | 27 | 0.87 | pass | 6/7 |
| 234 | volume_cube | 0 | 0 | 0.00 | pass | 0/7 |
| 264 | dog_age | 2 | 2 | 1.00 | fail | 6/7 |
| 266 | lateralsurface_cube | 2 | 2 | 1.00 | pass | 6/7 |
| 279 | is_num_decagonal | 4 | 4 | 1.00 | pass | 6/7 |
| 295 | sum_div | 16 | 12 | 0.75 | fail | 0/7 |
| 309 | maximum | 8 | 7 | 0.88 | pass | 7/7 |
| 354 | tn_ap | 8 | 8 | 1.00 | fail | 6/7 |
| 356 | find_angle | 4 | 4 | 1.00 | pass | 6/7 |
| 369 | lateralsurface_cuboid | 8 | 8 | 1.00 | pass | 6/7 |
| 373 | volume_cuboid | 6 | 6 | 1.00 | pass | 6/7 |
| 379 | surfacearea_cuboid | 14 | 14 | 1.00 | pass | 6/7 |
| 385 | get_perrin | 22 | 19 | 0.86 | pass | 0/7 |
| 389 | find_lucas | 16 | 12 | 0.75 | pass | 0/7 |
| 420 | cube_Sum | 24 | 22 | 0.92 | fail | 5/7 |
| 430 | parabola_directrix | 6 | 6 | 1.00 | fail | 6/7 |
| 441 | surfacearea_cube | 2 | 2 | 1.00 | pass | 6/7 |
| 458 | rectangle_area | 2 | 2 | 1.00 | pass | 6/7 |
| 468 | max_product | 18 | 16 | 0.89 | fail | 0/7 |
| 498 | gcd | 31 | 21 | 0.68 | pass | 7/7 |
| 499 | diameter_circle | 2 | 2 | 1.00 | pass | 6/7 |
| 549 | odd_Num_Sum | 20 | 17 | 0.85 | fail | 0/7 |
| 555 | difference | 19 | 11 | 0.58 | fail | 0/7 |
| 581 | surface_Area | 6 | 6 | 1.00 | pass | 6/7 |
| 627 | find_First_Missing | 38 | 13 | 0.34 | fail | 0/7 |
| 637 | noprofit_noloss | 2 | 2 | 1.00 | pass | 4/7 |
| 646 | No_of_cubes | 12 | 12 | 1.00 | pass | 6/7 |
| 654 | rectangle_perimeter | 4 | 4 | 1.00 | pass | 6/7 |
| 677 | validity_triangle | 26 | 16 | 0.62 | pass | 3/7 |
| 716 | rombus_perimeter | 2 | 2 | 1.00 | pass | 6/7 |
| 733 | find_first_occurrence | 26 | 24 | 0.92 | pass | 6/7 |
| 770 | odd_Num_Sum | 19 | 15 | 0.79 | fail | 0/7 |
| 789 | perimeter_polygon | 2 | 2 | 1.00 | pass | 6/7 |
| 814 | rombus_area | 2 | 2 | 1.00 | fail | 6/7 |
| 837 | cube_Sum | 24 | 22 | 0.92 | fail | 5/7 |
| 844 | get_Number | 2 | 2 | 1.00 | fail | 6/7 |
| 873 | fibonacci | 16 | 11 | 0.69 | pass | 7/7 |
| 882 | parallelogram_perimeter | 4 | 4 | 1.00 | fail | 6/7 |
| 908 | find_fixed_point | 23 | 19 | 0.83 | pass | 0/7 |
| 924 | max_of_two | 8 | 7 | 0.88 | pass | 7/7 |
| 926 | rencontres_number | 40 | 32 | 0.80 | fail | 0/7 |
| 931 | sum_series | 18 | 14 | 0.78 | pass | 0/7 |
| 960 | get_noOfways | 16 | 11 | 0.69 | fail | 0/7 |

### Fraction bucket against tests outcome

| fraction bucket | fail | pass | requires-excluded | total |
|---|---:|---:|---:|---:|
| all rungs refuted | 8 | 25 | 0 | 33 |
| some rungs refuted | 14 | 15 | 1 | 30 |
| none rungs refuted | 0 | 1 | 0 | 1 |

### Fraction bucket against kernel bar

| fraction bucket | all seven | some column | none | total |
|---|---:|---:|---:|---:|
| all rungs refuted | 0 | 33 | 0 | 33 |
| some rungs refuted | 4 | 6 | 20 | 30 |
| none rungs refuted | 0 | 0 | 1 | 1 |

### Mean fraction refuted, per tests outcome

| tests outcome | tasks | mean fraction |
|---|---:|---:|
| fail | 22 | 0.84 |
| pass | 41 | 0.90 |
| requires-excluded | 1 | 0.33 |

### Plain reading

All-rungs-refuted tasks: 33, of which 25 pass their tests (25/33). Some-rungs-refuted: 30, of which 15 pass (15/30 if any). No-rungs-refuted: 1, of which 1 pass (1/1 if any). Read as counts, not a claim of correlation: the fraction refuted does not sort tasks by tests outcome here -- a fully-refuted ladder is common in both the passing and the failing rows, since the ladder measures how much of the mutation space the spec sees, and the tests measure whether the spec is the problem's, two different questions by 12.6's own finding.

### The 34-of-35 restate-the-body claim, re-read

35 of the 64 tasks are the restate-the-body shape (`is_restate_body`, structural: sole `ensures` is `ret == E`, body is the single statement `ret := E`, same `E`). Of those, 33 have EVERY rung on the full ladder refuted (not just the first rung the single-twin rule tries), against the 33 of all 64 well-formed tasks with every rung refuted.

## Column: `qwen2.5-coder-1.5b-r2` (23 well-formed tasks)

| task_id | fn | rungs | refuted | fraction | tests | columns counting |
|---:|---|---:|---:|---:|---|---:|
| 24 | binary_to_decimal | 0 | 0 | 0.00 | fail | 0/7 |
| 86 | centered_hexagonal_number | 4 | 4 | 1.00 | fail | 6/7 |
| 122 | smartNumber | 4 | 4 | 1.00 | fail | 6/7 |
| 212 | fourth_Power_Sum | 8 | 8 | 1.00 | fail | 6/7 |
| 221 | first_even | 25 | 23 | 0.92 | fail | 5/7 |
| 287 | square_Sum | 17 | 15 | 0.88 | fail | 6/7 |
| 289 | odd_Days | 26 | 3 | 0.12 | fail | 7/7 |
| 347 | count_Squares | 2 | 2 | 1.00 | fail | 6/7 |
| 355 | count_Rectangles | 0 | 0 | 0.00 | undefined | 0/7 |
| 420 | cube_Sum | 23 | 22 | 0.96 | fail | 0/7 |
| 436 | neg_nos | 25 | 23 | 0.92 | fail | 7/7 |
| 443 | largest_neg | 25 | 23 | 0.92 | fail | 5/7 |
| 479 | first_Digit | 10 | 4 | 0.40 | pass | 0/7 |
| 566 | sum_digits | 0 | 0 | 0.00 | fail | 0/7 |
| 592 | sum_Of_product | 21 | 19 | 0.90 | fail | 0/7 |
| 675 | sum_nums | 32 | 14 | 0.44 | fail | 7/7 |
| 692 | last_Two_Digits | 2 | 2 | 1.00 | fail | 6/7 |
| 765 | is_polite | 0 | 0 | 0.00 | fail | 0/7 |
| 768 | check_Odd_Parity | 4 | 4 | 1.00 | pass | 6/7 |
| 793 | last | 30 | 24 | 0.80 | fail | 0/7 |
| 882 | parallelogram_perimeter | 4 | 4 | 1.00 | fail | 6/7 |
| 931 | sum_series | 8 | 8 | 1.00 | fail | 6/7 |
| 935 | series_sum | 8 | 8 | 1.00 | pass | 6/7 |

### Fraction bucket against tests outcome

| fraction bucket | fail | pass | undefined | total |
|---|---:|---:|---:|---:|
| all rungs refuted | 7 | 2 | 0 | 9 |
| some rungs refuted | 9 | 1 | 0 | 10 |
| none rungs refuted | 3 | 0 | 1 | 4 |

### Fraction bucket against kernel bar

| fraction bucket | all seven | some column | none | total |
|---|---:|---:|---:|---:|
| all rungs refuted | 0 | 9 | 0 | 9 |
| some rungs refuted | 3 | 3 | 4 | 10 |
| none rungs refuted | 0 | 0 | 4 | 4 |

### Mean fraction refuted, per tests outcome

| tests outcome | tasks | mean fraction |
|---|---:|---:|
| fail | 19 | 0.73 |
| pass | 3 | 0.80 |
| undefined | 1 | 0.00 |

### Plain reading

All-rungs-refuted tasks: 9, of which 2 pass their tests (2/9). Some-rungs-refuted: 10, of which 1 pass (1/10 if any). No-rungs-refuted: 4, of which 0 pass (0/4 if any). Read as counts, not a claim of correlation: the fraction refuted does not sort tasks by tests outcome here -- a fully-refuted ladder is common in both the passing and the failing rows, since the ladder measures how much of the mutation space the spec sees, and the tests measure whether the spec is the problem's, two different questions by 12.6's own finding.

### The 34-of-35 restate-the-body claim, re-read

13 of the 23 tasks are the restate-the-body shape (`is_restate_body`, structural: sole `ensures` is `ret == E`, body is the single statement `ret := E`, same `E`). Of those, 9 have EVERY rung on the full ladder refuted (not just the first rung the single-twin rule tries), against the 9 of all 23 well-formed tasks with every rung refuted.

