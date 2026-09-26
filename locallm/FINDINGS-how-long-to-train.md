# How long should you train? — measured, not guessed

The studio offers three practice lengths and tells you longer is better. That's a claim, and until now nobody had checked it on this corpus. These two experiments check it, end to end, from 500 steps to 160,000.

**Short version: longer is better — until 80,000 steps. After that you're paying full price for nothing.**

Everything below was run on one 4090, on `corpus.txt` (19,986,068 characters, 83-character vocabulary), on the Medium preset, on the exact split `group_split` produces with the defaults. 32 training runs, 96 minutes of GPU.

---

## 1. What the model is actually doing

It reads text one character at a time and guesses the next one.

```
"the cat sat on the m—"     → probably 'a'
"once upon a t—"            → almost certainly 'i'
"she opened the d—"         → 'o' (door), maybe 'r' (drawer)
```

That's the whole job. Same thing your phone does above the keyboard, one letter at a time instead of one word at a time.

## 2. Scoring it in something you can picture

Loss comes out as a number like `0.7059`, which tells you nothing at a glance. Exponentiate it and you get something you can hold:

> **How many characters is it effectively torn between?**

Like a multiple-choice question you've narrowed down. "Torn between 2" means it's down to a coin flip. "Torn between 20" means it's guessing.

`e^0.7059 = 2.03 choices`. That's the unit used everywhere below.

## 3. The ladder — four ways to play, worst to best

All four measured on **this** corpus, on the **same** held-out text, by `baselines.py`:

| how you guess | bits/char | torn between |
|---|---|---|
| **Uniform.** 83 characters, pick blind. | 6.375 | **83.00** |
| **Letter frequency.** Know 'e' is common and 'q' isn't. No context. | 4.446 | **21.80** |
| **Bigram.** Look at the previous 1 character. | 3.317 | **9.97** |
| **Trigram.** Look at the previous 2 characters, guess whatever followed most often. | 2.436 | **5.41** |
| **This model, best measured** (160,000 steps). | 0.995 | **1.99** |

**The trigram row is the important one.** It's a lookup table. No parameters, no gradient, no GPU — count every 3-character combination in 20MB of text and keep a tally. That alone gets you from 83 down to 5.41.

Which means: *most of the distance from "random" to "good" requires no learning at all.* If you compare the model against uniform, it looks like it closed 99% of the gap — and a trigram table closes 94% of that same gap while understanding nothing.

So the honest measurement is **`closed_fraction`**: of the distance the lookup table *couldn't* cover, how much did the model cover?

**Answer: 78%.** That's the part that actually required learning.

## 4. Homework vs. the exam

Before any training, the text is cut in two:

- **90% — the textbook.** The model studies this.
- **10% — the sealed exam.** The model *never* sees it during training. Not once.

`train` = score on the textbook. `val` = score on the exam.

**Only `val` counts.** Anyone can ace a test they have the answer key to.

## 5. The gap — the cheating detector

**gap = val − train.** The distance between exam and homework.

Two students, same textbook:

> **Kid A learns math.** Homework improves, test improves, roughly together. New problems are just more math.
>
> **Kid B memorizes the answer key.** Homework goes *perfect*. Test stalls, then slides. He didn't learn math — he learned that worksheet.

The gap separates them **without ever catching anyone in the act.** Kid B's gap grows. And critically:

**the gap starts widening BEFORE the exam score drops.**

It's the smoke, not the fire. Watch only `val` and you find out one or two doublings too late. That's why the tail experiment tracks the gap as a first-class number.

## 6. Why every arm runs 3–5 times

Same settings, different random starting points — like identical students who happen to open the book on different pages. They don't land on identical scores.

**That spread is the noise floor.** It's how much the answer moves for reasons that have nothing to do with what's being tested. A change smaller than the spread isn't a finding, it's noise in a lab coat.

Measured here for the first time in this project: **0.0022 – 0.0116**, depending on the arm.

Every claim below is checked against it. That rule was written down *before* any run — see the `prereg_*.json` files.

---

