"""Locate fenced-t parse refusals by training role without executing programs.

Sources: heldout_audit.blocks and student_sft.encode_row;
https://github.com/trestoncuzzort/dawnr/blob/main/t/heldout_audit.py
"""
from collections import Counter, defaultdict
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import heldout_audit
import surface


def census(path):
    data = path.read_bytes()
    rows = [json.loads(line) for line in data.decode().splitlines() if line.strip()]
    holders, texts = defaultdict(set), {}
    for i, row in enumerate(rows):
        for key, value in row.items():
            role = 'target' if key == 'chosen' else 'prompt' if key == 'prompt' else 'other'
            for block in heldout_audit.blocks({key: value}):
                sha = hashlib.sha256(block.encode()).hexdigest()
                texts[sha] = block
                holders[sha].add((i, role, row.get('source', 'unknown')))
    failures = set()
    for sha, block in texts.items():
        try:
            surface.parse(block)
        except surface.SurfaceError:
            failures.add(sha)
    roles, targets = Counter(), defaultdict(set)
    for sha in failures:
        roles['+'.join(sorted({role for _, role, _ in holders[sha]}))] += 1
        for i, role, source in holders[sha]:
            if role == 'target':
                targets[source].add(i)
    return {'dataset_sha256': hashlib.sha256(data).hexdigest(), 'rows': len(rows),
            'source_counts': dict(sorted(Counter(r.get('source', 'unknown') for r in rows).items())),
            'distinct_blocks': len(texts), 'unparsed_distinct_blocks': len(failures),
            'unparsed_by_roles': dict(sorted(roles.items())),
            'target_rows_with_unparsed_blocks_by_source': {k: len(v) for k, v in sorted(targets.items())},
            'model_reference_or_prover_calls': 0,
            'scope': 'Fenced t syntax only. Does not establish static validity, intent, or absence of contamination.',
            'sources': {str(p.relative_to(HERE.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in (Path(__file__), HERE / 'heldout_audit.py', HERE / 'surface.py', HERE / 'student_sft.py')}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rows', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = census(args.rows)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('rows', 'unparsed_distinct_blocks', 'unparsed_by_roles')}))


if __name__ == '__main__':
    main()
