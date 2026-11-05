#!/usr/bin/env python3
"""Render private owner SSH enrollment without installing or starting a service.

OpenSSH uses the first value obtained for most configuration keywords. Emit a
complete file, rather than append a hardening fragment to an unknown config.
Reference: https://man.openbsd.org/sshd_config
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys

USERNAME = re.compile(r"[a-z][a-z0-9_-]{0,30}")
PRIVATE_NETWORKS = tuple(map(ipaddress.ip_network, (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10",
    "127.0.0.0/8", "fc00::/7", "::1/128",
)))
RESERVED_USERS = frozenset(("root", "sshd", "nobody", "lfs", "bin", "daemon",
                            "systemd-network", "systemd-resolve"))


class Refusal(ValueError):
    pass


def canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode()


def owner_name(value: str) -> str:
    if not isinstance(value, str) or not USERNAME.fullmatch(value) or value in RESERVED_USERS:
        raise Refusal("owner must be a normal, non-system account name")
    return value


def listen_addresses(values: list[str]) -> list[str]:
    if not isinstance(values, list) or not 1 <= len(values) <= 8:
        raise Refusal("supply one to eight explicit private or loopback listen addresses")
    addresses = []
    for value in values:
        if not isinstance(value, str) or "%" in value:
            raise Refusal("listen address must be an IP literal without a scope suffix")
        try:
            parsed = ipaddress.ip_address(value)
        except ValueError as exc:
            raise Refusal("listen address must be an IP literal") from exc
        if not any(parsed.version == network.version and parsed in network for network in PRIVATE_NETWORKS):
            raise Refusal("public, wildcard, multicast and link-local listeners are not enrolled")
        normalized = str(parsed)
        if normalized in addresses:
            raise Refusal("duplicate listen address")
        addresses.append(normalized)
    return addresses


def public_keys(raw: bytes) -> tuple[bytes, list[str]]:
    """Accept plain Ed25519 keys; never interpret authorized_keys options."""
    if not isinstance(raw, bytes) or not raw or len(raw) > 16384:
        raise Refusal("public-key input is empty or too large")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Refusal("public-key file must be UTF-8") from exc
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not 1 <= len(lines) <= 8:
        raise Refusal("supply one to eight owner public keys")
    normalized, fingerprints = [], []
    for line in lines:
        if len(line) > 2048 or any(ord(ch) < 32 and ch != "\t" for ch in line):
            raise Refusal("malformed public-key line")
        parts = line.split()
        if len(parts) < 2 or parts[0] != "ssh-ed25519":
            raise Refusal("only plain ssh-ed25519 public keys are currently supported")
        try:
            blob = base64.b64decode(parts[1], validate=True)
        except (ValueError, binascii.Error) as exc:
            raise Refusal("invalid public-key base64") from exc
        prefix = struct.pack(">I", 11) + b"ssh-ed25519" + struct.pack(">I", 32)
        if len(blob) != len(prefix) + 32 or not blob.startswith(prefix) or blob[-32:] == bytes(32):
            raise Refusal("invalid Ed25519 SSH wire encoding")
        encoded = base64.b64encode(blob).decode("ascii")
        if encoded != parts[1]:
            raise Refusal("noncanonical public-key encoding")
        key = "ssh-ed25519 " + encoded
        if key in normalized:
            raise Refusal("duplicate owner public key")
        normalized.append(key)
        fingerprints.append("SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("="))
    return ("\n".join(normalized) + "\n").encode(), fingerprints


def render(owner: str, addresses: list[str], key_bytes: bytes, port: int = 22) -> dict[str, bytes]:
    owner = owner_name(owner)
    addresses = listen_addresses(addresses)
    if type(port) is not int or not 1 <= port <= 65535:
        raise Refusal("SSH port must be between 1 and 65535")
    keys, fingerprints = public_keys(key_bytes)
    listeners = "\n".join("ListenAddress " + address for address in addresses)
    config = f"""# Complete TUP owner policy. Private enrollment input; do not publish.
Port {port}
AddressFamily any
{listeners}
HostKey /etc/ssh/ssh_host_ed25519_key
PidFile /run/tup-sshd.pid
AllowUsers {owner}
AuthenticationMethods publickey
PubkeyAuthentication yes
AuthorizedKeysFile /etc/tup/authorized_keys/%u
AuthorizedKeysCommand none
TrustedUserCAKeys none
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitEmptyPasswords no
HostbasedAuthentication no
GSSAPIAuthentication no
UsePAM no
StrictModes yes
PermitUserEnvironment no
PermitUserRC no
IgnoreRhosts yes
LoginGraceTime 30
MaxAuthTries 3
MaxSessions 8
MaxStartups 10:30:30
PerSourceMaxStartups 3
LogLevel VERBOSE
SyslogFacility AUTHPRIV
UseDNS no
Compression no
AllowTcpForwarding local
AllowStreamLocalForwarding no
AllowAgentForwarding no
GatewayPorts no
PermitTunnel no
X11Forwarding no
PermitTTY yes
ClientAliveInterval 60
ClientAliveCountMax 3
Subsystem sftp internal-sftp
""".encode()
    service = b"""[Unit]
