# The student that ships: registered 2026-10-02 05:36Z, before it is trained

dawnr is being made installable (`install.sh`, `bin/dawnr`). The installer downloads a student model; the
measured-best student for writing `t` is the 4B on v5 (`t/PREDICT-2026-10-01-v6.md`, part 3), and its rows hold
44 specification-given rows from dafny-synthesis programs, GPL-3.0 at their source
(`internal/RELEASE-PROVENANCE-2026-10-01.md`). The release is that recipe without them.

**Recipe:** exactly the 4B on v5 (`t/student_sft.py`, Qwen3.5-4B, rank 64, five epochs, rows up to 2,845
tokens, seed 1, the reference attention path), on `sft-student-v5-0750-nogpl.jsonl`: the v5 rows minus the 44
(3,944 rows). Merged, exported to GGUF at Q8_0 (llama.cpp's `convert_hf_to_gguf.py --no-mtp`, then
`llama-quantize`), the format measured to keep every proof (`t/PREDICT-2026-10-01-small-hardware.md`).

**Measured before release,** at Q8_0 through llama-server as the installer runs it: the 33 given
specifications, and one greedy dev answer through the gate.

104. Given the specification, it proves at least 26 of 33 by all seven (v5 in bf16: 28; at Q8_0: 26).
105. One greedy dev answer proves at least 3 dev problems on complete specifications (v5: 4).

If either fails, the release is the 4B on v6 (trained without the 44 already), measured the same way.
Training waits for the desktop card, which is off the bus until it is power-cycled.

## Amendment, 2026-10-02 07:15Z: the operator's word, and the order of releases

The operator asked for the student to be published under Apache-2.0 now (2026-10-02). The desktop card is still
off the bus, so the recipe above cannot train yet. The registered fallback, the 4B on v6, was trained without
the GPL-derived rows already, so it is released first as `student-v1`, once it passes the same two measurements
at Q8_0 (predictions 104 and 105, as written). The recipe above trains when the card is back and is released as
`student-v2` if it proves more of the 33 by all seven than v1 does.

## Outcome for v2 (the recipe above), 2026-10-02 13:09Z

Trained when the card came back (3,944 rows, 1,225 steps, train loss 0.0239), merged, exported to Q8_0 and measured
the same way as v1, on the desktop CPU through llama-server:

| at Q8_0 | v1 (the 4B on v6, published) | v2 (the v5 recipe without the 44) |
|---|---:|---:|
| 33 given specifications, by all seven | 26 | 24 |
| by at least one | 27 | 27 |
| refuted by a kernel | 4 | 6 |
| dev problems on complete specifications, one greedy answer | 4 | 3 |

104. **Falsified for v2:** 24 of 33 by all seven, not at least 26.
105. **Holds for v2:** 3.

So v2 is not released and `student-v1` stays the installer's student. The 44 rows left out were all
specification-given rows from dafny-synthesis programs, the kind of row these 33 questions test, and the v5 recipe
without them proves two fewer by all seven than v1, which was trained with 185 more rows of other kinds. The v5
numbers in the held-out results (15 to 19 of 200) are of the recipe with those rows; no released weights hold them.
