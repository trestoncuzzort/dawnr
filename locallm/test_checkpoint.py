r"""Can a trained model be sampled after the session that trained it ended?

THE BUG. studio.py assigned `self.model` in exactly one place — the "done"
message at the end of a training run — and created the Sample button with
`state="disabled"`, re-enabling it only from that same handler. Nothing loaded
`<out>/ckpt.pt`. So the model on disk was unreachable from a fresh GUI: the
button stayed greyed, and `_generate` opened with `if self.model is None: return`,
which is silent. Reported as "when I sample the AI it won't talk back after
training."

RED WITNESS (source-level, because Tk needs a window station this shell has not
got — see the pre-fix file in git):
    git show <pre-fix>:localllm/studio.py | grep -A2 "def _generate"
        def _generate(self):
            if self.model is None:
                return
    grep -c "load_checkpoint\|_load_saved" studio.py   ->  0

These tests are the executable half: the load-from-disk path now exists, round
trips, and produces text. They do NOT drive the GUI — they cover the logic the
GUI delegates to, plus source-level assertions that the silent return is gone.
"""
import atexit
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import torch  # noqa: E402

import checkpoint  # noqa: E402
from data import CharTokenizer  # noqa: E402
from model import GPT, GPTConfig  # noqa: E402

STUDIO = (HERE / "studio.py").read_text(encoding="utf-8")


def _build_checkpoint() -> pathlib.Path:
    """Write a real, tiny checkpoint to a temp directory.

    These tests used to read `out_gui/`, which is whatever the author last
    trained and is not in the repository. On a fresh clone all five of them
    failed with FileNotFoundError before asserting anything — a red suite that
    says nothing about the code, which is worse than no test, because the next
    person learns to expect red.

    Untrained weights are the right fixture here: every test below is about the
    LOAD-AND-SAMPLE PATH, not about output quality. Random weights exercise the
    same save format train.py writes (`{"model": state_dict, "config":
    cfg.__dict__}` plus the tokenizer's own json), and they make the suite run
    in about a second with no GPU and no corpus.
    """
    out = pathlib.Path(tempfile.mkdtemp(prefix="locallm_ckpt_"))
    atexit.register(shutil.rmtree, out, True)

    # A vocabulary that contains the prompts the tests use, so encode/decode
    # round-trips them the way a real corpus-built tokenizer would.
    tok = CharTokenizer(sorted(set("abcdefghijklmnopqrstuvwxyz \n():=_")))
    cfg = GPTConfig(vocab_size=len(tok.chars), block_size=16,
                    n_layer=1, n_head=1, n_embd=16, dropout=0.0)
    model = GPT(cfg)
    torch.save({"model": model.state_dict(), "config": cfg.__dict__}, out / "ckpt.pt")
    tok.save(out / "tokenizer.json")
    return out


OUT = _build_checkpoint()


def test_checkpoint_exists_needs_both_files():
    """BOTH, which is the whole point of the name.

    Asserting only "a full directory is true, a missing directory is false"
    leaves the requirement untested: `(out/"ckpt.pt").exists() OR
    (out/"tokenizer.json").exists()` passes both of those. The half-checkpoints
    below are the cases that separate AND from OR — and a ckpt.pt with no
    tokenizer is the realistic one, being what an interrupted save leaves
    behind. A model that cannot decode what it generates is not a checkpoint.
    """
    assert checkpoint.checkpoint_exists(OUT), f"no trained model in {OUT}"
    assert not checkpoint.checkpoint_exists(HERE / "definitely_not_a_dir")

    for keep in ("ckpt.pt", "tokenizer.json"):
        half = pathlib.Path(tempfile.mkdtemp(prefix=f"locallm_half_{keep}_"))
        atexit.register(shutil.rmtree, half, True)
        shutil.copy(OUT / keep, half / keep)
        assert not checkpoint.checkpoint_exists(half), \
            f"a directory holding only {keep} was reported as a checkpoint"


def test_load_and_sample_round_trips():
    """The capability that did not exist: load a model trained earlier and get
    text out of it."""
    model, tok, cfg = checkpoint.load_checkpoint(OUT)
    assert cfg.vocab_size == len(tok.chars), "tokenizer/model vocab disagree"
    text = checkpoint.sample(model, tok, "def ", tokens=40, temperature=0.8, top_k=40)
    assert isinstance(text, str) and len(text) > 10, f"sampled nothing: {text!r}"
    assert text.startswith("def "), f"prompt not echoed into the sample: {text[:40]!r}"


def test_empty_prompt_still_produces_text():
    """An empty prompt encodes to nothing, and generating from an empty tensor is
    an error rather than an empty answer. Both callers used to handle this with
    their own `or [0]`; now one does."""
    model, tok, _ = checkpoint.load_checkpoint(OUT)
    assert len(checkpoint.sample(model, tok, "", tokens=20)) > 0


def test_prompt_of_unknown_characters_does_not_crash():
    """A char-level tokenizer built from this corpus has ~97 characters. A prompt
    made entirely of characters outside it encodes to nothing — the same empty
    path, reachable from the GUI's prompt box by typing an emoji."""
    model, tok, _ = checkpoint.load_checkpoint(OUT)
    assert len(checkpoint.sample(model, tok, "你好\U0001f600", tokens=20)) > 0


