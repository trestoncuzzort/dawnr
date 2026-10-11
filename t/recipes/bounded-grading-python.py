#!/usr/bin/env python3
"""Python launcher with an allocation bound during run_par's lowering only.

Use as PYTHON in a grading recipe. Other Python invocations are passed through.
Kernel processes retain their original limits. Engine source files are untouched.
Sources: t/run_par.py's lowering exception handling and entry-point lock;
https://docs.python.org/3/library/resource.html#resource.RLIMIT_AS
"""
import argparse
import os
from pathlib import Path
import resource
import sys


def bounded_call(function, limit_bytes, *args, **kwargs):
    """Restore both limits on success or failure, before the caller handles it."""
    if limit_bytes <= 0:
        raise ValueError('lowering memory limit must be positive')
    previous = resource.getrlimit(resource.RLIMIT_AS)
    finite = [v for v in previous if v != resource.RLIM_INFINITY]
    cap = min([limit_bytes, *finite])
    resource.setrlimit(resource.RLIMIT_AS, (cap, previous[1]))
    try:
        return function(*args, **kwargs)
    finally:
        resource.setrlimit(resource.RLIMIT_AS, previous)


def main():
    engine = Path(__file__).resolve().parents[1]
    if len(sys.argv) < 2 or Path(sys.argv[1]).resolve() != engine/'run_par.py':
        os.execv(sys.executable, [sys.executable, *sys.argv[1:]])
    limit_mb = int(os.environ.get('T_LOWER_MEMORY_MB', '4096'))
    if limit_mb <= 0:
        raise SystemExit('T_LOWER_MEMORY_MB must be positive')
    sys.path.insert(0, str(engine))
    import run_par
    from verifiers import acquire_run_lock
    original = run_par._lower_units

    def limited(*args, **kwargs):
        try:
            return bounded_call(original, limit_mb * 1024 * 1024, *args, **kwargs)
        except MemoryError:
            raise MemoryError(f'lowering address-space limit: {limit_mb} MiB') from None

    run_par._lower_units = limited
    args = sys.argv[2:]
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument('--out', type=Path, default=engine/'out')
    release = acquire_run_lock(pre.parse_known_args(args)[0].out)
    if not callable(release):
        print(f'REFUSED: {release}')
        return 2
    print(f'Lowering address-space limit: {limit_mb} MiB; restored before kernel dispatch', flush=True)
    try:
        return run_par.main(args)
    finally:
        release()


if __name__ == '__main__':
    raise SystemExit(main())
