#!/usr/bin/env python3
"""Install the reviewed manual-only archive under a real /usr/share/man tree."""
from pathlib import Path, PurePosixPath
import os
import shutil
import stat
import sys
import tarfile


def inventory(archive):
    members = archive.getmembers()
    if len(members) != 1256:
        raise ValueError("unreviewed manual archive member count")
    seen = set()
    for member in members:
        path = PurePosixPath(member.name)
        parts = path.parts
        if (member.name in seen or not parts or path.is_absolute()
                or ".." in parts or "\\" in member.name
                or parts[0] != "systemd-man-pages-261.2"
                or not (member.isdir() or member.isfile())):
            raise ValueError("unsafe or unexpected manual archive member")
        seen.add(member.name)
        if len(parts) == 1:
            if not member.isdir():
                raise ValueError("manual archive root must be a directory")
        elif parts[1] not in {"man1", "man3", "man5", "man7", "man8"}:
            raise ValueError("archive contains a non-manual destination")
        elif member.isdir():
            if len(parts) != 2:
                raise ValueError("unexpected nested manual directory")
        elif (len(parts) != 3 or member.mode & 0o111
              or not parts[2].endswith("." + parts[1][-1]) or member.size < 1):
            raise ValueError("archive contains non-manual or executable data")
    return members


def install(archive_path, destination=Path("/usr/share/man")):
    if not destination.is_absolute():
        raise ValueError("manual destination must be absolute")
    for path in (*reversed(destination.parents), destination):
        mode = path.lstat().st_mode
        if not stat.S_ISDIR(mode):
            raise ValueError("manual destination is redirected")
    with tarfile.open(archive_path, "r:xz") as archive:
        members = inventory(archive)
        # Validate the whole destination inventory before writing any member.
        for member in members:
            target = destination.joinpath(*PurePosixPath(member.name).parts[1:])
            for parent in (target, *target.parents):
                if parent == destination:
                    break
                if parent.is_symlink():
                    raise ValueError("existing manual path is redirected")
                if parent.exists() and parent != target and not parent.is_dir():
                    raise ValueError("existing manual parent is not a directory")
            if target.exists() and (member.isdir() != target.is_dir()):
                raise ValueError("manual path type conflicts with existing content")
            if target.exists() and not member.isdir() and not stat.S_ISREG(target.lstat().st_mode):
                raise ValueError("existing manual destination is not a regular file")
        for member in members:
            target = destination.joinpath(*PurePosixPath(member.name).parts[1:])
            if member.isdir():
                target.mkdir(mode=0o755, exist_ok=True)
            else:
                descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644)
                with os.fdopen(descriptor, "wb") as stream:
                    shutil.copyfileobj(archive.extractfile(member), stream)
                    os.fchmod(stream.fileno(), 0o644)


if __name__ == "__main__":
    install(Path(sys.argv[1]))
