#!/usr/bin/env python3
"""Check a research list of papers or repositories against its schema and the live sources.

    python.exe -I -X utf8 validate.py papers papers.jsonl
    python.exe -I -X utf8 validate.py repos repos.jsonl --online --final --receipt out.json

Offline: schema, enumerations, duplicates, the list of work already cited in dawnr, the licence
allow-list, target paths in the dawnr checkout, and repeated text (a list padded with one sentence
fails here). Online: every arXiv id and DOI must resolve to the stated title and the quotation must
occur in the stated source; every repository must exist, not be a fork, carry the stated licence,
and hold every listed path at the stated commit.

A result that could not be fetched is reported as unverifiable, never as passed.

Sources: arxiv.org/help/api/user-manual (id_list, one request per three seconds);
docs.openalex.org (works by DOI, abstract_inverted_index); docs.github.com/graphql
(Repository.licenseInfo, Repository.object with an expression "rev:path").
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

HERE = Path(__file__).resolve().parent
USER_AGENT = "dawnr-research-validator/1.0"
GH = os.environ.get("GH_EXE", "gh")
ROOTS = [HERE.parents[2]]  # the dawnr checkout this file is in

SUBSYSTEMS = ("native-bmc", "spec-quality", "proof-backends", "repair-loop", "constrained-generation", "teacher-data",
              "small-model-training", "evaluation-method", "assistant-runtime", "flight-domain", "documents-reasoning")
PAPER_FLOORS = dict(zip(SUBSYSTEMS, (40, 35, 35, 25, 25, 25, 25, 15, 15, 5, 5)))
REPO_FLOORS = dict(zip(SUBSYSTEMS, (50, 20, 40, 15, 25, 15, 35, 15, 25, 5, 5)))
TIER_A_FLOOR = {"papers": 30, "repos": 40}
TARGET = 250
# The project's standing rule for code it would ship or train on (RESEARCH-2026-10-05-what-to-steal.md).
LICENSES = {"MIT", "Apache-2.0", "Apache-2.0 WITH LLVM-exception", "BSD-2-Clause", "BSD-3-Clause", "0BSD", "ISC", "CC0-1.0", "CC-BY-4.0"}

PAPER_REQUIRED = {"id", "title", "first_author", "year", "venue", "url", "subsystem", "tier", "read_depth", "claim", "quote",
                  "quote_source", "take", "dawnr_target", "mode"}
PAPER_OPTIONAL = {"code_url", "code_license", "falsifier", "gap_note"}
PAPER_MODES = {"steal-code", "lift-pattern", "build-from-paper", "measure-against"}
REPO_REQUIRED = {"repo", "url", "spdx", "license_basis", "commit", "pushed_at", "stars", "language", "subsystem", "tier", "read_depth",
                 "paths", "take", "mode", "dawnr_target", "why", "caveat"}
REPO_OPTIONAL = {"license_path", "license_quote", "falsifier", "code_note", "archived"}
REPO_MODES = {"dependency", "vendor-file", "lift-pattern", "compose"}
NOT_CODE = re.compile(r"(^|/)(readme|license|licence|copying|notice|changelog|contributing|authors)([._-][^/]*)?$|\.(md|rst|txt)$", re.I)


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(text).lower())


def squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", html.unescape(str(text)).lower())


def read_list(path: Path) -> tuple[list[dict], list[str]]:
    items, problems = [], []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except ValueError as error:
            problems.append(f"line {number}: not JSON: {error}")
            continue
        if not isinstance(item, dict):
            problems.append(f"line {number}: not an object")
            continue
        items.append(item)
    return items, problems


def known(name: str) -> set[str]:
    path = HERE / name
    return {line.strip().lower() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()} if path.exists() else set()


def target_problem(value) -> str | None:
    text = str(value)
    if text.startswith("new:"):
        relative = text[4:]
        if any((root / relative).exists() for root in ROOTS):
            return f"dawnr_target {text}: marked new but the path exists"
        if not any((root / relative).parent.is_dir() for root in ROOTS):
            return f"dawnr_target {text}: parent directory does not exist in dawnr"
        return None
    if not any((root / text).exists() for root in ROOTS):
        return f"dawnr_target {text}: no such path in dawnr (use new:PATH for a file to be created)"
    return None


def common(item: dict, label: str, required: set, optional: set, modes: set, depths: set) -> list[str]:
    missing, extra = required - set(item), set(item) - required - optional
    problems = [f"{label}: missing {sorted(missing)}"] if missing else []
    if extra:
        problems.append(f"{label}: unknown fields {sorted(extra)}")
    if missing:
        return problems
    if item["subsystem"] not in SUBSYSTEMS:
        problems.append(f"{label}: unknown subsystem {item['subsystem']}")
    if item["tier"] not in ("A", "B", "C"):
        problems.append(f"{label}: tier must be A, B or C")
    if item["mode"] not in modes:
        problems.append(f"{label}: unknown mode {item['mode']}")
    if item["read_depth"] not in depths:
        problems.append(f"{label}: read_depth must be one of {sorted(depths)}")
    if len(words(item["take"])) < 12:
        problems.append(f"{label}: take is under 12 words")
    problem = target_problem(item["dawnr_target"])
    if problem:
        problems.append(f"{label}: {problem}")
    if item["tier"] == "A":
        if not re.search(r"\d", str(item.get("falsifier", ""))):
            problems.append(f"{label}: tier A needs a falsifier that names a number")
        if item["read_depth"] not in ("method", "code"):
            problems.append(f"{label}: tier A must be read at method or code depth")
    return problems


def check_paper(item: dict, seen_known: set[str]) -> list[str]:
    label = str(item.get("id", "?"))
    problems = common(item, label, PAPER_REQUIRED, PAPER_OPTIONAL, PAPER_MODES, {"abstract", "method"})
    if not re.fullmatch(r"arXiv:(\d{4}\.\d{4,5}|[a-z-]+(\.[A-Z]{2})?/\d{7})|doi:10\.\d{4,9}/\S+", label):
        problems.append(f"{label}: id must be arXiv:ID without a version, or doi:10.x/y")
    if label.startswith("arXiv:") and label[6:].lower() in seen_known:
        problems.append(f"{label}: already cited in dawnr")
    if PAPER_REQUIRED - set(item):
        return problems
    if not isinstance(item["year"], int) or not 1960 <= item["year"] <= 2026:
        problems.append(f"{label}: implausible year {item['year']}")
    if item["quote_source"] not in ("abstract", "fulltext"):
        problems.append(f"{label}: quote_source must be abstract or fulltext")
    if not 6 <= len(words(item["quote"])) <= 45:
        problems.append(f"{label}: quote must be 6 to 45 words")
    if len(words(item["claim"])) < 8:
        problems.append(f"{label}: claim is under 8 words")
    if item.get("code_license") and item["code_license"] not in LICENSES and item["mode"] == "steal-code":
        problems.append(f"{label}: steal-code from a licence outside the allow-list ({item['code_license']})")
    if item["mode"] == "steal-code" and not item.get("code_url"):
        problems.append(f"{label}: steal-code needs code_url")
    return problems


def check_repo(item: dict, seen_known: set[str]) -> list[str]:
    label = str(item.get("repo", "?"))
    problems = common(item, label, REPO_REQUIRED, REPO_OPTIONAL, REPO_MODES, {"readme", "code"})
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", label):
        problems.append(f"{label}: repo must be owner/name")
    if label.lower() in seen_known:
        problems.append(f"{label}: already cited in dawnr")
    if REPO_REQUIRED - set(item):
        return problems
    if item["spdx"] not in LICENSES:
        problems.append(f"{label}: licence {item['spdx']} is outside the allow-list")
    if item["license_basis"] not in ("api", "file"):
        problems.append(f"{label}: license_basis must be api or file")
    if item["license_basis"] == "file" and not (item.get("license_path") and len(words(item.get("license_quote", ""))) >= 6):
        problems.append(f"{label}: a licence read from a file needs license_path and a license_quote of at least 6 words")
    if not re.fullmatch(r"[0-9a-f]{40}", str(item["commit"])):
        problems.append(f"{label}: commit must be 40 hex digits")
    if not isinstance(item["paths"], list) or not item["paths"]:
        problems.append(f"{label}: paths must list at least one file or directory to take")
    else:
        for path in item["paths"]:
            if NOT_CODE.search(str(path)):
                problems.append(f"{label}: path {path} is documentation, not code")
    for field in ("why", "caveat"):
        if len(words(item[field])) < 5:
            problems.append(f"{label}: {field} is under 5 words")
    return problems


def repeated_text(items: list[dict], key: str, id_key: str) -> list[str]:
    """Pairs whose take sentences are nearly the same word set: one sentence used for many entries."""
    sets = [(str(item.get(id_key, "?")), set(words(item.get("take", "")))) for item in items]
    problems = []
    for i, (left, a) in enumerate(sets):
        for right, b in sets[i + 1:]:
            if a and b and len(a & b) / len(a | b) >= 0.8:
                problems.append(f"{left} and {right}: take text is nearly identical")
    return problems


def http_get(url: str, timeout: float = 60, tries: int = 4) -> str | None:
    delay = 5.0
    for attempt in range(tries):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            if error.code in (404, 410):
                return None
            if error.code not in (403, 429, 500, 502, 503, 504) or attempt == tries - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == tries - 1:
                raise
        time.sleep(delay)
        delay *= 3
    return None


def same_title(stated: str, found: str) -> bool:
    return SequenceMatcher(None, squash(stated), squash(found)).ratio() >= 0.85


def fulltext(identifier: str) -> str | None:
    for url in (f"https://arxiv.org/html/{identifier}", f"https://ar5iv.labs.arxiv.org/html/{identifier}"):
        try:
            text = http_get(url, tries=2)
        except (urllib.error.URLError, TimeoutError):
            text = None
        time.sleep(1.0)
        if text and len(text) > 5000:
            return re.sub(r"<[^>]+>", " ", text)
    return None


def online_papers(items: list[dict]) -> tuple[list[str], list[str]]:
    errors, unverifiable = [], []
    arxiv = [item for item in items if str(item.get("id", "")).startswith("arXiv:")]
    found = {}
    for start in range(0, len(arxiv), 50):
        batch = [item["id"][6:] for item in arxiv[start:start + 50]]
        url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"id_list": ",".join(batch), "max_results": len(batch)})
        text = http_get(url)
        time.sleep(3.1)
        if text is None:
            continue
        namespace = {"a": "http://www.w3.org/2005/Atom"}
        for entry in ET.fromstring(text).findall("a:entry", namespace):
            match = re.search(r"abs/(.+?)(v\d+)?$", entry.findtext("a:id", "", namespace))
            if match:
                found[match.group(1)] = {"title": " ".join(entry.findtext("a:title", "", namespace).split()),
                                         "abstract": entry.findtext("a:summary", "", namespace),
                                         "year": int(entry.findtext("a:published", "0", namespace)[:4] or 0)}
    for item in items:
        label = str(item.get("id", "?"))
        if label.startswith("arXiv:"):
            record = found.get(label[6:])
            if record is None:
                errors.append(f"{label}: no such arXiv record")
                continue
        elif label.startswith("doi:"):
            text = http_get("https://api.openalex.org/works/doi:" + urllib.parse.quote(label[4:], safe="/"))
            time.sleep(0.2)
            if text is None:
                errors.append(f"{label}: DOI not found in OpenAlex")
                continue
            work = json.loads(text)
            pieces = {position: word for word, positions in (work.get("abstract_inverted_index") or {}).items() for position in positions}
            record = {"title": work.get("display_name") or "", "abstract": " ".join(pieces[key] for key in sorted(pieces)),
                      "year": work.get("publication_year") or 0}
        else:
            continue
        if not same_title(str(item.get("title", "")), record["title"]):
            errors.append(f"{label}: stated title differs from the record: {record['title'][:90]}")
        if isinstance(item.get("year"), int) and record["year"] and abs(item["year"] - record["year"]) > 1:
            errors.append(f"{label}: stated year {item['year']}, record says {record['year']}")
        quote = squash(item.get("quote", ""))
        if item.get("quote_source") == "abstract":
            if not record["abstract"]:
                unverifiable.append(f"{label}: source has no abstract to compare the quotation with")
            elif quote not in squash(record["abstract"]):
                errors.append(f"{label}: quotation is not in the abstract")
        elif label.startswith("arXiv:"):
            body = fulltext(label[6:])
            if body is None:
                unverifiable.append(f"{label}: no full text could be fetched for the quotation")
            elif quote not in squash(body):
                errors.append(f"{label}: quotation is not in the full text")
        else:
            unverifiable.append(f"{label}: a full-text quotation behind a DOI cannot be checked here")
    return errors, unverifiable


def graphql(query: str) -> dict:
    run = subprocess.run([GH, "api", "graphql", "--input", "-"], input=json.dumps({"query": query}), text=True, encoding="utf-8",
                         capture_output=True, timeout=180)
    # gh exits non-zero when a repository is missing but still prints the partial data.
    try:
        return json.loads(run.stdout)
    except ValueError as error:
        raise RuntimeError(f"gh graphql gave no JSON: {run.stderr[:300]}") from error


def online_repos(items: list[dict]) -> tuple[list[str], list[str]]:
    errors, unverifiable = [], []
    usable = [item for item in items if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", str(item.get("repo", "")))
              and re.fullmatch(r"[0-9a-f]{40}", str(item.get("commit", "")))]
    for start in range(0, len(usable), 20):
        batch = usable[start:start + 20]
        parts = []
        for index, item in enumerate(batch):
            owner, name = item["repo"].split("/")
            objects = "".join(f"p{k}: object(expression: {json.dumps(item['commit'] + ':' + str(path))}) {{ __typename }} "
                              for k, path in enumerate(item.get("paths") or []))
            if item.get("license_path"):
                objects += f"lic: object(expression: {json.dumps(item['commit'] + ':' + str(item['license_path']))}) {{ ... on Blob {{ text }} }} "
            parts.append(f"r{index}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) "
                         f"{{ nameWithOwner isFork licenseInfo {{ spdxId }} commit: object(oid: {json.dumps(item['commit'])}) {{ __typename }} {objects}}}")
        answer = graphql("query { " + " ".join(parts) + " rateLimit { remaining } }").get("data") or {}
        for index, item in enumerate(batch):
            label, record = item["repo"], answer.get(f"r{index}")
            if record is None:
                errors.append(f"{label}: repository not found")
                continue
            if record["nameWithOwner"].lower() != label.lower():
                errors.append(f"{label}: moved to {record['nameWithOwner']}")
            if record["isFork"]:
                errors.append(f"{label}: is a fork")
            if record.get("commit") is None:
                errors.append(f"{label}: commit {item['commit'][:12]} not found")
            spdx = (record.get("licenseInfo") or {}).get("spdxId")
            if item.get("license_basis") == "api" and spdx != item.get("spdx"):
                errors.append(f"{label}: stated {item.get('spdx')}, GitHub says {spdx}")
            if item.get("license_basis") == "file":
                text = (record.get("lic") or {}).get("text")
                if text is None:
                    errors.append(f"{label}: licence file {item.get('license_path')} not found at the commit")
                elif squash(item.get("license_quote", "")) not in squash(text):
                    errors.append(f"{label}: licence quotation is not in {item.get('license_path')}")
            for k, path in enumerate(item.get("paths") or []):
                if record.get(f"p{k}") is None:
                    errors.append(f"{label}: path {path} not found at {item['commit'][:12]}")
    return errors, unverifiable


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("kind", choices=("papers", "repos"))
    parser.add_argument("file", type=Path)
    parser.add_argument("--online", action="store_true", help="check every entry against the live sources")
    parser.add_argument("--final", action="store_true", help="also require the target count and the tier A floor")
    parser.add_argument("--allow-known", action="store_true", help="for the validator's own tests")
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--show", type=int, default=40, help="problems to print")
    args = parser.parse_args(argv)

    items, problems = read_list(args.file)
    id_key = "id" if args.kind == "papers" else "repo"
    seen_known = set() if args.allow_known else known("known-arxiv.txt" if args.kind == "papers" else "known-repos.txt")
    check = check_paper if args.kind == "papers" else check_repo
    for item in items:
        problems += check(item, seen_known)
    identifiers = Counter(str(item.get(id_key, "?")).lower() for item in items)
    problems += [f"{key}: listed {count} times" for key, count in identifiers.items() if count > 1]
    if args.kind == "papers":
        titles = Counter(squash(item.get("title", "")) for item in items)
        problems += [f"title listed {count} times: {key[:60]}" for key, count in titles.items() if count > 1 and key]
    problems += repeated_text(items, "take", id_key)

    unverifiable = []
    if args.online:
        online_errors, unverifiable = (online_papers if args.kind == "papers" else online_repos)(items)
        problems += online_errors

    bad = {match.group(0).lower() for problem in problems for match in [re.match(r"\S+", problem)] if match}
    valid = [item for item in items if str(item.get(id_key, "?")).lower().rstrip(":") not in {b.rstrip(":") for b in bad}]
    by_subsystem = Counter(item.get("subsystem", "?") for item in items)
    by_tier = Counter(item.get("tier", "?") for item in items)
    floors = PAPER_FLOORS if args.kind == "papers" else REPO_FLOORS
    thin = {name: f"{by_subsystem.get(name, 0)}/{floor}" for name, floor in floors.items() if by_subsystem.get(name, 0) < floor}
    if args.final:
        if len(items) < TARGET:
            problems.append(f"count: {len(items)} entries, target {TARGET}")
        if by_tier.get("A", 0) < TIER_A_FLOOR[args.kind]:
            problems.append(f"tier: {by_tier.get('A', 0)} tier A entries, floor {TIER_A_FLOOR[args.kind]}")

    summary = {"kind": args.kind, "entries": len(items), "entries_without_problems": len(valid), "problems": len(problems),
               "unverifiable": len(unverifiable), "online": args.online, "final": args.final, "by_subsystem": dict(sorted(by_subsystem.items())),
               "by_tier": dict(sorted(by_tier.items())), "below_floor": thin, "input_sha256": hashlib.sha256(args.file.read_bytes()).hexdigest()}
    print(json.dumps(summary, indent=1))
    for problem in problems[:args.show]:
        print("PROBLEM", problem)
    if len(problems) > args.show:
        print(f"... and {len(problems) - args.show} more problems")
    for note in unverifiable[:args.show]:
        print("UNVERIFIABLE", note)
    if args.receipt:
        args.receipt.write_text(json.dumps({**summary, "problem_list": problems, "unverifiable_list": unverifiable}, indent=1) + "\n", encoding="utf-8")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
