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
from pathlib import Path
from urllib.parse import urlsplit

CATALOG_SCHEMA = "tup-source-catalog-v1"
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+-]*")
HEX256 = re.compile(r"[0-9a-f]{64}")
FINGERPRINT = re.compile(r"[0-9A-F]{40}|[0-9A-F]{64}")
GENTOO_PRIMARY = "DCD05B71EAB94199527F44ACDB6B8C1F96D8BF6D"


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


def published_digest(raw: bytes, selection: dict, source_name: str) -> str:
    """Select a digest for exactly one file from retained publisher metadata."""
    kind = selection.get("format")
    name = selection.get("filename", source_name)
    if name != source_name:
        raise Refusal("published digest must identify the selected source filename")
    values = []
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
    if method == "https-published-sha256":
        publication = material(evidence, auth.get("material"))
        expected = published_digest(publication.read_bytes(), auth.get("selection", {}), record["name"])
        if actual != expected:
            raise Refusal("archive differs from publisher SHA256")
        details = {"trust_class": "https-published-sha256", "assurance": "publisher HTTPS metadata; no signature verified"}
    elif method == "openpgp":
        details = verify_pgp(archive, auth, evidence, gpg)
    elif method == "distributor-openpgp-manifest":
        details = verify_distributor(archive, auth, cache, evidence, gpg, context if context is not None else {})
    else:
        raise Refusal("no supported authentication evidence")
    if auth.get("corroboration") is not None:
        corroboration = auth["corroboration"]
        if corroboration.get("method") != "distributor-openpgp-manifest":
            raise Refusal("unsupported source corroboration")
        details["corroboration"] = verify_distributor(
            archive, corroboration, cache, evidence, gpg, context if context is not None else {})
    if record.get("sha256") is not None and record["sha256"] != actual:
        raise Refusal("archive differs from reviewed pin")
    return {"name": record["name"], "status": "verified", "sha256": actual,
            "size": archive.stat().st_size, "authentication": {
                "status": "verified", "evidence_sha256": hashlib.sha256(encoded(auth)).hexdigest(),
                **details}}


def verify_catalog(catalog: dict, cache: Path, evidence: Path, gpg: Path | None = None) -> dict:
    validate_catalog(catalog, evidence)
    records = []
    context = {"requested": {}}
    for record in catalog["sources"]:
        auth = record.get("authentication", {})
        for item in (auth, auth.get("corroboration", {})):
            if item.get("method") == "distributor-openpgp-manifest":
                identity = hashlib.sha256(encoded(item.get("snapshot", {}))).hexdigest()
                context["requested"].setdefault(identity, set()).add(item.get("manifest_member"))
    for record in catalog["sources"]:
        try:
            records.append(verify_record(record, cache, evidence, gpg, context))
        except (Refusal, OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as exc:
            records.append({"name": record["name"], "status": "unresolved", "reason": str(exc)})
    return {"schema": "tup-source-verification-v1", "catalog_sha256": hashlib.sha256(encoded(catalog)).hexdigest(),
            "verifier": {"name": "source_lock.py", "sha256": digest(Path(__file__).resolve()),
                         "python_version": sys.version.split()[0]},
            "checked_at": datetime.now(timezone.utc).isoformat(), "sources": records,
            "complete": bool(records) and all(record["status"] == "verified" for record in records)}


def export_lock(catalog: dict, report: dict, book_source: Path) -> dict:
    if report.get("catalog_sha256") != hashlib.sha256(encoded(catalog)).hexdigest():
        raise Refusal("verification report does not describe this catalog")
    verified_names = [row.get("name") for row in report.get("sources", [])]
    selected_names = [row["name"] for row in catalog["sources"]]
    if (not report.get("complete") or not verified_names or
            len(verified_names) != len(set(verified_names)) or
            set(verified_names) != set(selected_names) or
            any(row.get("status") != "verified" for row in report["sources"])):
        raise Refusal("unverified candidate sources cannot enter a production lock")
    advisories = catalog.get("advisory_review", {})
    if (advisories.get("status") != "reviewed" or not advisories.get("reviewed_at") or
            not HEX256.fullmatch(advisories.get("material_sha256", "")) or
            not advisories.get("dispositions")):
        raise Refusal("dated advisory review is missing")
    if any(row.get("disposition") not in {"fixed-by-selection", "not-affected", "not-in-base"}
           for row in advisories.get("dispositions", [])):
        raise Refusal("unresolved advisory disposition")
    results = {row["name"]: row for row in report["sources"]}
    sources = []
    for row in catalog["sources"]:
        if row["disposition"] == "omit":
            continue
        verified = results[row["name"]]
        if verified.get("status") != "verified":
            raise Refusal("source lacks verification")
        sources.append({"name": row["name"], "url": row["url"], "sha256": verified["sha256"],
                        "authentication": verified["authentication"],
                        "verification_material": row["authentication"]})
    return {"schema": "tup-source-lock-v1", "architecture": "x86_64",
            "book_source_sha256": digest(book_source), "catalog_sha256": report["catalog_sha256"],
            "source_verification": {"schema": "tup-source-verification-v1", "status": "complete",
                                    "report_sha256": hashlib.sha256(encoded(report)).hexdigest(),
                                    "verifier": report["verifier"],
                                    "source_count": len(sources), "checked_at": report["checked_at"]},
            "provenance": "Each source verified against retained publisher evidence; trust class is recorded per source.",
            "advisory_review": advisories, "sources": sources}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--gpg", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--export", type=Path)
    parser.add_argument("--book-source", type=Path)
    args = parser.parse_args(argv)
    try:
        catalog = json.loads(args.catalog.read_bytes())
        report = verify_catalog(catalog, args.cache, args.evidence, args.gpg)
        args.report.write_bytes(encoded(report))
        if args.export:
            if args.book_source is None:
                raise Refusal("--export requires --book-source")
            lock = export_lock(catalog, report, args.book_source)
            args.export.write_bytes(encoded(lock))
        verified = sum(row["status"] == "verified" for row in report["sources"])
        print(f"{verified}/{len(report['sources'])} sources verified; complete={report['complete']}")
        return 0 if report["complete"] else 1
    except (Refusal, OSError, ValueError) as exc:
        print(f"source verification refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
