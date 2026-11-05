#!/usr/bin/env python3
"""Exercise nftables only in a fresh network namespace with disposable peers."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from remote.firewall import render

LISTEN = ["10.203.0.1", "fd42:203::1"]
PEERS = ["10.203.0.2", "fd42:203::2"]
OTHER = ["10.203.0.3", "fd42:203::3"]


def run_inside(nft: Path, parent_fd: int) -> dict:
    if (not os.readlink(f"/proc/self/fd/{parent_fd}").startswith("net:[") or
            os.fstat(parent_fd).st_ino == os.stat("/proc/self/ns/net").st_ino):
        raise RuntimeError("firewall probe requires a fresh network namespace")
    os.close(parent_fd)
    checks, servers, threads = [], [], []
    stopping = threading.Event()
    peer = None
    persistent = None

    def command(argv, *, input=None, success=True):
        result = subprocess.run(argv, input=input, capture_output=True, timeout=20)
        if success and result.returncode:
            raise RuntimeError(result.stderr.decode(errors="replace"))
        return result

    def nft_command(*args, input=None, success=True):
        return command([str(nft), *args], input=input, success=success)

    def peer_command(argv, **kwargs):
        return command(["nsenter", "--net=/proc/" + str(peer.pid) + "/ns/net", *argv], **kwargs)

    def reply(connection):
        with connection:
            connection.settimeout(.2)
            while not stopping.is_set():
                try:
                    data = connection.recv(128)
                    if not data:
                        break
                    connection.sendall(data)
                except socket.timeout:
                    continue
                except OSError:
                    break

    def echo(server):
        while not stopping.is_set():
            try:
                connection, _ = server.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            thread = threading.Thread(target=reply, args=(connection,), daemon=True)
            thread.start(); threads.append(thread)

    client_code = """import socket,sys
s=socket.socket(socket.AF_INET6 if ':' in sys.argv[1] else socket.AF_INET)
s.settimeout(1); s.bind((sys.argv[2],0))
try:
 s.connect((sys.argv[1],int(sys.argv[3]))); s.sendall(b'tup-fixture'); data=s.recv(128)
 assert data==b'tup-fixture'
except (OSError,AssertionError): sys.exit(2)
finally: s.close()
"""

    def connection(address, source, port, allowed):
        result = peer_command([sys.executable, "-c", client_code, address, source, str(port)], success=False)
        expected = 0 if allowed else 2
        if result.returncode != expected:
            raise RuntimeError(f"unexpected connection verdict for {address}, {source}, {port}: {result.returncode}")

    try:
        peer = subprocess.Popen(["unshare", "--net", "sleep", "120"])
        own_namespace = os.readlink("/proc/self/ns/net")
        for _ in range(100):
            if peer.poll() is not None:
                raise RuntimeError("disposable peer namespace failed")
            if os.readlink(f"/proc/{peer.pid}/ns/net") != own_namespace:
                break
            time.sleep(.01)
        else:
            raise RuntimeError("peer stayed in the server namespace")
        command(["ip", "link", "set", "lo", "up"])
        command(["ip", "link", "add", "tup_srv", "type", "veth", "peer", "name", "tup_cli"])
        command(["ip", "link", "set", "tup_cli", "netns", str(peer.pid)])
        command(["ip", "link", "set", "tup_srv", "up"])
        peer_command(["ip", "link", "set", "lo", "up"])
        peer_command(["ip", "link", "set", "tup_cli", "up"])
        for address in LISTEN:
            command(["ip", "address", "add", address + ("/64" if ":" in address else "/24"), "dev", "tup_srv", "nodad"])
        for address in PEERS + OTHER:
            peer_command(["ip", "address", "add", address + ("/64" if ":" in address else "/24"), "dev", "tup_cli", "nodad"])
        for address in LISTEN:
            for port in (2222, 3333):
                server = socket.socket(socket.AF_INET6 if ":" in address else socket.AF_INET)
                if ":" in address:
                    server.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                server.bind((address, port)); server.listen(8); server.settimeout(.2)
                servers.append(server)
                thread = threading.Thread(target=echo, args=(server,), daemon=True)
                thread.start(); threads.append(thread)
        # Positive controls prove the denied targets really have listeners.
        for address, source in zip(LISTEN, OTHER):
            for port in (2222, 3333):
                connection(address, source, port, True)
        checks.append("unfiltered IPv4/IPv6 listeners reachable")
        rules = render(LISTEN, PEERS, 2222)["firewall.nft"]
        nft_command("add", "table", "inet", "tup_probe_other")
        nft_command("-c", "-f", "-", input=rules)
        if nft_command("list", "table", "inet", "tup_host", success=False).returncode == 0:
            raise RuntimeError("nft check unexpectedly installed rules")
        nft_command("-f", "-", input=rules)
        before = nft_command("-s", "list", "table", "inet", "tup_host").stdout
        nft_command("-f", "-", input=rules)
        if before != nft_command("-s", "list", "table", "inet", "tup_host").stdout:
            raise RuntimeError("repeated load changed the selected policy")
        nft_command("list", "table", "inet", "tup_probe_other")
        checks.append("check-only, repeated load and unrelated-table preservation")
        for address, allowed, denied in zip(LISTEN, PEERS, OTHER):
            connection(address, allowed, 2222, True)
            connection(address, denied, 2222, False)
            connection(address, allowed, 3333, False)
        checks.append("IPv4/IPv6 owner admitted; other peer and other listening port denied")
        bad = nft_command("-f", "-", input=rules + b"invalid token here\n", success=False)
        if bad.returncode == 0 or before != nft_command("-s", "list", "table", "inet", "tup_host").stdout:
            raise RuntimeError("malformed replacement damaged the active policy")
        connection(LISTEN[0], PEERS[0], 2222, True)
        checks.append("malformed batch refused with working policy preserved")
        persistent_code = """import socket,sys
