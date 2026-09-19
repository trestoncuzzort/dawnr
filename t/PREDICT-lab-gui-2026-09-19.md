# Lab monitor repair, 2026-09-19

Before validation: the desktop monitor reads local answer folders and process IDs,
while all current jobs run on the lab workstation. Its GPU watcher misses
`loop_generate.py`, and its result counter accepts a flaky proof as clean.

Predictions and falsifiers:

- One remote snapshot will identify the three surviving generation jobs and give
  the same raw-answer counts as an independent count on the workstation. A
  missing job, shell counted as a job, or unequal count falsifies this.
- Constructing and updating the remote GUI will run no local completion commands,
  checker, or model. A subprocess call during the mocked GUI test falsifies this.
- A flaky or partial proof table will contribute zero clean answers; an explicitly
  failing test with seven stable proofs will count as proven but wrong even when
  the answer set has no passing tests. Fixtures with any other count falsify this.
- Disconnecting SSH will retain the last snapshot with an explicit stale status;
  a later successful poll will restore live status. A frozen callback or silently
  displayed current status falsifies this.

Validation runs on the lab workstation; the desktop only displays the window.

## Measured

`python3 -m unittest discover -s t -p 'test_lab_*.py' -v` passes all 18 tests on
the workstation, with Tk displayed through SSH forwarding. This includes
disconnect/reconnect rendering, event replay and rotation, reused process IDs,
partial and flaky proof tables, and GPU stop isolation using fake processes.
The stop test sends no signals to real workloads.

A live snapshot took 0.501 seconds and found all three generators and four GPUs.
Independent reads of all 67 answer sets matched its raw, clean and failing-test
counts. At that measurement the active sets held 49, 102 and 142 of 232 answers.
An immediate second event read returned zero new events after the initial 300.
The follow-up worker's heartbeat was current. All four predictions held.
