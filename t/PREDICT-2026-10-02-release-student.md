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
