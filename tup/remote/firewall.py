#!/usr/bin/env python3
"""Render an atomic nftables owner-access policy; never change live networking."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from remote.policy import (EXACT, PRIVATE, PRIVATE_SOURCES, Refusal, canonical, listen_addresses,
                           write_private_directory)

# The image's default table before any owner is enrolled: the private-networks
# table without its SSH accept rules, so tcp/22 is dropped for every source.
UNENROLLED = "unenrolled"


def source_sets() -> list[tuple[str, str]]:
    """PRIVATE_SOURCES as one nft anonymous prefix set per address family."""
    return [(family, ", ".join(str(network) for network in PRIVATE_SOURCES if network.version == version))
            for version, family in ((4, "ip"), (6, "ip6"))]


def render(addresses: list[str], peers: list[str], port: int = 22, scope: str = EXACT) -> dict[str, bytes]:
    if scope not in (EXACT, PRIVATE, UNENROLLED):
        raise Refusal("scope must be exact, private-networks or unenrolled")
    if scope != EXACT and (addresses or peers):
        raise Refusal("only the exact scope takes listener and peer addresses")
    owner_rules, mdns_rules = [], []
    if scope == EXACT:
        addresses = listen_addresses(addresses)
        peers = listen_addresses(peers)  # Same explicit private-address restrictions.
    else:
        addresses, peers = [], []
    if type(port) is not int or not 1 <= port <= 65535:
        raise Refusal("SSH port must be between 1 and 65535")
    if scope == EXACT:
        for version, family in ((4, "ip"), (6, "ip6")):
            targets = [value for value in addresses if ipaddress.ip_address(value).version == version]
            sources = [value for value in peers if ipaddress.ip_address(value).version == version]
            if bool(targets) != bool(sources):
                raise Refusal("each listener address family needs explicit owner peer addresses")
            if targets:
                owner_rules.append(f"        {family} daddr {{ {', '.join(targets)} }} "
                                   f"{family} saddr {{ {', '.join(sources)} }} "
                                   "ct state { new, established } counter accept")
    else:
        # sshd binds the wildcards in this scope, so the source prefixes are the
        # whole admission decision. mDNS (RFC 6762, UDP 5353) lets the same
        # networks resolve this host's .local name. Answers to a multicast
        # query are not conntrack replies, hence an explicit rule.
        for family, networks in source_sets():
            if scope == PRIVATE:
                owner_rules.append(f"        {family} saddr {{ {networks} }} "
                                   "ct state { new, established } counter accept")
            mdns_rules.append(f"        {family} saddr {{ {networks} }} udp dport 5353 accept")
    rules = ("""# Complete TUP host table. Apply as one nft -f transaction.
# Keep unrelated tables intact. Failed batches preserve the prior table.
destroy table inet tup_host
table inet tup_host {
    chain owner_ssh {
""" + "".join(rule + "\n" for rule in owner_rules) + f"""        counter drop
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
""" + "".join(rule + "\n" for rule in mdns_rules) + """        counter drop
    }
    chain forward {
        type filter hook forward priority filter; policy drop;
    }
    chain output {
        type filter hook output priority filter; policy accept;
    }
}
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
    plan = {
        "schema": "tup-firewall-plan-v1", "status": "rendered-not-applied",
        "release_eligible": False, "listen_addresses": addresses, "owner_peer_addresses": peers,
        "port": port, "files": {name: hashlib.sha256(data).hexdigest() for name, data in outputs.items()},
        "pending": ["target kernel and nftables", "boot ordering and actual denied-traffic tests",
                    "network renewal and recovery", "private transport integration", "owner revocation and job policy"],
    }
    if scope != EXACT:  # The exact-scope plan keeps its original bytes.
        plan["scope"] = scope
        plan["source_networks"] = [str(network) for network in PRIVATE_SOURCES]
    outputs["FIREWALL-PLAN.json"] = canonical(plan)
    return outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    scopes = parser.add_mutually_exclusive_group(required=True)
    scopes.add_argument("--listen", action="append")
    scopes.add_argument("--private-networks", action="store_true",
                        help="admit SSH and mDNS from private source networks to wildcard listeners")
    scopes.add_argument("--unenrolled", action="store_true",
                        help="the private-networks table without SSH accept rules: the image default")
    parser.add_argument("--peer", action="append")
    parser.add_argument("--port", type=int, default=22)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if bool(args.listen) != bool(args.peer):
        parser.error("--peer is required with --listen and refused with --private-networks or --unenrolled")
    scope = PRIVATE if args.private_networks else UNENROLLED if args.unenrolled else EXACT
    try:
        write_private_directory(args.output, render(args.listen, args.peer, args.port, scope))
    except (OSError, Refusal) as exc:
        print("REFUSED: " + str(exc), file=sys.stderr)
        return 1
    print("Private firewall policy rendered. No network or service was changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
