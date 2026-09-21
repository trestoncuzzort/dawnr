"""A uniform soup is the elementwise mean of its ingredients, and nothing else.

soup.average is the whole method of Wortsman et al. (arXiv:2203.05482) for the
uniform case, so these tests pin the arithmetic and the refusals: a soup of
models that are not fine-tunes of one core is not a soup, and averaging it
anyway would produce a model nobody trained.
"""
import sys
import tempfile
import unittest
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import soup  # noqa: E402


def ck(scale, *, config=None, fp="f", mask=None, dtype=torch.float32):
    return {"config": config or {"n_layer": 1, "n_embd": 4},
            "tokenizer_fingerprint": fp,
            "model": {"w": torch.full((2, 3), float(scale), dtype=dtype),
                      "mask": mask if mask is not None else torch.tril(torch.ones(3, 3, dtype=torch.bool))}}


class UniformSoup(unittest.TestCase):
    def test_float_weights_are_the_mean(self):
        out = soup.average([ck(1), ck(2), ck(6)])
        self.assertTrue(torch.equal(out["model"]["w"], torch.full((2, 3), 3.0)))

    def test_dtype_is_kept_and_the_sum_is_taken_in_float32(self):
        # 3 bf16 values whose bf16 running sum would round: the mean must match float32 arithmetic
        vals = [1.0, 1.0078125, 1.015625]
        out = soup.average([ck(v, dtype=torch.bfloat16) for v in vals])
        self.assertEqual(out["model"]["w"].dtype, torch.bfloat16)
        want = torch.tensor(sum(vals) / 3, dtype=torch.float32).to(torch.bfloat16)
        self.assertTrue(torch.all(out["model"]["w"] == want))

    def test_a_soup_of_one_model_repeated_is_that_model(self):
        out = soup.average([ck(5), ck(5)])
        self.assertTrue(torch.equal(out["model"]["w"], ck(5)["model"]["w"]))
        self.assertEqual(out["config"], ck(5)["config"])
        self.assertEqual(out["tokenizer_fingerprint"], "f")

    def test_identical_buffers_are_copied_differing_ones_refused(self):
        out = soup.average([ck(1), ck(2)])
        self.assertTrue(torch.equal(out["model"]["mask"], ck(1)["model"]["mask"]))
        with self.assertRaises(ValueError):
            soup.average([ck(1), ck(2, mask=torch.ones(3, 3, dtype=torch.bool))])

    def test_different_models_are_refused_not_averaged(self):
        for other in (ck(2, config={"n_layer": 2, "n_embd": 4}), ck(2, fp="g")):
            with self.subTest(other=other["config"], fp=other["tokenizer_fingerprint"]):
                with self.assertRaises(ValueError):
                    soup.average([ck(1), other])
        extra = ck(2)
        extra["model"]["extra"] = torch.zeros(1)
        with self.assertRaises(ValueError):
            soup.average([ck(1), extra])

    def test_optimizer_state_does_not_reach_the_soup(self):
        a, b = ck(1), ck(2)
        a["optimizer"] = {"state": 1}
        self.assertNotIn("optimizer", soup.average([a, b]))

    def test_the_command_refuses_ingredients_from_different_cores(self):
        with tempfile.TemporaryDirectory() as tmp:
            dirs = []
            for i, init in enumerate(("core-a", "core-b")):
                d = Path(tmp) / f"m{i}"
                d.mkdir()
                torch.save(ck(i), d / "ckpt.pt")
                (d / "tokenizer.json").write_text("{}")
                (d / "run.json").write_text('{"identities": {"init_ckpt_sha256": "%s"}}' % init)
                dirs.append(str(d))
            sys.argv = ["soup.py", "--out", str(Path(tmp) / "soup"), *dirs]
            with self.assertRaises(SystemExit):
                soup.main()
            self.assertFalse((Path(tmp) / "soup" / "ckpt.pt").exists())


if __name__ == "__main__":
    unittest.main()
