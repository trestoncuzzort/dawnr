#!/usr/bin/env python3
"""Owner-enrollment media and real SSH checks for the external TUP VM tests.

Test host only. Every check is recorded by name, as pass or fail, beside the
output it captured. A missing tool, a timeout and an unattempted check are all
failures; the only state that is neither is the root-only firewall listing on a
guest that has no sudo, and that one says so. Nothing here is hardware evidence.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
from tup.boot.inputs import Refusal, canonical, digest, file_hash
from tup.remote.policy import owner_name, public_keys

# Pinned by remote-tools.sha256, which uefi.sh checks before and after a run.
TOOLS = {"ssh": "/usr/bin/ssh", "ssh-keygen": "/usr/bin/ssh-keygen",
         "sftp": "/usr/bin/sftp", "mtools": "/usr/bin/mtools"}
HOST = "127.0.0.1"            # The only host forward QEMU is given.
GUEST_ADDRESS = "10.0.2.15"   # First lease of QEMU's built-in DHCP server.
LABEL = "TUP-ENROLL"
DEFAULT_OWNER = "owner"
# A stick prepared on a Mac: an MBR with one FAT32 (LBA) partition starting at the usual 1 MiB.
# 128 MiB at the 2-sector clusters mformat picks leaves about 130000 clusters, above FAT32's 65525 floor.
DISK_SECTORS, PART_START = 262144, 2048
FAT32_LBA = 0x0C
MARKER = "TUP-SSH-OK"
# The path is spliced into ssh -o values (split on blanks, expanded on %) and
# into QEMU option strings (split on commas), so it is restricted, not quoted.
SAFE_PATH = re.compile(r"/[A-Za-z0-9._/+-]+")
# sshd's default PATH is the BLFS /usr/bin; ip and nft live in /usr/sbin.
GUEST_PATH = "PATH=/usr/sbin:/usr/bin; export PATH; "
PAUSE = 5
# Recorded by verify(), in this order, then folded with the two groups conclude() adds.
SSH_CHECKS = (
    "owner_key_login", "known_hosts_created", "guest_uname", "guest_id",
    "guest_os_release", "guest_ip_address", "guest_kernel_cmdline", "guest_system_running", "sudo_probe",
    "nft_ruleset_as_root", "second_connection_same_known_hosts", "changed_host_key_refused",
    "sftp_round_trip_sha256", "root_login_refused", "password_authentication_refused",
    "unenrolled_key_refused", "owner_login_after_refusals", "poweroff_request")
CONCLUDED_CHECKS = ("guest_powered_off", "host_inputs_unchanged")
REQUIRED = ("serial_boot_verdict",) + SSH_CHECKS + CONCLUDED_CHECKS
MAY_NOT_APPLY = frozenset(("nft_ruleset_as_root",))
# Ventoy's fallback boot path starts the ISO's own GRUB with this; a run that shows it never passes.
VENTOY_FALLBACK = "rdinit=/vtoy/vtoy"


def execute(argv, timeout, env=None):
    """Run one host tool without a terminal; a timeout is a result, not an exception."""
    started = time.monotonic()
    try:
        done = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout,
                              env=env, start_new_session=True)
        code, out, err, late = done.returncode, done.stdout, done.stderr, False
    except subprocess.TimeoutExpired as error:
        code, out, err, late = None, error.stdout or b"", error.stderr or b"", True
    return {"returncode": code, "stdout": out, "stderr": err, "timed_out": late,
            "seconds": round(time.monotonic() - started, 3)}


def checked_port(port):
    if type(port) is not int or not 1024 <= port <= 65535:
        raise Refusal("the loopback SSH forward needs an unprivileged port, 1024-65535")
    return port


def host_environment():
    return {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "LANG": "C", "MTOOLSRC": os.devnull}


def fresh_remote(output):
    """Create OUTPUT/remote inside the run directory uefi.sh has just made."""
    output = Path(output)
    if not hasattr(os, "geteuid"):
        raise Refusal("enrollment media are prepared on the Linux test host")
    if not SAFE_PATH.fullmatch(str(output)) or len(str(output)) > 90:
        raise Refusal("output path must be absolute, at most 90 characters of A-Z a-z 0-9 . _ / + -")
    st = output.lstat()
    if not stat.S_ISDIR(st.st_mode) or output.resolve() != output:
        raise Refusal("output must be a real directory, never a link, file or device")
    if st.st_uid != os.geteuid() or st.st_mode & 0o077:
        raise Refusal("output must be a private directory of the calling user")
    remote = output / "remote"
    if remote.is_symlink() or remote.exists():
        raise Refusal("this output already holds enrollment material; use a new output directory")
    remote.mkdir(mode=0o700)
    return remote


def check_enrollment_image(image):
    """One MBR partition holding a FAT32 filesystem labelled TUP-ENROLL, read from the raw bytes."""
    with open(image, "rb") as stream:
        mbr = stream.read(512)
        if len(mbr) != 512 or mbr[510:512] != b"\x55\xaa":
            raise Refusal("enrollment image has no MBR")
        entries = [mbr[446 + 16 * n:462 + 16 * n] for n in range(4)]
        kind, start, count = entries[0][4], int.from_bytes(entries[0][8:12], "little"), int.from_bytes(entries[0][12:16], "little")
        if kind != FAT32_LBA or any(entry != bytes(16) for entry in entries[1:]) or start != PART_START \
                or start + count > DISK_SECTORS:
            raise Refusal("enrollment image does not hold exactly one FAT32 (LBA) MBR partition")
        stream.seek(start * 512)
        sector = stream.read(512)
    if (len(sector) != 512 or sector[510:512] != b"\x55\xaa" or sector[82:90] != b"FAT32   "
            or sector[71:82].decode("ascii", "replace").rstrip() != LABEL
            or int.from_bytes(sector[11:13], "little") != 512 or int.from_bytes(sector[36:40], "little") == 0):
        raise Refusal("the partition is not a FAT32 filesystem labelled " + LABEL)


def generate_key(tools, run, path):
    """One unencrypted, comment-free Ed25519 key pair at PATH and PATH.pub; the private half must be private."""
    made = run([tools["ssh-keygen"], "-q", "-t", "ed25519", "-N", "", "-C", "", "-f", str(path)], 60, host_environment())
    if made["returncode"] != 0:
        raise Refusal("ssh-keygen failed: " + made["stderr"].decode("utf-8", "replace").strip())
    private = Path(path).lstat()
    if not stat.S_ISREG(private.st_mode) or private.st_mode & 0o077:
        raise Refusal("generated private key is not a private regular file")
    return public_keys(Path(str(path) + ".pub").read_bytes())


def adopt_ventoy_keys(source, remote, media_sha256, owner, explicit):
    """Take the owner key pair a Ventoy image was built with; the stick itself carries the enrollment."""
    source = Path(source)
    if not hasattr(os, "geteuid"):
        raise Refusal("enrollment keys are read on the Linux test host")
    info = source.lstat()
    if not stat.S_ISDIR(info.st_mode) or source.resolve() != source or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise Refusal("enrollment key directory must be a private, real directory of the calling user")
    record = json.loads((source / "ENROLL.json").read_bytes())
    if record.get("schema") != "tup.runtime-ventoy-enroll.v1" or record.get("image_sha256") != media_sha256:
        raise Refusal("these enrollment keys were not made for this Ventoy image")
    if record.get("owner") != (owner if explicit else None):
        raise Refusal("the image enrolls owner %r; run with the same --owner (none means the guest default)" % record.get("owner"))
    for name in ("owner_key", "owner_key.pub"):
        entry = (source / name).lstat()
        if not stat.S_ISREG(entry.st_mode) or entry.st_mode & 0o077 and name == "owner_key":
            raise Refusal("enrollment key file is not a private regular file: " + name)
    keys, fingerprints = public_keys((source / "owner_key.pub").read_bytes())
    if digest(keys) != record.get("authorized_keys_sha256") or fingerprints[0] != record.get("owner_key_fingerprint"):
        raise Refusal("the owner public key differs from the one written onto the image")
    shutil.copyfile(source / "owner_key", remote / "owner_key")
    (remote / "owner_key").chmod(0o600)
    shutil.copyfile(source / "owner_key.pub", remote / "owner_key.pub")
    return keys, fingerprints


def build_enrollment_volume(remote, files, tools, run):
    """An MBR disk with one FAT32 partition labelled TUP-ENROLL, as a stick prepared on a Mac would be."""
    image = remote / "enroll.img"
    with image.open("xb") as stream:
        stream.truncate(DISK_SECTORS * 512)
    # mtools reaches a partition through a drive definition; this one is private to the run.
    rc = remote / "mtoolsrc"
    rc.write_bytes(f'drive p: file="{image}" partition=1\n'.encode())
    env = dict(host_environment(), MTOOLSRC=str(rc))
    staging = remote / "enroll"
    staging.mkdir(mode=0o700)
    steps = [("mpartition", "-I", "p:"),
             ("mpartition", "-c", "-d", "-T", hex(FAT32_LBA), "-b", str(PART_START), "-l", str(DISK_SECTORS - PART_START), "p:"),
             ("mformat", "-F", "-v", LABEL, "p:"), ("mmd", "p:tup-enroll")]
    for name, data in files.items():
        (staging / name).write_bytes(data)
        steps.append(("mcopy", str(staging / name), "p:tup-enroll/" + name))
    for step in steps:
        done = run([tools["mtools"], "-c", *step], 60, env)
        if done["returncode"] != 0:
            raise Refusal(step[0] + " failed: " + done["stderr"].decode("utf-8", "replace").strip())
    for name, data in files.items():  # Exit status alone does not show what the guest will read.
        back = run([tools["mtools"], "-c", "mtype", "p:tup-enroll/" + name], 60, env)
        if back["returncode"] != 0 or back["stdout"] != data:
            raise Refusal("enrollment image read-back differs: " + name)
    check_enrollment_image(image)
    image.chmod(0o400)
    return image


def prepare(output, owner, port, tools=TOOLS, run=execute, keys_from=None, media_sha256=None):
    """Make the ephemeral keys for one run and, for the direct ISO, its read-only TUP-ENROLL volume.

    With keys_from (a Ventoy image's enroll-keys directory) the enrollment is already on the stick:
    the owner key pair is taken from there and only the never-enrolled key is made.
    """
    explicit = owner is not None
    owner = owner_name(owner if explicit else DEFAULT_OWNER)
    port = checked_port(port)
    for name, path in sorted(tools.items()):
        if not os.path.isabs(path) or not os.path.isfile(path) or not os.access(path, os.X_OK):
            raise Refusal("required host tool is missing: " + name)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((HOST, port))  # Bound and released, never listening.
        except OSError as error:
            raise Refusal(f"loopback port {port} is not free") from error
    remote = fresh_remote(output)
    keys = {}
    if keys_from is None:
        keys["owner_key"] = generate_key(tools, run, remote / "owner_key")
    else:
        keys["owner_key"] = adopt_ventoy_keys(keys_from, remote, media_sha256, owner, explicit)
    keys["unenrolled_key"] = generate_key(tools, run, remote / "unenrolled_key")
    if keys["owner_key"][1] == keys["unenrolled_key"][1]:
        raise Refusal("the two test keys are identical")
    summary = {"schema": "tup.runtime-enrollment.v1", "owner": owner, "owner_file_written": explicit, "port": port,
               "owner_key_fingerprint": keys["owner_key"][1][0],
               "unenrolled_key_fingerprint": keys["unenrolled_key"][1][0],
               "tools": dict(sorted(tools.items()))}
    if keys_from is None:
        files = {"authorized_keys": keys["owner_key"][0]}
        if explicit:  # Without it the guest must fall back to its documented default account.
            files["owner"] = (owner + "\n").encode()
        image = build_enrollment_volume(remote, files, tools, run)
        summary.update({
            "enrollment": "separate volume: MBR, one FAT32 partition", "label": LABEL,
            "files": sorted("tup-enroll/" + name for name in files), "image_sha256": file_hash(image),
            "image_bytes": image.stat().st_size, "keys": "ephemeral Ed25519, generated for this run only"})
    else:
        summary.update({
            "enrollment": "on the Ventoy data partition, written when the image was built",
            "keys": "owner key pair generated with the image; unenrolled key generated for this run only"})
    (remote / "PREPARED.json").write_bytes(canonical(summary))
    return summary


def client_options(port, known_hosts, strict, password=False):
    """One complete client policy: no user or system configuration, agent or multiplexing."""
    options = {
        "StrictHostKeyChecking": strict, "UserKnownHostsFile": str(known_hosts),
        "GlobalKnownHostsFile": "/dev/null", "UpdateHostKeys": "no", "CheckHostIP": "no",
        "IdentitiesOnly": "yes", "IdentityAgent": "none", "ForwardAgent": "no", "ForwardX11": "no",
        "ClearAllForwardings": "yes", "ControlMaster": "no", "ControlPath": "none",
        "ConnectTimeout": "20", "ConnectionAttempts": "1", "Port": str(port), "LogLevel": "INFO",
        "BatchMode": "yes", "PreferredAuthentications": "publickey", "PubkeyAuthentication": "yes",
        "PasswordAuthentication": "no", "KbdInteractiveAuthentication": "no"}
    if password:  # Offer only passwords, answered by a recorded askpass, to see whether the server asks.
        options.update({"BatchMode": "no", "PreferredAuthentications": "password,keyboard-interactive",
                        "PubkeyAuthentication": "no", "PasswordAuthentication": "yes",
                        "KbdInteractiveAuthentication": "yes", "NumberOfPasswordPrompts": "1"})
    return [part for key, value in options.items() for part in ("-o", key + "=" + value)]


class Session:
    def __init__(self, remote, port, owner, tools=TOOLS, run=execute, clock=time.monotonic, sleep=time.sleep):
        self.remote, self.port, self.owner = Path(remote), checked_port(port), owner_name(owner)
        self.tools, self.run, self.clock, self.sleep = tools, run, clock, sleep
        self.known_hosts = self.remote / "known_hosts"
        self.outputs = self.remote / "checks"
        self.outputs.mkdir(mode=0o700)
        self.checks, self.sequence = [], 0

    def call(self, label, argv, timeout, env=None):
        """Run a command and keep both streams, whatever the verdict turns out to be."""
        self.sequence += 1
        result = self.run(argv, timeout, env or host_environment())
        result["argv"] = argv
        for stream in ("stdout", "stderr"):
            name = f"{self.sequence:02d}-{label}.{stream}"
            (self.outputs / name).write_bytes(result[stream])
            result[stream + "_file"] = "remote/checks/" + name
        return result

    def ssh(self, label, command, *, user=None, key="owner_key", strict="yes", known_hosts=None,
            password=False, timeout=120, env=None):
        argv = [self.tools["ssh"], "-F", "none", "-T", "-i", str(self.remote / key),
                *client_options(self.port, known_hosts or self.known_hosts, strict, password),
                "-l", user or self.owner, HOST, command]
        return self.call(label, argv, timeout, env)

    def add(self, name, passed, detail, result=None, status=None):
        item = {"name": name, "status": status or ("pass" if passed else "fail"), "detail": detail}
        if result is not None:
            item.update({key: result[key] for key in
                         ("argv", "returncode", "seconds", "timed_out", "stdout_file", "stderr_file")})
        self.checks.append(item)
        return item["status"] == "pass"

    def login(self, label, strict, budget):
        """Bounded retries; every attempt is counted and the last one's output is kept."""
        deadline, attempts, started = self.clock() + budget, 0, self.clock()
        while True:
            attempts += 1
            result = self.ssh(label, "echo " + MARKER, strict=strict, timeout=60)
            ok = result["returncode"] == 0 and result["stdout"].strip() == MARKER.encode()
            if ok or self.clock() + PAUSE >= deadline:
                break
            self.sequence -= 1  # Overwrite the superseded attempt; the count stays in the detail.
            self.sleep(PAUSE)
        return ok, f"{attempts} attempt(s) in {self.clock() - started:.0f} s of a {budget} s bound", result


def text(result, stream="stdout"):
    return result[stream].decode("utf-8", "replace")


def denied(result):
    """A refusal is only shown by the server's own authentication denial."""
    return (result["returncode"] == 255 and not result["timed_out"] and not result["stdout"]
            and "Permission denied" in text(result, "stderr"))


def host_key(session):
    lines = [line.split() for line in session.known_hosts.read_text().splitlines() if line.strip()]
    if len(lines) != 1 or len(lines[0]) != 3 or lines[0][0] != f"[{HOST}]:{session.port}":
        raise Refusal("known_hosts does not hold exactly one key for the forwarded port")
    blob = base64.b64decode(lines[0][2], validate=True)
    return {"type": lines[0][1],
            "fingerprint": "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")}


