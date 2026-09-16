#!/usr/bin/env python3
"""First end-to-end run of the t filter feeding locallm (2026-09-16).

Candidates: every t block the 27B wrote in the named spec-experiment dirs.
Filtered arm: tests pass AND at least --min-kernels columns read verified / refuted.
Control arm: a random sample of ALL candidates with the same character count.
Each arm trains locallm from scratch (same config, same seed); each model then
writes --samples continuations of "t 0\\n", and a sample counts when some prefix
ending at a line "}" parses as a t task. Prints both parse rates.
"""
import argparse, json, random, re, subprocess, sys
from pathlib import Path
T = Path.home() / "tup/t"; LL = Path.home() / "tup/locallm"
sys.path.insert(0, str(T))
import spec_experiment as se, surface

K = ['dafny', 'verus', 'spark', 'framac', 'lean', 'rocq', 'fstar']

def candidates(d: Path):
    tests = {v['name']: v['overall'] for v in json.loads((d / 'tests.json').read_text()).values()}
    rows = {}
    for l in (d / 'kernels.md').read_text().splitlines():
        if l.startswith('| mbpp_'):
            c = [x.strip() for x in l.strip().strip('|').split('|')]
            rows[c[0]] = sum(x == 'verified / refuted' for x in c[1:8])
    for f in sorted((d / 'raw').glob('*.json')):
        r = json.loads(f.read_text())
        b = se.find_block(r['reply'])
        if not b:
            continue
        name = f"mbpp_{r['task_id']}__{r['fn']}"
        yield name, b.strip() + "\n", tests.get(name), rows.get(name, 0)

def parses(sample: str) -> bool:
    lines = sample.split("\n")
    for i, l in enumerate(lines):
        if l.strip() == "}":
            try:
                surface.parse("\n".join(lines[:i + 1]) + "\n")
                return True
            except Exception:
                pass
    return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--min-kernels', type=int, default=1)
    ap.add_argument('--steps', type=int, default=1500)
    ap.add_argument('--samples', type=int, default=200)
    ap.add_argument('--work', default=str(Path(__file__).parent / 'work'))
    a = ap.parse_args()
    W = Path(a.work); W.mkdir(parents=True, exist_ok=True)
    cands = [c for d in a.dirs for c in candidates(Path(d))]
    filt = [c for c in cands if c[2] == 'pass' and c[3] >= a.min_kernels]
    fchars = sum(len(c[1]) for c in filt)
    rng = random.Random(1); pool = cands[:]; rng.shuffle(pool)
    ctrl, n = [], 0
    for c in pool:
        if n >= fchars: break
        ctrl.append(c); n += len(c[1])
    print(f"candidates {len(cands)}; filtered {len(filt)} ({fchars} chars); control {len(ctrl)} ({n} chars), "
          f"of which pass the gate {sum(c in filt for c in ctrl)}")
    py = str(Path.home() / '.venv-train/bin/python')
    for arm, docs in (('filtered', filt), ('control', ctrl)):
        corpus = W / f'{arm}.txt'
        corpus.write_text("\n".join(d[1] for d in docs))
        out = W / arm
        subprocess.run([py, 'train.py', '--data', str(corpus), '--out', str(out), '--steps', str(a.steps),
                        '--seed', '1337'], cwd=LL, check=True, stdout=open(W / f'{arm}-train.log', 'w'),
                       stderr=subprocess.STDOUT)
        import torch
        sys.path.insert(0, str(LL))
        import checkpoint
        torch.manual_seed(7)
        model, tok, _ = checkpoint.load_checkpoint(str(out))
        ok = 0; samples = []
        for _ in range(a.samples):
            txt = checkpoint.sample(model, tok, 't 0\n', 600, temperature=0.8, top_k=40)
            samples.append(txt); ok += parses(txt[txt.find('t 0'):] if 't 0' in txt else txt)
        (W / f'{arm}-samples.json').write_text(json.dumps(samples))
        print(f"{arm}: {ok} of {a.samples} samples parse as a t task")

if __name__ == '__main__':
    main()
