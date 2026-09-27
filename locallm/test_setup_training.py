"""setup_training.py, checked with no network and no real subprocess calls.

Every test here mocks urllib and subprocess: nothing downloads uv, nothing
downloads PyTorch, nothing shells out for real. Where the module needs a
uv release to exist, the test builds a tiny fake tar.gz or zip itself and
points UV_RELEASES at its own sha256 -- never the real ~15 MB asset.

    python3 -m unittest test_setup_training -v
"""
from __future__ import annotations

import collections
import hashlib
import io
import os
import stat
import sys
import tarfile
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import setup_training as st  # noqa: E402


def fake_targz(content: bytes, member: str) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        info = tarfile.TarInfo(name=member)
        info.size = len(content)
        info.mode = 0o755
        tf.addfile(info, io.BytesIO(content))
    return buf.getvalue()


def fake_zip(content: bytes, member: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(member, content)
    return buf.getvalue()


class _FakeResponse(io.BytesIO):
    """Stands in for what urlopen() returns: readable, and a context manager."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestPlatformKey(unittest.TestCase):
    def test_amd64_and_x86_64_are_the_same_arch(self):
        with mock.patch.object(st.platform, "system", return_value="Linux"), \
             mock.patch.object(st.platform, "machine", return_value="AMD64"):
            self.assertEqual(("linux", "x86_64"), st.platform_key())
        with mock.patch.object(st.platform, "system", return_value="Linux"), \
             mock.patch.object(st.platform, "machine", return_value="x86_64"):
            self.assertEqual(("linux", "x86_64"), st.platform_key())

    def test_arm64_and_aarch64_are_the_same_arch(self):
        with mock.patch.object(st.platform, "system", return_value="Darwin"), \
             mock.patch.object(st.platform, "machine", return_value="arm64"):
            self.assertEqual(("darwin", "aarch64"), st.platform_key())
        with mock.patch.object(st.platform, "system", return_value="Linux"), \
             mock.patch.object(st.platform, "machine", return_value="aarch64"):
            self.assertEqual(("linux", "aarch64"), st.platform_key())

    def test_windows_is_lowercased(self):
        with mock.patch.object(st.platform, "system", return_value="Windows"), \
             mock.patch.object(st.platform, "machine", return_value="AMD64"):
            self.assertEqual(("windows", "x86_64"), st.platform_key())

    def test_every_platform_key_has_a_pinned_release(self):
        # The product promises Windows, macOS and Linux (AGENTS.md / this
        # task's own constraints); each must have a real, listed uv build.
        for system in ("linux", "darwin", "windows"):
            self.assertTrue(
                any(key[0] == system for key in st.UV_RELEASES),
                f"no pinned uv release for {system}")

    def test_every_pinned_checksum_is_a_real_sha256_shape(self):
        for (asset, digest) in st.UV_RELEASES.values():
            self.assertEqual(64, len(digest), f"{asset}: {digest!r}")
            int(digest, 16)  # raises ValueError if it is not hex


class TestVenvPathsPerOS(unittest.TestCase):
    def test_windows_uses_scripts_and_python_exe(self):
        self.assertEqual(Path("/x/.venv-train/Scripts/python.exe"),
                          st.venv_python(Path("/x/.venv-train"), os_name="nt"))

    def test_posix_uses_bin_and_python(self):
        self.assertEqual(Path("/x/.venv-train/bin/python"),
                          st.venv_python(Path("/x/.venv-train"), os_name="posix"))

    def test_defaults_to_the_real_os_name(self):
        expected = "Scripts/python.exe" if os.name == "nt" else "bin/python"
        self.assertTrue(str(st.venv_python(Path("/x"))).replace("\\", "/")
                        .endswith(expected))


class TestDriverVersionParsing(unittest.TestCase):
    def test_three_part_version(self):
        self.assertEqual((550, 54, 14), st.parse_driver_version("550.54.14"))

    def test_two_part_version(self):
        self.assertEqual((580, 0), st.parse_driver_version("580.0"))

    def test_garbage_is_empty(self):
        self.assertEqual((), st.parse_driver_version("not a version"))


class TestWheelIndexTable(unittest.TestCase):
    """The stdlib fallback's driver -> PyTorch index table."""

    def test_no_driver_means_cpu(self):
        url, why = st.pick_wheel_index("linux", None)
        self.assertEqual(st.WHEEL_INDEX_BASE + "cpu", url)
        self.assertIn("no NVIDIA driver", why)

    def test_macos_is_always_cpu_build_even_with_a_driver(self):
        # PyTorch has no CUDA build for macOS at all; a driver tuple must
        # never be allowed to override that.
        url, why = st.pick_wheel_index("darwin", ("GeForce RTX 4080", "580.65.06"))
        self.assertEqual(st.WHEEL_INDEX_BASE + "cpu", url)
        self.assertIn("macOS", why)

    def test_driver_older_than_any_supported_cuda_is_cpu(self):
        url, why = st.pick_wheel_index("linux", ("Quadro K2000", "340.10"))
        self.assertEqual(st.WHEEL_INDEX_BASE + "cpu", url)
        self.assertIn("340.10", why)

    def test_cu118_bucket_on_linux(self):
        url, _why = st.pick_wheel_index("linux", ("GTX 1080", "470.63.01"))
        self.assertEqual(st.WHEEL_INDEX_BASE + "cu118", url)

    def test_cu128_bucket_on_linux(self):
        url, _why = st.pick_wheel_index("linux", ("RTX 4080", "550.54.14"))
        self.assertEqual(st.WHEEL_INDEX_BASE + "cu128", url)

    def test_cu130_bucket_needs_the_newest_driver(self):
        url, _why = st.pick_wheel_index("linux", ("RTX 5090", "580.65.06"))
        self.assertEqual(st.WHEEL_INDEX_BASE + "cu130", url)
        # One point under the threshold must NOT qualify.
        url2, _why2 = st.pick_wheel_index("linux", ("RTX 5090", "580.65.05"))
        self.assertEqual(st.WHEEL_INDEX_BASE + "cu128", url2)

    def test_windows_and_linux_thresholds_are_independent(self):
        # 526.00 clears Linux's cu128 threshold (525.60.13) but not Windows's
        # (528.33): the same driver number, two different picks, proving the
        # table is not just one column copied into the other.
        driver = ("Test GPU", "526.00")
        linux_url, _ = st.pick_wheel_index("linux", driver)
        windows_url, _ = st.pick_wheel_index("windows", driver)
        self.assertEqual(st.WHEEL_INDEX_BASE + "cu128", linux_url)
        self.assertEqual(st.WHEEL_INDEX_BASE + "cu118", windows_url)

    def test_unparseable_driver_string_is_cpu_not_a_crash(self):
        url, why = st.pick_wheel_index("linux", ("Mystery GPU", "N/A"))
        self.assertEqual(st.WHEEL_INDEX_BASE + "cpu", url)
        self.assertIn("N/A", why)

    def test_the_table_is_sorted_newest_first(self):
        # pick_wheel_index relies on this order to return the newest match.
        versions = [entry[0] for entry in st.CUDA_WHEEL_TABLE]
        self.assertEqual(sorted(versions, reverse=True), versions)


class TestNvidiaDriverInfo(unittest.TestCase):
    def test_no_nvidia_smi_on_path_is_no_driver(self):
        with mock.patch.object(st.shutil, "which", return_value=None):
            self.assertIsNone(st.nvidia_driver_info())

    def test_parses_name_and_driver_from_csv(self):
        completed = mock.Mock(returncode=0,
                              stdout="NVIDIA GeForce RTX 4080, 550.54.14\n")
        with mock.patch.object(st.shutil, "which", return_value="/usr/bin/nvidia-smi"), \
             mock.patch.object(st.subprocess, "run", return_value=completed) as run:
            info = st.nvidia_driver_info()
        self.assertEqual(("NVIDIA GeForce RTX 4080", "550.54.14"), info)
        run.assert_called_once()
        self.assertIn("--query-gpu=name,driver_version", run.call_args[0][0])

    def test_a_failing_nvidia_smi_is_no_driver(self):
        completed = mock.Mock(returncode=1, stdout="")
        with mock.patch.object(st.shutil, "which", return_value="/usr/bin/nvidia-smi"), \
             mock.patch.object(st.subprocess, "run", return_value=completed):
            self.assertIsNone(st.nvidia_driver_info())

    def test_nvidia_smi_that_hangs_or_errors_is_no_driver(self):
        with mock.patch.object(st.shutil, "which", return_value="/usr/bin/nvidia-smi"), \
             mock.patch.object(st.subprocess, "run", side_effect=OSError("boom")):
            self.assertIsNone(st.nvidia_driver_info())


class TestConsent(unittest.TestCase):
    def test_assume_yes_never_asks(self):
        with mock.patch("builtins.input", side_effect=AssertionError("must not prompt")):
            self.assertTrue(st.confirm("proceed?", True))

    def test_declines_when_not_a_tty_and_not_assumed(self):
        with mock.patch.object(st.sys.stdin, "isatty", return_value=False), \
             mock.patch("builtins.input", side_effect=AssertionError("must not prompt")):
            self.assertFalse(st.confirm("proceed?", False))

    def test_accepts_y_and_yes_case_insensitively(self):
        with mock.patch.object(st.sys.stdin, "isatty", return_value=True):
            for answer in ("y", "Y", "yes", "YES", "  yes  "):
                with mock.patch("builtins.input", return_value=answer):
                    self.assertTrue(st.confirm("proceed?", False), answer)

    def test_rejects_anything_else(self):
        with mock.patch.object(st.sys.stdin, "isatty", return_value=True):
            for answer in ("n", "no", "", "sure", "yesplease"):
                with mock.patch("builtins.input", return_value=answer):
                    self.assertFalse(st.confirm("proceed?", False), answer)

    def test_eof_on_input_declines_rather_than_crashing(self):
        with mock.patch.object(st.sys.stdin, "isatty", return_value=True), \
             mock.patch("builtins.input", side_effect=EOFError):
            self.assertFalse(st.confirm("proceed?", False))


class TempToolsMixin:
    """Points every path this module writes to at a throwaway directory, so
    no test ever touches the real locallm/.tools or .venv-train."""

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        patches = {
            "TOOLS_DIR": root / "tools",
            "DOWNLOADS_DIR": root / "tools" / "downloads",
            "UV_INSTALL_ROOT": root / "tools" / "uv",
            "UV_CACHE_DIR": root / "tools" / "uv-cache",
        }
        for name, value in patches.items():
            patcher = mock.patch.object(st, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.root = root


class TestChecksumVerification(TempToolsMixin, unittest.TestCase):
    FAKE_KEY = ("fakeos", "fakearch")

    def _register_fake_release(self, digest: str, asset: str = "uv-fake.tar.gz"):
        patcher = mock.patch.dict(st.UV_RELEASES, {self.FAKE_KEY: (asset, digest)})
        patcher.start()
        self.addCleanup(patcher.stop)
        return asset

    def test_refuses_a_file_that_does_not_match_the_pin(self):
        wrong_digest = "0" * 64
        self._register_fake_release(wrong_digest)
        archive = self.root / "downloaded.tar.gz"
        archive.write_bytes(fake_targz(b"not the real uv", "uv-fake/uv"))

        with self.assertRaises(st.ChecksumMismatch) as caught:
            st.verify_and_extract_uv(archive, self.FAKE_KEY)
        message = str(caught.exception)
        self.assertIn(wrong_digest, message)
        self.assertIn(st.sha256_of(archive), message)
        # And nothing was extracted from the untrusted archive.
        dest = st.uv_install_dir(self.FAKE_KEY) / "uv"
        self.assertFalse(dest.exists())

    def test_accepts_a_file_that_matches_the_pin_and_extracts_it(self):
        payload = b"#!/bin/sh\necho fake uv\n"
        archive_bytes = fake_targz(payload, "uv-fake/uv")
        digest = hashlib.sha256(archive_bytes).hexdigest()
        self._register_fake_release(digest)
        archive = self.root / "downloaded.tar.gz"
        archive.write_bytes(archive_bytes)

        dest = st.verify_and_extract_uv(archive, self.FAKE_KEY)
        self.assertEqual(payload, dest.read_bytes())
        if os.name != "nt":
            self.assertTrue(dest.stat().st_mode & stat.S_IXUSR, "not executable")


class TestArchiveExtraction(TempToolsMixin, unittest.TestCase):
    def test_extracts_uv_from_a_nested_tar_gz_member(self):
        payload = b"tar payload"
        archive = self.root / "a.tar.gz"
        archive.write_bytes(fake_targz(payload, "uv-x86_64-unknown-linux-gnu/uv"))
        dest = self.root / "out" / "uv"

        st.extract_uv_binary(archive, "uv", dest)
        self.assertEqual(payload, dest.read_bytes())

    def test_extracts_uv_exe_from_a_zip(self):
        payload = b"zip payload"
        archive = self.root / "a.zip"
        archive.write_bytes(fake_zip(payload, "uv.exe"))
        dest = self.root / "out" / "uv.exe"

        st.extract_uv_binary(archive, "uv.exe", dest)
        self.assertEqual(payload, dest.read_bytes())

    def test_never_extracts_uvx_when_asked_for_uv(self):
        archive = self.root / "a.tar.gz"
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            for member, content in (("d/uv", b"real"), ("d/uvx", b"other")):
                info = tarfile.TarInfo(name=member)
                info.size = len(content)
                tf.addfile(info, io.BytesIO(content))
        archive.write_bytes(buf.getvalue())
        dest = self.root / "out" / "uv"

        st.extract_uv_binary(archive, "uv", dest)
        self.assertEqual(b"real", dest.read_bytes())

    def test_refuses_when_the_binary_is_not_inside(self):
        archive = self.root / "a.tar.gz"
        archive.write_bytes(fake_targz(b"x", "uv-fake/readme.txt"))
        with self.assertRaises(st.SetupError) as caught:
            st.extract_uv_binary(archive, "uv", self.root / "out" / "uv")
        self.assertIn("uv", str(caught.exception))

    def test_leaves_no_partial_file_behind_on_refusal(self):
        archive = self.root / "a.tar.gz"
        archive.write_bytes(fake_targz(b"x", "nope"))
        dest = self.root / "out" / "uv"
        with self.assertRaises(st.SetupError):
            st.extract_uv_binary(archive, "uv", dest)
        self.assertFalse(dest.exists())
        self.assertFalse(dest.with_name(dest.name + ".part").exists())


class TestOfflineRefusal(TempToolsMixin, unittest.TestCase):
    KEY = ("linux", "x86_64")

    def test_refuses_clearly_when_nothing_is_cached_and_offline(self):
        with mock.patch.object(st.urllib.request, "urlopen",
                               side_effect=AssertionError("must not touch the network")):
            with self.assertRaises(st.SetupError) as caught:
                st.obtain_uv_archive(self.KEY, offline=True)
        message = str(caught.exception)
        self.assertIn("offline", message.lower())
        asset, digest = st.UV_RELEASES[self.KEY]
        self.assertIn(asset, message)
        self.assertIn(digest, message)
        self.assertIn(st.UV_BASE_URL, message)

    def test_a_manually_placed_file_is_used_offline_with_no_network_call(self):
        asset, _digest = st.UV_RELEASES[self.KEY]
        st.DOWNLOADS_DIR.mkdir(parents=True)
        local = st.DOWNLOADS_DIR / asset
        local.write_bytes(b"placed by hand")

        with mock.patch.object(st.urllib.request, "urlopen",
                               side_effect=AssertionError("must not touch the network")):
            got = st.obtain_uv_archive(self.KEY, offline=True)
        self.assertEqual(local, got)

    def test_main_offline_refuses_and_touches_neither_network_nor_subprocess(self):
        with mock.patch.object(st, "platform_key", return_value=self.KEY), \
             mock.patch.object(st.urllib.request, "urlopen",
                               side_effect=AssertionError("network touched")), \
             mock.patch.object(st.subprocess, "run",
                               side_effect=AssertionError("subprocess touched")):
            out = io.StringIO()
            with redirect_stdout(out):
                code = st.main(["--offline"])
        self.assertEqual(1, code)
        self.assertIn("OFFLINE", out.getvalue())


class TestEnsureUv(TempToolsMixin, unittest.TestCase):
    KEY = ("linux", "x86_64")

    def test_a_cached_binary_is_reused_with_no_network_call(self):
        dest = st.uv_install_dir(self.KEY) / "uv"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"already here")

        with mock.patch.object(st, "platform_key", return_value=self.KEY), \
             mock.patch.object(st.urllib.request, "urlopen",
                               side_effect=AssertionError("must not touch the network")):
            got = st.ensure_uv(offline=False)
        self.assertEqual(dest, got)

    def test_unsupported_platform_returns_none_for_the_caller_to_fall_back(self):
        with mock.patch.object(st, "platform_key", return_value=("plan9", "exotic")):
            self.assertIsNone(st.ensure_uv(offline=False))

    def test_fetches_verifies_and_extracts_when_nothing_is_cached(self):
        fake_key = ("fakeos", "fakearch")
        payload = b"the real fake uv binary"
        archive_bytes = fake_targz(payload, "uv-fake/uv")
        digest = hashlib.sha256(archive_bytes).hexdigest()

        with mock.patch.object(st, "platform_key", return_value=fake_key), \
             mock.patch.dict(st.UV_RELEASES, {fake_key: ("uv-fake.tar.gz", digest)}), \
             mock.patch.object(st.urllib.request, "urlopen",
                               return_value=_FakeResponse(archive_bytes)) as urlopen:
            got = st.ensure_uv(offline=False)
        urlopen.assert_called_once()
        self.assertEqual(payload, got.read_bytes())
        # A second call must not hit the network again.
        with mock.patch.object(st, "platform_key", return_value=fake_key), \
             mock.patch.dict(st.UV_RELEASES, {fake_key: ("uv-fake.tar.gz", digest)}), \
             mock.patch.object(st.urllib.request, "urlopen",
                               side_effect=AssertionError("should have used the cache")):
            again = st.ensure_uv(offline=False)
        self.assertEqual(got, again)


class TestUnusableNvidiaMessage(unittest.TestCase):
    def test_names_the_card_the_driver_and_the_fix(self):
        msg = st.unusable_nvidia_message(
            "NVIDIA GeForce RTX 4080", "550.54.14",
            st.WHEEL_INDEX_BASE + "cu128")
        self.assertIn("RTX 4080", msg)
        self.assertIn("550.54.14", msg)
        self.assertIn("setup_training.py", msg)
        self.assertIn(st.WHEEL_INDEX_BASE + "cu128", msg)


class TestMainFlow(TempToolsMixin, unittest.TestCase):
    KEY = ("linux", "x86_64")

    def test_declines_without_yes_when_not_a_tty(self):
        with mock.patch.object(st, "platform_key", return_value=self.KEY), \
             mock.patch.object(st.sys.stdin, "isatty", return_value=False), \
             mock.patch.object(st, "ensure_uv") as ensure_uv, \
             mock.patch.object(st, "create_venv_with_uv") as create_venv, \
             mock.patch.object(st, "install_torch_with_uv") as install_torch:
            out = io.StringIO()
            with redirect_stdout(out):
                code = st.main([])
        self.assertEqual(1, code)
        self.assertIn("Stopped", out.getvalue())
        ensure_uv.assert_not_called()
        create_venv.assert_not_called()
        install_torch.assert_not_called()

    def test_happy_path_with_uv_and_yes(self):
        fake_uv = self.root / "uv"
        with mock.patch.object(st, "platform_key", return_value=self.KEY), \
             mock.patch.object(st, "ensure_uv", return_value=fake_uv) as ensure_uv, \
             mock.patch.object(st, "create_venv_with_uv") as create_venv, \
             mock.patch.object(st, "install_torch_with_uv") as install_torch:
            out = io.StringIO()
            with redirect_stdout(out):
                code = st.main(["--yes", "--venv-dir", str(self.root / "env")])
        self.assertEqual(0, code)
        ensure_uv.assert_called_once_with(offline=False)
        create_venv.assert_called_once_with(fake_uv, self.root / "env")
        install_torch.assert_called_once_with(fake_uv, self.root / "env", backend="auto")

    def test_cpu_only_passes_the_cpu_backend(self):
        fake_uv = self.root / "uv"
        with mock.patch.object(st, "platform_key", return_value=self.KEY), \
             mock.patch.object(st, "ensure_uv", return_value=fake_uv), \
             mock.patch.object(st, "create_venv_with_uv"), \
             mock.patch.object(st, "install_torch_with_uv") as install_torch:
            out = io.StringIO()
            with redirect_stdout(out):
                code = st.main(["--yes", "--cpu-only", "--venv-dir", str(self.root / "env")])
        self.assertEqual(0, code)
        install_torch.assert_called_once_with(fake_uv, self.root / "env", backend="cpu")

    def test_no_uv_flag_uses_the_stdlib_fallback(self):
        with mock.patch.object(st, "platform_key", return_value=self.KEY), \
             mock.patch.object(st, "nvidia_driver_info", return_value=None), \
             mock.patch.object(st, "ensure_uv") as ensure_uv, \
             mock.patch.object(st, "create_venv_stdlib") as create_venv, \
             mock.patch.object(st, "install_torch_stdlib") as install_torch:
            out = io.StringIO()
            with redirect_stdout(out):
                code = st.main(["--yes", "--no-uv", "--venv-dir", str(self.root / "env")])
        self.assertEqual(0, code)
        ensure_uv.assert_not_called()
        create_venv.assert_called_once_with(self.root / "env")
        install_torch.assert_called_once_with(self.root / "env", st.WHEEL_INDEX_BASE + "cpu")

    def test_ensure_uv_returning_none_is_a_reported_error_not_a_crash(self):
        # Defensive: use_uv already checked key in UV_RELEASES, so ensure_uv()
        # should never return None here -- but if it somehow did, this must
        # not be an AssertionError with -O stripping it away underneath it.
        with mock.patch.object(st, "platform_key", return_value=self.KEY), \
             mock.patch.object(st, "ensure_uv", return_value=None), \
             mock.patch.object(st, "create_venv_with_uv") as create_venv:
            out = io.StringIO()
            with redirect_stdout(out):
                code = st.main(["--yes", "--venv-dir", str(self.root / "env")])
        self.assertEqual(1, code)
        self.assertIn("SETUP STOPPED", out.getvalue())
        create_venv.assert_not_called()

    def test_a_setup_error_is_reported_without_a_traceback(self):
        with mock.patch.object(st, "platform_key", return_value=self.KEY), \
             mock.patch.object(st, "ensure_uv", side_effect=st.SetupError("boom")):
            out = io.StringIO()
            with redirect_stdout(out):
                code = st.main(["--yes", "--venv-dir", str(self.root / "env")])
        self.assertEqual(1, code)
        self.assertIn("boom", out.getvalue())
        self.assertNotIn("Traceback", out.getvalue())

    def test_too_old_python_refuses_before_touching_anything(self):
        old = collections.namedtuple("V", "major minor micro")(3, 9, 0)
        with mock.patch.object(st.sys, "version_info", old), \
             mock.patch.object(st, "ensure_uv") as ensure_uv:
            out = io.StringIO()
            with redirect_stdout(out):
                code = st.main(["--yes"])
        self.assertEqual(1, code)
        ensure_uv.assert_not_called()


if __name__ == "__main__":
    unittest.main()
