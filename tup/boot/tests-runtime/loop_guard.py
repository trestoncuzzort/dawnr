#!/usr/bin/python3
"""Constrain upstream parted/partprobe calls to one verified disposable loop."""
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys


def workspace_root(value):
    """The caller names the disposable workspace; nothing is assumed about the host."""
    root = Path(value)
    if not root.is_absolute() or root.resolve() != root or root == Path(root.anchor):
        raise ValueError("workspace must be an absolute, resolved directory below the filesystem root")
    st = root.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
        raise ValueError("workspace must be a root-owned directory that others cannot write")
    return root


def check(loop, backing, identity, workspace, mounted=None):
    """mounted: the one (partition, mountpoint) pair this program mounted itself; any other mount refuses."""
    path = Path(backing)
    if not re.fullmatch(r"/dev/loop[0-9]+", loop):
        raise ValueError("only a whole loop device is permitted")
    if path.resolve() != path or workspace_root(workspace) not in path.parents:
        raise ValueError("backing path is outside the disposable VM workspace")
    st = path.lstat()
    if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1
            or [st.st_dev, st.st_ino, st.st_size] != identity):
        raise ValueError("backing-file identity changed")
    dev = Path(loop).lstat()
    if not stat.S_ISBLK(dev.st_mode) or os.major(dev.st_rdev) != 7:
        raise ValueError("target is not a kernel loop device")
    result = subprocess.run(["/usr/sbin/losetup", "--json", "--list", "--output",
                             "NAME,BACK-FILE,OFFSET,SIZELIMIT,RO", loop],
                            check=True, capture_output=True, text=True)
    rows = json.loads(result.stdout)["loopdevices"]
    if (len(rows) != 1 or rows[0]["name"] != loop or rows[0]["back-file"] != str(path)
            or rows[0]["offset"] != 0 or rows[0]["sizelimit"] != 0 or rows[0]["ro"]):
        raise ValueError("loop mapping differs from the approved backing file")
    # Ventoy uses a prefix match when unmounting; refuse all such mounts so its
    # helper cannot touch a similarly named unrelated loop device either.
    if foreign_mounts(loop, Path("/proc/mounts").read_text(), mounted):
        raise ValueError("loop-prefix mount exists; no automatic unmount is allowed")


def foreign_mounts(loop, mounts, mounted=None):
    """The /proc/mounts lines on the loop's name prefix, except the one pair the caller mounted itself."""
    ours = None if mounted is None else list(mounted)
    return [line for line in mounts.splitlines() if line.split()[0].startswith(loop) and line.split()[:2] != ours]


def main():
    loop, backing = os.environ["TUP_LOOP"], os.environ["TUP_LOOP_BACKING"]
    check(loop, backing, json.loads(os.environ["TUP_LOOP_IDENTITY"]), os.environ["TUP_LOOP_WORKSPACE"])
    name = Path(sys.argv[0]).name
    args = sys.argv[1:]
    if name == "partprobe":
        if args not in ([], [loop]):
            raise ValueError("partprobe may inspect only the verified loop")
        args = [loop]  # Upstream's argument-free call must never scan all disks.
    elif name == "parted":
        if args not in (["-v"], ["--version"]):
            if loop not in args or any(arg.startswith("/dev/") and arg != loop for arg in args):
                raise ValueError("parted target differs from the verified loop")
    else:
        raise ValueError("unknown guarded executable")
    prefix = Path(os.environ["TUP_PARTED_PREFIX"])
    env = dict(os.environ, LD_LIBRARY_PATH=str(prefix / "usr/lib/x86_64-linux-gnu"))
    os.execve(prefix / "usr/sbin" / name, [name, *args], env)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print("loop guard refused: " + str(error), file=sys.stderr)
        raise SystemExit(1)