def guest_checks(session, wait):
    """The fixed command set; each command is its own connection and its own verdict."""
    owner = session.owner
    fixed = (
        ("guest_uname", "uname -a", lambda out: out.startswith("Linux ") and " x86_64" in out,
         "a Linux x86_64 kernel line"),
        ("guest_id", "id", lambda out: re.match(r"uid=[1-9][0-9]*\(" + re.escape(owner) + r"\) ", out) is not None,
         f"a non-root uid named {owner}"),
        ("guest_os_release", "cat /etc/os-release",
         lambda out: out.splitlines().count("ID=tup") == 1
         and sum(line.startswith("VERSION_ID=") for line in out.splitlines()) == 1,
         "exactly one ID=tup and one VERSION_ID line"),
        ("guest_ip_address", "ip -brief address", lambda out: GUEST_ADDRESS + "/" in out,
         "the DHCP lease " + GUEST_ADDRESS),
        # The line is kept whatever the verdict: it shows which boot path actually ran.
        ("guest_kernel_cmdline", "cat /proc/cmdline",
         lambda out: bool(out.strip()) and VENTOY_FALLBACK not in out.split(),
         "a kernel command line without Ventoy's fallback " + VENTOY_FALLBACK))
    for name, command, accept, wanted in fixed:
        result = session.ssh(name, GUEST_PATH + command)
        ok = result["returncode"] == 0 and accept(text(result))
        detail = f"`{command}` " + ("showed " if ok else "did not show ") + wanted
        if name == "guest_kernel_cmdline":
            detail += ": " + text(result).strip()[:600]
        session.add(name, ok, detail, result)
    # --wait lets a boot still in progress under TCG finish; the bound is the SSH wait.
    result = session.ssh("guest_system_running", GUEST_PATH + "systemctl is-system-running --wait", timeout=wait)
    state = text(result).strip() or ("timed out" if result["timed_out"] else "no output")
    if not session.add("guest_system_running", result["returncode"] == 0 and state == "running",
                       "systemctl is-system-running: " + state, result):
        detail = session.ssh("guest_system_detail", GUEST_PATH + "systemctl list-units --failed --no-legend "
                             "--no-pager; systemctl list-jobs --no-pager")
        session.checks[-1]["detail"] += "; unit detail in " + detail["stdout_file"]
    probe = session.ssh("sudo_probe", GUEST_PATH + "command -v sudo")
    sudo = probe["returncode"] == 0 and bool(probe["stdout"].strip())
    session.add("sudo_probe", probe["returncode"] in (0, 1) and not probe["timed_out"],
                "sudo is " + ("present: " + text(probe).strip() if sudo else "absent"), probe)
    if sudo:
        result = session.ssh("nft_ruleset_as_root", GUEST_PATH + "sudo -n /usr/sbin/nft list ruleset")
        session.add("nft_ruleset_as_root", result["returncode"] == 0 and "table " in text(result),
                    "root listing of the nftables ruleset through sudo -n", result)
    else:
        session.add("nft_ruleset_as_root", False, "guest has no sudo, so the owner cannot read the ruleset as "
                    "root over SSH; the firewall is not inspected by this run", status="not-applicable")
    return sudo


