#!/usr/bin/env python3
"""Verify a reviewed source catalog and export the native source-lock v1.

Observed archive hashes are never an authenticator. A record needs either a
published strong digest in retained HTTPS metadata, or an OpenPGP signature
verified against its explicitly approved primary fingerprint and key material.
The catalog and its trust anchors are reviewed inputs, not self-authenticating.
"""
from __future__ import annotations

import argparse
import base64
import bz2
import gzip
import hashlib
import html
import json
import lzma
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

CATALOG_SCHEMA = "tup-source-catalog-v1"
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+-]*")
HEX256 = re.compile(r"[0-9a-f]{64}")
FINGERPRINT = re.compile(r"[0-9A-F]{40}|[0-9A-F]{64}")
GENTOO_PRIMARY = "DCD05B71EAB94199527F44ACDB6B8C1F96D8BF6D"
PATCH_POLICY_SHA256 = "85c9b35612c90dc4936acdfdf20e36f1b9f3939a49f5f79ef2bd195f14539ea7"
PATCH_CORROBORATION_SHA256 = "fb2162be4fe417b6f24f423d6ce3e32878646c80335152e6245c0e5c1df0ec6a"
SOURCE_POLICY_SHA256 = "536e77f61dd24a3269888645aa33fb4d55dfe5aa3fa0bcf4ac79915da42f33d1"
PYTHON_BACKPORT_SHA256 = "a850b836acef2d5b12591aaa6e70aafcc30ec80981823e79b5a657c77409c25b"
PYTHON_BACKPORT_REVIEW_SHA256 = "6672074b4b7827dbc299bb3257d0b01a45fe7afb87fc5d66a739212c9ece752a"


class Refusal(ValueError):
    pass


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def encoded(value) -> bytes:
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode()


def https(url: str) -> bool:
    parsed = urlsplit(url) if isinstance(url, str) else None
    return bool(parsed and parsed.scheme == "https" and parsed.hostname and
                not parsed.username and not parsed.password and not parsed.fragment)


def local_file(root: Path, name: str) -> Path:
    """Evidence paths are relative, contained and never symlink traversals."""
    if not isinstance(name, str) or not name or "\\" in name:
        raise Refusal("unsafe evidence path")
    parts = name.split("/")
    if any(not NAME.fullmatch(part) for part in parts):
        raise Refusal("unsafe evidence path")
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise Refusal("symlink evidence is not accepted")
    if not path.is_file():
        raise Refusal(f"missing evidence: {name}")
    return path


def material(root: Path, record: dict) -> Path:
    if not isinstance(record, dict) or not https(record.get("url")):
        raise Refusal("verification material requires a publisher HTTPS URL")
    expected = record.get("sha256", "")
    if not isinstance(expected, str) or not HEX256.fullmatch(expected):
        raise Refusal("verification material requires a pinned SHA256")
    path = local_file(root, record.get("path"))
    if digest(path) != expected:
        raise Refusal("verification material SHA256 mismatch")
    return path


def review_record(root: Path, record: dict, approved: str) -> Path:
    """Internal review evidence has no invented publisher URL or signature."""
    if not isinstance(record, dict) or record.get("sha256") != approved:
        raise Refusal("unapproved review policy identity")
    path = local_file(root, record.get("path"))
    if digest(path) != approved:
        raise Refusal("review policy bytes changed")
    return path


def verify_patch_exception(archive: Path, auth: dict, evidence: Path) -> dict:
    policy_path = review_record(evidence, auth.get("policy"), PATCH_POLICY_SHA256)
    corroboration_path = review_record(evidence, auth.get("corroboration"),
                                      PATCH_CORROBORATION_SHA256)
    policy = json.loads(policy_path.read_bytes())
    if (policy.get("schema") != "tup-reviewed-lfs-patch-exceptions-v1" or
            policy.get("decision") != "approved-provenance-exception" or
            policy.get("corroboration_sha256") != digest(corroboration_path)):
        raise Refusal("patch policy does not approve this provenance review")
    selected = [row for row in policy.get("patches", []) if row.get("name") == archive.name]
    if len(selected) != 1 or selected[0].get("sha256") != digest(archive):
        raise Refusal("patch is outside the exact approved name/digest set")
    return {"trust_class": "reviewed-lfs-patch-exception", "status": "accepted-exception",
            "policy_sha256": PATCH_POLICY_SHA256, "corroboration_sha256": PATCH_CORROBORATION_SHA256,
            "git_commit": policy["commit"], "git_blob": selected[0]["git_blob"],
            "required_gates": ["selected-version-patch-application", "required-package-tests"],
            "assurance": policy["assurance"]}


