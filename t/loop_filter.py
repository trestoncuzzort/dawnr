#!/usr/bin/env python3
"""t/loop_filter.py -- locallm builds models, t filters what they learn from (2026-09-16).

Round 0: locallm builds a model from random numbers on a starting corpus
(--corpus-file, e.g. t/out/loop-locallm/corpus.txt from loop_locallm.py corpus,
or --source spec-experiment dirs for the raw 27B output). Each round: sample N programs from "t 0\\n"; keep a
sample's first prefix ending at a "}" line that parses; well-formedness check;
drop exact copies of a training task or of an earlier sample (canonical AST with
the name erased); grade the novel ones in all seven kernels with twins (run_par);
CLEAN = verified / refuted in all seven. The next round trains from scratch on
every clean task found so far (the filtered water) and samples again.
Printed per round: samples, parsed, well-formed, novel, clean in all seven, clean
in at least one, and the clean share of all samples.
"""
import argparse, json, os, re, subprocess, sys, time
from dataclasses import dataclass
from pathlib import Path
T = Path(__file__).resolve().parent; LL = T.parent / "locallm"
sys.path.insert(0, str(T)); sys.path.insert(1, str(LL))
import spec_experiment as se, surface, fuzz_lower
# this lab machine's kernel install paths, prepended when present; elsewhere PATH as is
PATH = ("{h}/.cargo/bin:{h}/.opam/default/bin:{h}/.elan/bin:{h}/.local/fstar/fstar/bin:"
        "{h}/.local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin:{h}/.local/verus/verus-x86-linux:").format(h=Path.home())


_FAMILY_BASE = {"mbpp": 0, "dafny_synthesis_task_id": 0, "dafny-synthesis_task_id": 0,
                "he": se.HUMANEVAL_BASE, "apps": se.APPS_BASE}
_FAMILY = r"(mbpp|he|apps|dafny[_-]synthesis_task_id)_(\d+)"
_NAME = re.compile(_FAMILY + r"(?=__|[^A-Za-z0-9_]|$)")
_NAME_IN_TEXT = re.compile(r"(?<![A-Za-z0-9_])(" + _FAMILY + r"(?:__[A-Za-z0-9_]*)?)(?![A-Za-z0-9_])")


def problem_id(name) -> int | None:
    """Return the pool id named by a task, if any."""
    if not isinstance(name, str):
        return None
    match = _NAME.match(name)
    return _FAMILY_BASE[match.group(1)] + int(match.group(2)) if match else None


def problem_ids_in(text: str) -> dict[int, set[str]]:
    """Return every pool id and spelling found in text."""
    found: dict[int, set[str]] = {}
    for match in _NAME_IN_TEXT.finditer(text or ""):
        found.setdefault(_FAMILY_BASE[match.group(2)] + int(match.group(3)), set()).add(match.group(1))
    return found


def held_out_ids_in(text: str, held_out: set[int]) -> dict[int, set[str]]:
    """Return held-out pool ids and spellings found in text."""
    return {task_id: names for task_id, names in problem_ids_in(text).items() if task_id in held_out}


def task_names(text: str) -> list[str]:
    """Return task names declared in text."""
    return re.findall(r"(?m)^task\s+([A-Za-z_][A-Za-z0-9_]*)", text or "")


@dataclass(frozen=True)
class Decontamination:
    drop_document_names: frozenset[str]
    exclude_train_ids: frozenset[int]
    overlap_eval_ids: frozenset[int]


