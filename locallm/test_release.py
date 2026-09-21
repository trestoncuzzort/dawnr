"""What the release has to be true of before anybody downloads it.

    python3 -m unittest test_release

No torch, no display, no network, and it runs from any directory: the zips are
built for real into a temporary folder, because a mocked zip cannot be
byte-compared with another mocked zip and that comparison is the whole point.

The builds here pass a fake two-file checkpoint rather than the real 43.5 MB one.
That keeps the suite at well under a second while still exercising the path the
model actually travels; the real bundle is measured on the command line, where
its size can be read against the 43,526,601 bytes ckpt.pt is known to be.
"""
from __future__ import annotations

import hashlib
import io
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import release  # noqa: E402

TOP = release.TOP


def fake_model(folder: Path) -> Path:
    """A checkpoint folder of the right shape and the wrong size."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "ckpt.pt").write_bytes(b"not a checkpoint, only its shape\n")
    (folder / "tokenizer.json").write_text('["a", "b"]\n', encoding="utf-8")
    return folder


class TestClosure(unittest.TestCase):
    def test_holds_the_programs_a_stranger_runs(self):
        names = release.closure(HERE)
        for wanted in ("home.py", "look.py", "plain_generate.py"):
            self.assertIn(wanted, names)

    def test_carries_no_test_and_no_research_script(self):
        names = release.closure(HERE)
        self.assertEqual([], [n for n in names if n.startswith("test_")])
        self.assertEqual([], release.research(names))
        # Named one by one as well as by pattern: the patterns are the rule and
        # these are the files the rule exists for.
        for unwanted in ("train_factorial.py", "train_distributed.py",
                         "research_model.py", "continue_from_checkpoint.py",
                         "completion_batch.py", "next_latent.py",
                         "test_release.py", "release.py"):
            self.assertNotIn(unwanted, names)

    def test_an_import_with_no_file_is_a_sentence(self):
        # The one that would otherwise ship broken: home.py imports look, look.py
        # is not there, and "is there a file of that name" would read the absence
        # as somebody else's package.
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "locallm"
            src.mkdir()
            (src / "home.py").write_text("import look\n", encoding="utf-8")
            with self.assertRaises(release.ReleaseError) as caught:
                release.closure(src, roots=("home.py",))
            said = str(caught.exception)
            self.assertIn("look", said)
            self.assertIn("home.py", said)

    def test_a_missing_entry_point_is_a_sentence(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "locallm"
            src.mkdir()
            with self.assertRaises(release.ReleaseError) as caught:
                release.closure(src, roots=("home.py",))
            self.assertIn("home.py", str(caught.exception))

    def test_a_declared_dependency_is_not_ours_to_ship(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "locallm"
            src.mkdir()
            (src / "home.py").write_text(
                "import json\nimport torch\nimport tokenizers\n"
                "import tkinterdnd2\n", encoding="utf-8")
            self.assertEqual(["home.py"], release.closure(src, roots=("home.py",)))


class TestZip(unittest.TestCase):
    def test_two_builds_of_one_tree_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            model = fake_model(Path(tmp) / "model")
            first = release.build(Path(tmp) / "one", model_dir=model)
            second = release.build(Path(tmp) / "two", model_dir=model)
            self.assertEqual(first.sha256, second.sha256)
            self.assertEqual(
                hashlib.sha256(first.path.read_bytes()).hexdigest(),
                hashlib.sha256(second.path.read_bytes()).hexdigest())

    def test_everything_is_under_one_top_level_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            built = release.build(tmp, model_dir=fake_model(Path(tmp) / "model"))
            with zipfile.ZipFile(built.path) as zf:
                names = zf.namelist()
            self.assertTrue(names)
            self.assertEqual({TOP}, {n.split("/")[0] for n in names})
            for name in names:
                self.assertTrue(name.startswith(f"{TOP}/"), name)

    def test_the_model_lands_where_home_py_looks_for_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            built = release.build(tmp, model_dir=fake_model(Path(tmp) / "model"))
            with zipfile.ZipFile(built.path) as zf:
                names = set(zf.namelist())
            # home.py: ready_made(HERE) reads HERE/INCLUDED/ckpt.pt, and HERE is
            # home.py's own folder, so the two must be siblings in the zip.
            self.assertIn(f"{TOP}/{release.INCLUDED}/ckpt.pt", names)
            self.assertIn(f"{TOP}/{release.INCLUDED}/tokenizer.json", names)
            self.assertIn(f"{TOP}/home.py", names)

    def test_manifest_accounts_for_every_other_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            built = release.build(tmp, model_dir=fake_model(Path(tmp) / "model"))
            with zipfile.ZipFile(built.path) as zf:
                members = set(zf.namelist())
                text = zf.read(f"{TOP}/MANIFEST.txt").decode("utf-8")
                recorded = {}
                for line in text.splitlines():
                    # hash, size, path — path last because a launcher name may
                    # contain spaces.
                    parts = line.split(None, 2)
                    if len(parts) == 3 and len(parts[0]) == 64 \
                            and parts[2].startswith(f"{TOP}/"):
                        recorded[parts[2]] = (parts[0], int(parts[1]))
                self.assertEqual(members - {f"{TOP}/MANIFEST.txt"},
                                 set(recorded))
                for name, (digest, size) in sorted(recorded.items()):
                    blob = zf.read(name)
                    self.assertEqual(size, len(blob), name)
                    self.assertEqual(digest, hashlib.sha256(blob).hexdigest(),
                                     name)

    def test_no_model_omits_the_folder_and_stays_small(self):
        with tempfile.TemporaryDirectory() as tmp:
            built = release.build(tmp, include_model=False)
            with zipfile.ZipFile(built.path) as zf:
                names = zf.namelist()
                manifest = zf.read(f"{TOP}/MANIFEST.txt").decode("utf-8")
            prefix = f"{TOP}/{release.INCLUDED}/"
            self.assertEqual([], [n for n in names if n.startswith(prefix)])
            self.assertIn("bundled model: none", manifest)
            self.assertLess(built.size, 1_000_000, f"{built.size} bytes")


class TestFrontDoor(unittest.TestCase):
    def test_the_launchers_are_the_ones_the_document_promises(self):
        # START-HERE.md's "Start it" table is where a stranger learns the name of
        # the file to run. If the two lists drift, the zip ships a document that
        # tells them to run something that is not there.
        page = HERE / "START-HERE.md"
        if not page.is_file():
            self.skipTest("START-HERE.md is not written yet")
        text = page.read_text(encoding="utf-8")
        for name in release.LAUNCHERS:
            self.assertIn(name, text)

    def test_a_launcher_ships_executable_and_a_module_does_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "locallm"
            src.mkdir()
            (src / "home.py").write_text("print('hello')\n", encoding="utf-8")
            (src / "start-linux.sh").write_text(
                "#!/bin/sh\nexec python3 home.py\n", encoding="utf-8")
            built = release.build(Path(tmp) / "dist", src=src,
                                  include_model=False, roots=("home.py",))
            with zipfile.ZipFile(built.path) as zf:
                mode = {i.filename: i.external_attr >> 16 for i in zf.infolist()}
            self.assertEqual(0o755, mode[f"{TOP}/start-linux.sh"])
            self.assertEqual(0o644, mode[f"{TOP}/home.py"])

    def test_a_missing_front_door_file_is_a_note_not_a_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "locallm"
            src.mkdir()
            (src / "home.py").write_text("print('hello')\n", encoding="utf-8")
            built = release.build(Path(tmp) / "dist", src=src,
                                  include_model=False, roots=("home.py",))
            self.assertTrue(built.path.is_file())
            said = " ".join(built.notes)
            for name in ("START-HERE.md",) + release.LAUNCHERS:
                self.assertIn(name, said)

    def test_a_launcher_naming_an_unshipped_module_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "locallm"
            src.mkdir()
            (src / "home.py").write_text("print('hello')\n", encoding="utf-8")
            (src / "start-windows.bat").write_text(
                "python install.py\r\n", encoding="utf-8")
            built = release.build(Path(tmp) / "dist", src=src,
                                  include_model=False, roots=("home.py",))
            self.assertTrue(any("install.py" in n for n in built.notes),
                            built.notes)


class TestRefusal(unittest.TestCase):
    def test_a_missing_checkpoint_names_the_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "no-model"
            empty.mkdir()
            out = Path(tmp) / "dist"
            with self.assertRaises(release.ReleaseError) as caught:
                release.build(out, model_dir=empty)
            said = str(caught.exception)
            self.assertIn("ckpt.pt", said)
            self.assertIn(str(empty), said)
            self.assertIn("--no-model", said)
            self.assertFalse((out / f"{TOP}.zip").exists(),
                             "refusing must not leave a partial zip")

    def test_the_command_line_refuses_without_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "no-model"
            empty.mkdir()
            err, out = io.StringIO(), io.StringIO()
            with redirect_stderr(err), redirect_stdout(out):
                code = release.main(["--out", tmp, "--model-dir", str(empty)])
            self.assertEqual(2, code)
            self.assertIn("ckpt.pt", err.getvalue())
            self.assertNotIn("Traceback", err.getvalue())
            self.assertEqual("", out.getvalue())


if __name__ == "__main__":
    unittest.main()
