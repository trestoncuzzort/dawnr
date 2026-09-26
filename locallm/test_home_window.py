"""Step 4 in a real Tk window, with torch made absent: it talks, it streams, it stops.

test_home.py never builds a window; this file does, so it needs a display and
skips without one. Run it headless:

    xvfb-run -a python3 -m unittest test_home_window -v

studio is made to look missing whatever is installed (home.engine's cache is
filled with the sentence a machine without torch produces), and the page is
pointed at a scratch folder whose `included-model` is a real checkpoint from this
repository, read by plain_generate. What is checked is what a person would see:
the text in the reply box grows while the model is writing, rather than
appearing at the end; Stop ends it early and says so; and a run left alone
writes exactly what plain_generate.sample writes for the same prompt.
"""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import time
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import home  # noqa: E402

MODEL = HERE.parent / "t/runs/2026-09-16/filter-loop/clean/r0/model"   # context 128


def usable():
    if not (os.environ.get("DISPLAY") or sys.platform in ("win32", "darwin")):
        return "no display; run under xvfb-run -a"
    ckpt = MODEL / "ckpt.pt"
    if not ckpt.is_file() or ckpt.stat().st_size < 1000:
        return "the checkpoint's weights are not in this checkout (git lfs pull)"
    return ""


@unittest.skipIf(usable(), usable())
class StepFourWithoutTorch(unittest.TestCase):
    def setUp(self):
        import tkinter as tk                                     # noqa: PLC0415
        self.tmp = tempfile.TemporaryDirectory()
        folder = pathlib.Path(self.tmp.name)
        (folder / home.INCLUDED).symlink_to(MODEL, target_is_directory=True)
        self.saved = (home.HERE, list(home._ENGINE))
        home.HERE = folder
        home._ENGINE[:] = [(None, "ModuleNotFoundError: No module named 'torch'")]
        self.root = tk.Tk()
        self.page = home.Home(self.root)

    def tearDown(self):
        for cb in self.root.tk.call("after", "info"):
            self.root.after_cancel(cb)
        self.root.destroy()
        home.HERE, home._ENGINE[:] = self.saved[0], self.saved[1]
        self.tmp.cleanup()

    def pump(self, until, seconds=60.0):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.root.update()
            if until():
                return True
            time.sleep(0.01)
        return False

    def reply(self):
        return self.page.reply.get("1.0", "end-1c")

    def card(self):
        return self.page._marks[4].cget("text"), self.page._says[4].cget("text")

    def start(self, prompt, tokens):
        page = self.page
        self.assertTrue(page.b_ready._enabled, "the included model was not offered")
        self.assertIn("plain Python", self.card()[1])
        page.b_ready._press()
        self.assertTrue(page.plain, "it did not load through plain_generate")
        self.assertIn("Ready", self.card()[0])
        page.v_prompt.set(prompt)
        page.v_tokens.set(str(tokens))
        page.b_write._press()
        self.assertTrue(page.b_hush._enabled, "Stop is not live while writing")
        self.assertFalse(page.b_write._enabled)

    def test_the_text_appears_as_it_is_written(self):
        """Watched from inside mainloop, the way a person watches it.

        Polling with root.update() from the test cannot tell: the whole run
        happened inside one update() call when this was first written. A
        sampler scheduled on the Tk loop itself sees what the screen shows,
        and at Python's default 5 ms switch interval it saw the text arrive
        in two jumps in 2.4 s, which is what home.py's switch-interval change
        fixes (the test failed that way before it).
        """
        import sys as _sys                                        # noqa: PLC0415
        before = _sys.getswitchinterval()
        self.start("function to ", 60)
        seen = []

        def look():
            seen.append(len(self.reply()))
            if self.page.b_hush._enabled:
                self.root.after(50, look)
            else:
                self.root.quit()
        self.root.after(50, look)
        self.root.after(120_000, self.root.quit)          # a hang fails, not blocks
        self.root.mainloop()
        self.assertFalse(self.page.b_hush._enabled, "writing never finished")
        steps = len(set(seen))
        self.assertGreaterEqual(steps, 8, f"the reply arrived in {steps} steps, not "
                                          f"as it was written")
        self.assertEqual(len(self.reply()), len("function to ") + 60)
        self.assertIn("Written", self.card()[0])
        self.assertIn("a second on this computer", self.card()[1])
        self.assertTrue(self.page.b_write._enabled)
        self.assertEqual(_sys.getswitchinterval(), before, "the interval was not put back")

    def test_stop_ends_it_early_and_says_so(self):
        self.start("task ", 400)
        self.assertTrue(self.pump(lambda: len(self.reply()) > len("task ") + 5))
        self.page.b_hush._press()
        self.assertTrue(self.pump(lambda: self.page.b_write._enabled, seconds=10),
                        "Stop did not end the writing within ten seconds")
        self.assertLess(len(self.reply()), len("task ") + 400)
        mark, why = self.card()
        self.assertIn("Stopped", mark)
        self.assertIn("as asked", why)
        self.assertFalse(self.page.b_hush._enabled)


if __name__ == "__main__":
    unittest.main(verbosity=2)
