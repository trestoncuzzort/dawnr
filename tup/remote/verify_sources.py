#!/usr/bin/env python3
"""Recheck the four remote-layer inputs with TUP's existing source verifier."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from boot.inputs import load_json
from sources import source_lock as verifier

HERE = Path(__file__).resolve().parent
NAMES = {"openssh-10.6p1.tar.gz", "libmnl-1.0.5.tar.bz2",
         "libnftnl-1.3.2.tar.xz", "nftables-1.1.7.tar.xz"}


def verify(cache: Path, gpg: Path, remote: Path = HERE) -> dict:
    ssh = load_json(remote / "source.json")
    firewall = load_json(remote / "firewall-sources.json")
    if (ssh.get("schema") != "tup-remote-source-v1" or
            firewall.get("schema") != "tup-remote-firewall-sources-v1"):
        raise verifier.Refusal("unknown remote source catalog")
    records = [(dict(ssh["archive"], sha256=ssh["verification"]["sha256"]),
                remote / "evidence/openssh-10.6p1")]
    records += [(record, remote / "evidence/netfilter") for record in firewall["sources"]]
    if len(records) != 4 or {row["name"] for row, _ in records} != NAMES:
        raise verifier.Refusal("remote source closure changed without review")
    results = []
    for record, evidence in records:
        if record.get("disposition") != "retain" or not verifier.HEX256.fullmatch(record.get("sha256", "")):
            raise verifier.Refusal("remote source lacks its reviewed digest")
        result = verifier.verify_record(record, cache, evidence, gpg)
        if result["status"] != "verified":
            raise verifier.Refusal("remote source authentication is incomplete")
        results.append(result)

    review = load_json(remote / "advisories.json")
    if (review.get("reviewed_at") != "2026-11-05" or
            review.get("request") != {"method": "POST", "fields": {
                "stype": "Book", "release": "13.1", "desc": "true", "submit": "Search"}} or
            review.get("snapshot", {}).get("url") != "https://www.linuxfromscratch.org/advisories/index.php"):
        raise verifier.Refusal("remote advisory review differs from the reviewed complete query")
    snapshot = verifier.material(remote / "evidence/netfilter", review["snapshot"])
    inventory = verifier.advisory_inventory(snapshot.read_bytes())
    selected = [row for row in inventory if row["package"].lower() in {"openssh", "libmnl", "libnftnl", "nftables"}]
    if (review.get("inventory_sha256") != hashlib.sha256(verifier.encoded(inventory)).hexdigest() or
            review.get("selected_advisories") != selected or
            review.get("dispositions") != [{"id": "sa-13.1-057", "package": "openssh",
                "disposition": "fixed-by-selection", "selected_sources": ["openssh-10.6p1.tar.gz"]}] or
            [row["id"] for row in selected] != ["sa-13.1-057"]):
        raise verifier.Refusal("remote advisory selection or disposition requires new review")
    for material in review["upstream_material"]:
        verifier.material(remote / "evidence/netfilter", material)
    return {"schema": "tup-remote-source-verification-v1", "status": "verified",
            "scope": "four-remote-layer-sources", "release_eligible": False,
            "verifier_sha256": verifier.digest(Path(verifier.__file__)),
            "catalogs": {name: verifier.digest(remote / name) for name in
                         ("source.json", "firewall-sources.json", "advisories.json")},
            "sources": results, "advisory_review_sha256": verifier.digest(remote / "advisories.json"),
            "limitations": ["Target core dependencies retain their separate source lock and release gates",
                            "Source verification does not establish target compilation or remote access"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--gpg", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = verify(args.cache, args.gpg)
        raw = (json.dumps(report, indent=2) + "\n").encode()
        if args.output:
            with args.output.open("xb") as stream:
                stream.write(raw)
        else:
            sys.stdout.buffer.write(raw)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("REFUSED: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
