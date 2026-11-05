#!/usr/bin/env python3
"""Render an atomic nftables owner-access policy; never change live networking."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from remote.policy import Refusal, canonical, listen_addresses, write_private_directory


def render(addresses: list[str], peers: list[str], port: int = 22) -> dict[str, bytes]:
    addresses = listen_addresses(addresses)
    peers = listen_addresses(peers)  # Same explicit private-address restrictions.
    if type(port) is not int or not 1 <= port <= 65535:
        raise Refusal("SSH port must be between 1 and 65535")
    owner_rules = []
    for version, family in ((4, "ip"), (6, "ip6")):
        targets = [value for value in addresses if ipaddress.ip_address(value).version == version]
        sources = [value for value in peers if ipaddress.ip_address(value).version == version]
        if bool(targets) != bool(sources):
            raise Refusal("each listener address family needs explicit owner peer addresses")
        if targets:
            owner_rules.append(f"        {family} daddr {{ {', '.join(targets)} }} "
                               f"{family} saddr {{ {', '.join(sources)} }} "
                               "ct state { new, established } counter accept")
    rules = ("""# Complete TUP host table. Apply as one nft -f transaction.
# Keep unrelated tables intact. Failed batches preserve the prior table.
destroy table inet tup_host
table inet tup_host {
    chain owner_ssh {
""" + "\n".join(owner_rules) + f"""
        counter drop
    }}
    chain input {{
        type filter hook input priority filter; policy drop;
        iifname "lo" accept
        ct state invalid drop
        tcp dport {port} jump owner_ssh
        ct state established,related accept
        ip protocol icmp icmp type {{ destination-unreachable, time-exceeded, parameter-problem }} accept
        ip protocol icmp icmp type echo-request limit rate 5/second burst 10 packets accept
        meta l4proto ipv6-icmp icmpv6 type {{ destination-unreachable, packet-too-big, time-exceeded, parameter-problem }} accept
        ip6 hoplimit 255 icmpv6 type {{ nd-neighbor-solicit, nd-neighbor-advert }} accept
        ip6 saddr fe80::/10 ip6 hoplimit 255 icmpv6 type nd-router-advert accept
        ip6 saddr fe80::/10 ip6 hoplimit 1 icmpv6 type {{ mld-listener-query, mld-listener-report, mld-listener-done, mld2-listener-report }} accept
        meta l4proto ipv6-icmp icmpv6 type echo-request limit rate 5/second burst 10 packets accept
        udp sport 67 udp dport 68 accept
        ip6 saddr fe80::/10 udp sport 547 udp dport 546 accept
        counter drop
    }}
    chain forward {{
        type filter hook forward priority filter; policy drop;
    }}
    chain output {{
        type filter hook output priority filter; policy accept;
    }}
}}
""").encode()
    service = b"""[Unit]
Description=TUP host firewall
DefaultDependencies=no
Wants=network-pre.target
Before=network-pre.target tup-sshd.service shutdown.target
After=local-fs.target
Conflicts=shutdown.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/nft -f /etc/tup/firewall.nft
ExecReload=/usr/sbin/nft -f /etc/tup/firewall.nft
# Deliberately retain kernel rules when the unit stops. Requires= stops SSH.

[Install]
WantedBy=multi-user.target
"""
    outputs = {"firewall.nft": rules, "tup-firewall.service": service}
    outputs["FIREWALL-PLAN.json"] = canonical({
        "schema": "tup-firewall-plan-v1", "status": "rendered-not-applied",
        "release_eligible": False, "listen_addresses": addresses, "owner_peer_addresses": peers,
        "port": port, "files": {name: hashlib.sha256(data).hexdigest() for name, data in outputs.items()},
        "pending": ["target kernel and nftables", "boot ordering and actual denied-traffic tests",
                    "network renewal and recovery", "private transport integration", "owner revocation and job policy"],
    })
    return outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen", action="append", required=True)
    parser.add_argument("--peer", action="append", required=True)
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        write_private_directory(args.output, render(args.listen, args.peer, args.port))
    except (OSError, Refusal) as exc:
        print("REFUSED: " + str(exc), file=sys.stderr)
        return 1
    print("Private firewall policy rendered. No network or service was changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
