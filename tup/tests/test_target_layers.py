"""Refuse unsafe target exports and inconsistent layer chapters before any package command."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

TUP = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("target_layers", TUP / "target/build.py")
target = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(target)
BASH = os.environ.get("TUP_TEST_BASH") or shutil.which("bash")


def shell_path(path):
    text = path.resolve().as_posix()
    return "/" + text[0].lower() + text[2:] if os.name == "nt" else text


class TargetExportTests(unittest.TestCase):
    def fixture(self, root):
        (root / "usr/bin").mkdir(parents=True)
        (root / "etc/ssh").mkdir(parents=True)
        for name in ("python3", "gcc", "make", "su"):
            (root / "usr/bin" / name).write_bytes(b"fixture")

    def test_retained_core_build_state_refuses(self):
        for name in target.EXCLUDED:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self.fixture(root)
                (root / name).mkdir()
                (root / name / "retained").write_bytes(b"old core state")
                with self.assertRaises(target.Refusal):
                    target.check_export(root)

    def test_cloned_host_key_enrollment_or_earlier_layer_refuses(self):
        for name in ("etc/ssh/ssh_host_ed25519_key", "etc/tup/owner-enrolled.json", target.STAGE + "/driver.sh"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self.fixture(root)
                path = root / name
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(b"private fixture")
                with self.assertRaises(target.Refusal):
                    target.check_export(root)

    @unittest.skipUnless(os.name == "posix", "requires Linux symlinks")
    def test_core_tool_escape_refuses_and_internal_version_link_works(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root)
            python = root / "usr/bin/python3"
            python.unlink()
            python.symlink_to("/usr/bin/python3")
            with self.assertRaises(target.Refusal):
                target.check_export(root)
            python.unlink()
            (root / "usr/bin/python3.14").write_bytes(b"versioned fixture")
            python.symlink_to("python3.14")
            target.check_export(root)


class LayerChapterTests(unittest.TestCase):
    def chapters(self):
        return [name for name, relative in target.CHAPTERS.items() if (TUP / relative).is_dir()]

    def test_committed_chapters_follow_the_page_contract(self):
        present = self.chapters()
        self.assertEqual(present[:2], ["remote", "boot"])
        for chapter in present:
            for page in target.chapter_pages(TUP, chapter):
                raw = (TUP / target.CHAPTERS[chapter] / page).read_bytes()
                with self.subTest(page=page):
                    self.assertNotIn(b"\r", raw)
                    lines = raw.decode("utf-8").splitlines()
                    self.assertEqual(lines[0], "#!/bin/bash")
                    self.assertEqual(sum(line == "source /tup-layer/common.sh" for line in lines), 1)
                    # The driver parses any "# TUP_TARBALL" line; only line 2 may carry one.
                    self.assertFalse(any(line.startswith("# TUP_TARBALL") for line in lines[2:]))
                    # A staged path of the retired draft layout must not survive.
                    self.assertNotIn(b"/tup-remote", raw)

    def test_selected_archives_are_exactly_the_reviewed_layer_inputs(self):
        self.assertEqual(target.chapter_archives(TUP, ["remote", "boot"]), [
            "libmnl-1.0.5.tar.bz2", "libnftnl-1.3.2.tar.xz", "nftables-1.1.7.tar.xz", "openssh-10.6p1.tar.gz",
            "LVM2.2.03.42.tgz", "linux-6.18.60.tar.xz", "linux-firmware-20261019.tar.xz"])

    def test_order_and_page_set_disagreement_refuses(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            pages = source / target.CHAPTERS["boot"]
            pages.mkdir(parents=True)
            (pages / "ORDER").write_text("01-one.sh\n", encoding="utf-8")
            (pages / "01-one.sh").write_text("#!/bin/bash\n# TUP_TARBALL=one-1.0.tar.xz\n", encoding="utf-8")
            self.assertEqual(target.chapter_archives(source, ["boot"]), ["one-1.0.tar.xz"])
            (pages / "02-unlisted.sh").write_text("#!/bin/bash\n", encoding="utf-8")
            with self.assertRaisesRegex(target.Refusal, "disagree"):
                target.chapter_pages(source, "boot")
            (pages / "02-unlisted.sh").unlink()
            (pages / "01-one.sh").write_text("#!/bin/bash\n# TUP_TARBALL_x86_64=one-1.0.tar.xz\n", encoding="utf-8")
            with self.assertRaisesRegex(target.Refusal, "architecture-independent"):
                target.chapter_archives(source, ["boot"])

    def test_staged_input_change_is_detected_but_the_manifest_is_allowed(self):
        with tempfile.TemporaryDirectory() as temporary:
            stage = Path(temporary) / "stage"
            (stage / "chapters").mkdir(parents=True)
            (stage / "chapters/page.sh").write_bytes(b"echo reviewed\n")
            frozen = target.inventory(stage)
            (stage / "BUILD-INPUTS.json").write_bytes(b"{}\n")
            self.assertTrue(target.staged_unchanged(stage, frozen))
            (stage / "chapters/page.sh").write_bytes(b"echo changed\n")
            self.assertFalse(target.staged_unchanged(stage, frozen))

    def test_runner_and_pages_are_valid_bash_and_refuse_direct_use(self):
        if not BASH:
            self.skipTest("Bash is required for syntax checks")
        scripts = [TUP / "target/run.sh", TUP / "target/common.sh"]
        for chapter in self.chapters():
            scripts += [TUP / target.CHAPTERS[chapter] / page for page in target.chapter_pages(TUP, chapter)]
        for script in scripts:
            result = subprocess.run([BASH, "-n", shell_path(script)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, f"{script.name}: {result.stderr}")
        # Outside the runner's namespaces and chroot the shared prologue must stop a page.
        result = subprocess.run([BASH, "-c", 'source "$1"; echo reached', "fixture", shell_path(TUP / "target/common.sh")],
                                capture_output=True, text=True, timeout=10, env={"PATH": os.environ.get("PATH", "")})
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("reached", result.stdout)
        # Too few arguments or a relative root never reach a mount command.
        for arguments in ([], ["relative-root", "2", "a", "b", "c", "d", "remote"]):
            result = subprocess.run([BASH, shell_path(TUP / "target/run.sh"), *arguments], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