def host_key_checks(session):
    before = file_hash(session.known_hosts)
    result = session.ssh("second_connection", "echo " + MARKER)
    ok = (result["returncode"] == 0 and result["stdout"].strip() == MARKER.encode()
          and file_hash(session.known_hosts) == before)
    session.add("second_connection_same_known_hosts", ok,
                "StrictHostKeyChecking=yes against the unchanged known_hosts of the first connection", result)
    # The same host name with a different key must stop the client before authentication.
    other = (session.remote / "unenrolled_key.pub").read_text().split()
    changed = session.remote / "known_hosts.changed"
    changed.write_bytes(f"[{HOST}]:{session.port} {other[0]} {other[1]}\n".encode())
    pinned = file_hash(changed)
    result = session.ssh("changed_host_key", "echo " + MARKER, known_hosts=changed)
    ok = (result["returncode"] == 255 and not result["stdout"] and file_hash(changed) == pinned
          and "Host key verification failed" in text(result, "stderr"))
    session.add("changed_host_key_refused", ok, "a known_hosts naming a different key ends the connection", result)


def transfer_check(session):
    folder = session.remote / "transfer"
    folder.mkdir(mode=0o700)
    sent, returned, name = folder / "sent.bin", folder / "returned.bin", "tup-runtime-transfer.bin"
    sent.write_bytes(os.urandom(1024 * 1024))
    batch = folder / "batch"
    batch.write_bytes(f'put "{sent}" "{name}"\nget "{name}" "{returned}"\nrm "{name}"\n'.encode())
    argv = [session.tools["sftp"], "-F", "none", "-i", str(session.remote / "owner_key"), "-b", str(batch),
            *client_options(session.port, session.known_hosts, "yes"), f"{session.owner}@{HOST}"]
    result = session.call("sftp_round_trip", argv, 300)
    ok = result["returncode"] == 0 and returned.is_file() and file_hash(returned) == file_hash(sent)
    session.add("sftp_round_trip_sha256", ok, "1 MiB put, get and remove over SFTP; SHA256 "
                + (file_hash(sent) if ok else "not preserved"), result)


