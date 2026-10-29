# Validate completed model outputs before cloud grading

Registered before any candidate grading submission. The current cloud job already
backs up completed outputs as encrypted, digest-named objects. A bounded collector
now prepares the existing cloud grading inputs as those outputs arrive. It performs
no training, decoding, reference execution, model selection or held-out evaluation.

The private registration SHA-256 is
`342f91652c6d035d14bb7ee24bd42128a6688a6f6283162d14afc1d26dd16cf0`.
All 573 source/data hashes read from the live execution checkout were independently
matched to its registered Git content or LFS digests. Grading uses workflow tag
`v6.0.2`, commit `50e811ba2e0a80acb7f31ee551d5cebf1d071864`. The existing pinned
graders and all release thresholds remain unchanged.

Expected behavior when actual outputs become available:

1. Submit exactly twelve complete development parts: two seeds, three offsets and
   the original 95/145 panels. A valid zero-answer part is submitted too. Validate
   source/model identity, completion receipt, archive digest, every panel ID and
   public member before uploading the original archive. No other panel is public.
2. Prepare two precision measurements and two given-specification measurements
   with their existing encrypted input formats. Require complete panel accounting,
   the exact registered generation arguments, and consistent model identities.
   Raw private answers never enter a public development archive.
3. Verify encrypted backup digests before opening, and every payload file after
   decryption. Keep recovered private files inaccessible to other local accounts.
   Count transfers against the existing download allowance.
4. Record each dispatch attempt before the external call. Reuse its run ID on a
   restart; an ambiguous response requires inspection instead of another dispatch.
   Preserve failed grades rather than repeating them to obtain a favorable result.

The implementation tests altered sources, archive members, panel membership,
incomplete receipts, private-file inclusion, zero-answer runs, encryption recovery
and ambiguous dispatches. An existing real input backup was recovered with all
nine payload hashes verified; its temporary plaintext was removed. The live storage
probe saw four training/input backups and no grading output, and made no submission.
These checks validate the handoff implementation, not any model-quality claim.

Sources: `t/recipes/release_decode_arms.py`, `t/recipes/grade_spec33.py`,
`.github/workflows/ceiling.yml`, `t/recipes/teacher_outputs.sh`,
[Cloud Storage object identity](https://docs.cloud.google.com/storage/docs/objects),
[workflow dispatch](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event),
and [release-asset pagination](https://docs.github.com/en/rest/releases/assets#list-release-assets).
