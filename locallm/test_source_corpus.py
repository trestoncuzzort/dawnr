"""Exercise attribution, splitting, exclusion, and reproducibility on real local Git trees."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import build_source_corpus as corpus


def command(root, *args):
    subprocess.run(["git", "-C", str(root), "-c", "core.hooksPath=/dev/null", *args],
                   check=True, capture_output=True)


def write(root, path, content):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content.encode() if isinstance(content, str) else content)


def commit(root):
    command(root, "add", ".")
    command(root, "-c", "user.name=Corpus fixture", "-c", "user.email=fixture@example.invalid",
            "commit", "-qm", "Fixture source")


class SourceCorpusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.sources = self.base / "sources"
        for name, info in corpus.SOURCES.items():
            root = self.sources / name
            root.mkdir(parents=True)
            command(root, "init", "-q")
            command(root, "remote", "add", "origin", info["url"] + ".git")
            write(root, "LICENSE", f"Permission notice for {name} fixture sources.\n")
            write(root, "COPYRIGHT", f"Per-file copyright exceptions for {name}.\n")
            for i in range(24):
                if name == "cpython":
                    write(root, f"Lib/module{i}.py", f"# Copyright fixture {i}\ndef module{i}(): return {i}\n")
                    write(root, f"Doc/library/module{i}.rst", f"Module {i}\n========\nDocumentation number {i}.\n")
                elif name == "rust":
                    write(root, f"library/core/src/module{i}/mod.rs", f"// Copyright fixture {i}\nfn function{i}() {{}}\n")
                else:
                    write(root, f"Mathlib/Algebra/Module{i}/Basic.lean", f"-- Copyright fixture {i}\ndef number{i} : Nat := {i}\n")
            commit(root)

    def build(self, out="corpus", workers=2):
        dest = self.base / out
        report = corpus.build(self.sources, dest, validation_fraction=0.25, seed=1337, workers=workers)
        records = [json.loads(line) for line in (dest / "provenance.jsonl").read_text().splitlines()]
        return dest, report, records

    def test_module_families_cover_implementation_tests_and_docs(self):
        self.assertEqual(corpus.module_family("cpython", "Lib/http/client.py"),
                         corpus.module_family("cpython", "Lib/test/test_httplib.py"))
        self.assertEqual(corpus.module_family("cpython", "Lib/http/client.py"),
                         corpus.module_family("cpython", "Doc/library/http.client.rst"))
        self.assertEqual(corpus.module_family("cpython", "Lib/asyncio/tasks.py"),
                         corpus.module_family("cpython", "Doc/library/asyncio-eventloop.rst"))
        self.assertEqual(corpus.module_family("rust", "library/core/src/fmt/mod.rs"),
                         corpus.module_family("rust", "library/coretests/tests/fmt/float.rs"))
        self.assertEqual(corpus.module_family("mathlib4", "Mathlib/Algebra/Group.lean"),
                         corpus.module_family("mathlib4", "Mathlib/Algebra/Group/Defs.lean"))
        self.assertEqual(corpus.source_kind("mathlib4", "Mathlib/Algebra/Group.lean"), "proof")
        self.assertEqual(corpus.source_kind("cpython", "Lib/test/test_http.py"), "test")
        self.assertEqual(corpus.source_kind("rust", "library/coretests/tests/fmt.rs"), "test")

    def test_provenance_pins_bytes_and_preserves_license_and_headers(self):
        dest, report, rows = self.build()
        self.assertEqual(report["selected_files"], 96)
        self.assertEqual(report["included_files"], 96)
        for row in rows:
            original = (self.sources / row["source"] / row["path"]).read_bytes()
            self.assertEqual(row["sha256"], hashlib.sha256(original).hexdigest())
            filename = "train.txt" if row["split"] == "train" else "validation.txt"
            self.assertIn(original.decode(), (dest / filename).read_text())
            self.assertEqual(len(row["revision"]), 40)
            self.assertTrue(row["license_snapshots"])
        for name in corpus.SOURCES:
            self.assertEqual((dest / "licenses" / name / "LICENSE").read_bytes(),
                             (self.sources / name / "LICENSE").read_bytes())
            self.assertEqual((dest / "licenses" / name / "COPYRIGHT").read_bytes(),
                             (self.sources / name / "COPYRIGHT").read_bytes())
        self.assertEqual(report["cross_split_group_overlap"], 0)
        self.assertEqual(report["truncated_files"], 0)

    def test_exact_and_normalized_duplicates_cannot_cross_splits(self):
        root = self.sources / "cpython"
        names = {}
        for i in range(100):
            name = f"dup{i}"
            names.setdefault(corpus.choose_split("cpython:" + name, 1337, 0.25), name)
        a, b = names["train"], names["validation"]
        write(root, f"Lib/{a}.py", "x = 782397\n")
        write(root, f"Lib/{b}.py", "x = 782397\n")
        write(root, "Lib/normalized_a.py", "unique_value = 321897\r\n")
        write(root, "Lib/normalized_b.py", "unique_value = 321897   \n\n")
        commit(root)
        _, report, rows = self.build()
        self.assertEqual(report["excluded"]["exact-duplicate"], 1)
        self.assertEqual(report["excluded"]["normalized-duplicate"], 1)
        self.assertEqual(report["cross_split_exact_overlap"], 0)
        self.assertEqual(report["cross_split_normalized_overlap"], 0)
        duplicate_rows = [row for row in rows if row.get("duplicate_of")]
        self.assertEqual(len(duplicate_rows), 2)

    def test_filters_are_accounted_for_and_source_is_never_executed(self):
        root = self.sources / "cpython"
        cases = {"Lib/nul.py": b"bad\x00data", "Lib/bad_encoding.py": b"bad\xffdata",
                 "Lib/test/fixtures/sample.py": "fixture = 1\n",
                 "Lib/generated.py": "# Automatically generated by fixture\nvalue = 1\n",
                 "Lib/benchmark.py": "# HumanEval benchmark examples\n",
                 "Doc/library/apps_reference.rst": "ordinary docs\n"}
        for path, text in cases.items():
            write(root, path, text)
        marker = self.base / "executed"
        write(root, "Lib/dont_execute.py", f"raise RuntimeError({str(marker)!r})\n")
        commit(root)
        _, report, rows = self.build()
        for reason in ("binary-nul", "non-utf8", "vendored-generated-or-fixture-directory",
                       "generated-header", "benchmark-name-in-content", "benchmark-name-in-path"):
            self.assertEqual(report["excluded"][reason], 1, reason)
        self.assertTrue(next(row for row in rows if row["path"] == "Lib/dont_execute.py")["included"])
        self.assertFalse(marker.exists())

    def test_output_is_identical_across_worker_counts(self):
        first, _, _ = self.build("one", workers=1)
        second, _, _ = self.build("four", workers=4)
        for name in ("train.txt", "validation.txt", "provenance.jsonl", "sources-lock.json", "quality.json", "DATASET.md"):
            self.assertEqual((first / name).read_bytes(), (second / name).read_bytes(), name)

    def test_quoted_generated_headers_exclude_tables_not_generation_documentation(self):
        root = self.sources / "cpython"
        cases = {
            "Lib/encodings/mac_cyrillic.py":
                '\"\"\" Python Character Mapping Codec mac_cyrillic generated from '
                "'MAPPINGS/VENDORS/APPLE/CYRILLIC.TXT' with gencodec.py.\n\n\"\"\"#\"\n"
                "import codecs\ndecoding_table = 'table'\n",
            "Lib/quoted_generated.py": '\"\"\"This file is generated by a tool.\"\"\"\nx = 1\n',
            "Lib/raw_generated.py": "r'''This code was automatically generated.'''\nx = 2\n",
            "Doc/library/generation.rst": "Code generation\n===============\n"
                "Python can generate code from templates.\n"
                "The generated file contains an example header:\n"
                "    print('This file is generated by a tool.')\n",
        }
        for path, text in cases.items():
            write(root, path, text)
        commit(root)
        _, report, rows = self.build()
        by_path = {row["path"]: row for row in rows if row["source"] == "cpython"}
        self.assertEqual(report["excluded"]["generated-header"], 3)
        for path in cases:
            self.assertEqual(by_path[path]["included"], path.startswith("Doc/"), path)

    def test_modified_revision_and_missing_license_are_refused(self):
        root = self.sources / "cpython"
        write(root, "Lib/module0.py", "modified = True\n")
        with self.assertRaisesRegex(ValueError, "differ from the pinned revision"):
            self.build()
        command(root, "checkout", "--", "Lib/module0.py")
        command(root, "rm", "-q", "LICENSE")
        commit(root)
        with self.assertRaisesRegex(ValueError, "root license"):
            self.build()
        self.assertFalse((self.base / "corpus").exists())

    def test_existing_output_is_preserved(self):
        dest, _, _ = self.build()
        before = (dest / "quality.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.build()
        self.assertEqual((dest / "quality.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
