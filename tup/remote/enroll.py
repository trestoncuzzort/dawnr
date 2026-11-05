#!/usr/bin/env python3
"""Apply owner enrollment found on the boot media, exactly once.

tup-enroll.service runs this as root before the firewall and sshd units. It
looks for a directory that holds `authorized_keys`, validates every input with
the renderers in policy.py and firewall.py, checks the staged files with the
real sshd and nft, and only then creates the account and installs the files.
The marker /etc/tup/owner-enrolled.json is written last; tup-sshd.service does
not start without it. No input means no account, no key and no listener.

The owner account has no password and, where sudo is installed, passwordless
sudo: whoever holds an enrolled private key is root on this machine.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from remote import firewall, policy
from remote.policy import Refusal

# Search order. The first is a filesystem labelled TUP-ENROLL that the unit
# mounts read-only; the others are the USB filesystem holding the ISO file
# (Ventoy boot) and the live medium itself, as mounted by the initramfs.
INPUT_DIRECTORIES = ("run/tup-enroll/tup-enroll", "run/initramfs/isoscan/tup-enroll",
                     "run/initramfs/live/tup-enroll")
MARKER = "etc/tup/owner-enrolled.json"
HOST_KEY = "etc/ssh/ssh_host_ed25519_key.pub"
SSHD_CONFIG = "etc/ssh/sshd_config"
FIREWALL = "etc/tup/firewall.nft"
SUDOERS = "etc/sudoers.d/10-tup-owner"
RESULT = "run/tup-enroll.result"
ISSUE = "run/issue.d/50-tup.issue"
TOOLS = {"useradd": "usr/sbin/useradd", "ssh-keygen": "usr/bin/ssh-keygen",
         "sshd": "usr/sbin/sshd", "nft": "usr/sbin/nft"}
SUDO = {"sudo": "usr/bin/sudo", "visudo": "usr/sbin/visudo"}
HOW = ("copy your Ed25519 public key to the boot USB stick as tup-enroll/authorized_keys "
       "(or to a filesystem labelled TUP-ENROLL) and reboot")
FINGERPRINT = re.compile(r"\d+ (SHA256:[A-Za-z0-9+/]{43}) .*\(([A-Z0-9-]+)\)")


def inside(root: Path, relative: str) -> Path:
    """Join below root. No component, the last included, may be a symlink."""
    path = Path(root)
    for part in Path(relative).parts:
        if part == ".." or Path(part).is_absolute():
            raise Refusal("unsafe enrollment path")
        path = path / part
        if path.is_symlink():
            raise Refusal(f"symbolic link in enrollment path: /{relative}")
    return path


def read_regular(path: Path, limit: int, what: str) -> bytes | None:
    """Bounded read of a regular file; None when absent; never follows a link."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode):
        raise Refusal(f"{what} must be a regular file")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
    with os.fdopen(fd, "rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise Refusal(f"{what} is too large")
    return data


def text_lines(raw: bytes | None, what: str) -> list[str] | None:
    if raw is None:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Refusal(f"{what} must be UTF-8") from exc
    return [line.strip() for line in text.splitlines() if line.strip()]


def locate(root: Path) -> tuple[str | None, list[str]]:
    """First input directory holding authorized_keys, plus those found without one."""
    without = []
    for relative in INPUT_DIRECTORIES:
        directory = inside(root, relative)
        if not directory.is_dir():
            continue
        if os.path.lexists(directory / "authorized_keys"):
            return relative, without
        without.append("/" + relative)
    return None, without


def plan(directory: Path) -> dict:
    """Validate the whole input and render every file. Changes nothing."""
    raw = {name: read_regular(directory / name, limit, "enrollment input " + name)
           for name, limit in (("authorized_keys", 16384), ("owner", 256), ("listen", 4096), ("peer", 4096))}
    if raw["authorized_keys"] is None:
        raise Refusal("enrollment input authorized_keys is missing")
    _, fingerprints = policy.public_keys(raw["authorized_keys"])
    owner = text_lines(raw["owner"], "enrollment input owner")
    if owner is not None and len(owner) != 1:
        raise Refusal("enrollment input owner must hold exactly one account name")
    owner = policy.owner_name("owner" if owner is None else owner[0])
    listen = text_lines(raw["listen"], "enrollment input listen")
    peer = text_lines(raw["peer"], "enrollment input peer")
    if (listen is None) != (peer is None):
        raise Refusal("the exact scope needs both a listen and a peer file; supply neither for private networks")
    scope = policy.PRIVATE if listen is None else policy.EXACT
    access = policy.render(owner, listen, raw["authorized_keys"], 22, scope)
    wall = firewall.render(listen, peer, 22, scope)
    files = {f"etc/tup/authorized_keys/{owner}": (access["authorized_keys"], 0o644),
             SSHD_CONFIG: (access["sshd_config"], 0o600), FIREWALL: (wall["firewall.nft"], 0o600)}
    if scope == policy.EXACT:
        # Later boots of a persistent root wait for the network before binding.
        # The boot that applies this has already loaded the image's unit.
        files["etc/systemd/system/tup-sshd.service"] = (access["tup-sshd.service"], 0o644)
    return {"owner": owner, "scope": scope, "listen": listen or [], "peer": peer or [],
            "fingerprints": fingerprints, "files": files,
            "inputs": {name: hashlib.sha256(data).hexdigest() for name, data in raw.items() if data is not None}}


def entry(root: Path, relative: str, name: str) -> list[str] | None:
    """The colon-separated passwd, shadow, group or gshadow entry for name."""
    raw = read_regular(inside(root, relative), 4 * 1024 * 1024, "/" + relative)
    for line in (raw or b"").decode("utf-8", errors="surrogateescape").splitlines():
        fields = line.split(":")
        if fields[0] == name:
            return fields
    return None


def trusted_directory(path: Path) -> None:
    """sshd StrictModes walks to /: every directory root-owned, not writable by others."""
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022:
        raise Refusal(f"{path} must be a directory owned by root and not writable by group or others")


def stage(path: Path, data: bytes, mode: int) -> Path:
    """Durable sibling of path, to be checked first and renamed into place later."""
    temporary = path.with_name(f".{path.name}.tup-new")
    try:
        os.unlink(temporary)  # Left by an interrupted attempt; unlink never follows a link.
    except FileNotFoundError:
        pass
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
                 | getattr(os, "O_BINARY", 0), mode)
    with os.fdopen(fd, "wb") as stream:
        os.fchmod(stream.fileno(), mode)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return temporary


def sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def run_command(argv: list[str]) -> tuple[int, bytes]:
    done = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=120, check=False, env={"PATH": "/usr/bin:/usr/sbin", "LC_ALL": "C"})
    if done.returncode:
        sys.stderr.buffer.write(done.stderr)
        sys.stderr.flush()
    return done.returncode, done.stdout


def apply(root: Path = Path("/"), run=None) -> dict:
    """Enroll once. A Refusal means no marker; before useradd it means no change."""
    if os.name != "posix":
        raise Refusal("enrollment applies on Linux, where ownership and modes can be checked")
    root = Path(root)
    if run is None:
        if root != Path("/"):
            raise Refusal("a root other than / needs an injected command runner")
        run = run_command
    if root.is_symlink():
        raise Refusal("the root must not be a symbolic link")
    marker = inside(root, MARKER)
    if read_regular(marker, 1024 * 1024, "the enrollment marker") is not None:
        return {"state": "already-enrolled"}
    location, without = locate(root)
    if location is None:
        return {"state": "no-input", "without_keys": without}
    todo = plan(inside(root, location))
    owner, scope, files = todo["owner"], todo["scope"], todo["files"]

    # Preflight. Every refusal down to the try block leaves the system untouched.
    for relative in ("etc/passwd", "etc/shadow", "etc/group", "etc/gshadow"):
        if entry(root, relative, owner) is not None:
            raise Refusal(f"an account or group named {owner} already exists; enrollment never adopts one")
    if os.path.lexists(inside(root, "home") / owner):
        raise Refusal(f"/home/{owner} already exists")
    tools = {name: str(root / relative) for name, relative in {**TOOLS, **SUDO}.items()}
    for name, relative in TOOLS.items():
        if not os.path.isfile(tools[name]):
            raise Refusal(f"/{relative} is missing; the remote layer is not installed")
    sudo = all(os.path.isfile(tools[name]) for name in SUDO)
    if sudo:
        files[SUDOERS] = (f"{owner} ALL=(ALL:ALL) NOPASSWD: ALL\n".encode(), 0o440)
    for relative in files:
        if os.path.lexists(final := inside(root, relative)) and not final.is_file():
            raise Refusal(f"/{relative} exists and is not a regular file")
    missing = []
    for relative in sorted({parent.as_posix() for name in files for parent in Path(name).parents}, key=len):
        directory = inside(root, relative)
        if os.path.lexists(directory):
            trusted_directory(directory)
        else:
            missing.append(directory)

    staged, made = {}, []
    try:
        for directory in missing:
            os.mkdir(directory, 0o700)
            made.append(directory)
            os.chmod(directory, 0o750 if directory.name == "sudoers.d" else 0o755)
        for relative, (data, mode) in files.items():
            staged[relative] = stage(inside(root, relative), data, mode)
        if run([tools["ssh-keygen"], "-A"])[0]:
            raise Refusal("ssh-keygen could not create host keys")
        host = read_regular(inside(root, HOST_KEY), 4096, "/" + HOST_KEY)
        if host is None:
            raise Refusal("ssh-keygen left no Ed25519 host key")
        host_fingerprint = policy.public_keys(host)[1][0]
        code, effective = run([tools["sshd"], "-T", "-f", str(staged[SSHD_CONFIG])])
        if code:
            raise Refusal("sshd rejected the staged configuration")
        policy.check_effective(effective, owner, todo["listen"] or None, 22, scope)
        if sudo and run([tools["visudo"], "-c", "-f", str(staged[SUDOERS])])[0]:
            raise Refusal("visudo rejected the staged sudoers file")
        # Check mode sends the batch to the kernel without committing it.
        if run([tools["nft"], "-c", "-f", str(staged[FIREWALL])])[0]:
            raise Refusal("nft rejected the staged firewall")

        # Everything that can be checked has been. From here the system changes.
        if run([tools["useradd"], "--create-home", "--home-dir", f"/home/{owner}", "--shell", "/bin/bash",
                "--user-group", "--password", "*", "--comment", "TUP owner", owner])[0]:
            raise Refusal("useradd failed")
        account = entry(root, "etc/passwd", owner) or []
        shadow = entry(root, "etc/shadow", owner) or []
        # "*" matches no password. Unlike "!", portable OpenSSH does not treat it
        # as a locked account (platform_locked_account: LOCKED_PASSWD_PREFIX is
        # "!" on Linux), so public-key login works without PAM.
        if (len(account) != 7 or account[5:] != [f"/home/{owner}", "/bin/bash"] or len(shadow) < 2
                or shadow[1] != "*" or not account[2].isdigit() or not account[3].isdigit()
                or int(account[2]) < 1000 or not inside(root, f"home/{owner}").is_dir()):
            raise Refusal("useradd did not create the expected unprivileged account")
        for relative, temporary in staged.items():
            os.replace(temporary, inside(root, relative))
        staged.clear()
        made.clear()
        for directory in sorted({inside(root, name).parent for name in files}):
            sync_directory(directory)
        if run([tools["nft"], "-f", str(inside(root, FIREWALL))])[0]:
            raise Refusal("nft could not load the installed firewall")
        record = {
            "schema": "tup-owner-enrolled-v1", "owner": owner, "scope": scope, "port": 22,
            "listen_addresses": todo["listen"] or list(policy.WILDCARD_LISTENERS),
            "owner_peer_addresses": todo["peer"], "input": "/" + location, "input_files": todo["inputs"],
            "owner_key_fingerprints": todo["fingerprints"],
            "host_key_fingerprints": {Path(HOST_KEY).name: host_fingerprint},
            "account": {"uid": int(account[2]), "gid": int(account[3]), "home": account[5], "shell": account[6]},
            "files": {"/" + relative: hashlib.sha256(data).hexdigest() for relative, (data, _) in files.items()},
            "sudo": "passwordless-all" if sudo else "absent",
        }
        staged[MARKER] = stage(marker, policy.canonical(record), 0o644)
        os.replace(staged.pop(MARKER), marker)
        sync_directory(marker.parent)
    finally:
        for temporary in staged.values():
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
        for directory in reversed(made):
            try:
                os.rmdir(directory)
            except OSError:
                pass  # ssh-keygen filled a new /etc/ssh; host keys are not enrollment.
    return {"state": "enrolled", "record": record}