## 7. Experiment 1 — the presets (500 → 10,000 steps, 5 seeds each)

`prereg_steps_vs_quality.json` · `exp_steps_vs_quality_result.json`

| steps | val | noise floor | torn between | vs the lookup table |
|---|---|---|---|---|
| 500 | 1.3323 | 0.0116 | 3.79 | 37% |
| 1,500 | 1.0281 | 0.0112 | 2.80 | 59% |
| 5,000 | 0.8329 | 0.0072 | 2.30 | 71% |
| 10,000 | 0.7738 | 0.0055 | 2.17 | 74% |

| step-up | improvement | noise | real? |
|---|---|---|---|
| 500 → 1,500 | 0.3042 | 0.0116 | **yes — 26× the noise** |
| 1,500 → 5,000 | 0.1952 | 0.0112 | **yes — 17× the noise** |
| 5,000 → 10,000 | 0.0591 | 0.0072 | **yes — 8× the noise** |

**Verdict: longer training measurably helps.** The preset wording is supported.

But look at the price. 500→1,500 is 3× the work for 0.3042. 5,000→10,000 is 2× the work for 0.0591. Per unit of work, that's about **five times less value**.

## 8. Experiment 2 — go find the tail (20,000 → 160,000 steps, 3 seeds each)

`prereg_steps_tail.json` · `exp_steps_tail_result.json`

At 4,096 characters read per step, one full pass through this corpus is **4,879 steps**. So these arms read the whole book 4×, 8×, 16×, and **33×**.

At 33 read-throughs the interesting question isn't "does it stop helping" — it's **"does it start hurting?"**

| steps | crossings | train | val | **gap** | noise | vs table |
|---|---|---|---|---|---|---|
| 20,000 | 4.1× | 0.7167 | 0.7309 | **+0.0142** | 0.0048 | 76% |
| 40,000 | 8.2× | 0.6866 | 0.7059 | **+0.0194** | 0.0022 | 77% |
| 80,000 | 16.4× | 0.6713 | 0.6921 | **+0.0208** | 0.0052 | 77% |
| 160,000 | 32.8× | 0.6657 | 0.6893 | **+0.0236** | 0.0045 | 78% |

| doubling | improvement | noise | worth it? |
|---|---|---|---|
| 20k → 40k | 0.0250 | 0.0048 | yes — 5× the noise |
| 40k → 80k | 0.0138 | 0.0052 | yes — 2.7× the noise |
| **80k → 160k** | **0.0028** | **0.0052** | **NO — smaller than the noise** |

### That last row is the tail

Doubling from 80,000 to 160,000 steps costs **an extra ~7 minutes of GPU per run** and buys an improvement *smaller than the difference between two identical runs that merely started on different random numbers.*

**80,000 steps is the ceiling for this model on this corpus.**

### And it didn't fade — it fell off a cliff

The improvements per doubling: `0.0429 → 0.0250 → 0.0138 → 0.0028`

The first three are a clean halving — each doubling gives ~55% of the last. If that pattern had continued, the final doubling should have returned about **0.0076**. It returned **0.0028** — a third of trend.

> Like a car that does 0–30 in 3 seconds, 30–60 in 6, 60–90 in 12 — and then 90–120 never happens. It isn't slowing down anymore. **It's at top speed.**

## 9. Why it stopped — and this is the useful part

Two very different reasons a model stops improving. They need **opposite** fixes, and the gap column tells you which one you have.

**It's cramming.** Homework score keeps rocketing while the test stalls. `train` keeps falling fast, `val` goes flat.

**It's full.** It learned everything it's capable of learning. `train` **and** `val` flatten together.

From 80k → 160k:

| | dropped by |
|---|---|
| train | 0.0056 |
| val | 0.0028 |

**Both nearly flat.** The *textbook* score stopped improving too.

**This model isn't cramming. It's full.** 3.18M parameters holding a 19,986,068-character corpus — about **6 characters of text per parameter.** It ran out of room.

The prediction going in was that a model this small might be *too small to overfit*, and that a flat tail was the likely honest outcome rather than a dramatic turn-up. That's what happened.