def documentation_members(archive: Path) -> list[dict]:
    members, names = [], set()
    with tarfile.open(archive) as bundle:
        for entry in bundle:
            name = entry.name.rstrip("/")
            parts = name.split("/")
            if (name in names or "\\" in name or any(ord(c) < 32 for c in name) or
                    parts[0] != "systemd-man-pages-261.2" or any(p in {"", ".", ".."} for p in parts)):
                raise Refusal("unsafe or duplicate documentation path")
            names.add(name)
            if entry.isdir():
                if entry.mode not in {0o755, 0o775} or len(parts) > 2:
                    raise Refusal("unsafe documentation directory")
                content = None
            elif entry.isfile():
                if (entry.mode != 0o644 or len(parts) != 3 or not re.fullmatch(r"man[13578]", parts[1]) or
                        not parts[2].endswith("." + parts[1][-1]) or entry.size > 4 * 1024 ** 2):
                    raise Refusal("unexpected documentation file")
                content = hashlib.sha256(bundle.extractfile(entry).read()).hexdigest()
            else:
                raise Refusal("documentation contains a link or special member")
            members.append({"path": entry.name, "type": "directory" if entry.isdir() else "regular",
                            "mode": oct(entry.mode), "size": entry.size, "sha256": content})
            if len(members) > 2000:
                raise Refusal("documentation inventory exceeds inspection budget")
    return members


def verify_source_exception(archive: Path, auth: dict, evidence: Path) -> dict:
    policy_path = review_record(evidence, auth.get("policy"), SOURCE_POLICY_SHA256)
    policy = json.loads(policy_path.read_bytes())
    selected = [row for row in policy.get("sources", []) if row.get("name") == archive.name]
    if (policy.get("decision") != "approved-exact-provenance-exceptions" or len(selected) != 1 or
            selected[0].get("sha256") != digest(archive) or
            selected[0].get("size") != archive.stat().st_size or
            selected[0].get("proposed_class") != auth.get("method")):
        raise Refusal("source is outside the exact approved provenance exception")
    approved = selected[0]
    details = {"status": "accepted-exception", "trust_class": auth["method"],
               "policy_sha256": SOURCE_POLICY_SHA256, "source_size": archive.stat().st_size,
               "assurance": approved["assurance"]}
    if auth["method"] == "reviewed-distributor-https-exception":
        if auth.get("material") != approved["material"]:
            raise Refusal("unapproved distributor checksum material")
        publication = material(evidence, auth["material"])
        text = publication.read_text(encoding="utf-8")
        name = re.escape(archive.name)
        values = re.findall(r"^SHA512 \(" + name + r"\) = ([0-9a-f]{128})$", text, re.M)
        sizes = re.findall(r"^Size \(" + name + r"\) = (\d+) bytes$", text, re.M)
        with archive.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha512").hexdigest()
        if (values != [approved["published_sha512"]] or sizes != [str(approved["size"])] or
                actual != values[0]):
            raise Refusal("source differs from the exact distributor filename/size/SHA512")
        details.update(distributor=approved["distributor"], material_sha256=digest(publication),
                       source_digest_algorithm="sha512", source_digest=actual,
                       required_gates=["required-package-tests"])
    else:
        if auth.get("inventory") != approved["inventory"] or auth.get("book_material") != approved["book_material"]:
            raise Refusal("unapproved documentation inventory or origin evidence")
        inventory = review_record(evidence, auth["inventory"], approved["inventory"]["sha256"])
        recorded = json.loads(inventory.read_bytes())
        material(evidence, auth["book_material"])
        if (recorded.get("name") != archive.name or recorded.get("sha256") != digest(archive) or
                recorded.get("unsafe_members") != [] or recorded.get("members") != documentation_members(archive)):
            raise Refusal("documentation differs from the reviewed complete inventory")
        details.update(inventory_sha256=digest(inventory), install_destination="/usr/share/man",
                       required_gates=["documentation-install-confinement", "documentation-inventory"])
    return details


