"""student_generate.decode halves a batch that runs out of memory (accelerate's find_executable_batch_size,
github.com/huggingface/accelerate utils/memory.py) and gives an empty reply only to a prompt that never fits."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import student_generate as sg  # noqa: E402


def fake(limit, calls, never=()):
    def run(model, tok, convs, max_new, temperature, top_p, seed):
        calls.append((len(convs), seed))
        if len(convs) > limit or any(c in never for c in convs):
            raise RuntimeError("CUDA out of memory. Tried to allocate 6.42 GiB")
        return [(f"r{c}", True, 1) for c in convs]
    return run


class Halving(unittest.TestCase):
    def test_splits_until_it_fits_and_keeps_order(self):
        calls = []
        out = sg.decode(None, None, list(range(8)), 16, 0.7, 0.95, 5, fake(2, calls))
        self.assertEqual([t for t, _, _ in out], [f"r{i}" for i in range(8)])
        # depth first: 8 fails, its first 4 fails, two 2s pass, the second 4 fails, two 2s pass; each half's seed + 1
        self.assertEqual(calls, [(8, 5), (4, 5), (2, 5), (2, 6), (4, 6), (2, 6), (2, 7)])

    def test_a_prompt_that_never_fits_gets_an_empty_reply(self):
        calls = []
        out = sg.decode(None, None, [0, 1, 2, 3], 16, 0.0, 0.95, None, fake(4, calls, never=(2,)))
        self.assertEqual(out[2], ("", False, 0))
        self.assertEqual([t for t, _, _ in out[:2] + out[3:]], ["r0", "r1", "r3"])

    def test_other_errors_are_raised(self):
        def bad(*a):
            raise ValueError("not memory")
        with self.assertRaises(ValueError):
            sg.decode(None, None, [0, 1], 16, 0.0, 0.95, None, bad)


if __name__ == "__main__":
    unittest.main()
