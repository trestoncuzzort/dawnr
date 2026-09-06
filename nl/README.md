# nl: programming problems with solutions, four public sources

**24,748 problems, 23,319 of them (94.2%) carrying reference solutions.** Normalised to
one gzipped JSONL per split, one JSON object per line.

Counts and checksums in [`manifest.json`](manifest.json) are measured from these exact
files. Nothing here is copied from upstream documentation.

Merged into tup on 2026-09-06 from the standalone repo `nl-problems` at commit
`5a8e03f85ee37225dfd7621d3e79b4be8dda5994`, byte for byte: all ten files were verified
against `manifest.json` on arrival, both the gzipped and the decompressed SHA-256, plus
every record count and byte count. Fifty checks, fifty passes. The standalone repo's
`.gitattributes` and `.gitignore` were folded into tup's own and not carried over; nothing
else was dropped.

Why it is here: this is the 24,748-problem corpus that any coverage claim about the t
lifter would eventually be measured against. See [`FIDELITY.md`](FIDELITY.md) for why no
such number means anything until the lifter is shown to preserve meaning on the simplest
tasks first.

## Files

| file | records | with solutions | raw | gzipped |
|---|---:|---:|---:|---:|
| `data/apps_raw_test.jsonl.gz` | 5,000 | 3,765 (75.3%) | 1,292.4 MB | 429.1 MB |
| `data/apps_raw_train.jsonl.gz` | 5,000 | 5,000 (100%) | 107.1 MB | 26.0 MB |
| `data/codecontests_train.jsonl.gz` | 13,328 | 13,134 (98.5%) | 2,360.6 MB | 497.5 MB |
| `data/codecontests_test.jsonl.gz` | 165 | 165 (100%) | 40.7 MB | 5.9 MB |
| `data/codecontests_valid.jsonl.gz` | 117 | 117 (100%) | 49.3 MB | 3.6 MB |
| `data/mbpp_test.jsonl.gz` | 500 | 500 (100%) | 0.3 MB | 0.1 MB |
| `data/mbpp.jsonl.gz` | 374 | 374 (100%) | 0.2 MB | 0.0 MB |
| `data/mbpp_validation.jsonl.gz` | 90 | 90 (100%) | 0.0 MB | 0.0 MB |
| `data/mbpp_prompt.jsonl.gz` | 10 | 10 (100%) | 0.0 MB | 0.0 MB |
| `data/humaneval.jsonl.gz` | 164 | 164 (100%) | 0.2 MB | 0.0 MB |
| **total** | **24,748** | **23,319 (94.2%)** | **3,850.9 MB** | **962.3 MB** |

The 1,429 problems without solutions are not an oversight: 1,235 are APPS test problems
whose solutions are withheld in the split as shipped, and 194 are CodeContests train
problems that carry none upstream.

## Reading it

Gzip costs nothing at read time stream it, never decompress to disk:

```python
import gzip, json

with gzip.open("data/codecontests_train.jsonl.gz", "rt") as f:
    for line in f:
        rec = json.loads(line)
        print(rec["name"], len(rec["solutions"]), "solutions")
```

To clone (the data is in Git LFS, since `apps_raw_test.jsonl` alone is 1.29 GB and GitHub
caps single files at 100 MB):

```bash
git lfs install
git clone <repo-url>
git lfs pull          # if data/ files arrive as pointer stubs
```

## Schemas

**CodeContests** (`codecontests_*`) Codeforces, CodeChef, AtCoder, HackerEarth, Aizu.

| field | type | notes |
|---|---|---|
| `name` | str | problem slug |
| `description` | str | problem statement |
| `source` | str | `CODEFORCES` \| `CODECHEF` \| `ATCODER` \| `HACKEREARTH` \| `AIZU` \| `UNKNOWN_SOURCE` |
| `difficulty` | int | raw upstream code, kept for compatibility |
| `difficulty_label` | str | decoded: `EASY`…`HARDEST`, or the contest letter `A`–`V` |
| `cf_rating`, `cf_points` | int, float | `0` where unknown |
| `cf_tags` | list[str] | e.g. `["greedy","math"]` |
| `cf_contest_id`, `cf_index` | int, str | |
| `public_tests` | list[{input,output}] | the samples shown in the statement |
| `private_tests` | list[{input,output}] | **held-out judge tests** |
| `generated_tests` | list[{input,output}] | **generated judge tests** the bulk of the test data |
| `solutions` | list[{language,solution}] | correct, **capped at 25** see below |
| `incorrect_solutions` | list[{language,solution}] | **wrong** submissions, capped at 25 |
| `time_limit_seconds`, `time_limit_nanos`, `memory_limit_bytes` | int | |
| `input_file`, `output_file` | str | usually empty (stdin/stdout) |
| `is_description_translated`, `untranslated_description` | bool, str | |

`language` is one of `PYTHON3`, `PYTHON`, `CPP`, `JAVA`, `UNKNOWN_LANGUAGE` decoded to
strings here, not the raw ClassLabel integers.

`incorrect_solutions` is worth calling out: these are human-written *wrong* answers to
problems whose correct answers sit in the same record. That is a ready-made preference
signal chosen/rejected pairs grounded in a real judge rather than in a model's opinion.

**APPS** (`apps_raw_*`) scraped with judge data.

