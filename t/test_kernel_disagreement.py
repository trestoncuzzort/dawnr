"""The disagreement census must be able to find a disagreement.

It reports 0 contradictions over 3,321 graded programs. A zero from a detector
nobody tested is indistinguishable from a broken parser, and this project has
already published one zero that was a property of the search rather than of the
data (locallm/FINDINGS-completeness-2026-09-20.md). These feed it contradictions
it must catch and agreements it must not flag.
"""
import tempfile
import unittest
from pathlib import Path

import kernel_disagreement as kd

HEAD = ("| task | dafny | verus | spark | framac | lean | rocq | fstar |\n"
        "|---|---|---|---|---|---|---|---|\n")
OK = "verified / refuted"


def table(*rows):
    d = Path(tempfile.mkdtemp()) / "tag"
    d.mkdir()
    (d / "kernels.md").write_text(HEAD + "".join(rows), encoding="utf-8")
    return [d / "kernels.md"]


def row(name, *cells):
    return f"| {name} | " + " | ".join(cells) + " |\n"


class DetectorTests(unittest.TestCase):
    def test_it_catches_verified_against_refuted(self):
        t = table(row("mbpp_1__f", OK, OK, OK, OK, OK, OK, "refuted / refuted"))
        r = kd.scan(t)
        self.assertEqual(len(r["real_contradictions"]), 1)
        c = r["real_contradictions"][0]
        self.assertEqual(c["refuted"], ["fstar"])
        self.assertEqual(r["minority"]["fstar"], 1, "the lone dissenter is the one to audit")

    def test_it_catches_a_twin_that_verifies_where_others_refute(self):
        t = table(row("mbpp_2__g", OK, OK, OK, OK, OK, OK, "verified / verified"))
        r = kd.scan(t)
        self.assertEqual(len(r["twin_unsound"]), 1)
        self.assertEqual(r["twin_unsound"][0]["twin_verified"], ["fstar"])

    def test_full_agreement_is_not_flagged(self):
        r = kd.scan(table(row("mbpp_3__h", *[OK] * 7)))
        self.assertEqual(r["real_contradictions"], [])
        self.assertEqual(r["twin_unsound"], [])
        self.assertEqual(r["rows"], 1)

    def test_a_gap_is_not_a_contradiction(self):
        """unproved is not refuted: a prover that cannot decide has not disagreed."""
        t = table(row("mbpp_4__i", OK, OK, OK, OK, OK, OK, "unproved / refuted"))
        r = kd.scan(t)
        self.assertEqual(r["real_contradictions"], [], "unproved must not count as refuted")
        self.assertEqual(r["gap_majority"]["fstar"], 1)

    def test_a_flaked_suffix_does_not_hide_the_verdict(self):
        t = table(row("mbpp_5__j", OK, OK, OK, OK, OK, OK, "refuted (FLAKED) / refuted"))
        self.assertEqual(len(kd.scan(t)["real_contradictions"]), 1,
                         "a FLAKED suffix still carries its verdict word")

    def test_it_reads_the_real_tables_without_dropping_rows(self):
        """Guards the parser: a silent parse failure would also report zero."""
        from pathlib import Path as P
        tables = sorted((P(kd.__file__).parent / "out" / "spec-experiment").glob("*/kernels.md"))
        if not tables:
            self.skipTest("no graded sets present")
        r = kd.scan(tables)
        expected = 0
        for t in tables:          # every data row of the agreement table (the one headed `| task |`), counted without the parser
            inside = False
            for line in t.read_text(encoding="utf-8").splitlines():
                if line.startswith("#"):
                    inside = False
                    continue
                cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else []
                if cells and cells[0] == "task":
                    inside = True
                elif inside and cells and cells[0] and not set(cells[0]) <= set("-: "):
                    expected += 1
        self.assertEqual(r["rows"], expected, "the parser should see every graded row the files hold")
        self.assertGreater(sum(r["gap_majority"].values()), 0,
                           "some kernel somewhere failed to decide; zero means nothing parsed")


if __name__ == "__main__":
    unittest.main()


# Five findings of the GPT-6 Astra review of 2026-10-13: each table under its own header, ties and twin-side
# minorities counted fairly, the no-contradiction claim scoped to the selection, every kernel in the gap report.