def printable(text: str) -> str:
    """agetty expands backslash escapes in issue files; keep plain ASCII only."""
    return "".join(ch if " " <= ch <= "~" and ch != "\\" else "?" for ch in text)


def console_status(root: Path = Path("/"), run=run_command) -> bytes:
    """Write the enrollment state where agetty reads it after /etc/issue."""
    root = Path(root)
    raw = read_regular(inside(root, MARKER), 1024 * 1024, "the enrollment marker")
    if raw is None:
        lines = ["TUP owner access: NOT ENROLLED. SSH is off; this image has no account or key.",
                 "  To enroll, copy your Ed25519 public key to the boot USB stick as",
                 "  tup-enroll/authorized_keys (or to a filesystem labelled TUP-ENROLL), then reboot."]
        result = read_regular(inside(root, RESULT), 1024, "/" + RESULT)
        if result:
            lines.append("  Last attempt: " + printable(result.decode("utf-8", errors="replace").strip()))
    else:
        try:
            record = json.loads(raw)
            owner, scope = policy.owner_name(record["owner"]), record["scope"]
            if scope == policy.EXACT:
                target = str(ipaddress.ip_address(record["listen_addresses"][0]))
            elif scope == policy.PRIVATE:
                target = "\\n.local"  # agetty prints the host name for \n; resolved answers for it over mDNS.
            else:
                raise Refusal("unknown scope")
        except (ValueError, KeyError, IndexError, TypeError):
            lines = ["TUP owner access: the enrollment marker is unreadable."]
        else:
            lines = [f"TUP owner access: ENROLLED. Account {owner}, scope {scope}.",
                     f"  Connect from the home network:  ssh {owner}@{target}"]
    key = inside(root, HOST_KEY)
    if os.path.lexists(key):
        code, output = run([str(root / TOOLS["ssh-keygen"]), "-l", "-f", str(key)])
        match = None if code else FINGERPRINT.fullmatch(output.decode("utf-8", errors="replace").strip())
        lines += ([f"  {match.group(2)} host key fingerprint:  {match.group(1)}",
                   "  Compare it with the fingerprint ssh shows on the first connection."] if match
                  else ["  The SSH host key fingerprint could not be read."])
    text = ("\n".join(lines) + "\n\n").encode("ascii")
    issue = inside(root, ISSUE)
    os.makedirs(issue.parent, mode=0o755, exist_ok=True)
    os.replace(stage(issue, text, 0o644), issue)
    return text


