"""Controls for a Python-only sibling escaping a t-program audit."""
import unittest
import student_row_families as families


class FamilyControls(unittest.TestCase):
    def test_python_sibling_and_unrelated_problem(self):
        rows = [{"task_id": 227, "source": "graded"},
                {"task_id": "227", "source": "python"},
                {"task_id": 228, "source": "python"},
                {"name": "mbpp_227__min_of_three", "kind": "spec-given"}]
        gone, report = families.close(rows, [0], {227, 228})
        self.assertEqual(gone, {0, 1, 3})
        self.assertEqual(report["family_only_rows"], [1, 3])

    def test_anonymous_rows_do_not_share_identity(self):
        rows = [{}, {"name": None}, {"name": "None"}, {"name": ""}]
        self.assertEqual(families.close(rows, [0], set())[0], {0})

    def test_document_spellings(self):
        rows = [{"name": "vericoding_DD0052"}, {"name": "vericoding_dd0052__calDiv"},
                {"name": "vericoding_dd0053__other"}]
        self.assertEqual(families.close(rows, [0], set())[0], {0, 1})

    def test_split_also_refuses_python_only_row(self):
        self.assertEqual(families.close([{"task_id": 227}], [], {228})[0], {0})

    def test_invalid_id_or_conflicting_name(self):
        for row in ({"task_id": True}, {"task_id": 1.5}, {"task_id": "bad"},
                    {"task_id": -1}, {"task_id": 227, "name": "mbpp_228__other"}):
            with self.subTest(row=row), self.assertRaises(ValueError):
                families.close([row], [], {227, 228})

    def test_invalid_finding_fails_closed(self):
        for index in (-1, 1, "0", True):
            with self.subTest(index=index), self.assertRaises(ValueError):
                families.close([{}], [index], set())

    def test_missing_dataset_is_an_error_not_a_split_rejection(self):
        rows = [{"task_id": 200157}, {"task_id": 227}]
        with self.assertRaisesRegex(ValueError, "missing 1 identified"):
            families.require_pool_coverage(rows, {227: {}})
        families.require_pool_coverage(rows, {227: {}, 200157: {}})
        families.require_pool_coverage(rows, {227: {}}, {227})


if __name__ == "__main__":
    unittest.main()