def test_missing_checkpoint_names_the_directory():
    """Failing silently is what caused the report. A missing model must say which
    directory it looked in."""
    try:
        checkpoint.load_checkpoint(HERE / "no_such_out")
    except FileNotFoundError as e:
        assert "no_such_out" in str(e), f"error does not name the directory: {e}"
    else:
        raise AssertionError("loading a missing checkpoint did not raise")


def test_studio_has_no_silent_return_on_missing_model():
    """The exact line that produced the symptom."""
    assert "if self.model is None:\n            return" not in STUDIO, \
        "studio._generate still returns silently when no model is loaded"


def test_studio_can_load_from_disk():
    assert "_load_saved" in STUDIO, "studio has no load-from-disk path"
    assert "checkpoint.load_checkpoint" in STUDIO, \
        "studio does not use the shared loader"


def test_studio_and_cli_share_one_sampler():
    """generate.py and the GUI must not drift apart — the parent repo has paid
    for duplicated helpers before (venv_guard.py)."""
    gen = (HERE / "generate.py").read_text(encoding="utf-8")
    assert "checkpoint.sample" in gen, "generate.py does not use the shared sampler"
    assert "checkpoint.sample" in STUDIO, "studio.py does not use the shared sampler"
    assert "model.generate(idx" not in STUDIO, \
        "studio.py still has its own copy of the sampling loop"


def test_cli_still_works():
    """Regression: the refactor must not break the documented CLI."""
    p = subprocess.run([sys.executable, str(HERE / "generate.py"),
                        "--out", str(OUT), "--prompt", "def ", "--tokens", "30"],
                       capture_output=True, text=True, timeout=600, cwd=str(HERE))
    assert p.returncode == 0, f"generate.py failed: {p.stderr[-400:]}"
    assert len(p.stdout.strip()) > 10, f"generate.py printed nothing: {p.stdout!r}"


def _seeded_model(block_size=16):
    torch.manual_seed(173)
    tok = CharTokenizer(sorted(set("abcdefghijklmnopqrstuvwxyz \n():=_")))
    cfg = GPTConfig(vocab_size=len(tok.chars), block_size=block_size,
                    n_layer=2, n_head=2, n_embd=32, dropout=0.0)
    return GPT(cfg).eval(), tok


def test_default_cache_follows_the_device():
    """CPU and CUDA decode on the cache by default when the prompt is shorter
    than the window, where it measured faster (CPU on 2026-09-26; CUDA on
    2026-09-30, t/PREDICT-2026-09-30-cached-decoding-pick.md: 0.14 of the
    uncached wall clock on the round's own path, every reply byte-equal); a
    prompt that fills the window stays uncached, where the cache measured up
    to 7 percent slower; MPS is unchanged because it was never measured
    (FINDINGS-kv-cache-2026-09-19.md). No GPU is touched here: the rule is a
    function of the device, and sample() is checked to consult it."""
    assert checkpoint.cache_by_default("cpu", 4, 16) is True
    assert checkpoint.cache_by_default(torch.device("cpu"), 15, 16) is True
    assert checkpoint.cache_by_default("cpu", 16, 16) is False
    assert checkpoint.cache_by_default("cpu", 40, 16) is False
    for device in ("cuda", "cuda:1", torch.device("cuda", 0)):
        assert checkpoint.cache_by_default(device, 4, 16) is True, device
        assert checkpoint.cache_by_default(device, 16, 16) is False, device
    for device in ("mps", "meta"):
        assert checkpoint.cache_by_default(device, 4, 16) is False, device

    model, tok = _seeded_model(block_size=16)
    seen = []
    generate = model.generate

    def spy(*args, **kwargs):
        seen.append(kwargs["use_cache"])
        return generate(*args, **kwargs)

    model.generate = spy
    checkpoint.sample(model, tok, "def ", tokens=5)
    checkpoint.sample(model, tok, "def ", tokens=5, device="cpu")
    checkpoint.sample(model, tok, "def ", tokens=5, use_cache=False)
    checkpoint.sample(model, tok, "abcdefghijklmnopq", tokens=5)       # 17 tokens, window 16
    checkpoint.sample(model, tok, "abcdefghijklmnopq", tokens=5, use_cache=True)
    assert seen == [True, True, False, False, True], seen

    asked = []
    rule = checkpoint.cache_by_default
    checkpoint.cache_by_default = lambda device, n, block: asked.append(
        (torch.device(device).type, n, block)) or False
    try:
        checkpoint.sample(model, tok, "def ", tokens=5)
    finally:
        checkpoint.cache_by_default = rule
    assert asked == [("cpu", 4, 16)] and seen[-1] is False, (asked, seen)


def test_cached_and_uncached_greedy_samples_agree():
    """The flipped default must not change what a greedy sample says: the same
    text inside the 16-token window, across it, and from a prompt longer than it."""
    model, tok = _seeded_model()
    for prompt in ("def ", "", "abcdefghijklmnopqrstu"):
        cached = checkpoint.sample(model, tok, prompt, tokens=60, temperature=0, use_cache=True)
        uncached = checkpoint.sample(model, tok, prompt, tokens=60, temperature=0, use_cache=False)
        default = checkpoint.sample(model, tok, prompt, tokens=60, temperature=0)
        assert cached == uncached == default, prompt


if __name__ == "__main__":
    fails = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            try:
                fn(); print(f"PASS {name}")
            except AssertionError as e:
                fails.append(name); print(f"FAIL {name}: {e}")
    print(f"\n{len(fails)} failed")
    raise SystemExit(1 if fails else 0)