class AdvisoryTable(HTMLParser):
    """Parse the LFS application's two-row advisory records, including its
    unclosed header row. Cross-reference IDs in descriptions are not records.
    """
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.cells, self.cell, self.links = [], [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.cells, self.cell, self.links = [], None, []
        elif tag == "td":
            self.cell = []
        elif tag == "a" and self.cell is not None:
            value = dict(attrs).get("href", "")
            if https(value):
                self.links.append(value)
        elif tag in {"br", "p", "li"} and self.cell is not None:
            self.cell.append(" ")

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None:
            self.cells.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.cells:
            self.rows.append((self.cells, self.links))
            self.cells, self.links = [], []


def advisory_inventory(raw: bytes) -> list[dict]:
    parser = AdvisoryTable()
    parser.feed(raw.decode("utf-8"))
    inventory, pending = [], None
    for cells, links in parser.rows:
        if len(cells) == 4 and re.fullmatch(r"sa-13\.1-\d{3}", cells[0]):
            if pending is not None:
                raise Refusal("advisory snapshot is missing a description")
            pending = dict(zip(("id", "package", "date", "severity"), cells))
        elif pending is not None:
            if len(cells) != 1 or not cells[0]:
                raise Refusal("advisory snapshot has an invalid description row")
            pending.update(description=cells[0], links=sorted(set(links)))
            inventory.append(pending)
            pending = None
    ids = [row["id"] for row in inventory]
    if pending is not None or not ids or len(ids) != len(set(ids)):
        raise Refusal("advisory snapshot is empty, incomplete or has duplicate IDs")
    return sorted(inventory, key=lambda row: row["id"])


def verify_advisory_review(catalog: dict, evidence: Path) -> dict:
    review = catalog.get("advisory_review", {})
    if review.get("status") != "reviewed":
        raise Refusal("dated advisory review is missing")
    reviewed_at = review.get("reviewed_at", "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", reviewed_at):
        raise Refusal("advisory review date must be an ISO calendar date")
    datetime.strptime(reviewed_at, "%Y-%m-%d")
    snapshot = material(evidence, review.get("snapshot"))
    if (review["snapshot"]["url"] != "https://www.linuxfromscratch.org/advisories/index.php" or
            review.get("request") != {"method": "POST", "fields": {
                "stype": "Book", "release": "13.1", "desc": "true", "submit": "Search"}} or
            review.get("material_sha256") != digest(snapshot)):
        raise Refusal("advisory review does not bind the complete 13.1 query")
    inventory = advisory_inventory(snapshot.read_bytes())
    if review.get("inventory_sha256") != hashlib.sha256(encoded(inventory)).hexdigest():
        raise Refusal("advisory inventory differs from the retained snapshot")
    if any(row["date"] > reviewed_at for row in inventory):
        raise Refusal("advisory review predates its evidence")
    selected = {row["name"] for row in catalog["sources"]}
    packages = review.get("package_sources", {})
    mapped = [name for names in packages.values() for name in names]
    if set(mapped) != selected or len(mapped) != len(set(mapped)):
        raise Refusal("advisory package scope must cover every selected source exactly once")
    dispositions = review.get("dispositions", [])
    ids = [row.get("id") for row in dispositions]
    if len(ids) != len(set(ids)):
        raise Refusal("duplicate advisory disposition")
    baseline = {row["id"]: row for row in inventory}
    supplemental = {"upstream-expat-2.10.0", "upstream-expat-CVE-2025-66382"}
    if set(ids) != set(baseline) | supplemental:
        raise Refusal("advisory dispositions do not cover the complete snapshot and required upstream review")
    deferred = False
    for row in dispositions:
        ident, package, decision = row["id"], row.get("package"), row.get("disposition")
        if ident in baseline and package != baseline[ident]["package"]:
            raise Refusal("advisory disposition package differs from the snapshot")
        if ident in supplemental and package != "expat":
            raise Refusal("unapproved supplemental advisory package")
        if ident in {"sa-13.1-088", "sa-13.1-089"} and decision != "fixed-by-native-patch":
            raise Refusal("selected Python requires the reviewed native security backport")
        if not isinstance(row.get("reason"), str) or not row["reason"].strip():
            raise Refusal("advisory disposition requires a reason")
        references = row.get("evidence", [])
        if decision != "not-in-base" and not references:
            raise Refusal("affected-package disposition lacks evidence")
        for reference in references:
            material(evidence, reference)
        affected = row.get("selected_sources", [])
        if decision == "not-in-base":
            if package in packages or affected:
                raise Refusal("a base package cannot be dismissed as not-in-base")
        elif decision in {"fixed-by-selection", "fixed-by-native-patch", "not-affected", "deferred-release-gate"}:
            if (package not in packages or not affected or not set(affected) <= selected or
                    not set(affected) & set(packages[package])):
                raise Refusal("affected advisory does not identify its selected source")
            if decision == "fixed-by-native-patch":
                if (ident not in {"sa-13.1-088", "sa-13.1-089"} or package != "python" or
                        affected != ["Python-3.14.10.tar.xz"]):
                    raise Refusal("unapproved advisory native backport")
                for field, expected, basename in (
                    ("native_patch", PYTHON_BACKPORT_SHA256, "python-3.14.10-security-backports.patch"),
                    ("native_review", PYTHON_BACKPORT_REVIEW_SHA256, "PYTHON-BACKPORT-REVIEW.json")):
                    value = row.get(field, {})
                    if (value.get("path") != "tup/native/profiles/lfs-13.1-systemd/" + basename or
                            value.get("sha256") != expected):
                        raise Refusal("advisory backport does not bind its reviewed repository input")
                    review_record(evidence, {"path": basename, "sha256": value["sha256"]}, expected)
            elif decision == "deferred-release-gate":
                if (ident != "upstream-expat-CVE-2025-66382" or row.get("gate_id") != "H55" or
                        affected != ["expat-2.10.0.tar.xz"]):
                    raise Refusal("unknown advisory deferral cannot authorize a build-only lock")
                deferred = True
            elif ident == "upstream-expat-CVE-2025-66382":
                raise Refusal("open Expat CPU DoS cannot be declared fixed or unaffected")
        else:
            raise Refusal("unresolved advisory disposition")
    gates = [{"id": "H55", "status": "open", "advisories": ["CVE-2025-66382"],
              "required_evidence": ["host XML exposure review",
                                    "workload CPU/time containment demonstrated or qualified upstream fix"]}] if deferred else []
    return {"status": "reviewed", "review_sha256": hashlib.sha256(encoded(review)).hexdigest(),
            "snapshot_count": len(inventory), "disposition_count": len(dispositions),
            "lock_purpose": "build-only" if deferred else "production",
            "release_eligible": not deferred, "release_gates": gates}


def published_digest(raw: bytes, selection: dict, source_name: str) -> str:
    """Select a digest for exactly one file from retained publisher metadata."""
    kind = selection.get("format")
    name = selection.get("filename", source_name)
    if name != source_name:
        raise Refusal("published digest must identify the selected source filename")
    values = []
    if kind == "sha512-announcement":
        text = html.unescape(re.sub(r"<[^>]*>", "", raw.decode("utf-8")))
        if "SHA-512 checksums" not in text:
            raise Refusal("announcement does not identify its digest algorithm")
        values = re.findall(r"(?m)^[ \t]*([0-9a-f]{128})[ \t]*(?:\r?\n)?[ \t]+" +
                            re.escape(name) + r"[ \t]*$", text)
        if len(values) != 1:
            raise Refusal("no unique published SHA512 for selected filename")
        return values[0]
    if kind == "sha256sum":
        for line in raw.decode("utf-8").splitlines():
            match = re.fullmatch(r"([0-9a-fA-F]{64}) [ *](.+)", line)
            if match and match[2] == name:
                values.append(match[1].lower())
    elif kind == "bare-sha256":
        # The reviewed material URL identifies the one artifact, e.g. .sha256.
        value = raw.decode("ascii").strip()
        if HEX256.fullmatch(value.lower()):
            values.append(value.lower())
    elif kind == "gnu-announcement":
        text = html.unescape(re.sub(r"<[^>]*>", "", raw.decode("utf-8")))
        escaped = re.escape(name)
        # GNU release announcements use named File blocks, BSD checksum
        # notation, or checksum lists. Only SHA256 fields are selected.
        blocks = re.split(r"(?m)^[ \t]*File:[ \t]*", text)[1:]
        for block in blocks:
            lines = block.splitlines()
            if lines and lines[0].strip() == name:
                values += re.findall(r"\bSHA256 sum:\s*([0-9a-fA-F]{64})(?![0-9a-fA-F])", block)
        patterns = [r"(?m)^[ \t]*SHA256 \(" + escaped + r"\)\s*=\s*([A-Za-z0-9+/=]+)[ \t]*$",
                    r"(?m)^[ \t]*([A-Za-z0-9+/]{43}=?|[0-9a-fA-F]{64})[ \t]+(?:\r?\n)?" + escaped + r"[ \t]*$"]
        for pattern in patterns:
            for value in re.findall(pattern, text):
                if HEX256.fullmatch(value.lower()):
                    values.append(value.lower())
                else:
                    decoded = base64.b64decode(value + "=" * (-len(value) % 4), validate=True)
                    if len(decoded) != 32:
                        raise Refusal("invalid GNU SHA256 checksum length")
                    values.append(decoded.hex())
    elif kind == "github-release":
        payload = json.loads(raw)
        if payload.get("tag_name") != selection.get("tag"):
            raise Refusal("GitHub release tag mismatch")
        for asset in payload.get("assets", []):
            if asset.get("name") == name:
                value = asset.get("digest", "") or ""
                if value.startswith("sha256:"):
                    values.append(value.removeprefix("sha256:").lower())
    elif kind == "sourceforge-files":
        # SourceForge publishes per-file metadata in a JSON assignment inside
        # its official project file listing. Parse data; never evaluate JS.
        text = raw.decode("utf-8")
        assignments = re.findall(r"net\.sf\.files\s*=\s*(\{.*?\});", text, re.S)
        if len(assignments) != 1:
            raise Refusal("missing or ambiguous SourceForge file metadata")
        artifact = json.loads(assignments[0]).get(name, {})
        expected_path = selection.get("project_path")
        if (not isinstance(expected_path, str) or artifact.get("name") != name or
                artifact.get("full_path") != expected_path + "/" + name or
                artifact.get("path") != "/" + expected_path or artifact.get("type") != "f"):
            raise Refusal("SourceForge file identity mismatch")
        values.append(artifact.get("sha256") or "")
    elif kind == "pypi-release":
        payload = json.loads(raw)
        if payload.get("info", {}).get("version") != selection.get("version"):
            raise Refusal("PyPI release version mismatch")
        for artifact in payload.get("urls", []):
            if artifact.get("filename") == name:
                values.append(artifact.get("digests", {}).get("sha256", ""))
    elif kind == "html-table":
        # Match the exact download URL in a publisher's table row. No arbitrary
        # first-hash extraction: neighboring architecture/artifact hashes differ.
        text = raw.decode("utf-8")
        url = selection.get("artifact_url", "")
        if not https(url):
            raise Refusal("HTML digest selection requires an artifact URL")
        for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", text, re.S | re.I):
            if re.search(r'href=["\']' + re.escape(url) + r'["\']', row):
                codes = re.findall(r"<code\b[^>]*>(.*?)</code>", row, re.S | re.I)
                # Python splits its displayed checksum across spans and <wbr>.
                # Join text only inside code elements in this exact file row.
                for code in codes or [row]:
                    value = html.unescape(re.sub(r"<[^>]*>", "", code) if codes else code)
                    values += re.findall(r"(?<![0-9a-fA-F])([0-9a-fA-F]{64})(?![0-9a-fA-F])", value)
    else:
        raise Refusal("unsupported published-digest format")
    if len(values) != 1 or not HEX256.fullmatch(values[0].lower()):
        raise Refusal(f"no unique published SHA256 for {name}")
    return values[0].lower()


def approved_signature(stdout: bytes, returncode: int, primary: str) -> str:
    if not FINGERPRINT.fullmatch(primary):
        raise Refusal("invalid approved primary fingerprint")
    lines = stdout.decode("utf-8", errors="strict").splitlines()
    rejected = ("BADSIG", "ERRSIG", "REVKEYSIG", "EXPKEYSIG", "EXPSIG", "NO_PUBKEY")
    if returncode or any(line.startswith("[GNUPG:] " + flag + " ") for flag in rejected for line in lines):
        raise Refusal("OpenPGP signature verification failed")
    valid = [line.split()[2:] for line in lines if line.startswith("[GNUPG:] VALIDSIG ")]
    # VALIDSIG fields: signer, date, timestamp, expiry, version, reserved,
    # pubkey algorithm, digest algorithm, signature class, primary fingerprint.
    if len(valid) != 1 or len(valid[0]) < 9:
        raise Refusal("missing or ambiguous OpenPGP VALIDSIG status")
    fields = valid[0]
    actual_primary = fields[9] if len(fields) >= 10 else fields[0]
    if actual_primary != primary:
        raise Refusal("signature is not from the approved primary fingerprint")
    if fields[7] not in {"8", "9", "10"}:  # SHA256/384/512
        raise Refusal("weak OpenPGP signature digest")
    return fields[0]


def gpg_path(path: Path, gpg: Path) -> str:
    """Git for Windows GPG requires MSYS paths for its home directory."""
    absolute = path.resolve()
    if os.name == "nt" and (gpg.parent / "msys-2.0.dll").is_file():
        if len(absolute.drive) != 2 or absolute.drive[1] != ":":
            raise Refusal("MSYS GPG requires a local drive path")
        return "/" + absolute.drive[0].lower() + absolute.as_posix()[2:]
    return str(absolute)


def verify_pgp(archive: Path, auth: dict, evidence: Path, gpg: Path) -> dict:
    if gpg is None or not gpg.is_file():
        raise Refusal("OpenPGP verifier executable unavailable")
    approval = auth.get("approval", {})
    if not approval.get("reviewed_at") or not approval.get("basis"):
        raise Refusal("OpenPGP key approval is missing its dated review")
    material(evidence, approval.get("material"))
    if approval.get("profile") is not None:
        material(evidence, approval["profile"])
    key = material(evidence, auth.get("key"))
    signature = material(evidence, auth.get("signature"))
    primary = auth.get("primary_fingerprint", "")
    if not FINGERPRINT.fullmatch(primary):
        raise Refusal("no approved primary fingerprint")
    with tempfile.TemporaryDirectory(prefix="tup-source-gpg-") as temporary:
        home = Path(temporary)
        command = [str(gpg), "--no-options", "--homedir", gpg_path(home, gpg), "--batch",
                   "--no-auto-key-retrieve", "--auto-key-locate", "clear"]
        env = dict(os.environ, GNUPGHOME=gpg_path(home, gpg))
        imported = subprocess.run(command + ["--import", gpg_path(key, gpg)], capture_output=True, env=env, timeout=60)
        if imported.returncode:
            raise Refusal("cannot import approved publisher key material")
        payload = archive
        if auth.get("payload", "archive") == "uncompressed-tar":
            opener = {".xz": lzma.open, ".gz": gzip.open, ".bz2": bz2.open}.get(archive.suffix)
            if opener is None:
                raise Refusal("unsupported signed-tar compression")
            payload = home / "payload.tar"
            with opener(archive, "rb") as source, payload.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
        elif auth.get("payload", "archive") != "archive":
            raise Refusal("unsupported signed payload")
        checked = subprocess.run(command + ["--status-fd", "1", "--verify", gpg_path(signature, gpg), gpg_path(payload, gpg)],
                                 capture_output=True, env=env, timeout=120)
        signer = approved_signature(checked.stdout, checked.returncode, primary)
        if auth.get("signing_fingerprint") is not None and signer != auth["signing_fingerprint"]:
            raise Refusal("signature is not from the approved signing fingerprint")
    return {"trust_class": "publisher-openpgp", "primary_fingerprint": primary,
            "signing_fingerprint": signer, "verifier_sha256": digest(gpg),
            "status_sha256": hashlib.sha256(checked.stdout).hexdigest()}


def validate_catalog(catalog: dict, evidence: Path) -> None:
    if catalog.get("schema") != CATALOG_SCHEMA or catalog.get("architecture") != "x86_64":
        raise Refusal("unsupported source catalog")
    inventory = material(evidence, catalog.get("inventory"))
    urls = inventory.read_text(encoding="utf-8").splitlines()
    baseline = {url.rsplit("/", 1)[-1] for url in urls if url.strip()}
    if not baseline or len(baseline) != len([url for url in urls if url.strip()]):
        raise Refusal("empty or duplicate baseline inventory")
    records = catalog.get("sources", [])
    if not isinstance(records, list) or len(records) != len(baseline):
        raise Refusal("catalog does not cover the complete baseline inventory")
    identities = [record.get("baseline_name") for record in records if isinstance(record, dict)]
    if set(identities) != baseline or len(set(identities)) != len(identities):
        raise Refusal("missing or duplicate baseline source record")
    names = set()
    for record in records:
        name = record.get("name", "")
        if not isinstance(name, str) or not NAME.fullmatch(name) or name in names:
            raise Refusal("duplicate or unsafe selected source name")
        if not https(record.get("url")):
            raise Refusal("selected source URL must use HTTPS")
        if record.get("disposition") not in {"retain", "replace", "omit"}:
            raise Refusal("source has no reviewed disposition")
        if record["disposition"] != "retain" and not record.get("reason"):
            raise Refusal("source change requires a reason")
        names.add(name)


def gentoo_manifest_entry(raw: bytes, name: str) -> tuple[int, str]:
    entries = []
    for line in raw.decode("utf-8").splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[:2] == ["DIST", name]:
            if len(fields) < 5 or (len(fields) - 3) % 2 or not fields[2].isdigit():
                raise Refusal("malformed Gentoo DIST entry")
            pairs = list(zip(fields[3::2], fields[4::2]))
            if len({algorithm for algorithm, _ in pairs}) != len(pairs):
                raise Refusal("duplicate Gentoo digest algorithm")
            expected = dict(pairs).get("SHA512", "")
            if not re.fullmatch(r"[0-9a-f]{128}", expected):
                raise Refusal("Gentoo DIST entry lacks a strong SHA512")
            entries.append((int(fields[2]), expected))
    if len(entries) != 1:
        raise Refusal("missing or ambiguous exact filename in Gentoo Manifest")
    return entries[0]


def snapshot_manifests(path: Path, requested: set[str]) -> dict[str, bytes]:
    """Read only named regular-file Manifests; never extract archive paths."""
    found = {}
    with tarfile.open(path, mode="r|xz") as archive:
        for number, member in enumerate(archive):
            if number > 250000 or member.offset_data + member.size > 2 * 1024 ** 3:
                raise Refusal("distributor snapshot exceeds inspection budget")
            if member.name not in requested:
                continue
            if member.name in found or not member.isfile() or member.size > 4 * 1024 ** 2:
                raise Refusal("ambiguous or unsafe Manifest member")
            found[member.name] = archive.extractfile(member).read()
    if set(found) != requested:
        raise Refusal("signed snapshot does not contain every requested Manifest")
    return found


def verify_distributor(archive: Path, auth: dict, cache: Path, evidence: Path,
                       gpg: Path | None, context: dict) -> dict:
    if auth.get("distributor") != "Gentoo":
        raise Refusal("unapproved distributor trust root")
    snapshot = auth.get("snapshot", {})
    signature = snapshot.get("authentication", {})
    if (signature.get("method") != "openpgp" or signature.get("primary_fingerprint") != GENTOO_PRIMARY or
            signature.get("payload", "archive") != "archive"):
        raise Refusal("unapproved Gentoo snapshot authentication")
    approval = material(evidence, signature.get("approval", {}).get("material"))
    if (signature["approval"]["material"]["url"] != "https://www.gentoo.org/downloads/signatures/" or
            GENTOO_PRIMARY not in approval.read_text(encoding="utf-8")):
        raise Refusal("Gentoo primary fingerprint lacks official approval material")
    member = auth.get("manifest_member", "")
    if (not isinstance(member, str) or not member.endswith("/Manifest") or
            any(not NAME.fullmatch(part) for part in member.split("/"))):
        raise Refusal("unsafe Gentoo Manifest member name")
    retained = material(evidence, auth.get("manifest"))
    identity = hashlib.sha256(encoded(snapshot)).hexdigest()
    verified = context.setdefault("snapshots", {})
    if identity not in verified:
        bundle = material(cache, snapshot.get("material"))
        details = verify_pgp(bundle, signature, evidence, gpg)
        requested = context.get("requested", {}).get(identity, {member})
        manifests = snapshot_manifests(bundle, requested)
        verified[identity] = (details, manifests)
    details, manifests = verified[identity]
    if member not in manifests or retained.read_bytes() != manifests[member]:
        raise Refusal("retained Manifest is not linked to the authenticated snapshot")
    size, expected = gentoo_manifest_entry(manifests[member], archive.name)
    if archive.stat().st_size != size:
        raise Refusal("source size differs from authenticated distributor Manifest")
    with archive.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha512").hexdigest()
    if actual != expected:
        raise Refusal("source SHA512 differs from authenticated distributor Manifest")
    return {**details, "trust_class": "distributor-openpgp-manifest", "distributor": "Gentoo",
            "snapshot_sha256": snapshot["material"]["sha256"], "manifest_member": member,
            "manifest_sha256": digest(retained), "source_digest_algorithm": "sha512",
            "source_digest": expected, "source_size": size,
            "assurance": "Gentoo-signed snapshot authenticates exact upstream filename, size and SHA512; SHA256 pin is derived after verification"}


def stream_identity(stream, limit=64 * 1024 ** 2) -> tuple[int, str]:
    size, hasher = 0, hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        size += len(chunk)
        if size > limit:
            raise Refusal("tar equivalence payload exceeds inspection budget")
        hasher.update(chunk)
    return size, hasher.hexdigest()


def lzip_tar_identity(archive: Path, executable: Path | None) -> tuple[int, str, str]:
    if executable is None or not executable.is_file():
        raise Refusal("maintained lzip executable is required for tar equivalence")
    with tempfile.TemporaryFile() as output:
        result = subprocess.run([str(executable.resolve()), "--decompress", "--stdout", str(archive.resolve())],
                                stdout=output, stderr=subprocess.PIPE, timeout=60)
        if result.returncode:
            raise Refusal("lzip rejected the authenticated reference archive")
        output.seek(0)
        size, value = stream_identity(output)
    return size, value, digest(executable)


def verify_tar_equivalence(archive: Path, auth: dict, cache: Path, evidence: Path,
                           gpg: Path | None, context: dict) -> dict:
    # This is the one reviewed compression alternative, not a general content
    # equivalence claim. Every decompressed tar byte, including metadata, must
    # agree; no files are extracted and no upstream scripts run.
    reference = material(cache, auth.get("reference_archive"))
    if (archive.name != "make-4.4.1.tar.gz" or reference.name != "make-4.4.1.tar.lz" or
            auth.get("reference_authentication", {}).get("method") != "distributor-openpgp-manifest"):
        raise Refusal("unapproved source tar equivalence")
    authenticated = {**verify_distributor(reference, auth["reference_authentication"], cache, evidence, gpg, context),
                     "status": "verified", "evidence_sha256": hashlib.sha256(encoded(auth["reference_authentication"])).hexdigest()}
    size, value, verifier = lzip_tar_identity(reference, context.get("lzip"))
    with gzip.open(archive, "rb") as stream:
        if stream_identity(stream) != (size, value) or size == 0:
            raise Refusal("source does not contain the exact authenticated tar bytes")
    return {"trust_class": "distributor-openpgp-tar-equivalence", "reference_name": reference.name,
            "reference_sha256": digest(reference), "reference_authentication": authenticated,
            "uncompressed_sha256": value, "uncompressed_size": size, "source_size": archive.stat().st_size,
            "decompressor": {"name": "lzip", "sha256": verifier},
            "assurance": "Gentoo authenticates the Lzip reference; complete decompressed tar bytes agree. The selected gzip wrapper is not publisher-signed."}


def verify_record(record: dict, cache: Path, evidence: Path, gpg: Path | None,
                  context: dict | None = None) -> dict:
    if record["disposition"] == "omit":
        return {"name": record["name"], "status": "omitted", "reason": record["reason"]}
    if record.get("integrity_review", {}).get("status") == "unresolved":
        raise Refusal("conflicting source evidence requires explicit integrity review")
    archive = local_file(cache, record["name"])
    actual = digest(archive)
    auth = record.get("authentication", {})
    method = auth.get("method")
    if method in {"https-published-sha256", "https-published-sha512"}:
        publication = material(evidence, auth.get("material"))
        expected = published_digest(publication.read_bytes(), auth.get("selection", {}), record["name"])
        algorithm = "sha256" if method.endswith("sha256") else "sha512"
        if (algorithm == "sha512") != (auth.get("selection", {}).get("format") == "sha512-announcement"):
            raise Refusal("published digest trust class and algorithm disagree")
        with archive.open("rb") as stream:
            published_actual = hashlib.file_digest(stream, algorithm).hexdigest()
        if published_actual != expected:
            raise Refusal("archive differs from publisher " + algorithm.upper())
        details = {"trust_class": method, "assurance": "publisher HTTPS metadata; no signature verified",
                   "source_digest_algorithm": algorithm, "source_digest": expected}
    elif method == "openpgp":
        details = verify_pgp(archive, auth, evidence, gpg)
    elif method == "distributor-openpgp-manifest":
        details = verify_distributor(archive, auth, cache, evidence, gpg, context if context is not None else {})
    elif method == "distributor-openpgp-tar-equivalence":
        details = verify_tar_equivalence(archive, auth, cache, evidence, gpg, context if context is not None else {})
    elif method == "reviewed-lfs-patch-exception":
        details = verify_patch_exception(archive, auth, evidence)
    elif method in {"reviewed-distributor-https-exception", "reviewed-lfs-documentation-exception"}:
        details = verify_source_exception(archive, auth, evidence)
    else:
        raise Refusal("no supported authentication evidence")
    if method != "reviewed-lfs-patch-exception" and auth.get("corroboration") is not None:
        corroboration = auth["corroboration"]
        if corroboration.get("method") != "distributor-openpgp-manifest":
            raise Refusal("unsupported source corroboration")
        details["corroboration"] = verify_distributor(
            archive, corroboration, cache, evidence, gpg, context if context is not None else {})
    if record.get("sha256") is not None and record["sha256"] != actual:
        raise Refusal("archive differs from reviewed pin")
    status = details.get("status", "verified")
    return {"name": record["name"], "status": status, "sha256": actual,
            "size": archive.stat().st_size, "authentication": {
                "status": status, "evidence_sha256": hashlib.sha256(encoded(auth)).hexdigest(),
                **details}}


def verify_catalog(catalog: dict, cache: Path, evidence: Path, gpg: Path | None = None,
                   lzip: Path | None = None) -> dict:
    validate_catalog(catalog, evidence)
    records = []
    context = {"requested": {}, "lzip": lzip}
    for record in catalog["sources"]:
        auth = record.get("authentication", {})
        for item in (auth, auth.get("corroboration", {}), auth.get("reference_authentication", {})):
            if item.get("method") == "distributor-openpgp-manifest":
                identity = hashlib.sha256(encoded(item.get("snapshot", {}))).hexdigest()
                context["requested"].setdefault(identity, set()).add(item.get("manifest_member"))
    for record in catalog["sources"]:
        try:
            records.append(verify_record(record, cache, evidence, gpg, context))
        except (Refusal, OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as exc:
            records.append({"name": record["name"], "status": "unresolved", "reason": str(exc)})
    try:
        advisory_status = verify_advisory_review(catalog, evidence)
    except (Refusal, OSError, ValueError) as exc:
        advisory_status = {"status": "unresolved", "reason": str(exc)}
    return {"schema": "tup-source-verification-v1", "catalog_sha256": hashlib.sha256(encoded(catalog)).hexdigest(),
            "verifier": {"name": "source_lock.py", "sha256": digest(Path(__file__).resolve()),
                         "python_version": sys.version.split()[0]},
            "checked_at": datetime.now(timezone.utc).isoformat(), "sources": records,
            "advisory_review": advisory_status,
            "authenticated_count": sum(record["status"] == "verified" for record in records),
            "accepted_exception_count": sum(record["status"] == "accepted-exception" for record in records),
            "complete": bool(records) and all(record["status"] in {"verified", "accepted-exception"} for record in records)}


def export_lock(catalog: dict, report: dict, book_source: Path) -> dict:
    if report.get("catalog_sha256") != hashlib.sha256(encoded(catalog)).hexdigest():
        raise Refusal("verification report does not describe this catalog")
    verified_names = [row.get("name") for row in report.get("sources", [])]
    selected_names = [row["name"] for row in catalog["sources"]]
    if (not report.get("complete") or not verified_names or
            len(verified_names) != len(set(verified_names)) or
            set(verified_names) != set(selected_names) or
            any(row.get("status") not in {"verified", "accepted-exception"} for row in report["sources"])):
        raise Refusal("unverified candidate sources cannot enter a production lock")
    advisories = catalog.get("advisory_review", {})
    advisory_status = report.get("advisory_review", {})
    if (advisory_status.get("status") != "reviewed" or
            advisory_status.get("review_sha256") != hashlib.sha256(encoded(advisories)).hexdigest()):
        raise Refusal("dated advisory review is missing or unresolved")
    results = {row["name"]: row for row in report["sources"]}
    sources = []
    for row in catalog["sources"]:
        if row["disposition"] == "omit":
            continue
        verified = results[row["name"]]
        if verified.get("status") not in {"verified", "accepted-exception"}:
            raise Refusal("source lacks verification")
        sources.append({"name": row["name"], "url": row["url"], "sha256": verified["sha256"],
                        "authentication": verified["authentication"],
                        "verification_material": row["authentication"]})
    return {"schema": "tup-source-lock-v1", "architecture": "x86_64",
            "book_source_sha256": digest(book_source), "catalog_sha256": report["catalog_sha256"],
            "source_verification": {"schema": "tup-source-verification-v1", "status": "complete",
                                    "report_sha256": hashlib.sha256(encoded(report)).hexdigest(),
                                    "verifier": report["verifier"],
                                    "authenticated_count": report["authenticated_count"],
                                    "accepted_exception_count": report["accepted_exception_count"],
                                    "source_count": len(sources), "checked_at": report["checked_at"]},
            "provenance": "Each source has verified authentication or a narrowly named reviewed provenance exception; assurance and remaining gates are recorded per source.",
            "lock_purpose": advisory_status["lock_purpose"],
            "release_eligible": advisory_status["release_eligible"],
            "release_gates": advisory_status["release_gates"],
            "advisory_review": advisories, "sources": sources}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--gpg", type=Path)
    parser.add_argument("--lzip", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--export", type=Path)
    parser.add_argument("--book-source", type=Path)
    args = parser.parse_args(argv)
    try:
        catalog = json.loads(args.catalog.read_bytes())
        report = verify_catalog(catalog, args.cache, args.evidence, args.gpg, args.lzip)
        args.report.write_bytes(encoded(report))
        if args.export:
            if args.book_source is None:
                raise Refusal("--export requires --book-source")
            lock = export_lock(catalog, report, args.book_source)
            args.export.write_bytes(encoded(lock))
        verified = sum(row["status"] == "verified" for row in report["sources"])
        print(f"{verified}/{len(report['sources'])} sources authenticated; "
              f"{report['accepted_exception_count']} accepted exceptions; complete={report['complete']}")
        return 0 if report["complete"] else 1
    except (Refusal, OSError, ValueError) as exc:
        print(f"source verification refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