def main(argv=None, root: Path = Path("/"), run=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--console-status", action="store_true",
                        help="only write /run/issue.d/50-tup.issue for the local console")
    args = parser.parse_args(argv)
    root = Path(root)
    note = None  # What tup-console-status.service repeats above the login prompt.
    try:
        if os.name != "posix" or (root == Path("/") and os.geteuid() != 0):
            raise Refusal("run as root on the TUP target")
        if args.console_status:
            console_status(root, run or run_command)
            return 0
        outcome = apply(root, run)
    except (OSError, Refusal, subprocess.SubprocessError) as exc:
        if args.console_status:
            print(f"TUP console status: REFUSED: {exc}", file=sys.stderr)
            return 1
        status, message = 1, f"REFUSED: {exc}. No owner was enrolled; SSH stays off."
        note = f"REFUSED: {exc}"
    else:
        status = 0
        if outcome["state"] == "enrolled":
            enrolled = outcome["record"]
            message = (f"enrolled {enrolled['owner']} from {enrolled['input']} (scope {enrolled['scope']}); "
                       f"host key {enrolled['host_key_fingerprints'][Path(HOST_KEY).name]}")
        elif outcome["state"] == "already-enrolled":
            message = "already enrolled; nothing changed"
        else:
            message = "no enrollment input; SSH stays off. To enroll, " + HOW + "."
            if outcome["without_keys"]:
                note = "found " + ", ".join(outcome["without_keys"]) + " without a file named authorized_keys"
                message += " Note: " + note + "."
    print("TUP enrollment: " + message, file=sys.stderr if status else sys.stdout, flush=True)
    if note is not None:
        try:
            result = inside(root, RESULT)
            os.replace(stage(result, (note + "\n").encode("utf-8", errors="replace"), 0o644), result)
        except (OSError, Refusal) as exc:
            print(f"TUP enrollment: could not record the result for the console: {exc}", file=sys.stderr)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
