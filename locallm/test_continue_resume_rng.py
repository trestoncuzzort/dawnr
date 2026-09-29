"""continue_from_checkpoint resumes its generator states on the CPU (2026-09-29): state.pt is
loaded with map_location=device, which moves the saved ByteTensors to the GPU, and
torch.set_rng_state takes a CPU ByteTensor only (docs.pytorch.org, torch.set_rng_state). The
English pilot's arm B stage 2 refused its own resume with "RNG state must be a torch.ByteTensor";
restore_rng brings both streams back the way train_distributed.py always did. The CUDA case runs
where a device exists and is skipped elsewhere; the CPU case runs everywhere."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import torch  # noqa: E402

from continue_from_checkpoint import restore_rng  # noqa: E402


def _saved_state(device: str) -> dict:
    torch.manual_seed(7)
    if device.startswith("cuda"):
        torch.cuda.manual_seed_all(7)
    return {"rng": torch.get_rng_state(),
            "cuda_rng": torch.cuda.get_rng_state_all() if device.startswith("cuda") else None}


class RestoreRngTests(unittest.TestCase):
    def test_cpu_state_round_trips_through_a_file(self):
        state = _saved_state("cpu")
        expected = torch.rand(3)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.pt"
            torch.save(state, path)
            loaded = torch.load(path, map_location="cpu", weights_only=False)
        torch.manual_seed(0)  # disturb the stream
        restore_rng(loaded, "cpu", torch)
        self.assertTrue(torch.equal(expected, torch.rand(3)))

    @unittest.skipUnless(torch.cuda.is_available(), "needs a CUDA device: map_location moves the state there")
    def test_a_state_loaded_onto_the_gpu_is_restored_on_the_cpu(self):
        state = _saved_state("cuda")
        expected_cpu = torch.rand(3)
        expected_gpu = torch.rand(3, device="cuda")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.pt"
            torch.save(state, path)
            loaded = torch.load(path, map_location="cuda", weights_only=False)
        self.assertEqual("cuda", loaded["rng"].device.type)  # the failure's precondition
        torch.manual_seed(0)
        torch.cuda.manual_seed_all(0)
        restore_rng(loaded, "cuda", torch)
        self.assertTrue(torch.equal(expected_cpu, torch.rand(3)))
        self.assertTrue(torch.equal(expected_gpu, torch.rand(3, device="cuda")))


if __name__ == "__main__":
    unittest.main()
