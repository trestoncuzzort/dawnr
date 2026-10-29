# Bind model measurements to observed weight files

The development and precision routes carry a model digest. The current spec33
script records an answer-model label, while its backup carries only the answers.
A matching label alone does not establish which weight file generated them.

Before either seed reaches that run, install a separate observer on the existing
approved cloud machine. Preserve the current training, export and decode scripts.
The observer reads process metadata and writes its own receipts. It issues no
model request, changes no prompt, and never restarts the training service.

For each final export, verify the file against its export receipt and preserve
the small training/export metadata separately from the large encrypted model
backup. For spec33, observe the actual server command and process identity before
any answer is present. Observe the matching client in the same job and parent
process, and verify the server owns the requested local listening socket. Bind
the fixed question digest, source hashes, server binary and unchanged model file
to the complete answer file after those processes finish. Record process start
time as well as PID so PID reuse cannot supply continuity.

Predictions before deployment:

1. Altered model bytes, wrong commands, an existing answer prefix, missing client
   evidence, duplicate/foreign/incomplete answers and changed sources are refused.
2. A synthetic process/answer lifecycle produces one consistent receipt, with no
   model, reference or prover call. The process metadata reader identifies a real
   harmless process correctly.
3. The cloud observer starts while both spec33 answer files are absent and while
   the existing training process continues. Its deployed code/config hashes match
   the reviewed local copies.
4. Each seed eventually leaves one complete observed identity receipt matching
   its independently recovered export and spec33 answers. A missed observation
   stays a provenance gap; no label is substituted for a checksum and no model
   reading is repeated to obtain a favorable record.

The four small identity groups are sealed with the existing output key and stored
in the existing private bucket. Bound each group to 16 MiB and their combined
uploads to 64 MiB, preserving the existing model/checkpoint and transfer budgets.
No new cloud machine or teacher allocation is required. Identity evidence is a
prerequisite for selection, not evidence that the model is better.

The observer, private registration and service definition are frozen in
[the input receipt](../release/evidence/model-identity-observer-inputs-2026-10-29.json).
Twenty-one focused checks passed before deployment, including a harmless real
process and listening socket. The observer also fingerprints the server's local
shared libraries; it keeps metadata uploads separate from process observation.

Sources: `t/recipes/v6_spec_route.py`, `t/recipes/spec33.sh`,
`t/score_spec_given.py`, the registered training worker and backup procedure,
and [Linux process metadata](https://docs.kernel.org/filesystems/proc.html).
