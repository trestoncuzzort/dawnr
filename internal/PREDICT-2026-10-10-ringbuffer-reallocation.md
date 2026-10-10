# PX4 ring-buffer reallocation regression, 2026-10-10

Source examined: `PX4-Autopilot` at upstream commit `e1c28e27550114e85ddb8760ab3355eaa7a89d8a`. Its `Ringbuffer` API documents that callers may deallocate and allocate again. `deallocate()` releases storage and clears capacity, but the head and tail indices survive.

## Prediction

Partially used, drained, or wrapped state followed by reallocation to an 8-byte or 32-byte buffer should produce a nonempty or invalid queue. A drained buffer whose old indices are 12 should write outside an 8-byte replacement when filled. Clearing both indices during deallocation should restore an empty queue, permit its full usable capacity, reject one additional byte, and preserve FIFO data.

## Read

The six old-source controls matched: all four partially-used/wrapped reallocation cases failed the empty-state assertions; the drained-to-8 case produced an AddressSanitizer heap-buffer-overflow; and drained-to-32 was a passing capacity control. The fix resets both indices with the released pointer and capacity.

All 15 ring-buffer gtests, including the six smaller/larger reallocation cases, passed under local ASan and UBSan. The complete PX4 SITL native suite passed 212/212 on the lab with the fix. The final exact `unit-Ringbuffer` target passed after rebuilding the updated test file. Firmware target `px4_fmu-v6x_default` completed all 1,300 steps; `make check_format` and `git diff --check` passed.

No hardware was flashed or tested. This demonstrates the documented library lifecycle defect; it does not establish that a current PX4 production caller resizes a live ring buffer. The patch is prepared for review in a separate PX4 checkout. It has not been signed off or submitted.
