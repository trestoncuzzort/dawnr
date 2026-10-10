"""Coordinated writers exercise collisions without relying on scheduler luck."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import cache
import surface
import tlib
from verifiers import Outcome, Result


class LibraryConcurrencyTests(unittest.TestCase):
    def test_same_name_calls_in_one_output_root_keep_their_own_sources(self):
        barrier = threading.Barrier(2)
        local = threading.local()

        def verify(path):
            barrier.wait(timeout=10)
            text = path.read_text()
            if not path.stem.endswith("_twin"):
                self.assertEqual(text, local.expected, "another library call overwrote the source")
            outcome = Outcome.REFUTED if path.stem.endswith("_twin") else Outcome.VERIFIED
            return Result("dafny", "fake-v1", hashlib.sha256(text.encode()).hexdigest(), outcome)

        with tempfile.TemporaryDirectory() as directory, \
             patch("tlib.kernel_version", return_value="fake-v1"), \
             patch("verifiers.dafny.verify", side_effect=verify):
            root = Path(directory)

            def work(k):
                task = surface.parse(f"t 1\ntask same(x: int) returns (r: int)\n"
                                     f"ensures r == x + {k}\n{{ r := x + {k}; }}\n")
                local.expected = tlib.lower(task, "dafny")
                return tlib.verify(task, kernels=["dafny"], flake=1, out_dir=root / "out",
                                   cache_dir=root / "cache")

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(work, k) for k in (1, 2)]
                for future in futures:
                    future.result(timeout=20)

    def test_same_process_cache_writers_do_not_share_a_temporary_file(self):
        barrier = threading.Barrier(2)
        replace = os.replace

        def replace_together(source, destination):
            barrier.wait(timeout=10)
            return replace(source, destination)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = [{"outcome": value, "backend_version": "fake-v1"}
                    for value in (Outcome.VERIFIED, Outcome.REFUTED)]
            with patch("cache.os.replace", side_effect=replace_together), ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(cache.write, "dafny", "same", value, root) for value in data]
                for future in futures:
                    future.result(timeout=20)
            self.assertIn(cache.read("dafny", "same", root), data)
            self.assertEqual(list((root / "dafny").glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
