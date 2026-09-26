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
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping
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
    # 2026-09-25: which policy file excluded each train id, by file name, so a
    # refusal can say whether an id is a same-task reading (2026-09-21) or a
    # behavioural twin (t/behavioural_decontam.py); and the held-out ids that
    # have such a twin in training, for a scorer that splits held-out results
    # by similarity. The clean 200 stay defined by overlap_eval_ids alone, so
    # every arm scored before this file remains comparable.
    excluded_by: Mapping[int, tuple[str, ...]] = field(default_factory=dict, hash=False)
    behavioural_overlap_eval_ids: frozenset[int] = frozenset()


BEHAVIOURAL_POLICY = T / "decontamination-behavioural-2026-09-25.json"
# t/behavioural_decontam.SCHEMA. 2 since the review of 2026-09-25: an own input a
# reference did not answer leaves the count (HyClone, https://arxiv.org/html/2508.01357v1,
# drops such inputs), and a pair the rule left undecided carries a reading by
# hand, `read_by_hand`, whose same-function rows are excluded like duplicates.
BEHAVIOURAL_SCHEMA = 2
BEHAVIOURAL_SAME = "same function"


def _behavioural_exclusions(path: Path) -> tuple[frozenset[int], frozenset[int]]:
    """The train ids t/behavioural_decontam.py excluded, and the held-out ids they twin.

    Refused by name when the file is missing or does not describe what it
    claims: a policy that silently loads as empty would let every behavioural
    twin back into the corpus, which is the failure this file exists to stop
    (Riddell et al., https://ar5iv.labs.arxiv.org/html/2403.04811; Soft
    Contamination, https://arxiv.org/html/2602.12413v1)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != BEHAVIOURAL_SCHEMA:
        raise TypeError(f"schema {data.get('schema')!r} is not {BEHAVIOURAL_SCHEMA}")
    rule, ids, duplicates = data.get("rule"), data.get("exclude_train_ids"), data.get("duplicates")
    read_by_hand, undecided = data.get("read_by_hand"), data.get("undecided")
    if (not isinstance(rule, dict) or not isinstance(ids, list) or not isinstance(duplicates, list)
            or not isinstance(read_by_hand, list) or not isinstance(undecided, list)):
        raise TypeError("expected rule, exclude_train_ids, duplicates, read_by_hand and undecided")
    unread = [row for row in undecided if row.get("reading") not in (BEHAVIOURAL_SAME, "different function")]
    if unread:
        # a pair the rule could not decide is not admitted by default: it is read, or the file is refused
        raise ValueError(f"{len(unread)} undecided pair(s) have no reading by hand, e.g. "
                         f"{unread[0].get('train_id')} vs {unread[0].get('eval_id')}")
    excluded = frozenset(int(value) for value in ids)
    listed = (frozenset(int(row["train_id"]) for row in duplicates)
              | frozenset(int(row["train_id"]) for row in read_by_hand if row.get("reading") == BEHAVIOURAL_SAME))
    if excluded != listed:
        raise ValueError("exclude_train_ids does not equal the train ids of the listed duplicates and same-function readings")
    return excluded, frozenset(int(value) for value in data.get("behavioural_overlap_eval_ids", []))


def decontamination(path: Path = T / "decontamination-2026-09-21.json",
                    behavioural_path: Path | None = BEHAVIOURAL_POLICY) -> Decontamination:
    """Load the checked-in exclusions for future corpora and scoring: the same-task
    list read by hand (2026-09-21) merged with the behavioural duplicates computed
    by t/behavioural_decontam.py (2026-09-25) and the pairs its rule left
    undecided that were read by hand as the same function. `behavioural_path=None` loads the
    first file alone; the default path must exist."""
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
        same_task = frozenset(int(value) for value in train_ids)
        overlap = frozenset(int(value) for value in overlap_ids)
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read decontamination policy {path}") from error
    excluded_by = {task_id: (Path(path).name,) for task_id in same_task}
    behavioural, behavioural_evals = frozenset(), frozenset()
    if behavioural_path is not None:
        try:
            behavioural, behavioural_evals = _behavioural_exclusions(Path(behavioural_path))
        except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
            raise ValueError(f"cannot read behavioural decontamination policy {behavioural_path}: "
                             f"{type(error).__name__}: {error}") from error
        for task_id in behavioural:
            excluded_by[task_id] = excluded_by.get(task_id, ()) + (Path(behavioural_path).name,)
    return Decontamination(frozenset(names), same_task | behavioural, overlap,
                           MappingProxyType(excluded_by), behavioural_evals)


def r12_dev_ids(path: Path = T / "r12-dev-ids.json", split_path: Path | str | None = None) -> frozenset[int]:
    """The dev-split ids (t/r12-dev-ids.json, written by t/r12_data_queue.sh
    dev-ids) that choose the fine-tune's stopping step by tests passed, and so
    must never be trained on. They belong to one split: the file records the
    digest of the split it was drawn from, and for any other split there are no
    dev ids, so a corpus built or checked against another split is unchanged.
    A missing file means no dev ids; a malformed one is refused by name."""
    import hashlib
    path = Path(path)
    if not path.exists():
        return frozenset()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        ids = frozenset(int(value) for value in data["dev_ids"])
        recorded = data["inputs"]["split_sha256"]
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read the dev-split ids {path}") from error
    if split_path is None:
        return ids
    try:
        actual = hashlib.sha256(Path(split_path).read_bytes()).hexdigest()
    except OSError:
        return frozenset()
    return ids if actual == recorded else frozenset()


# Evaluation data must stay unseen during development, including instruction
# tuning, not merely be excluded from the final score (Sainz et al., 2023,
# https://arxiv.org/abs/2310.18018, sections 1 and 3). The policy is therefore
# applied at every point where bytes can become training data. We inspect both
# text aliases and producer-supplied task_id fields: a row renamed after export
# must not turn a known held-out or same-task item into an untraceable one.
@dataclass(frozen=True)
class TrainingDataValidation:
    """All policy violations found in one prospective training input."""

    held_out: dict[int, frozenset[str]]
    same_task_names: frozenset[str]
    same_task_ids: frozenset[int]

    @property
    def ok(self) -> bool:
        return not (self.held_out or self.same_task_names or self.same_task_ids)


def _as_task_id(value: object) -> int | None:
    """Return a JSON task id without treating bool as the integer 0 or 1."""
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def validate_training_data(text: str, eval_ids: Iterable[int], *,
                           names: Iterable[str | None] = (),
                           task_ids: Iterable[object] = (),
                           policy: Decontamination | None = None) -> TrainingDataValidation:
    """Validate a prospective training document, corpus, or decoded JSONL row.

    Callers pass producer metadata separately because a JSONL task_id can still
    identify a held-out item after a task body or display name was renamed.
    This is deliberately a pure report rather than an exception: corpus
    assembly drops bad documents, while preflight and continuation refuse them.
    """
    policy = policy or decontamination()
    eval_ids = frozenset(int(task_id) for task_id in eval_ids)
    seen_names = set(task_names(text))
    seen_names.update(name for name in names if isinstance(name, str) and name)
    found = {task_id: set(spellings) for task_id, spellings in problem_ids_in(text).items()}
    for name in seen_names:
        task_id = problem_id(name)
        if task_id is not None:
            found.setdefault(task_id, set()).add(name)
    for raw_id in task_ids:
        task_id = _as_task_id(raw_id)
        if task_id is not None:
            found.setdefault(task_id, set()).add(f"task_id={task_id}")
    held = {task_id: frozenset(spellings) for task_id, spellings in found.items()
            if task_id in eval_ids}
    return TrainingDataValidation(
        held_out=held,
        same_task_names=frozenset(seen_names & policy.drop_document_names),
        same_task_ids=frozenset(set(found) & policy.exclude_train_ids),
    )


def held_out_detail(held: dict[int, frozenset[str]] | dict[int, set[str]]) -> str:
    """A stable, short diagnostic for held-out aliases and explicit ids."""
    rows = [f"{task_id} ({', '.join(sorted(spellings))})"
            for task_id, spellings in sorted(held.items())]
    return f"{len(held)} held-out id(s): {rows[:5]}" + (" ..." if len(rows) > 5 else "")


def same_task_detail(validation: TrainingDataValidation) -> str:
    """A stable, short diagnostic for the checked-in A2 exclusions."""
    rows = (sorted(validation.same_task_names)
            + [f"task_id={task_id}" for task_id in sorted(validation.same_task_ids)])
    return f"{len(rows)} same-task source(s): {rows[:5]}" + (" ..." if len(rows) > 5 else "")


@dataclass
class TrainingDataGate:
    """A corpus-builder view of validate_training_data that records dropped rows."""

    eval_ids: frozenset[int]
    policy: Decontamination = field(default_factory=decontamination)
    held: list[str] = field(default_factory=list)
    decontaminated: list[str] = field(default_factory=list)

    def admit(self, text: str, names: Iterable[str | None] = (),
              task_ids: Iterable[object] = ()) -> bool:
        names = [name for name in names if isinstance(name, str) and name]
        task_ids = list(task_ids)
        result = validate_training_data(text, self.eval_ids, names=names, task_ids=task_ids,
                                        policy=self.policy)
        label = "/".join(names) or next(iter(text.strip().splitlines()), "<unnamed>")
        if result.held_out:
            self.held.append(f"{label[:60]} ({', '.join(map(str, sorted(result.held_out)))})")
        if result.same_task_names or result.same_task_ids:
            detail = (sorted(result.same_task_names)
                      + [f"task_id={task_id}" for task_id in sorted(result.same_task_ids)])
            self.decontaminated.append(f"{label[:60]} ({', '.join(detail)})")
        return result.ok

# The head lines t/loop_locallm.py writes in front of a program: Problem: and
# Signature: (2026-09-19), Example: (the same evening), and Spec: (2026-09-25),
# the marker of a specification document (loop_locallm.py corpus --spec-docs):
# the same head, this one line with nothing after the colon, then the task's
# declaration and its requires/ensures clauses with no body. It is a second
# document beside the program, never a prefix inside it: Distilling
# Step-by-Step, https://ar5iv.labs.arxiv.org/html/2305.02301, Table 2, trains
# the extra target as its own task (ANLI 49.58) and measures it folded into
# the answer's sequence at 43.50, under the plain finetune's 43.58.
SPEC_LINE = "Spec:\n"
HEAD_LINE = re.compile(r"^(?:(?:Problem|Signature|Example): .*|Spec:)\n", re.M)


def is_spec_document(doc: str) -> bool:
    """True for a document that carries the Spec: marker: a specification with
    no body. Such a document has no program to key: what strip_head leaves of
    it is a declaration that surface.parse refuses (`expected '{'`), first_task
    finds no closing brace, and key() is never reached. A reader that computes
    recitation keys asks here first, so a spec document is counted as what it
    is instead of as a parse failure."""
    return bool(re.search(r"(?m)^Spec:\n", doc))


def strip_head(doc: str) -> str:
    """Remove every head line this project writes, not just the two it wrote first.

    The corpus grew a `Signature:` line on 2026-09-19 and an `Example:` line the
    same evening. A stripper that knows only `Problem:` and `Signature:` leaves
    the rest in front of the program, `surface.parse` fails, and the document
    vanishes from the copy check without a word. The `Spec:` line (2026-09-25)
    is stripped the same way; what remains of a spec document is a declaration
    without a body, which is not a program (see is_spec_document).
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