### But the cramming is starting

`+0.0142 → +0.0194 → +0.0208 → +0.0236` — the gap widened **66%** across the run, and cleared the noise bar on two of three doublings.

The verdict the script printed, from rules written before any data existed:

> *"no turn-up yet, but the train/val gap is widening beyond noise — memorising is detectable before it is costly"*

**The smoke, caught before the fire.** Which is exactly what tracking the gap is for.

---

## 10. What this means for the app

1. **"Train longer for better results" is true — up to 80,000 steps.** Past that the app would be selling a wait that buys nothing. It currently has no idea and would happily run all night.

2. **More time is now the wrong lever.** The fix for a full model isn't patience — it's a **bigger model** or **more text**. Rereading the same textbook a fifth time doesn't help; you need a harder book.

3. **`closed_fraction` plateaued early** — 76 → 77 → 77 → 78%. This model closes about 78% of what the lookup table couldn't, and that's about as good as it gets at this size.

4. **The noise floor is now a known number.** Every future "setting A beats setting B" claim in this repo can be checked against it. Before this week, none could be.

## 11. Why any of this is cool

**The rules were written before the data existed.** Both `prereg_*.json` files declare — in advance — the question, what counts as a real result, and what gets reported for *every* possible outcome, including the boring ones.

That means nobody can look at the numbers, decide what would sound impressive, and go find it. Which is, roughly, how most numbers on the internet get made.

The tail experiment's prereg commits to publishing a flat result as loudly as a dramatic one:

> *"A flat tail is as useful a product fact as a rising one."*

It came out flat-ish. It got published. That's the point.

**Also worth noticing:** the trigram baseline is *deliberately weak* — add-1 smoothing, only 2 characters of context. A stronger baseline would make the model look worse. That's on purpose. Understating the baseline is the failure mode to avoid, because it flatters the model. If someone builds a better n-gram and the advantage shrinks, **the new number is the honest one.**

## 12. What is NOT claimed

- That these numbers transfer to another corpus, architecture, or vocabulary. They don't; they're this corpus at this size.
- That validation loss says anything about whether the generated text *reads* well. It doesn't. It measures prediction, not quality.
- That 3 seeds can detect an effect smaller than the spread they measure.
- That no turn-up exists past 160,000 steps. It was looked for out to 33 crossings and not found. That is not the same as "not there."
- That the model is *not* memorizing. It is — measurably. It just hasn't cost anything yet.

## 13. Reproducing it

```bash
python exp_steps_vs_quality.py     # 20 runs, ~18 min on a 4090
python exp_steps_tail.py           # 12 runs, ~78 min on a 4090
```

Each reads its `prereg_*.json` for arms and seeds, writes `exp_*_result.json`, and the tail experiment writes a partial result after **every arm** — a crash 75 minutes in doesn't cost the first 75 minutes.

Both use the same corpus, the same split, the same architecture, and the same training loop `train.py` uses — including the bf16 autocast and the cosine schedule with warmup — so the arms are comparable to a real run and to each other.

Each arm is its **own run with its own schedule**, not one long run sampled at checkpoints. The schedule decays to `lr/10` at the declared endpoint, so a 160k run at step 20k sits at a different learning rate than a 20k run at its end. Sampling one long run would compare arms that never existed.

---

## Note, 2026-09-26: the app now has a stopping rule

Section 10's "it currently has no idea and would happily run all night" is no longer true of `train.py` or the studio. Both stop once validation has not dropped by more than 0.005 for 5 checks in a row, and both save the best-validation weights, not the last. The 0.005 comes from this finding: the 80,000-step arm's seed spread was 0.0052, and the 80k→160k doubling (+0.0028) was judged against it. With that threshold the stopper agrees with the verdict above that the doubling bought nothing. The rule is Lightning's `EarlyStopping`, and which weights are kept follows its `ModelCheckpoint`. The numbers above were measured before the rule existed, on separate fixed-length runs, and they are unchanged. Where the rule stops a Thorough run on this corpus has not been measured yet.
