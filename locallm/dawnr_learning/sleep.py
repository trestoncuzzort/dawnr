"""sleep.py: between sessions, a person's adapter learns from what they told dawnr, with replay against forgetting.

    python3 locallm/dawnr_learning sleep --person NAME --model <chat checkpoint dir> \
        [--replay conversations.jsonl] [--guard-text validation.txt] [--device cuda]

One sleep, in order:

1. The person's examples (feedback.PersonStore.training_examples: rated up,
   edited, or marked wrong with a correction; every target checked by the t
   tool, nothing from outside). training_examples() itself applies the same
   held-out gates every trainer here uses (feedback.held_out_gate:
   loop_filter.validate_training_data over the held-out ids and the same-task
   exclusions, and the r12 dev ids) before this or any other reader sees the
   examples, so an example that names a held-out problem is dropped and
   counted here whatever the person typed.
2. A cap on how many are used: beyond `max_examples` a seeded random subset is
   kept. Rolnick et al. (arXiv:1811.11682) found that randomly discarding data
   from a capped replay buffer does almost as well as keeping everything.
3. A hash split of the person's examples into train and validation; the
   validation part chooses when to stop and which weights to keep (the
   product's rule, train.EarlyStopper: stop when validation has not improved by
   more than noise for `patience` checks, keep the best weights).
4. A LoRA adapter (model.add_lora, attention and MLP, arXiv:2106.09685) on the
   frozen base, trained on batches that mix the person's rows with rows replayed
   from the base's own training conversations, an exact number per batch
   (continue_from_checkpoint.replay_rows' rule; Ibrahim et al.,
   arXiv:2403.08763, replay a fraction of the previous data against
   forgetting). Loss on the assistant's tokens only (chat.render_conversation's
   mask: the person's words and tool outputs are never targets).
5. A guard before anything is kept: the adapter's loss on held-out plain source
   code (the core's own validation text, never trained on) against the frozen
   base's on the same fixed windows. A rise over `guard_tolerance` nats per
   token refuses the adapter: the person keeps the one they had. Loss on t
   conversations is not the guard, because a person's style legitimately makes
   the canonical style less likely; plain code is style-neutral.
6. The adapter is saved with its manifest (adapters.save_adapter): the base,
   the examples it was trained on by id and hash, its size under the cap.

Two modes. `rebuild` (the default) trains a fresh adapter on everything the
person has kept; it is exact: an erased example is simply absent, and its cost
grows with the whole store. `continue` starts from the previous adapter and
plans its steps from the examples that adapter has not seen, with `old_share`
of the person's rows in every batch drawn from the older ones (Rolnick et al.'s
replay of past events), and optionally EWC (Kirkpatrick et al.,
arXiv:1612.00796): a quadratic anchor to the previous adapter weighted by the
diagonal Fisher of the examples it was trained on, saved beside it
(`fisher=True`). Its cost grows with the new examples only. `continue` refuses
to run on a stale adapter (something it learned from was erased or corrected),
since continuing would keep what the person asked to forget. It is built and
tested; it has not been measured against `rebuild` (DAWNR-LEARNING.md says so).

The base's weights are fingerprinted before and after (model.base_fingerprint):
a sleep that changed them would be a bug, and it raises.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCALLM = HERE.parent
ROOT = LOCALLM.parent
for p in (str(LOCALLM), str(ROOT / "t")):
    if p not in sys.path:
        sys.path.insert(0, p)


@dataclass
class SleepConfig:
    r: int = 8
    alpha: float | None = None          # None: alpha = r (scaling 1), the LoRA paper's untuned default
    dropout: float = 0.05
    lr: float = 3e-4                    # the 2026-09-27 pilot: 1e-3 broke the programs within 10 steps
    weight_decay: float = 0.0
    batch_size: int = 8
    replay_frac: float = 0.25           # share of every batch's rows from the base's conversations; 0 = none
    epochs: float = 10.0                # planned steps: epochs over the person's training rows ...
    min_steps: int = 30                 # ... at least this many ...
    max_steps: int = 300                # ... and never more than this (the step cap)
    warmup: int = 5
    grad_clip: float = 1.0
    max_step_tokens: int = 5120         # padded tokens per forward pass; a larger batch is accumulated in parts
    eval_every: int = 10
    patience: int = 4                   # checks without improvement (train.EarlyStopper counts checks)
    min_delta: float = 0.005            # train.EARLY_STOP_MIN_DELTA
    val_frac: float = 0.2
    max_examples: int = 2000
    max_adapter_bytes: int = 16 * 2 ** 20
    guard_tolerance: float | None = 0.05
    behavior_tolerance: int = 1         # the behaviour guard allows this many fewer passing answers than the base
    mode: str = "rebuild"               # or "continue"
    old_share: float = 0.5              # continue mode: share of the person's rows from examples seen before
    ewc_lambda: float = 0.0             # continue mode: the EWC anchor's strength
    fisher: bool = False                # compute and save the diagonal Fisher (for a later continue)
    seed: int = 1337

    def __post_init__(self):
        if self.mode not in ("rebuild", "continue"):
            raise ValueError("mode is rebuild or continue")
        if not 0 <= self.replay_frac < 1 or not 0 <= self.val_frac < 1:
            raise ValueError("replay_frac and val_frac lie in [0, 1)")
        if self.batch_size < 1 or self.max_steps < 1 or self.eval_every < 1 or self.r < 1:
            raise ValueError("batch_size, max_steps, eval_every and r are positive")
        if self.ewc_lambda and self.mode != "continue":
            raise ValueError("EWC anchors to a previous adapter: it needs mode='continue'")


# -------------------------------------------------------------- examples --

# The held-out gate now lives on the store (feedback.held_out_gate), so training_examples() applies it for
# every reader instead of each trainer re-applying its own copy (DAWNR-LEARNING.md section 8: style_profile
# read around the copy that used to live only here). Kept importable as sleep.gate_examples for callers
# that already spell it that way; it is the same function, not a second implementation of the same check.
from .feedback import held_out_gate as gate_examples  # noqa: E402,F401


def cap_examples(examples: list[dict], cap: int, seed: int) -> list[dict]:
    """At most `cap` examples: a seeded random subset beyond it (Rolnick et al.'s random discard)."""
    if len(examples) <= cap:
        return list(examples)
    rng = random.Random(seed)
    chosen = sorted(rng.sample(range(len(examples)), cap))
    return [examples[i] for i in chosen]


def hash_unit(text: str, seed: int) -> float:
    digest = hashlib.sha256(f"{seed}\x00{text}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2 ** 64


def split_examples(examples: list[dict], val_frac: float, seed: int) -> tuple[list[dict], list[dict]]:
    """A hash split by example content; at least one on each side when there are two or more."""
    if len(examples) < 2 or val_frac <= 0:
        return list(examples), []
    ranked = sorted(examples, key=lambda e: hash_unit(e["hash"], seed))
    n_val = min(len(examples) - 1, max(1, round(val_frac * len(examples))))
    val_ids = {e["id"] for e in ranked[:n_val]}
    return [e for e in examples if e["id"] not in val_ids], [e for e in examples if e["id"] in val_ids]


def render_fit(tokenizer, messages: list[dict], block: int):
    """(ids, mask) of a conversation that fits the block, dropping its oldest turn pairs if it must; else None."""
    import chat
    messages = list(messages)
    while True:
        ids, mask = chat.render_conversation(tokenizer, {"messages": messages})
        if len(ids) <= block + 1:
            return ids, mask
        if len(messages) <= 2:
            return None
        messages = messages[2:]


class Rows:
    """Rendered conversations; batches padded to their own longest row; targets masked to the assistant."""

    def __init__(self, tokenizer, conversations: list[dict], block: int, pad_id: int = 0):
        self.rows, self.too_long = [], 0
        for conv in conversations:
            fit = render_fit(tokenizer, conv["messages"], block)
            if fit is None:
                self.too_long += 1
                continue
            ids, mask = fit
            self.rows.append((ids[:-1], [t if m else -1 for t, m in zip(ids[1:], mask[1:])]))
        self.pad_id = pad_id

    def __len__(self) -> int:
        return len(self.rows)

    def target_tokens(self) -> int:
        return sum(sum(1 for t in y if t != -1) for _x, y in self.rows)

    def batch(self, indices, device):
        import torch
        chosen = [self.rows[i] for i in indices]
        width = max(len(x) for x, _y in chosen)
        x = torch.full((len(chosen), width), self.pad_id, dtype=torch.long)
        y = torch.full((len(chosen), width), -1, dtype=torch.long)
        for i, (xi, yi) in enumerate(chosen):
            x[i, :len(xi)] = torch.tensor(xi, dtype=torch.long)
            y[i, :len(yi)] = torch.tensor(yi, dtype=torch.long)
        return x.to(device), y.to(device)


def mean_loss(model, rows: Rows, device, batch_size: int = 8, autocast=None) -> float | None:
    """Token-weighted mean loss over every row (the assistant's tokens only), in eval mode."""
    import torch
    if rows is None or not len(rows):
        return None
    was = model.training
    model.eval()
    total = count = 0.0
    with torch.no_grad():
        for start in range(0, len(rows), batch_size):
            x, y = rows.batch(range(start, min(start + batch_size, len(rows))), device)
            n = int((y != -1).sum())
            if not n:
                continue
            if autocast is not None:
                with autocast:
                    _, loss = model(x, y)
            else:
                _, loss = model(x, y)
            total += float(loss) * n
            count += n
    model.train(was)
    return total / count if count else None


class GuardWindows:
    """Fixed windows of held-out plain source code, the same ones before and after (a style-neutral loss)."""

    def __init__(self, tokenizer, text: str, block: int, windows: int = 16, seed: int = 12345):
        import torch
        ids = tokenizer.encode(text)
        if len(ids) < block + 2:
            raise ValueError(f"the guard text holds {len(ids)} tokens, not one window of {block}")
        g = torch.Generator().manual_seed(seed)
        starts = torch.randint(len(ids) - block - 1, (windows,), generator=g).tolist()
        self.x = torch.tensor([ids[s:s + block] for s in starts], dtype=torch.long)
        self.y = torch.tensor([ids[s + 1:s + block + 1] for s in starts], dtype=torch.long)
        self.block, self.windows = block, windows

    def loss(self, model, device, batch_size: int = 4, autocast=None) -> float:
        import torch
        was = model.training
        model.eval()
        total = 0.0
        with torch.no_grad():
            for s in range(0, self.windows, batch_size):
                x, y = self.x[s:s + batch_size].to(device), self.y[s:s + batch_size].to(device)
                if autocast is not None:
                    with autocast:
                        _, loss = model(x, y)
                else:
                    _, loss = model(x, y)
                total += float(loss) * len(x)
        model.train(was)
        return total / self.windows


class BehaviorGuard:
    """Prompts the frozen base answers, asked again with the adapter on; the t tool judges every answer.

    A loss cannot see this failure: the pilot of 2026-09-27 (DAWNR-LEARNING.md)
    fitted a person's style to 0.14 nats per token on held-out examples of it
    while every answer the adapted model then wrote failed the t tool. So a
    sleep keeps an adapter state only while dawnr still writes programs that
    pass on these prompts at least as often as the base did, less a tolerance:
    dawnr's rule that nothing is relied on before it is checked, applied to
    dawnr's own weights. The prompts must never be trained on in the same sleep
    (the caller keeps them out of the replay rows), or the check would be a
    rehearsal."""

    def __init__(self, prompts: list[str], max_tokens: int = 640):
        if not prompts:
            raise ValueError("a behaviour guard needs prompts")
        self.prompts, self.max_tokens = list(prompts), max_tokens

    def check(self, model, tokenizer) -> dict:
        from chat_eval import ask
        from dawnr_harness.checker import check
        from engine import Engine
        from .feedback import final_program
        was = model.training
        model.eval()
        engine = Engine(model, tokenizer)
        each = []
        for user in self.prompts:
            got = ask(engine, tokenizer, user, self.max_tokens)
            program = final_program(got["parts"]) if got["parts"] else None
            each.append(bool(program) and check(program, user)[0])
        model.train(was)
        return {"passed": sum(each), "asked": len(each), "each": each}


# -------------------------------------------------------------- training --

def diagonal_fisher(model, rows: Rows, device, autocast=None) -> dict:
    """The empirical diagonal Fisher of the adapter's parameters on these rows: mean squared gradient of each
    row's loss (EWC, arXiv:1612.00796: first-order derivatives only). CPU tensors keyed as in lora_state."""
    import torch
    from model import lora_modules
    params = {}
    for name, m in lora_modules(model):
        params[name + ".lora_A"], params[name + ".lora_B"] = m.lora_A, m.lora_B
    fisher = {k: torch.zeros_like(p, device="cpu", dtype=torch.float32) for k, p in params.items()}
    was = model.training
    model.eval()
    n = 0
    for i in range(len(rows)):
        x, y = rows.batch([i], device)
        if not int((y != -1).sum()):
            continue
        model.zero_grad(set_to_none=True)
        if autocast is not None:
            with autocast:
                _, loss = model(x, y)
        else:
            _, loss = model(x, y)
        loss.backward()
        for k, p in params.items():
            if p.grad is not None:
                fisher[k] += p.grad.detach().float().cpu() ** 2
        n += 1
    model.zero_grad(set_to_none=True)
    model.train(was)
    return {k: v / max(n, 1) for k, v in fisher.items()}


def train_adapter(model, tokenizer, train_rows: Rows, val_rows: Rows | None, replay: Rows | None,
                  cfg: SleepConfig, device: str, *, guard: GuardWindows | None = None,
                  behavior: BehaviorGuard | None = None, init_state: dict | None = None,
                  anchor: dict | None = None, extra_evals: dict | None = None,
                  old_rows: Rows | None = None, log=None) -> tuple[dict | None, dict]:
    """Train a LoRA adapter on the model (which must carry none); return (best adapter state or None, record).

    `train_rows` plan the steps (epochs over them); `old_rows`, in continue
    mode, are the person's examples the previous adapter already learned, drawn
    for `old_share` of the person's rows; `replay` rows come from the base's own
    conversations. A check whose person-validation loss is the best so far is
    kept only if `behavior` (when given) still passes; the first one that does
    not ends training, and the last accepted state is the result. The adapter
    is left attached to the model holding the returned state; the record says
    what happened, including both guards' verdicts. A state of None means no
    state was acceptable (the adapter is then removed from the model)."""
    import torch
    import train as core_train
    from model import (add_lora, base_fingerprint, has_lora, load_lora_state, lora_parameters, lora_state,
                       remove_lora, set_lora_enabled)
    if has_lora(model):
        raise ValueError("train_adapter starts from a model with no adapter")
    if not len(train_rows):
        raise ValueError("no training rows for the person")
    started = time.monotonic()
    torch.manual_seed(cfg.seed)
    fp_before = base_fingerprint(model)
    autocast = (torch.autocast(device_type="cuda", dtype=torch.bfloat16)
                if core_train.wants_bf16(device) else None)
    base_evals = {"person_val": mean_loss(model, val_rows, device, autocast=autocast),
                  "person_train": mean_loss(model, train_rows, device, autocast=autocast)}
    for name, rows in (extra_evals or {}).items():
        base_evals[name] = mean_loss(model, rows, device, autocast=autocast)
    guard_base = guard.loss(model, device, autocast=autocast) if guard is not None else None
    behavior_base = behavior.check(model, tokenizer) if behavior is not None else None
    behavior_checks = []

    if init_state is not None:
        load_lora_state(model, init_state)
    else:
        add_lora(model, r=cfg.r, alpha=cfg.alpha, dropout=cfg.dropout)
    params = lora_parameters(model)
    optimizer = torch.optim.AdamW(params, lr=cfg.lr, betas=core_train.BETAS, weight_decay=cfg.weight_decay)
    anchor_t = None
    if anchor is not None and cfg.ewc_lambda:
        from model import lora_modules
        anchor_t = []
        for name, m in lora_modules(model):
            for which in ("lora_A", "lora_B"):
                key = f"{name}.{which}"
                anchor_t.append((getattr(m, which), anchor["theta"][key].to(device),
                                 anchor["fisher"][key].to(device)))

    replay_n = int(round(cfg.replay_frac * cfg.batch_size)) if replay is not None and len(replay) else 0
    if replay is not None and len(replay) and cfg.replay_frac > 0 and replay_n < 1:
        raise ValueError(f"replay_frac {cfg.replay_frac} of a batch of {cfg.batch_size} is no row; raise either")
    person_n = cfg.batch_size - replay_n
    if person_n < 1:
        raise ValueError("every batch needs at least one of the person's rows")
    old_n = int(round(cfg.old_share * person_n)) if old_rows is not None and len(old_rows) else 0
    old_n = min(old_n, person_n - 1)
    person_n -= old_n
    per_epoch = math.ceil(len(train_rows) / person_n)
    planned = int(min(cfg.max_steps, max(cfg.min_steps, math.ceil(cfg.epochs * per_epoch))))
    stopper = core_train.EarlyStopper(min_delta=cfg.min_delta, patience=cfg.patience)
    rng = random.Random(cfg.seed)
    order: list[int] = []
    best_state, curve, accepted_step, split_steps = None, [], None, 0
    model.train()
    step, reason = 0, "finished"
    while step < planned:
        take = []
        while len(take) < person_n:
            if not order:
                order = list(range(len(train_rows)))
                rng.shuffle(order)
            take.append(order.pop())
        x, y = train_rows.batch(take, device)
        extra = []
        if old_n:
            extra.append(old_rows.batch([rng.randrange(len(old_rows)) for _ in range(old_n)], device))
        if replay_n:
            extra.append(replay.batch([rng.randrange(len(replay)) for _ in range(replay_n)], device))
        if extra:
            width = max([x.size(1)] + [ex.size(1) for ex, _ey in extra])
            pad = lambda t, v: torch.nn.functional.pad(t, (0, width - t.size(1)), value=v)  # noqa: E731
            x = torch.cat([pad(x, train_rows.pad_id)] + [pad(ex, train_rows.pad_id) for ex, _ey in extra])
            y = torch.cat([pad(y, -1)] + [pad(ey, -1) for _ex, ey in extra])
        lr = core_train.cosine_lr(step, cfg.warmup, planned, cfg.lr, cfg.lr / 10)
        for group in optimizer.param_groups:
            group["lr"] = lr
        # a batch over the token budget is split into micro-batches of whole rows, each weighted by its share of
        # the batch's supervised tokens, so the summed gradient is the whole batch's (Hugging Face, "Fixing
        # Gradient Accumulation", huggingface.co/blog/gradient_accumulation); within the budget it is one pass
        optimizer.zero_grad(set_to_none=True)
        n_total = max(int((y != -1).sum()), 1)
        rows_per = x.size(0) if x.size(0) * x.size(1) <= cfg.max_step_tokens else \
            max(1, cfg.max_step_tokens // x.size(1))
        split_steps += rows_per < x.size(0)
        loss_value, broke = 0.0, False
        for start in range(0, x.size(0), rows_per):
            xs, ys = x[start:start + rows_per], y[start:start + rows_per]
            n = int((ys != -1).sum())
            if not n:
                continue
            if autocast is not None:
                with autocast:
                    _, part = model(xs, ys)
            else:
                _, part = model(xs, ys)
            part = part * (n / n_total) if rows_per < x.size(0) else part
            if anchor_t is not None and start == 0:
                penalty = sum((f * (p - a) ** 2).sum() for p, a, f in anchor_t)
                part = part + cfg.ewc_lambda / 2 * penalty
            if not math.isfinite(float(part.detach())):
                broke = True
                break
            part.backward()
            loss_value += float(part.detach())
        if broke:
            reason = "non_finite_train"
            break
        if cfg.grad_clip:
            torch.nn.utils.clip_grad_norm_(params, cfg.grad_clip)
        optimizer.step()
        step += 1
        if step % cfg.eval_every == 0 or step == planned:
            val = mean_loss(model, val_rows, device, autocast=autocast) if val_rows is not None and len(val_rows) \
                else None
            point = {"step": step, "batch_loss": round(loss_value, 5), "lr": lr,
                     "person_val": None if val is None else round(val, 5)}
            stop, candidate = False, True
            if val is not None:
                stop = stopper.update(step, val)
                candidate = stopper.best_step == step
            if candidate:
                verdict = behavior.check(model, tokenizer) if behavior is not None else None
                if verdict is not None:
                    point["behavior_passed"] = verdict["passed"]
                    behavior_checks.append({"step": step, "passed": verdict["passed"]})
                if verdict is None or verdict["passed"] >= behavior_base["passed"] - cfg.behavior_tolerance:
                    best_state, accepted_step = lora_state(model), step
                else:
                    stop, reason = True, "behavior_guard"
            curve.append(point)
            if log:
                log(point)
            if stop:
                if reason == "finished":
                    reason = stopper.reason
                break
    refused = best_state is None               # no check was acceptable (or none was finite)
    if not refused:
        load_lora_state(model, best_state)
    model.eval()
    # measured on the accepted state, or (when every state was refused) on the last one, which is then removed
    after = {"person_val": mean_loss(model, val_rows, device, autocast=autocast),
             "person_train": mean_loss(model, train_rows, device, autocast=autocast)}
    for name, rows in (extra_evals or {}).items():
        after[name] = mean_loss(model, rows, device, autocast=autocast)
    record = {"config": asdict(cfg), "planned_steps": planned, "steps": step, "stop": reason,
              "split_steps": split_steps,
              "best_step": accepted_step, "best_val_step": stopper.best_step, "curve": curve, "rows": {
                  "person_train": len(train_rows), "person_val": len(val_rows) if val_rows is not None else 0,
                  "replay_pool": len(replay) if replay is not None else 0, "person_rows_per_batch": person_n,
                  "old_rows_per_batch": old_n, "old_pool": len(old_rows) if old_rows is not None else 0,
                  "replay_rows_per_batch": replay_n, "too_long_dropped": train_rows.too_long + (
                      val_rows.too_long if val_rows is not None else 0)},
              "loss_base": base_evals, "loss_adapter": after, "device": device,
              "behavior": None if behavior is None else {
                  "base_passed": behavior_base["passed"], "asked": behavior_base["asked"],
                  "tolerance": cfg.behavior_tolerance, "checks": behavior_checks, "ok": not refused}}
    if refused:
        remove_lora(model)
        record["guard"] = {"ok": None, "why": "not run: the behaviour guard refused every state"}
    elif guard is not None:
        set_lora_enabled(model, True)
        guard_after = guard.loss(model, device, autocast=autocast)
        rise = guard_after - guard_base
        ok = cfg.guard_tolerance is None or rise <= cfg.guard_tolerance
        record["guard"] = {"base": guard_base, "adapter": guard_after, "rise": rise,
                           "tolerance": cfg.guard_tolerance, "ok": ok, "windows": guard.windows,
                           "block": guard.block}
        if not ok:
            remove_lora(model)
            best_state = None
    else:
        record["guard"] = {"ok": None, "why": "not run: no held-out text given"}
    if best_state is not None and cfg.fisher:
        record["fisher"] = "computed on the person's training rows"
        best_state = dict(best_state, fisher=diagonal_fisher(model, train_rows, device, autocast=autocast))
    fp_after = base_fingerprint(model)
    if fp_after != fp_before:
        raise RuntimeError("the base weights changed during a sleep; this is a bug, nothing was saved")
    record["base_fingerprint"] = fp_before
    record["seconds"] = round(time.monotonic() - started, 2)
    return best_state, record


# ------------------------------------------------------------ one person --

def replay_and_probe(path: Path, n_probe: int, seed: int) -> tuple[list[dict], list[str]]:
    """The base's training-side conversations (chat_data.py JSONL), less `n_probe` chosen by a seeded hash,
    whose prompts become the behaviour guard's: a guard prompt is never also a replay row."""
    convs = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    train = [c for c in convs if c.get("split", "train") == "train" and len(c["messages"]) == 2]
    ranked = sorted(train, key=lambda c: hash_unit(json.dumps(c["messages"][0], sort_keys=True), seed))
    probe = ranked[:n_probe]
    ids = {id(c) for c in probe}
    return [c for c in convs if c.get("split", "train") == "train" and id(c) not in ids], \
        [c["messages"][0]["content"] for c in probe]


def sleep_person(store, model_dir: Path, *, cfg: SleepConfig | None = None, replay: Path | None = None,
                 guard_text: Path | None = None, split: Path | None = None, device: str | None = None,
                 guard_chars: int = 400_000, behavior_prompts: int = 24, log=print) -> dict:
    """One sleep for one person from files: load the base, gather and gate the examples, train, guard, save.

    With `replay` (the base's chat_data.py conversations) the behaviour guard
    asks `behavior_prompts` of its training-side prompts, which are then kept
    out of the replay rows; without it, the person's own validation examples.
    Twenty-four, not eight: arm A's 8-prompt guard missed an adapter that halved
    the correct held-out answers (DAWNR-LEARNING.md, section 7). The person's
    style profile is refreshed at the end of every sleep."""
    import torch  # noqa: F401
    from checkpoint import load_checkpoint
    from train import pick_device
    from . import adapters
    from model import remove_lora
    cfg = cfg or SleepConfig()
    split = Path(split) if split is not None else ROOT / "t" / "out" / "loop" / "split-v5.json"
    device = device or pick_device()
    identity = adapters.base_identity(model_dir)
    examples, excluded = store.training_examples(check=True, split_path=split)      # gated: feedback.held_out_gate
    examples = cap_examples(examples, cfg.max_examples, cfg.seed)
    record = {"person": store.person, "base": identity, "mode": cfg.mode, "examples_available": len(examples),
              "excluded": excluded, "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if not examples:
        record["result"] = "nothing to learn: no usable examples"
        return record
    directory = adapters.adapter_dir(store, identity)
    st = adapters.status(store, identity)
    init_state = anchor = None
    trained_before = {}
    if cfg.mode == "continue":
        if not st["exists"] or not st["fresh"]:
            raise ValueError(f"continue needs a fresh adapter for this base ({st['why'] or 'none'}); use rebuild")
        saved = adapters.load_adapter_file(directory)
        init_state = {"config": saved["config"], "tensors": saved["tensors"]}
        trained_before = {e["id"]: e["hash"] for e in adapters.load_manifest(directory)["examples"]}
        if cfg.ewc_lambda:
            if "fisher" not in saved:
                raise ValueError("EWC needs the previous adapter's Fisher (sleep with fisher=True)")
            anchor = {"theta": saved["tensors"], "fisher": saved["fisher"]}
    model, tokenizer, _ = load_checkpoint(model_dir, device)
    block = model.config.block_size
    train_ex, val_ex = split_examples(examples, cfg.val_frac, cfg.seed)
    old_rows = None
    plan_ex = train_ex
    if cfg.mode == "continue":
        plan_ex = [e for e in train_ex if e["id"] not in trained_before]
        if not plan_ex:
            record["result"] = "nothing new since the last sleep"
            return record
        seen = [e for e in train_ex if e["id"] in trained_before]
        old_rows = Rows(tokenizer, seen, block) if seen else None
    rows_train = Rows(tokenizer, plan_ex, block)
    rows_val = Rows(tokenizer, val_ex, block) if val_ex else None
    replay_rows = behavior = None
    if replay is not None:
        pool, probe = replay_and_probe(replay, behavior_prompts, cfg.seed)
        replay_rows = Rows(tokenizer, pool, block) if cfg.replay_frac > 0 else None
        behavior = BehaviorGuard(probe) if probe else None
        record["behavior_prompts_from"] = "the base's training-side conversations"
    elif val_ex:
        # no base conversations on this machine: the guard asks the person's own held-out prompts (their
        # validation examples, never trained on in this sleep), so dawnr must not get worse at their own tasks
        prompts = [next(m["content"] for m in reversed(e["messages"][:-1]) if m.get("role") == "user")
                   for e in val_ex]
        behavior = BehaviorGuard([p for p in prompts if isinstance(p, str)][:behavior_prompts])
        record["behavior_prompts_from"] = "the person's own validation examples"
    guard = None
    if guard_text is not None:
        with Path(guard_text).open(encoding="utf-8") as f:
            guard = GuardWindows(tokenizer, f.read(guard_chars), min(512, block))
    state, rec = train_adapter(model, tokenizer, rows_train, rows_val, replay_rows, cfg, device, guard=guard,
                               behavior=behavior, init_state=init_state, anchor=anchor, old_rows=old_rows, log=log)
    record.update(rec)
    if state is None:
        record["result"] = "refused by a guard: the previous adapter (if any) stays"
    else:
        fisher = state.pop("fisher", None)
        manifest = {"person": store.person, "base": identity, "mode": cfg.mode,
                    "examples": [{"id": e["id"], "hash": e["hash"]} for e in train_ex + val_ex],
                    "trained_on": [e["id"] for e in train_ex], "validated_on": [e["id"] for e in val_ex],
                    "sleep": {k: rec[k] for k in ("steps", "best_step", "stop", "loss_base", "loss_adapter", "guard",
                                                  "behavior")}}
        record["manifest"] = adapters.save_adapter(state, directory, manifest, cfg.max_adapter_bytes, fisher=fisher)
        record["result"] = "saved"
    remove_lora(model)
    try:                                              # the no-weights learner, refreshed at every sleep
        from . import style_profile
        record["profile"] = style_profile.refresh(store)
    except Exception as e:                            # noqa: BLE001  (recorded, never silent)
        record["profile"] = {"error": f"{type(e).__name__}: {e}"}
    sleeps = store.dir / "sleeps"
    sleeps.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    (sleeps / f"sleep-{stamp}.json").write_text(json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8")
    return record

