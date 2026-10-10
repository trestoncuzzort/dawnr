"""Regression witnesses for loading more than one Dafny translation in a process."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import judge
import surface


@unittest.skipUnless(judge.DAFNY, "Dafny is not installed")
class JudgeCompilationTests(unittest.TestCase):
    def compile(self, root, name, source):
        work = root / name
        work.mkdir()
        return judge.compile_task(surface.parse(source), work)

    def test_underscores_use_the_compilers_python_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            call = self.compile(Path(tmp), "underscores", "t 1 task with_under_score(x: int) returns (r: int) "
                                "ensures r == x + 1 { r := x + 1; }")
            self.assertEqual(call((9,)), 10)

    def test_same_name_different_bodies_remain_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self.compile(root, "first", "t 1 task probe(x: int) returns (r: int) "
                                 "ensures r == x + 1 { r := x + 1; }")
            second = self.compile(root, "second", "t 1 task probe(x: int) returns (r: int) "
                                  "ensures r == x + 2 { r := x + 2; }")
            self.assertEqual(first((5,)), 6)
            self.assertEqual(second((5,)), 7)
            self.assertEqual(first((-5,)), -4)

    def test_recursion_and_sequences_keep_their_own_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self.compile(root, "first", """t 1 gate recursion
                task probe(n: int) returns (r: int)
                  requires n >= 0 ensures r == n decreases n
                { if n == 0 { r := 0; } else { r := 1 + probe(n - 1); } }
                """)
            second = self.compile(root, "second", """t 1
                task probe(s: seq) returns (r: seq)
                  ensures r == s + [9]
                { r := s + [9]; }
                """)
            self.assertEqual(first((4,)), 4)
            self.assertEqual(second(([1, 2],)), [1, 2, 9])
            self.assertEqual(first((6,)), 6)

    def test_import_state_is_restored(self):
        before_path = list(sys.path)
        before = {n: m for n, m in sys.modules.items()
                  if n in ("module_", "System_", "_dafny") or
                  n.startswith(("module_.", "System_.", "_dafny."))}
        with tempfile.TemporaryDirectory() as tmp:
            self.compile(Path(tmp), "first", "t 1 task different(x: int) returns (r: int) "
                         "ensures r == x { r := x; }")
        after = {n: m for n, m in sys.modules.items()
                 if n in ("module_", "System_", "_dafny") or
                 n.startswith(("module_.", "System_.", "_dafny."))}
        self.assertEqual(sys.path, before_path)
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
