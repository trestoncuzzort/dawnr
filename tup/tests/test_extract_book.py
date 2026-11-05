"""Offline extraction tests; fixtures never execute book/build commands."""
from __future__ import annotations

import hashlib
import html
import io
import json
from pathlib import Path
import re
import tarfile
import tempfile
import unittest
from unittest import mock

from tup import extract_book as book


def toc(links):
    return '<div class="toc">' + ''.join(f'<a href="{p}">{p}</a>' for p in links) + '</div>'


class ExtractionRegressionTests(unittest.TestCase):
    def reader(self, master, chapter):
        return lambda url: {
            book.BASE + "index.html": toc(master),
            book.BASE + "chapter07/chapter07.html": toc(chapter),
        }[url]

    def test_reordered_chapter_is_not_accepted_by_matching_counts(self):
        with mock.patch.object(book, "fetch", self.reader(
                ["chapter07/second.html", "chapter07/first.html"],
                ["first.html", "second.html"])):
            with self.assertRaisesRegex(ValueError, "order"):
                book.toc_pages(7)

    def test_missing_chapter_page_refuses_before_generation(self):
        with mock.patch.object(book, "fetch", self.reader(
                ["chapter07/first.html"], ["first.html", "second.html"])):
            with self.assertRaisesRegex(ValueError, "chapter"):
                book.toc_pages(7)

    def test_unavailable_chapter_index_is_not_a_success(self):
        def read(url):
            if url.endswith("index.html"):
                return toc(["chapter07/first.html"])
            raise OSError("chapter unavailable")
        with mock.patch.object(book, "fetch", read):
            with self.assertRaisesRegex(OSError, "chapter unavailable"):
                book.toc_pages(7)

    def test_non_make_and_underscore_suite_targets_are_guarded(self):
        for command in ("unshare -m ninja test", "ninja -C build test",
                        "TEST_JOBS=4 make test_harness", "make check_local",
                        "bash tests/run.sh --srcdir=$PWD"):
            with self.subTest(command=command):
                guarded = book.guard_tests(command, "fixture")
                self.assertIn('if tup_tests_enabled "fixture"', guarded)
                self.assertIn(command, guarded)
                self.assertIn("tup_receipt_skip_tests", guarded)

    def test_toc_preserves_case_underscores_and_multiline_attributes(self):
        reader = self.reader(["chapter07/Python.html", "chapter07/a_b.html"],
                             ["Python.html", "a_b.html"])
        with mock.patch.object(book, "fetch", lambda url: reader(url).replace(' href=', '\n href=')):
            self.assertEqual(book.toc_pages(7), ["chapter07/Python.html", "chapter07/a_b.html"])

    def test_html_command_classes_entities_and_output_are_distinct(self):
        parsed = book.BookHTML("<title>Fixture</title><pre class='root extra'><kbd>echo &lt;thing&gt; &amp;</kbd></pre>"
                               "<pre class='screen'>not a command</pre>"
                               "<pre id='x' class='userinput'><kbd>ninja test</kbd></pre>")
        self.assertEqual([b["text"] for b in parsed.blocks], ["echo <thing> &", "ninja test"])


class PinnedSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(book.__file__).parent
        cls.inputs = cls.root / "extraction" / "13.1-systemd"
        cls.snapshot = cls.inputs / "LFS-BOOK-13.1.tar.xz"
        cls.metadata = cls.inputs / "snapshot.json"
        cls.audit = cls.inputs / "audit-profile.json"
        cls.files = book.render_offline(cls.snapshot, cls.metadata, cls.audit, book.MAINTAINED)
        cls.manifest = json.loads(cls.files["EXTRACTION.json"])

    def test_original_snapshot_pin_is_an_observation(self):
        self.assertEqual(hashlib.sha256(self.snapshot.read_bytes()).hexdigest(),
                         "090b2b127ac35634269d610e2649dab031fd8a5aa9acfaf10a3c971deda5ed89")
        self.assertEqual(json.loads(self.metadata.read_bytes())["authentication"], "observed-integrity")

    def test_pinned_chapter_names_and_maintained_source_list(self):
        chapters = self.manifest["chapters"]
        self.assertEqual({ch: len(order) for ch, order in chapters.items()},
                         {"ch05": 6, "ch06": 18, "ch07": 15, "ch08": 85, "ch09": 10, "ch10": 4, "ch11": 5})
        self.assertEqual(chapters["ch07"][9:], ["10-zlib.sh", "11-mpdecimal.sh", "12-Python.sh", "13-texinfo.sh", "14-util-linux.sh", "15-cleanup.sh"])
        self.assertEqual(chapters["ch08"][76:78], ["77-systemd.sh", "78-dbus.sh"])
        self.assertEqual(chapters["ch09"][-1], "10-systemd-custom.sh")
        self.assertEqual(self.manifest["source_list"], "wget-list-systemd")
        self.assertEqual(self.manifest["source_count"], 94)

    def test_every_original_command_is_preserved_between_markers(self):
        count = 0
        with tarfile.open(self.snapshot) as archive:
            for page, entry in self.manifest["pages"].items():
                raw = archive.extractfile("13.1/" + entry["source_page"]).read().decode()
                # Independent reader of the known pinned HTML shape. Compare
                # actual command bytes, not only metadata generated by parser.
                expected = [html.unescape(re.sub(r"<[^>]+>", "", value)).strip("\n")
                            for value in re.findall(r'<pre class="(?:userinput|root)">(.*?)</pre>', raw, re.S)]
                rendered = self.files[page].decode()
                found = re.findall(r"^# TUP_BLOCK_BEGIN=\d{3}\n(.*?)\n# TUP_BLOCK_END=\d{3}$", rendered, re.M | re.S)
                self.assertEqual(found, expected, page)
                self.assertEqual([hashlib.sha256(command.encode()).hexdigest() for command in found],
                                 [block["sha256"] for block in entry["blocks"]], page)
                count += len(found)
        self.assertEqual(count, 640)

    def test_suites_and_combined_build_tests_are_distinguished(self):
        expected = {("ch08/77-systemd.sh", 4): "test", ("ch08/78-dbus.sh", 3): "test",
                    ("ch08/21-pkgconf.sh", 4): "test", ("ch08/46-perl.sh", 4): "test",
                    ("ch08/53-mpdecimal.sh", 3): "test", ("ch08/07-bzip2.sh", 5): "build-test",
                    ("ch08/54-Python.sh", 3): "build-test", ("ch08/81-util-linux.sh", 3): "platform"}
        for (page, index), kind in expected.items():
            self.assertEqual(self.manifest["pages"][page]["blocks"][index - 1]["kind"], kind)

    def test_checkpoint_never_approves_unselected_commands(self):
        for page, entry in self.manifest["pages"].items():
            if entry["blocks"]:
                self.assertIn("native-policy-review", entry["requires_override"], page)
                before = self.files[page].split(b"# TUP_BOOK_COMMANDS_BEGIN", 1)[0]
                self.assertIn(b"exit 97\n", before, page)
                self.assertIn(b": <<'TUP_UNSELECTED_", before, page)

    def test_regeneration_is_offline_and_matches_checked_in_bytes(self):
        with mock.patch.object(book.urllib.request, "urlopen", side_effect=AssertionError("network used")):
            again = book.render_offline(self.snapshot, self.metadata, self.audit, book.MAINTAINED)
        self.assertEqual(self.files, again)
        book.publish_extraction(again, self.root / "book-x86_64-13.1-systemd", check=True)

    def test_corrupt_snapshot_does_not_render(self):
        with tempfile.TemporaryDirectory() as temporary:
            changed = Path(temporary) / "book.tar.xz"
            changed.write_bytes(self.snapshot.read_bytes()[:-1] + b"X")
            with self.assertRaisesRegex(ValueError, "digest/size"):
                book.render_offline(changed, self.metadata, self.audit, book.MAINTAINED)

    def test_changed_audit_order_or_block_hash_refuses(self):
        original = json.loads(self.audit.read_bytes())
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "audit.json"
            for mutation in ("order", "block"):
                review = json.loads(json.dumps(original))
                if mutation == "order":
                    review["chapters"]["ch07"][9:11] = reversed(review["chapters"]["ch07"][9:11])
                else:
                    review["pages"]["chapter08/systemd.html"]["blocks"][3]["sha256"] = "0" * 64
                path.write_text(json.dumps(review), encoding="utf-8")
                with self.assertRaises(ValueError):
                    book.render_offline(self.snapshot, self.metadata, path, book.MAINTAINED)

    def test_archive_traversal_links_and_duplicates_are_rejected(self):
        for kind in ("traversal", "symlink", "duplicate"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "book.tar"
                with tarfile.open(path, "w") as archive:
                    member = tarfile.TarInfo("13.1/../escape" if kind == "traversal" else "13.1/index.html")
                    if kind == "symlink":
                        member.type = tarfile.SYMTYPE
                        member.linkname = "/outside"
                    archive.addfile(member)
                    if kind == "duplicate":
                        archive.addfile(member)
                meta = json.loads(self.metadata.read_bytes())
                meta.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), size_bytes=path.stat().st_size)
                with self.assertRaisesRegex(ValueError, "unsafe/duplicate"):
                    book.OfflineBook(path, meta)

    def test_authentication_cannot_be_upgraded_by_a_label(self):
        metadata = json.loads(self.metadata.read_bytes())
        metadata["authentication"] = "publisher-authenticated"
        with self.assertRaisesRegex(ValueError, "authentication assertion"):
            book.OfflineBook(self.snapshot, metadata)

    def test_historical_trees_and_different_existing_output_are_not_overwritten(self):
        for destination in (self.root / "book", self.root / "book-x86_64"):
            with self.assertRaisesRegex(ValueError, "historical"):
                book.publish_extraction(self.files, destination)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "generated"
            destination.mkdir()
            retained = destination / "retained"
            retained.write_bytes(b"keep")
            with self.assertRaisesRegex(ValueError, "existing extraction differs"):
                book.publish_extraction(self.files, destination)
            self.assertEqual(retained.read_bytes(), b"keep")


if __name__ == "__main__":
    unittest.main()