def decontamination(path: Path = T / "decontamination-2026-09-21.json") -> Decontamination:
    """Load the checked-in same-task exclusions for future corpora and scoring."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        documents = data["drop_documents"]
        train_ids = data["exclude_future_train_ids"]
        overlap_ids = data["overlap_ids"]
        if not isinstance(documents, dict) or not isinstance(train_ids, list) or not isinstance(overlap_ids, list):
            raise TypeError("expected drop_documents and two id lists")
        names = set()
        for source in documents:
            if not isinstance(source, str):
                raise TypeError("a document source is not a string")
            _, separator, name = source.partition(":")
            if not separator or not name:
                raise ValueError(f"invalid document source {source!r}")
            names.add(name)
        if len(names) != len(documents):
            raise ValueError("document sources do not name distinct tasks")
        return Decontamination(frozenset(names), frozenset(int(value) for value in train_ids),
                               frozenset(int(value) for value in overlap_ids))
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read decontamination policy {path}") from error


HEAD_LINE = re.compile(r"^(?:Problem|Signature|Example): .*\n", re.M)


def strip_head(doc: str) -> str:
    """Remove every head line this project writes, not just the two it wrote first.

    The corpus grew a `Signature:` line on 2026-09-19 and an `Example:` line the
    same evening. A stripper that knows only `Problem:` and `Signature:` leaves
    the rest in front of the program, `surface.parse` fails, and the document
    vanishes from the copy check without a word.
    """
    out = doc
    while True:
        stripped = HEAD_LINE.sub("", out, count=1)
        if stripped == out:
            return out
        out = stripped

def key(task):
    # The program with its name, format version and gate erased: none of the
    # three changes what the kernels check. Until 2026-09-17 the version
    # stayed in the key, so a sample written as `t 1` never matched a `t 0`
    # corpus document it copied exactly (the 27B answers are `t 0`); recounted
    # on 2026-09-16's committed rounds, 17 of clean r0's 46 and 26 of r1's 57
    # were such copies (t/runs/2026-09-17/README.md).
    t = se.rename_task(__import__("copy").deepcopy(task), "x_task")
    t.pop("gate", None); t["t"] = 1
    return surface.canon(t)

def split_docs(text):
    return [d.strip() + "\n" for d in re.split(r"(?m)^t 0\s*$", text) if d.strip()]

HEADER = re.compile(r"(?m)^t \d+\s*$")

def first_task(sample):
    m = HEADER.search(sample)
    lines = sample[m.start():].split("\n") if m else sample.split("\n")
    for i, l in enumerate(lines):
        if l.strip() == "}":
            try:
                return surface.parse("\n".join(lines[:i + 1]) + "\n")
            except Exception:
                pass
    return None

def train(corpus_txt, out, steps, log):
    subprocess.run([sys.executable, "train.py", "--data", str(corpus_txt), "--out", str(out),
                    "--steps", str(steps), "--seed", "1337"], cwd=LL, check=True,
                   stdout=open(log, "w"), stderr=subprocess.STDOUT)
    subprocess.run(["git", "checkout", "--", "locallm/runs.jsonl"], cwd=LL.parent)

def sample(out, n, seed, header):
    import torch, checkpoint
    torch.manual_seed(seed)
    model, tok, _ = checkpoint.load_checkpoint(str(out))
    return [checkpoint.sample(model, tok, header, 700, temperature=0.8, top_k=40) for _ in range(n)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", nargs="*", default=[], help="spec-experiment dirs whose raw replies are the dirty source")
    ap.add_argument("--corpus-file", default="", help="start from this corpus instead (documents split at blank lines before a header)")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--samples", type=int, default=500)
    ap.add_argument("--steps", type=int, default=1500)
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument("--work", default=str(T / "out" / "loop-filter"))
    a = ap.parse_args()
    W = Path(a.work).resolve(); W.mkdir(parents=True, exist_ok=True)   # absolute: train() runs locallm/train.py from locallm/
    src = []
    for d in a.source:
        for f in sorted(Path(d, "raw").glob("*.json")):
            b = se.find_block(json.loads(f.read_text())["reply"])
            if b:
                src.append(b.strip() + "\n")
    if a.corpus_file:
        text = Path(a.corpus_file).read_text()
        src = [d.strip() + "\n"
               for d in re.split(r"\n\s*\n(?=Problem: |Signature: |t \d)", text) if d.strip()]
    corpus = src
    seen, unparsed = set(), 0
    for doc in src:
        try:
            seen.add(key(surface.parse(strip_head(doc))))
        except Exception:
            # Counted, not swallowed: a document that does not parse is a
            # document missing from the copy check, and a silent miss lets a
            # duplicate through the filter this file exists to be.
            unparsed += 1
    clean = []
    print(f"source: {len(src)} blocks, {sum(map(len, src))} chars, {len(seen)} parse"
          + (f", {unparsed} DID NOT PARSE and are absent from the copy check" if unparsed else ""),
          flush=True)
    seed_docs = list(corpus)
    for r in range(a.rounds):
        R = W / f"r{r}"; R.mkdir(exist_ok=True)
        if (R / "kernels.md").exists() and (R / "samples.json").exists() and (R / "tasks").is_dir():
            # a round whose grading finished: reuse its samples and verdicts
            names = {f.stem: f.read_text() for f in (R / "tasks").glob("*.t")}
            for body in names.values():
                try:
                    seen.add(key(surface.parse(body)))
                except Exception:
                    unparsed += 1
            print(f"round {r}: resumed from {R} ({len(names)} novel samples graded)", flush=True)
        else:
            (R / "corpus.txt").write_text("\n".join(corpus))
            train(R / "corpus.txt", R / "model", a.steps, R / "train.log")
            from collections import Counter
            header = Counter(d.split("\n", 1)[0] for d in corpus if not d.startswith("Problem: ")).most_common(1)[0][0] + "\n"
            texts = sample(R / "model", a.samples, 100 + r, header)
            (R / "samples.json").write_text(json.dumps(texts))
            parsed = wf = novel = 0
            tdir = R / "tasks"; tdir.mkdir(exist_ok=True)
            names = {}
            for i, s in enumerate(texts):
                task = first_task(s)
                if task is None: continue
                parsed += 1
                name = f"r{r}_s{i}"
                try:
                    task = se.rename_task(task, name)
                    if fuzz_lower.check_wf(task): continue
                except Exception:
                    continue
                wf += 1
                k = key(task)
                if k in seen: continue
                seen.add(k); novel += 1
                (tdir / f"{name}.t").write_text(surface.print_task(task))
                names[name] = surface.print_task(task)
            print(f"round {r}: corpus {len(corpus)} docs; samples {a.samples}, parsed {parsed}, well-formed {wf}, novel {novel}", flush=True)
            if novel:
                env = dict(os.environ, PATH=PATH + os.environ.get("PATH", ""))
                subprocess.run(["python3", "run_par.py", "--jobs", str(a.jobs), "--tasks", str(tdir), "--out", str(R / "kernels"),
                                "--table", str(R / "kernels.md")], cwd=T, env=env, stdout=open(R / "grade.log", "w"),
                               stderr=subprocess.STDOUT)
        c7 = c1 = 0; new = []
        if (R / "kernels.md").exists():
            for l in (R / "kernels.md").read_text().splitlines():
                m = re.match(r"\| (r\d+_s\d+) \|(.*)\|\s*$", l)
                if not m or m.group(1) not in names: continue
                cells = [x.strip() for x in m.group(2).split("|")][:7]
                good = sum(x == "verified / refuted" for x in cells)
                c1 += good >= 1
                if good == 7:
                    c7 += 1; new.append(names[m.group(1)])
        clean += new
        print(f"round {r}: clean in all seven {c7}, in at least one {c1}; clean share of samples {c7}/{a.samples}; clean pool {len(clean)}", flush=True)
        if not clean:
            print("no clean tasks: the filter passed nothing; stopping", flush=True); break
        # the next model is built from the seed water plus every clean sample so far
        corpus = seed_docs + clean
    print("LOOP_DONE", flush=True)

if __name__ == "__main__":
    main()
