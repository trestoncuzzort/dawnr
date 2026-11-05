#!/usr/bin/env python3
"""Recheck the remote chapter's five inputs: verify_sources.py's four, then sudo."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from boot.inputs import load_json
from remote import verify_sources as four
from sources import source_lock as verifier

HERE = Path(__file__).resolve().parent
SUDO = "sudo-1.9.17p2.tar.gz"
SUDO_URL = "https://www.sudo.ws/dist/" + SUDO
# Current signing primary as published on the retained upstream download page.
SUDO_PRIMARY = "59D1E9CCBA2B376704FDD35BA9F4C021CEA470FB"
SUDO_ADVISORIES = {"upstream-sudo-CVE-2025-32463": "chroot_bug", "upstream-sudo-CVE-2025-32462": "host_any"}
SUDO_FIXED_IN = "1.9.17p1"  # reviewed: the selected 1.9.17p2 is the next patch release


def page_text(path: Path) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]*>", "", path.read_text(encoding="utf-8"))).split())


def verify_sudo(cache: Path, gpg: Path, remote: Path = HERE) -> dict:
    catalog = load_json(remote / "sudo-source.json")
    record = catalog.get("source", {})
    auth = record.get("authentication", {})
    approval = auth.get("approval", {}).get("material", {})
    if (catalog.get("schema") != "tup-remote-sudo-source-v1" or record.get("name") != SUDO or
            record.get("url") != SUDO_URL or record.get("disposition") != "retain" or
            not verifier.HEX256.fullmatch(record.get("sha256", "")) or auth.get("method") != "openpgp" or
            auth.get("primary_fingerprint") != SUDO_PRIMARY or auth.get("signing_fingerprint") != SUDO_PRIMARY or
            auth.get("payload") != "archive" or approval.get("url") != "https://www.sudo.ws/getting/download/"):
        raise verifier.Refusal("sudo source record changed without review")
    evidence = remote / "evidence/sudo"
    # The retained official page must itself publish the approved fingerprint
    # and this exact archive's digest. Neither replaces the signature check.
    page = verifier.material(evidence, approval)
    grouped = " ".join(SUDO_PRIMARY[index:index + 4] for index in range(0, 40, 4))
    if "current pgp signing key with the fingerprint " + grouped + " and the old" not in page_text(page):
        raise verifier.Refusal("sudo download page does not publish the approved signing fingerprint")
    if verifier.published_digest(page.read_bytes(), {"format": "html-table", "artifact_url": SUDO_URL},
                                 SUDO) != record["sha256"]:
        raise verifier.Refusal("sudo pin differs from the digest published on the download page")
    result = verifier.verify_record(record, cache, evidence, gpg)
    if result["status"] != "verified" or result["authentication"].get("trust_class") != "publisher-openpgp":
        raise verifier.Refusal("sudo source authentication is incomplete")

    review = load_json(remote / "sudo-advisories.json")
    if (review.get("schema") != "tup-remote-sudo-advisory-review-v1" or review.get("reviewed_at") != "2026-11-05" or
            review.get("request") != {"method": "POST", "fields": {
                "stype": "Book", "release": "13.1", "desc": "true", "submit": "Search"}} or
            review.get("snapshot", {}).get("url") != "https://www.linuxfromscratch.org/advisories/index.php" or
            review.get("upstream_index", {}).get("url") != "https://www.sudo.ws/security/advisories/"):
        raise verifier.Refusal("sudo advisory review differs from the reviewed complete query")
    # The LFS snapshot is the retained one advisories.json already binds.
    snapshot = verifier.material(remote / "evidence/netfilter", review["snapshot"])
    inventory = verifier.advisory_inventory(snapshot.read_bytes())
    selected = [row for row in inventory if "sudo" in row["package"].lower()]
    dispositions = review.get("dispositions", [])
    if (review.get("inventory_sha256") != hashlib.sha256(verifier.encoded(inventory)).hexdigest() or
            selected or review.get("selected_advisories") != [] or
            [row.get("id") for row in dispositions] != list(SUDO_ADVISORIES)):
        raise verifier.Refusal("sudo advisory selection or disposition requires new review")
    index = verifier.material(evidence, review["upstream_index"]).read_text(encoding="utf-8")
    slugs = list(dict.fromkeys(re.findall(r'href="/security/advisories/([a-z0-9_]+)/"', index)))
    if slugs[:2] != list(SUDO_ADVISORIES.values()):
        raise verifier.Refusal("upstream sudo advisory index has an unreviewed newest record")
    for row in dispositions:
        slug = SUDO_ADVISORIES[row["id"]]
        proof = row.get("evidence", {})
        if (row.get("package") != "sudo" or row.get("disposition") != "fixed-by-selection" or
                row.get("selected_sources") != [SUDO] or row.get("fixed_in") != SUDO_FIXED_IN or
                proof.get("url") != "https://www.sudo.ws/security/advisories/" + slug + "/"):
            raise verifier.Refusal("sudo advisory disposition requires new review")
        text = page_text(verifier.material(evidence, proof))
        if (row["id"].removeprefix("upstream-sudo-") not in text or
                "The bug is fixed in sudo " + SUDO_FIXED_IN + "." not in text):
            raise verifier.Refusal("retained sudo advisory does not state the reviewed fix release")
    for material in review["upstream_material"]:
        verifier.material(evidence, material)
    return {"schema": "tup-remote-sudo-source-verification-v1", "status": "verified",
            "scope": "sudo-owner-administration-source", "release_eligible": False,
            "verifier_sha256": verifier.digest(Path(verifier.__file__)),
            "catalogs": {name: verifier.digest(remote / name) for name in
                         ("sudo-source.json", "sudo-advisories.json")},
            "sources": [result], "published_sha256_on_approval_page": record["sha256"],
            "advisory_review_sha256": verifier.digest(remote / "sudo-advisories.json"),
            "limitations": ["Target core dependencies retain their separate source lock and release gates",
                            "Source verification does not establish target compilation or working administration"]}


def verify(cache: Path, gpg: Path, remote: Path = HERE) -> dict:
    """One call for the layer runner. The four-source check runs unchanged."""
    first = four.verify(cache, gpg, remote)
    sudo = verify_sudo(cache, gpg, remote)
    sources = first["sources"] + sudo["sources"]
    if (first.get("status") != "verified" or len(sources) != 5 or
            {row["name"] for row in sources} != four.NAMES | {SUDO} or
            any(row["status"] != "verified" for row in sources)):
        raise verifier.Refusal("remote layer source closure changed without review")
    return {"schema": "tup-remote-layer-source-verification-v1", "status": "verified",
            "scope": "five-remote-layer-sources", "release_eligible": False,
            "verifier_sha256": verifier.digest(Path(verifier.__file__)),
            "catalogs": {**first["catalogs"], **sudo["catalogs"]}, "sources": sources,
            "remote": first, "sudo": sudo,
            "limitations": first["limitations"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--gpg", type=Path, required=True)
    parser.add_argument("--sudo-only", action="store_true", help="check only the sudo record and its advisories")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = (verify_sudo if args.sudo_only else verify)(args.cache, args.gpg)
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