def refusal_checks(session):
    result = session.ssh("root_login", "echo " + MARKER, user="root")
    session.add("root_login_refused", denied(result), "root with the enrolled key: "
                + ("authentication denied" if denied(result) else "no authentication denial was observed"), result)
    # ssh never prompts in batch mode, so a forced askpass stands in for a person
    # and leaves a marker if the server ever asks for a password.
    asked = session.remote / "askpass.asked"
    askpass = session.remote / "askpass.sh"
    askpass.write_bytes(f"#!/bin/sh\n: > '{asked}'\nprintf '%s\\n' not-the-password\n".encode())
    askpass.chmod(0o700)
    env = dict(host_environment(), SSH_ASKPASS=str(askpass), SSH_ASKPASS_REQUIRE="force")
    result = session.ssh("password_authentication", "echo " + MARKER, password=True, env=env)
    offered = re.search(r"Permission denied \(([A-Za-z0-9,@._-]+)\)", text(result, "stderr"))
    methods = offered.group(1).split(",") if offered else []
    ok = (denied(result) and bool(methods) and not asked.exists()
          and not {"password", "keyboard-interactive"} & set(methods))
    session.add("password_authentication_refused", ok, "server offered " + (",".join(methods) or "nothing parseable")
                + "; password prompt " + ("seen" if asked.exists() else "never requested"), result)
    result = session.ssh("unenrolled_key", "echo " + MARKER, key="unenrolled_key")
    session.add("unenrolled_key_refused", denied(result), "owner with a key that was never enrolled: "
                + ("authentication denied" if denied(result) else "no authentication denial was observed"), result)
    # OpenSSH penalises a source for failed authentication; all test traffic shares
    # one source address, so say how long the owner had to wait afterwards.
    ok, detail, result = session.login("login_after_refusals", "yes", 120)
    session.add("owner_login_after_refusals", ok, detail, result)


