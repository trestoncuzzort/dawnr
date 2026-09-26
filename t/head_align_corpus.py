"""Give every training document a head, so the model is never rewarded for
writing a program that ignores one.

Round 7's corpus was 58 documents with a `Problem:`/`Signature:` head and 222
bare programs, and its model wrote a signature of its own for 55 of 136
well-formed answers: it had learned to produce programs, not to condition on a
head. This rewrites a corpus so a bare program is preceded by the signature it
actually has. Nothing is invented: the line is derived from the program's own
parameter and return types, and a document that already has a head is left
exactly as it was.

A head is whatever loop_filter.HEAD_LINE says it is, so a new head line is
added in one place. That includes the `Spec:` line of a specification document
(loop_locallm.py corpus --spec-docs, 2026-09-25): it starts with the same
`Problem:` head as the program it stands beside, carries no body, and is kept
exactly as it was and counted as `spec_documents`, never parsed as a program.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import re

import loop_filter
import surface

# The same boundary loop_locallm.REPLY_BOUNDARY cuts at. A spec document
# begins with `Problem: `, so it is split off there; its `Spec:` line follows
# the head with no blank line and is never a boundary.
SPLIT = re.compile(r"\n\s*\n(?=Problem: |Signature: |t \d)")


def type_name(node):
    if isinstance(node, str):
        return node
    if isinstance(node, dict) and "pair" in node:
        return "(%s, %s)" % tuple(type_name(t) for t in node["pair"])
    if isinstance(node, dict) and "seq" in node:
        return "seq<%s>" % type_name(node["seq"])
    raise ValueError(f"unknown type {node!r}")


def head_for(task):
    kinds = ", ".join(type_name(p["type"]) for p in task["params"])
    return f"Signature: {task['name']}({kinds}) -> {type_name(task['returns'][0]['type'])}\n"


def align(text):
    documents, added, kept, spec, unparsed = [], 0, 0, 0, 0
    for chunk in SPLIT.split(text):
        chunk = chunk.strip()
        if not chunk:
            continue
        if loop_filter.HEAD_LINE.match(chunk + "\n"):
            documents.append(chunk + "\n")
            kept += 1
            spec += loop_filter.is_spec_document(chunk)
            continue
        try:
            task = surface.parse(chunk + "\n")
        except Exception:
            documents.append(chunk + "\n")
            unparsed += 1
            continue
        documents.append(head_for(task) + chunk + "\n")
        added += 1
    return documents, {"heads_added": added, "already_headed": kept, "spec_documents": spec,
                       "unparsed": unparsed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    documents, counts = align(args.corpus.read_text(encoding="utf-8"))
    args.out.write_text("\n\n".join(documents) + "\n", encoding="utf-8")
    counts.update(documents=len(documents), bytes=args.out.stat().st_size,
                  sha256=sha256(args.out.read_bytes()).hexdigest())
    print(__import__("json").dumps(counts))


if __name__ == "__main__":
    main()
