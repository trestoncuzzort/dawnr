"""The pipeline must actually use the selected core and retain its run record."""
import argparse
import tempfile
import unittest
from unittest.mock import patch

import loop_locallm


class CoreWiringTests(unittest.TestCase):
    def test_modern_training_configuration_reaches_the_trainer(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(width=512, heads=8, corpus=tmp + "/corpus.txt", model=tmp + "/model",
                                      steps=5, block=1024, layers=8, batch=2, seed=1, architecture="modern",
                                      tokenizer="bpe", vocab_size=8192, gradient_checkpointing=True)
            with patch.object(loop_locallm.subprocess, "run") as run:
                run.return_value.returncode = 0
                self.assertEqual(loop_locallm.cmd_train(args), 0)
            self.assertEqual(run.call_count, 1)
            command = run.call_args.args[0]
            self.assertEqual(command[command.index("--architecture") + 1], "modern")
            self.assertEqual(command[command.index("--tokenizer") + 1], "bpe")
            self.assertIn("--gradient-checkpointing", command)
            self.assertTrue(run.call_args.kwargs["env"]["LOCALLM_RUN_LOG"].endswith("/model/runs.jsonl"))


if __name__ == "__main__":
    unittest.main()
