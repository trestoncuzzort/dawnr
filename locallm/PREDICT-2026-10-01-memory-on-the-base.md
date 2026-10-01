# Remembering the person, on the chosen weights: registered 2026-10-01 11:28Z

## What this is

`AMBITION.md`'s row "to remember the person across sessions" was built (a per-person store the person
controls, dawnr's own recall) and measured on the from-scratch core: untrained it never used the memory
it was handed; trained on 197 memory conversations it recalled the person's preference 46% of the time
and never invented one, and did not apply it to a program (0%)
(`locallm/memory-conversations-results-2026-09-27.json`). The plan of record re-measures the row on the
chosen base. This is that measurement: the same 112 held-out items, the same store, the same recall, the
same judge (`memory_eval.judge`).

## The measurement (`locallm/memory_eval_native.py`)

What dawnr's recall returns for the item's person and first message is put in one system turn labelled
"Memory from earlier sessions with this person:" (a pretrained model has no memory token); greedy; 400
tokens. Two models, at the lab's CPU through llama.cpp:

- the base Qwen3.5-4B (Q4_K_M), untrained on anything here;
- the student, the 4B on v4 at Q8_0 (the file that keeps every proof), with its own system prompt first.

## Predictions

71. Both recall the remembered preference when it is there on at least 80% of the 28 items. Falsified
    below 80% for either.
72. Neither invents a preference when the store is empty: at most 1 of the 28. Falsified above 1.
73. The student applies the remembered parameter name to a program that still passes its examples on
    at least 3 of the 14 `use` items (the from-scratch model: 0). Falsified below 3.
