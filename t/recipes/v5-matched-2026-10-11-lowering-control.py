#!/usr/bin/env python3
"""Reproduce the allocation refusal and compare a normal lowering byte for byte.

Sources: bounded-grading-python.py and t/run_par.py::_lower_units.
Run on the lab, from the repository root, before restarting the two graders.
"""
import importlib.util
import json
from pathlib import Path
import resource
import sys
import time

spec = importlib.util.spec_from_file_location('bounded', 't/recipes/bounded-grading-python.py')
bounded = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bounded)
before = resource.getrlimit(resource.RLIMIT_AS)
assert bounded.bounded_call(lambda: 17, 256 * 1024**2) == 17
assert resource.getrlimit(resource.RLIMIT_AS) == before
try:
    bounded.bounded_call(lambda: bytearray(512 * 1024**2), 256 * 1024**2)
except MemoryError:
    pass
else:
    raise AssertionError('allocation was not refused')
assert resource.getrlimit(resource.RLIMIT_AS) == before
try:
    bounded.bounded_call(lambda: 1 / 0, 256 * 1024**2)
except ZeroDivisionError:
    pass
else:
    raise AssertionError('exception lost')
assert resource.getrlimit(resource.RLIMIT_AS) == before

sys.path.insert(0, 't')
import harness
import lower_rocq
import run_par

tasks = Path('t/out/spec-experiment/v5-matched-20261011-v5/tasks')
def arguments(name):
    task = harness.load(tasks / (name + '.json'))
    twin, _op, witness = harness.twin_cached(task)
    return task, lower_rocq.lower, twin, witness, harness.real_witness(task)

start = time.monotonic()
try:
    bounded.bounded_call(run_par._lower_units, 4096 * 1024**2,
                         *arguments('mbpp_748__capital_words_spaces'))
except MemoryError:
    pass
else:
    raise AssertionError('expected real lowering refusal')
assert resource.getrlimit(resource.RLIMIT_AS) == before
args = arguments('mbpp_672__max_of_three')
assert bounded.bounded_call(run_par._lower_units, 4096 * 1024**2, *args) == run_par._lower_units(*args)
assert resource.getrlimit(resource.RLIMIT_AS) == before
record = {'allocation_refused': True, 'normal_return_unchanged': True,
          'exception_preserved': True, 'limits_restored': True,
          'real_task_refused': 'mbpp_748__capital_words_spaces',
          'normal_lowering_byte_identical': 'mbpp_672__max_of_three',
          'limit_mib': 4096, 'elapsed_seconds': time.monotonic() - start}
Path('t/out/v5-matched-20261011/lowering-control.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record))
