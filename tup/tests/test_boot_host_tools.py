import io
import os
from pathlib import Path
import tempfile
import tarfile
import unittest
from unittest.mock import patch

from tup.boot import host_tools as host
from tup.boot.inputs import Refusal, canonical, file_hash


class HostToolsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="tup-host-tests-")
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def archive(self, members):
        path = self.root / "source.tar"
        with tarfile.open(path, "w") as output:
            for name, kind, value in members:
                member = tarfile.TarInfo(name)
                member.mode = 0o755
                if kind == "link":
                    member.type = tarfile.SYMTYPE
                    member.linkname = value
                    output.addfile(member)
                else:
                    member.size = len(value)
                    output.addfile(member, io.BytesIO(value))
        return path

    def test_archive_traversal_refuses_before_writing_outside(self):
        path = self.archive([("package/../../escape", "file", b"bad")])
        with self.assertRaises(Refusal):
            host.unpack(path, self.root / "extracted", "package")
        self.assertFalse((self.root / "escape").exists())

    def test_archive_duplicate_paths_refuse(self):
        path = self.archive([("package/configure", "file", b"first"),
                             ("package/configure", "file", b"last")])
        with self.assertRaises(Refusal):
            host.unpack(path, self.root / "extracted", "package")

    @unittest.skipUnless(os.name == "posix", "Linux link extraction")
    def test_escaping_archive_link_refuses(self):
        path = self.archive([("package/escape", "link", "../../outside")])
        with self.assertRaises(tarfile.FilterError):
            host.unpack(path, self.root / "extracted", "package")

    def test_wrong_source_tree_refuses(self):
        path = self.archive([("different/configure", "file", b"data")])
        with self.assertRaises(Refusal):
            host.unpack(path, self.root / "extracted", "package")

    def test_safe_source_extraction_preserves_command(self):
        path = self.archive([("package/configure", "file", b"#!/bin/sh\nexit 0\n")])
        result = host.unpack(path, self.root / "extracted", "package")
        self.assertEqual((result / "configure").read_bytes(), b"#!/bin/sh\nexit 0\n")
        if os.name == "posix":
            self.assertTrue(os.access(result / "configure", os.X_OK))

    def test_tampered_catalog_never_reaches_signature_verifier(self):
        catalog = self.root / "catalog.json"
        catalog.write_bytes(b"{}")
        with patch.object(host.source_lock, "verify_record") as verifier:
            with self.assertRaises(Refusal):
                host.authenticated_sources(catalog, "0" * 64, self.root, self.root)
            verifier.assert_not_called()

    def test_incomplete_or_duplicate_source_catalog_refuses(self):
        catalog = self.root / "catalog.json"
        for records in ([], [{"name": "dracut-112.tar.gz"}] * 3):
            catalog.write_bytes(canonical({"schema": "tup.boot-source-catalog.v1", "sources": records}))
            with self.assertRaises(Refusal):
                host.authenticated_sources(catalog, file_hash(catalog), self.root, self.root)

    def test_missing_review_refuses(self):
        catalog = self.root / "catalog.json"
        records = [{"name": name, "disposition": "retain", "authentication": {}}
                   for name, _ in host.RECIPES.values()]
        catalog.write_bytes(canonical({"schema": "tup.boot-source-catalog.v1", "sources": records}))
        with self.assertRaises(Refusal):
            host.authenticated_sources(catalog, file_hash(catalog), self.root, self.root)

    @unittest.skipUnless(os.name == "posix", "Linux staged-prefix semantics")
    def test_staged_install_outside_prefix_refuses(self):
        staging = self.root / "staging"
        prefix = self.root / "prefix"
        (staging / prefix.relative_to("/")).mkdir(parents=True)
        (staging / "etc").mkdir()
        (staging / "etc/unexpected").write_text("bad")
        with self.assertRaises(Refusal):
            host.publish_staged(staging, prefix)
        self.assertFalse(prefix.exists())

    @unittest.skipUnless(os.name == "posix", "Linux staged-prefix semantics")
    def test_staged_symlink_cannot_escape(self):
        staging = self.root / "staging"
        prefix = self.root / "prefix"
        staged_prefix = staging / prefix.relative_to("/")
        staged_prefix.mkdir(parents=True)
        (staged_prefix / "escape").symlink_to("/usr/bin")
        with self.assertRaises(Refusal):
            host.publish_staged(staging, prefix)
        self.assertFalse(prefix.exists())

    @unittest.skipUnless(os.name == "posix", "Linux staged-prefix semantics")
    def test_component_collision_refuses_before_any_copy(self):
        staging = self.root / "staging"
        prefix = self.root / "prefix"
        staged_prefix = staging / prefix.relative_to("/")
        staged_prefix.mkdir(parents=True)
        prefix.mkdir()
        (prefix / "existing").write_text("old")
        (staged_prefix / "existing").write_text("new")
        (staged_prefix / "additional").write_text("new")
        with self.assertRaises(Refusal):
            host.publish_staged(staging, prefix)
        self.assertEqual((prefix / "existing").read_text(), "old")
        self.assertFalse((prefix / "additional").exists())

    @unittest.skipUnless(os.name == "posix", "Linux workspace semantics")
    def test_partial_workspace_cannot_be_replayed(self):
        workspace = host.fresh_workspace(self.root / "workspace")
        (workspace / "partial").write_text("already started")
        with self.assertRaises(Refusal):
            host.fresh_workspace(workspace)
        self.assertEqual((workspace / "partial").read_text(), "already started")

    @unittest.skipUnless(os.name == "posix", "Linux workspace semantics")
    def test_prefix_shell_injection_and_aliases_refuse(self):
        for name in ("space here", "semi;colon", "pipe|here", "back`tick", "paren()"):
            with self.assertRaises(Refusal):
                host.fresh_workspace(self.root / name)
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(Refusal):
            host.fresh_workspace(alias / "child")

    def test_upstream_install_destinations_are_explicit(self):
        prefix = Path("/isolated/host/prefix")
        staging = Path("/isolated/host/staging")
        for component in host.RECIPES:
            steps = host.commands(component, Path("/source"), prefix, staging, 2)
            self.assertIn("make", steps[-1][1])
            self.assertTrue(any(str(staging) in arg for arg in steps[-1][1]))
            self.assertFalse(any("grub-install" in arg for _, argv in steps for arg in argv))
        options = host.commands("dracut", Path("/source"), prefix, staging, 2)[0][1]
        self.assertIn(f"--systemdsystemunitdir={prefix}/lib/systemd/system", options)
        self.assertIn("--disable-dracut-cpio", options)


if __name__ == "__main__":
    unittest.main()
