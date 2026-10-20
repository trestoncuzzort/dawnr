"""A spec_fun that calls another spec_fun, used with a division in the task body: the "dm" bridging assert must name
the ACSL logic function, never the C mirror `{name}_c`, which is unbound inside an annotation (frama-c 33.0:
"[kernel:annot-error] unbound logic function h2_0_c"; crawford-drone verify/t_mlp/p8b, 2026-10-20)."""
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import lower_framac  # noqa: E402
import tasks_io  # noqa: E402

TASK = """t 1
task nested_u(err: int, head: int) returns (y: int)
  requires err >= 0 - 64000
  requires err <= 64000
  requires head >= 0 - 64000
  requires head <= 64000
  ensures y >= 0 - 1000
  ensures y <= 1000
spec fun h1(err: int, head: int): int
= if ((3 * err + 5 * head + 7000) / 1000) < 0 then 0 else ((3 * err + 5 * head + 7000) / 1000)
spec fun h2(err: int, head: int): int
= ((11 * h1(err, head) + (0 - 4000)) / 1000)
{
  y := (11 * h2(err, head) + 3) / 1000;
  if y > 1000 {
    y := 1000;
  } else {
    if y < 0 - 1000 {
      y := 0 - 1000;
    }
  }
}
"""


class NestedSpecFunAssertTest(unittest.TestCase):
    def test_bridging_assert_names_logic_functions(self):
        path = HERE / "out" / "nested_u.t"
        path.parent.mkdir(exist_ok=True)
        path.write_text(TASK, encoding="utf-8")
        task = tasks_io.load_task(path)
        src = lower_framac.lower(task, task["body"])
        annots = re.findall(r"/\*@.*?\*/", src, flags=re.S)
        self.assertTrue(annots)
        for a in annots:
            self.assertNotIn("_c(", a, msg=f"C mirror inside an ACSL annotation:\n{a[:300]}")
        self.assertIn("int h2_c(", src)            # the executable mirror still exists for the body
        self.assertIn("h2(err, head)", "".join(a for a in annots if "assert" in a))   # the bridging assert names the logic function


if __name__ == "__main__":
    unittest.main()
