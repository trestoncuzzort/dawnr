"""A comparison certificate must survive printing without weakening the adapter.

Sources: PREDICT-2026-10-25-framac-certificate-binding.md; ACSL local bindings.
Native proof calls are opt-in for the cloud container check.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parent))
import lower_framac
import surface
import tlib
from verifiers import cell_pair, framac


SOURCE = """t 0
task certificate_nonzero(x: int) returns (r: int)
  ensures r != 0
{
  if x < 0 { r := -1; } else { r := 1; }
}
"""


def sources():
    task = surface.parse(SOURCE)
    twin, _operator, witness = tlib.twin(task)
    assert twin is not None and witness is not None
    return lower_framac.lower(task, task["body"]), lower_framac.lower(task, twin, witness=witness)


class BindingText(unittest.TestCase):
    def test_binding_avoids_names_in_the_predicate_and_context(self):
        text = lower_framac._certificate_negation("t_refutation_clause != 0", {"t_refutation_clause_"})
        self.assertIn(r"\let t_refutation_clause__ = (t_refutation_clause != 0); t_refutation_clause__", text)

    def test_the_lowered_twin_keeps_the_original_contract(self):
        real, twin = sources()
        self.assertIn(r"ensures (\result != 0);", real)
        self.assertIn(r"ensures (\result != 0);", twin)
        self.assertIn(r"assert t_refutation_certificate: !(\let", twin)
        self.assertNotIn("axiom", twin)


@unittest.skipUnless(framac.FRAMAC, "Frama-C printer unavailable")
class PrintedBinding(unittest.TestCase):
    def test_printed_comparison_certificate_keeps_explicit_negation(self):
        _, twin = sources()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "twin.c"
            path.write_text(twin)
            printed = subprocess.run([framac.FRAMAC, "-no-autoload-plugins", "-print", str(path)],
                                     capture_output=True, text=True, timeout=30, check=True)
        self.assertTrue(framac._cert_states_negation(printed.stdout), printed.stdout)


@unittest.skipUnless(framac.FRAMAC and os.environ.get("T_RUN_NATIVE_CERTIFICATE_TESTS") == "1",
                     "native proof check is enabled in the cloud container")
class NativeBinding(unittest.TestCase):
    def test_nonzero_real_and_broken_twin_agree_three_times(self):
        real_source, twin_source = sources()
        with tempfile.TemporaryDirectory() as directory:
            real, twin = Path(directory) / "real.c", Path(directory) / "twin.c"
            real.write_text(real_source)
            twin.write_text(twin_source)
            (r, ra), (t, ta) = cell_pair(framac.verify, real, twin, 3)
        self.assertTrue(ra and ta, (r.to_json(), t.to_json()))
        self.assertEqual(r.outcome, "verified", r.to_json())
        self.assertEqual(t.outcome, "refuted", t.to_json())


if __name__ == "__main__":
    unittest.main()
