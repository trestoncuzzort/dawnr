"""Positive syntax controls accompany the adapter's negative review probes."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verifiers import framac as f
import lower_framac
import surface


class PrintedSyntax(unittest.TestCase):
    def test_kernel_printed_negation_is_recognized(self):
        self.assertTrue(f._cert_states_negation(
            '/*@ assert t_refutation_certificate: ¬(r ≥ 0 ∧ r ≡ x); */'))
        self.assertFalse(f._cert_states_negation(
            '/*@ assert t_refutation_certificate: 1 == 1; */'))
        self.assertFalse(f._cert_states_negation(
            r'/*@ assert t_refutation_certificate: \false_name; */'))

    def test_real_statement_suffix_does_not_mask_a_precondition(self):
        for prop, expected in [
            ('reverse_t_wp_smoke_dead_code_s8', False),
            ('f_wp_smoke_dead_code_wp_smoke_default_requires', True),
            ('f_wp_smoke_dead_code_s8_extra', True),
        ]:
            report = [{'smoke': True, 'passed': False, 'property': prop}]
            self.assertEqual(f._vacuity_smoke('', report)[0], expected)

    def test_lowered_gcd_has_a_bounded_decrease_obligation(self):
        task = surface.parse((Path(__file__).parent / 'tasks/gcd.t').read_text())
        source = lower_framac.lower(task, task['body'])
        self.assertTrue(f._wf_obligation(source, 'gcds'))

    def test_quantified_marker_and_unbounded_comparison_are_rejected(self):
        for body in [r'\true', r'\forall integer n; \true',
                     r'\forall integer n; bad(n) < bad(n) + 1']:
            self.assertFalse(f._wf_obligation('lemma bad_terminates: ' + body + ';', 'bad'))


@unittest.skipUnless(f.FRAMAC, 'Frama-C is not installed')
class NativeNegativeControls(unittest.TestCase):
    def check_refused(self, source):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'probe.c'
            path.write_text(source)
            result = f.verify(path)
        self.assertNotIn(result.outcome, (f.Outcome.VERIFIED, f.Outcome.REFUTED), result.to_json())
        self.assertNotEqual(result.outcome, f.Outcome.TOOL_ERROR, result.to_json())

    def test_unrelated_certificate(self):
        self.check_refused(r'''
            /*@ requires n >= 0;
                ensures \exists integer a,b,c,d; n == a*a+b*b+c*c+d*d; */
            void squares(int n) {}
            void t_certificate(void) {
                /*@ assert t_refutation_certificate: 1 == 1; */
            }
        ''')

    def test_precondition_vacuity_with_misleading_name(self):
        self.check_refused(r'''
            /*@ requires x > 0 && x < 0; ensures \result == 998; */
            int f_wp_smoke_dead_code(int x) { return 999; }
        ''')

    def test_inconsistent_definition_with_tautological_marker(self):
        self.check_refused(r'''
            /* t_vacuity_probe */
            /*@ logic integer bad(integer n) = bad(n) + 1;
                lemma bad_terminates_0: \true; */
            /*@ ensures bad(x) >= 0 ==> \result == 998; */
            int target(int x) { return 999; }
        ''')


if __name__ == '__main__':
    unittest.main()