| field | type | notes |
|---|---|---|
| `id` | int | index within split |
| `question` | str | problem statement |
| `solutions` | str | **JSON-encoded string** holding a list parse a second time |
| `input_output` | str | **JSON-encoded string** `{"inputs":[…],"outputs":[…]}` |
| `difficulty` | str | `introductory` \| `interview` \| `competition` |
| `url` | str | originating problem page |
| `starter_code` | str | often empty |

Mind the double encoding: `json.loads(rec["input_output"])` is required. CodeContests
does *not* share this quirk its tests are real nested objects.

**HumanEval** 164 records, matching the canonical size.

| field | type | notes |
|---|---|---|
| `task_id` | str | e.g. `HumanEval/0` |
| `prompt` | str | signature + docstring |
| `canonical_solution` | str | body only, not the full function |
| `test` | str | `check(candidate)` harness |
| `entry_point` | str | function to call |

**MBPP** (`mbpp`, `mbpp_test`, `mbpp_validation`, `mbpp_prompt`) all four upstream
splits of the `full` config.

| field | type |
|---|---|
| `task_id` | int |
| `text` | str |
| `code` | str |
| `test_list` | list[str] |

## The solution cap, and how to lift it

CodeContests upstream holds **4,494,491 correct and 8,715,949 incorrect solutions**
20.93 GB as JSONL, which does not fit in GitHub LFS. Solutions are 92.3% of that bulk
(`incorrect_solutions` 63.4%, `solutions` 28.9%); all the test data together is 7.5%.

So the cap falls only on solutions. **Every problem, and every test, is here in full**
all 1,307,729 public, private and generated tests. Solutions are capped at 25 correct and
25 incorrect per problem, preferring `PYTHON3` > `PYTHON` > `CPP` > `JAVA`, which retains
296,828 correct and 272,311 incorrect.

To rebuild the uncapped 20.93 GB version:

```bash
python scripts/rebuild_codecontests_full.py --out ./cc_full
```

It downloads ~7.6 GB of parquet and writes ~20.9 GB of JSONL, with identical field
semantics and ClassLabel decoding. The shipped files are a strict subset: same rows, same
keys, fewer entries in the two solution lists.

## Provenance and licensing read before redistributing

| source | upstream | licence |
|---|---|---|
| CodeContests | `deepmind/code_contests` | CC-BY-4.0 |
| APPS | `codeparrot/apps` | MIT |
| MBPP | `google-research-datasets/mbpp` | CC-BY-4.0 |
| HumanEval | `openai/openai_humaneval` | MIT |

Licences are as declared on HuggingFace and have **not** been independently reviewed. Note
separately that problem *statements* from Codeforces, AtCoder, CodeChef and Aizu carry the
original judges' copyright, which is not the dataset authors' to relicense.

**This directory is not tup's to relicense, and tup's MIT licence does not reach it.** tup
is private today; `nl/` was imported on that basis. It is excluded from the publish
whitelist in `forge/sync_public.py`, which is allow-only, so it cannot reach a public
mirror by omission, only by someone adding it on purpose. Before tup is made public
again, `nl/` is either removed from the tree or cleared on its own terms; the four upstream
licences above are BY, not NC, so redistribution with attribution is arguable, but the
judges' statement copyright is the part nobody here has cleared. Check the terms before
republishing, redistributing outside the lab, or shipping any of it in a public model
release.

## Known limitations

- **Cross-source duplication is measured, not removed.** `scripts/corpus_audit.py`
  normalises every problem statement (casefold, drop punctuation, collapse whitespace) and
  hashes it. Of 24,747 statements, 23,336 are distinct; 1,356 duplicate groups hold 2,767
  records, **11.18% of the corpus**. 362 of those groups cross a source boundary and
  **every one of them is APPS against CodeContests**, which is what this entry always
  suspected and now knows. The other 994 are duplicates inside a single source. Byte
  equality after normalisation is a FLOOR: it catches verbatim reuse and misses paraphrase,
  so the real overlap is larger. Nothing is deduplicated; the numbers are here so a
  training run can decide.
- **Decontamination is bounded inside this corpus only.** Of HumanEval's 164, **0** appear
  in any trainable split here. Of `mbpp_test`'s 500, **3 (0.6%)** do. That is the whole of
  what a local computation can settle. These benchmarks sit inside many pretraining
  corpora, and no amount of hashing in this repo speaks to that; evaluating on `humaneval`
  or `mbpp_test` after training on public text is contaminated until someone proves
  otherwise.
- **Nothing has been executed.** No solution was run against its own tests to confirm it
  passes, and no `incorrect_solution` was run to confirm it fails. Both labels are taken
  on upstream's word.
- **`incorrect_solutions` are not labelled by failure mode** a wrong answer, a timeout
  and a compile error are not distinguished.

## Integrity

`manifest.json` records per file: record count, and SHA-256 of both the raw `.jsonl` and
the shipped `.jsonl.gz`.

```bash
gunzip -c data/mbpp.jsonl.gz | sha256sum     # compare to raw_sha256
sha256sum data/mbpp.jsonl.gz                 # compare to gz_sha256
```

To re-verify every file at once, both hashes, the record counts and the byte counts:

```bash
python3 scripts/verify_manifest.py           # 50 checks; exit 1 on any mismatch
```

Last run 2026-09-06 on the merge into tup: 50 of 50 passed.