def qmp_powerdown(path, timeout=15):
    """The single use of the QMP socket: press the virtual power button."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as link:
        link.settimeout(timeout)
        link.connect(str(path))
        stream = link.makefile("rwb")
        if "QMP" not in json.loads(stream.readline()):
            raise Refusal("the socket did not greet as QMP")
        for command in ("qmp_capabilities", "system_powerdown"):
            stream.write(json.dumps({"execute": command}).encode() + b"\r\n")
            stream.flush()
            while True:
                line = stream.readline()
                if not line:
                    raise Refusal("QMP closed before answering " + command)
                reply = json.loads(line)
                if "event" in reply:
                    continue
                if reply.get("return") != {}:
                    raise Refusal(f"QMP refused {command}: {reply}")
                break


def request_poweroff(session, sudo, qmp, powerdown):
    if sudo:
        result = session.ssh("poweroff_request", GUEST_PATH + "sudo -n systemctl poweroff")
        # The session may be cut before its exit status arrives; a sudo complaint is the refusal.
        ok = (result["returncode"] in (0, 255) and not result["timed_out"]
              and "sudo:" not in text(result, "stderr"))
        return session.add("poweroff_request", ok, "owner ran sudo -n systemctl poweroff", result), "owner-systemctl-poweroff"
    try:
        powerdown(qmp)
        ok, detail = True, "QMP system_powerdown accepted"
    except (OSError, ValueError) as error:
        ok, detail = False, "QMP system_powerdown failed: " + str(error)
    return session.add("poweroff_request", ok, detail), "qmp-system_powerdown"


def verify(output, port, owner, wait, tools=TOOLS, run=execute, clock=time.monotonic, sleep=time.sleep,
           powerdown=qmp_powerdown):
    """Run every check, then ask the guest to power off. uefi.sh watches QEMU exit."""
    output = Path(output)
    remote = output / "remote"
    if type(wait) is not int or not 30 <= wait <= 1800:
        raise Refusal("the SSH wait must be 30-1800 seconds")
    session = Session(remote, port, owner, tools, run, clock, sleep)
    sudo, key = False, None
    ok, detail, result = session.login("owner_key_login", "accept-new", wait)
    session.add("owner_key_login", ok, f"{session.owner} with the enrolled key, first connection: " + detail, result)
    if ok:
        try:
            key = host_key(session)
            session.add("known_hosts_created", True, f"first connection recorded one {key['type']} key {key['fingerprint']}")
        except (OSError, ValueError) as error:
            session.add("known_hosts_created", False, str(error))
        sudo = guest_checks(session, wait)
        host_key_checks(session)
        transfer_check(session)
        refusal_checks(session)
    else:
        for name in SSH_CHECKS[1:-1]:
            session.add(name, False, "not attempted: the owner login never succeeded")
    requested, method = request_poweroff(session, sudo, output / "qmp.sock", powerdown)
    report = {"schema": "tup.runtime-remote-checks.v1", "owner": session.owner, "port": session.port,
              "host": HOST, "sudo_present": sudo if ok else None, "host_key": key,
              "poweroff_method": method, "poweroff_requested": requested, "checks": session.checks}
    (remote / "CHECKS.json").write_bytes(canonical(report))
    return report


def conclude(output, kind, media_sha256, memory_mib, cpus, port, boot_verdict, verify_ran, powered_off,
             power_down_logged, qemu_exit, poweroff_seconds, poweroff_budget, inputs_unchanged):
    """Fold the serial verdict, the SSH checks, the observed power-off and the input rechecks into RESULT.json.

    inputs_unchanged is 1 only when uefi.sh found the media and every pinned tool unchanged after
    the guest was gone; a result must never say VERIFIED for a run the wrapper rejects.
    """
    output = Path(output)
    remote = output / "remote"
    if (output / "RESULT.json").exists():
        raise Refusal("this output already has a result; a result is never replaced")
    report = json.loads((remote / "CHECKS.json").read_bytes()) if (remote / "CHECKS.json").is_file() else {}
    checks = [{"name": "serial_boot_verdict", "status": "pass" if boot_verdict == "BOOTED" else "fail",
               "detail": "boot_verdict.sh: " + boot_verdict}] + report.get("checks", [])
    # QEMU runs with -no-reboot, so its exit alone would also describe a guest reset.
    off = bool(powered_off) and qemu_exit == 0 and bool(power_down_logged)
    checks.append({"name": "guest_powered_off", "status": "pass" if off else "fail", "detail":
                   (f"QEMU exited with status {qemu_exit} {poweroff_seconds} s after the request"
                    if powered_off else f"QEMU was still running after {poweroff_seconds} s of a "
                    f"{poweroff_budget} s budget, or power-off was never requested")
                   + "; the kernel's 'reboot: Power down' line is "
                   + ("on" if power_down_logged else "absent from") + " the serial log"
                   + f"; method {report.get('poweroff_method', 'none')}"})
    checks.append({"name": "host_inputs_unchanged", "status": "pass" if inputs_unchanged == 1 else "fail",
                   "detail": "after the guest had stopped, the media digest and every pinned host tool "
                   + ("matched" if inputs_unchanged == 1 else "did not all match (see host-recheck.txt)")
                   + " what the run started with"})
    names = [item["name"] for item in checks]
    for name in REQUIRED:  # A check that is absent was not passed.
        if name not in names:
            checks.append({"name": name, "status": "fail", "detail": "not recorded: the SSH verification "
                           + ("stopped early" if verify_ran else "did not run")})
    failed = sorted({item["name"] for item in checks if item["status"] != "pass"
                     and not (item["status"] == "not-applicable" and item["name"] in MAY_NOT_APPLY)}
                    | {name for name in names if names.count(name) != 1 or name not in REQUIRED})
    removed = []
    for name in ("owner_key", "unenrolled_key"):  # Ephemeral; the public halves and fingerprints stay.
        if (remote / name).is_file():
            (remote / name).unlink()
            removed.append(name)
    verdict = ("TUP REMOTE ACCESS VERIFIED (external VM, TCG; not hardware)" if not failed else
               "TUP REMOTE ACCESS FAILED (external VM, TCG): " + ", ".join(failed))
    result = {
        "schema": "tup.runtime-remote-result.v1", "kind": kind, "verdict": verdict, "passed": not failed,
        "failed_checks": failed, "boot_verdict": boot_verdict, "checks": checks,
        "media_sha256": media_sha256, "memory_mib": memory_mib, "vcpus": cpus,
        "sudo_present": report.get("sudo_present"), "host_key": report.get("host_key"),
        "poweroff_method": report.get("poweroff_method"), "private_keys_removed": removed,
        "scope": {
            "environment": "external-vm", "emulator": "qemu", "accelerator": "tcg", "kvm": False,
            "firmware": "OVMF", "hardware_tested": False, "physical_boot_tested": False,
            "release_eligible": False, "remote_access_tested": bool(verify_ran),
            "network": f"QEMU user networking, restrict=on; the only host forward is {HOST}:{port} to "
                       f"{GUEST_ADDRESS}:22, so every peer the guest sees is 10.0.2.2",
            "enrollment": ("a read-only TUP-ENROLL volume: MBR, one FAT32 partition" if kind == "tup-iso-ssh" else
                           "tup-enroll/authorized_keys on the Ventoy data partition of the one boot stick"),
            "not_established": ["boot or networking on the owner's hardware", "the real USB stick",
                                "access from another machine on a LAN", "firewall behaviour for non-private "
                                "sources", "persistence across reboot", "performance (TCG is emulation)",
                                *(["enrollment media as a whole-device FAT filesystem without a partition table",
                                   "enrollment media partitioned by anything but this tool's MBR/FAT32 layout"]
                                  if kind == "tup-iso-ssh" else
                                  ["a data partition written by the owner's own operating system (this one was "
                                   "written by the builder's Linux exfat driver)",
                                   "the Windows installer Ventoy2Disk.exe (the Linux script's defaults were used)"])]}}
    pending = output / "RESULT.json.pending"
    with open(pending, "xb") as stream:
        stream.write(canonical(result))
        stream.flush()
        os.fsync(stream.fileno())
    pending.rename(output / "RESULT.json")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "verify", "conclude"):
        command = commands.add_parser(name)
        command.add_argument("--output", required=True, type=Path)
        command.add_argument("--port", required=True, type=int)
        if name == "prepare":
            command.add_argument("--owner")
            command.add_argument("--keys-from", type=Path, help="enroll-keys directory of a Ventoy image")
            command.add_argument("--media-sha256", help="digest of that image")
        if name == "verify":
            command.add_argument("--owner", required=True)
            command.add_argument("--wait", required=True, type=int)
        if name == "conclude":
            command.add_argument("--kind", required=True, choices=("tup-iso-ssh", "ventoy-tup-ssh"))
            command.add_argument("--media-sha256", required=True)
            command.add_argument("--boot-verdict", required=True)
            for number in ("memory-mib", "cpus", "verify-ran", "powered-off", "power-down-logged",
                           "qemu-exit", "poweroff-seconds", "poweroff-budget", "inputs-unchanged"):
                command.add_argument("--" + number, required=True, type=int)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            if (args.keys_from is None) != (args.media_sha256 is None):
                raise Refusal("--keys-from and --media-sha256 go together")
            print(json.dumps(prepare(args.output, args.owner, args.port, keys_from=args.keys_from,
                                     media_sha256=args.media_sha256), indent=2, sort_keys=True))
            return 0
        if args.command == "verify":
            report = verify(args.output, args.port, args.owner, args.wait)
            bad = [item["name"] for item in report["checks"] if item["status"] == "fail"]
            print(json.dumps({"failed": bad, "poweroff_requested": report["poweroff_requested"]}, sort_keys=True))
            # 0: everything passed; 3: something failed but power-off is under way; 1: nothing to wait for.
            return 1 if not report["poweroff_requested"] else 3 if bad else 0
        result = conclude(args.output, args.kind, args.media_sha256, args.memory_mib, args.cpus, args.port,
                          args.boot_verdict, args.verify_ran, args.powered_off, args.power_down_logged,
                          args.qemu_exit, args.poweroff_seconds, args.poweroff_budget, args.inputs_unchanged)
        print(result["verdict"])
        return 0 if result["passed"] else 1
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print("remote check refused: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