def test_reordered_second_table_does_not_misattribute_verdicts():
    import tempfile
    from pathlib import Path
    import kernel_disagreement as kd

    names = ['dafny', 'verus', 'spark', 'framac', 'lean', 'rocq', 'fstar']
    def header(ns):
        return '| task | ' + ' | '.join(ns) + ' |\n' + '|---' * (len(ns) + 1) + '|\n'
    def row(task, cells):
        return '| ' + task + ' | ' + ' | '.join(cells) + ' |\n'
    ok = 'verified / refuted'
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'kernels.md'
        p.write_text(header(names) + row('p', [ok] * 7) + '\n' + header(names[::-1]) + row('q', ['refuted / refuted'] + [ok] * 6), encoding='utf-8')
        try:
            result = kd.scan([p])
        except ValueError:
            return  # Explicit refusal is preferable to fabricated attribution.
        assert result['rows'] == 2
        assert result['real_contradictions'][0]['refuted'] == ['fstar']


def test_tied_votes_are_not_biased_toward_verified():
    import tempfile
    from pathlib import Path
    import kernel_disagreement as kd

    head = '| task | dafny | verus | spark | framac | lean | rocq | fstar |\n|---|---|---|---|---|---|---|---|\n'
    cells = ['verified / refuted', 'refuted / refuted'] + ['unproved / refuted'] * 5
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'kernels.md'
        p.write_text(head + '| p | ' + ' | '.join(cells) + ' |\n', encoding='utf-8')
        result = kd.scan([p])
    assert result['minority']['dafny'] == result['minority']['verus']


def test_twin_majority_is_not_reported_as_minority():
    import tempfile
    from pathlib import Path
    import kernel_disagreement as kd

    names = ['dafny', 'verus', 'spark', 'framac', 'lean', 'rocq', 'fstar']
    head = '| task | ' + ' | '.join(names) + ' |\n' + '|---' * 8 + '|\n'
    cells = ['verified / verified'] * 6 + ['verified / refuted']
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'kernels.md'
        p.write_text(head + '| p | ' + ' | '.join(cells) + ' |\n', encoding='utf-8')
        result = kd.scan([p])
    assert len(result['twin_unsound']) == 1
    assert all(result['minority'][k] == 0 for k in names[:-1]), result['minority']


def test_filtered_report_does_not_claim_all_sets_agree():
    import tempfile
    from pathlib import Path
    from io import StringIO
    from contextlib import redirect_stdout
    from unittest.mock import patch
    import kernel_disagreement as kd

    head = '| task | dafny | verus | spark | framac | lean | rocq | fstar |\n|---|---|---|---|---|---|---|---|\n'
    ok = 'verified / refuted'
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for tag, last in [('selected', ok), ('excluded', 'refuted / refuted')]:
            directory = root / tag
            directory.mkdir()
            cells = [ok] * 6 + [last]
            (directory / 'kernels.md').write_text(head + '| p | ' + ' | '.join(cells) + ' |\n', encoding='utf-8')
        output = StringIO()
        with patch.object(kd, 'SE', root), patch('sys.argv', ['kernel_disagreement.py', '--tag', 'selected']), redirect_stdout(output):
            assert kd.main() == 0
        assert 'Across every graded answer set' not in output.getvalue()


def test_gap_report_includes_kernels_from_later_tables():
    import tempfile
    from pathlib import Path
    from io import StringIO
    from contextlib import redirect_stdout
    from unittest.mock import patch
    import kernel_disagreement as kd

    names = ['dafny', 'verus', 'spark', 'framac', 'lean', 'rocq', 'fstar']
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for tag, ns in [('a', names[:-1]), ('b', names)]:
            directory = root / tag
            directory.mkdir()
            head = '| task | ' + ' | '.join(ns) + ' |\n' + '|---' * (len(ns) + 1) + '|\n'
            cells = ['verified / refuted'] * len(ns)
            if tag == 'b':
                cells[-1] = 'unproved / refuted'
            (directory / 'kernels.md').write_text(head + '| p | ' + ' | '.join(cells) + ' |\n', encoding='utf-8')
        output = StringIO()
        with patch.object(kd, 'SE', root), patch('sys.argv', ['kernel_disagreement.py']), redirect_stdout(output):
            assert kd.main() == 0
        assert '| fstar | 1 |' in output.getvalue()
