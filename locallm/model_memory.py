"""Choose smaller CPU buffers when two local models leave little free RAM.

This selects a loading policy, not a guaranteed peak-memory bound. The 2 GiB
reserve covers working buffers and proof tools; an 8 GiB native trial required
llama.cpp's no-repack mode. Unknown platforms retain the server's defaults.
Sources: locallm/dawnr_tasks.py; llama.cpp common/arg.cpp at f1cee9941b0e843ea260bf8dd9a090fbd9711b6a;
https://docs.kernel.org/admin-guide/cgroup-v2.html#memory-interface-files
"""
from __future__ import annotations

from pathlib import Path
import re
import sys

RESERVE = 2 * 1024**3


def model_bytes(path: Path) -> int:
    match = re.fullmatch(r'(.*)-(\d{5})-of-(\d{5})\.gguf', path.name)
    if not match:
        return path.stat().st_size
    count = int(match[3])
    if not 1 <= int(match[2]) <= count <= 99999:
        raise ValueError('invalid GGUF shard count')
    return sum((path.parent / f'{match[1]}-{index:05d}-of-{count:05d}.gguf').stat().st_size
               for index in range(1, count + 1))


def available_bytes(proc: Path = Path('/proc'), cgroups: Path = Path('/sys/fs/cgroup')) -> int | None:
    bounds = []
    try:
        match = re.search(r'^MemAvailable:\s+(\d+)\s+kB$', (proc/'meminfo').read_text(), re.M)
        if match:
            bounds.append(int(match[1]) * 1024)
    except OSError:
        pass
    try:
        memberships = (proc/'self/cgroup').read_text().splitlines()
    except OSError:
        memberships = []
    for line in memberships:
        if not line.startswith('0::'):
            continue
        group = cgroups / line[3:].lstrip('/')
        if '..' in group.parts:
            continue
        while group == cgroups or cgroups in group.parents:
            try:
                maximum = (group/'memory.max').read_text().strip()
                if maximum != 'max':
                    current = int((group/'memory.current').read_text())
                    bounds.append(max(0, int(maximum) - current))
            except (OSError, ValueError):
                pass
            if group == cgroups:
                break
            group = group.parent
    return min(bounds) if bounds else None


def prefer_small_buffers(models: list[Path], available: int | None) -> bool:
    if available is None:
        return False
    try:
        return available < sum(model_bytes(path) for path in models) + RESERVE
    except (OSError, ValueError):
        return False  # the normal loader will report a missing or invalid model


if __name__ == '__main__':
    print('low' if prefer_small_buffers([Path(p) for p in sys.argv[1:]], available_bytes()) else 'normal')