s=socket.socket(); s.settimeout(1); s.bind((sys.argv[2],0)); s.connect((sys.argv[1],2222))
s.sendall(b'before'); assert s.recv(128)==b'before'; print('established',flush=True)
sys.stdin.readline()
try: s.sendall(b'after'); s.recv(128); sys.exit(3)
except socket.timeout: print('blocked',flush=True)
finally: s.close()
"""
        persistent = subprocess.Popen(["nsenter", "--net=/proc/" + str(peer.pid) + "/ns/net", sys.executable,
                                       "-c", persistent_code, LISTEN[0], PEERS[0]], stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if not select.select([persistent.stdout], [], [], 3)[0] or persistent.stdout.readline() != b"established\n":
            raise RuntimeError("persistent connection control failed")
        nft_command("-f", "-", input=render(LISTEN, OTHER, 2222)["firewall.nft"])
        stdout, stderr = persistent.communicate(b"probe\n", timeout=3)
        if persistent.returncode or stdout != b"blocked\n":
            raise RuntimeError("removed peer retained established SSH traffic: " + stderr.decode(errors="replace"))
        for address, removed, replacement in zip(LISTEN, PEERS, OTHER):
            connection(address, removed, 2222, False)
            connection(address, replacement, 2222, True)
        checks.append("peer removal blocks existing SSH flow and new flows; replacement peer admitted")
        return {"schema": "tup-firewall-probe-v1", "status": "passed", "release_eligible": False,
                "checks": checks, "nft_sha256": hashlib.sha256(nft.read_bytes()).hexdigest(),
                "policy_sha256": hashlib.sha256(rules).hexdigest(),
                "limitations": ["Disposable network namespaces on the build-host kernel",
                                "TCP fixture only; no SSH daemon, owner authentication or target boot",
                                "No physical DHCP, overlay transport or service lifecycle qualification"]}
    finally:
        stopping.set()
        for server in servers:
            server.close()
        for thread in threads:
            thread.join(timeout=2)
        for process in (persistent, peer):
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=2)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nft", required=True, type=Path)
    parser.add_argument("--parent-netns-fd", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if sys.platform != "linux" or os.geteuid() != 0:
        parser.error("run this disposable probe as root on Linux")
    if args.parent_netns_fd is None:
        descriptor = os.open("/proc/self/ns/net", os.O_RDONLY)
        try:
            return subprocess.run(["unshare", "--mount", "--net", "--pid", "--fork",
                                   "--kill-child=KILL", "--mount-proc", sys.executable, str(Path(__file__).resolve()),
                                   "--nft", str(args.nft.resolve()), "--parent-netns-fd", str(descriptor)],
                                  pass_fds=(descriptor,), timeout=90).returncode
        finally:
            os.close(descriptor)
    try:
        print(json.dumps(run_inside(args.nft, args.parent_netns_fd), indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print("REFUSED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