Description=TUP owner SSH access
Wants=network-online.target
After=network-online.target tup-firewall.service
Requires=tup-firewall.service
ConditionPathExists=/etc/tup/owner-enrolled.json
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
ExecStartPre=/usr/bin/ssh-keygen -A
ExecStartPre=/usr/sbin/sshd -t -f /etc/ssh/sshd_config
ExecStart=/usr/sbin/sshd -D -e -f /etc/ssh/sshd_config
ExecReload=/usr/sbin/sshd -t -f /etc/ssh/sshd_config
ExecReload=/usr/bin/kill -HUP $MAINPID
KillMode=control-group
TimeoutStopSec=30
Restart=on-failure
RestartSec=5
UMask=0077

[Install]
WantedBy=multi-user.target
"""
    outputs = {"sshd_config": config, "authorized_keys": keys, "tup-sshd.service": service}
    outputs["ENROLLMENT-PLAN.json"] = canonical({
        "schema": "tup-owner-enrollment-plan-v1",
        "status": "rendered-not-applied", "release_eligible": False,
        "owner": owner, "listen_addresses": addresses, "port": port,
        "owner_key_fingerprints": fingerprints,
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in outputs.items()},
        "pending": ["target account and privileges", "firewall activation and negative tests",
                    "first-boot host identity", "effective sshd policy and real login",
                    "persistent jobs", "private overlay and external-network Mac login"],
    })
    return outputs


def check_effective(raw: bytes, owner: str, addresses: list[str], port: int = 22) -> None:
    """Check actual sshd -T output, whose keyword capitalization can vary."""
    owner = owner_name(owner)
    addresses = listen_addresses(addresses)
    if type(port) is not int or not 1 <= port <= 65535:
        raise Refusal("invalid effective-policy port")
    if not isinstance(raw, bytes) or not raw or len(raw) > 1024 * 1024:
        raise Refusal("missing or oversized effective sshd configuration")
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise Refusal("effective sshd output is not UTF-8") from exc
    parsed = {}
    for line in lines:
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise Refusal("malformed effective sshd configuration")
        parsed.setdefault(parts[0].lower(), []).append(parts[1])
    required = {
        "port": str(port), "allowusers": owner, "addressfamily": "any",
        "hostkey": "/etc/ssh/ssh_host_ed25519_key", "pidfile": "/run/tup-sshd.pid",
        "authenticationmethods": "publickey", "pubkeyauthentication": "yes",
        "permitrootlogin": "no", "passwordauthentication": "no",
        "kbdinteractiveauthentication": "no", "permitemptypasswords": "no",
        "hostbasedauthentication": "no", "strictmodes": "yes",
        "authorizedkeysfile": "/etc/tup/authorized_keys/%u",
        "authorizedkeyscommand": "none", "trustedusercakeys": "none",
        "permituserenvironment": "no", "permituserrc": "no",
        "allowtcpforwarding": "local", "allowstreamlocalforwarding": "no",
        "allowagentforwarding": "no", "gatewayports": "no",
        "permittunnel": "no", "x11forwarding": "no",
        "ignorerhosts": "yes", "logingracetime": "30", "maxauthtries": "3",
        "maxsessions": "8", "maxstartups": "10:30:30", "persourcemaxstartups": "3",
        "loglevel": "VERBOSE", "syslogfacility": "AUTHPRIV", "usedns": "no",
        "compression": "no", "permittty": "yes", "clientaliveinterval": "60",
        "clientalivecountmax": "3", "subsystem": "sftp internal-sftp",
    }
    for name, value in required.items():
        if parsed.get(name) != [value]:
            raise Refusal("effective sshd policy mismatch: " + name)
    expected = {f"[{address}]:{port}" if ":" in address else f"{address}:{port}" for address in addresses}
    actual = parsed.get("listenaddress", [])
    if len(actual) != len(expected) or set(actual) != expected:
        raise Refusal("effective SSH listeners differ from private enrollment")
    for optional in ("gssapiauthentication", "usepam"):
        if optional in parsed and parsed[optional] != ["no"]:
            raise Refusal("unexpected authentication mechanism enabled: " + optional)


def write_private_directory(destination: Path, outputs: dict[str, bytes]) -> None:
    """Create a new private Linux staging directory; never apply to /etc."""
    if os.name != "posix":
        raise Refusal("write enrollment on Linux, where ownership and mode can be checked")
    destination = destination.absolute()
    if any(name not in {"sshd_config", "authorized_keys", "tup-sshd.service", "ENROLLMENT-PLAN.json",
                        "firewall.nft", "tup-firewall.service", "FIREWALL-PLAN.json"}
           for name in outputs):
        raise Refusal("unexpected enrollment output name")
    parent = destination.parent
    if parent.resolve() != parent or not parent.is_dir():
        raise Refusal("enrollment parent must exist without symlink traversal")
    info = parent.stat()
    if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o022:
        raise Refusal("enrollment parent must be owned by the caller and not writable by others")
    destination.mkdir(mode=0o700, exist_ok=False)
    # A failed write leaves an incomplete private directory for diagnosis. There
    # is no application/completion marker and an existing path is never reused.
    for name, content in outputs.items():
        fd = os.open(destination / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    for path in (destination, parent):
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--listen", action="append", required=True)
    parser.add_argument("--public-keys", type=Path, required=True)
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        with args.public_keys.open("rb") as stream:
            key_bytes = stream.read(16385)
        result = render(args.owner, args.listen, key_bytes, args.port)
        write_private_directory(args.output, result)
    except (OSError, Refusal) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    print("Private owner policy rendered. No account, firewall or service was changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
