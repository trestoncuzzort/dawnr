---
name: cite-your-source
description: Before writing or changing an implementation, look for a source that already solves the problem and name it in the commit message. Use before writing new Python, or when the commit-msg hook refuses a commit touching .py files.
license: the repository's LICENSE
---

# Citing what an implementation is based on

The rule (AGENTS.md, rule 5): every implementation is checked against prior
art *before* code is written, not after, and not only when the problem looks
hard. A commit that changes Python must say, in its own message, one of two
things:

1. **A source.** A URL (with or without its scheme), a bare host and path
   (`stackoverflow.com/q/39417091`), or a paper id (`arXiv:2604.21570`). Say
   what it is a source *for*, in prose: which decision or which piece of the
   change it comes from, not a link with no context.
2. **`INVENTED:`**, followed by what was searched for and why nothing usable
   existed. "Invented" is an honest, allowed answer; a search that was never
   run is not.

Search first. Look for a repository, a paper, or documentation that already
made this decision, even for something that looks small or obvious: this
project once skipped the search twice in one session and, searching
afterwards, found a paper that had already taken the opposite choice on one
of the same design questions (t/FINDINGS-examples-evidence-2026-09-20.md). A
citation is not decoration; it is how a reader later tells a reasoned
decision from a guess.

**Mechanically.** `.githooks/commit-msg` refuses a commit that touches a
`.py` file and whose message matches neither pattern above (a link-shaped
string, or the literal text `INVENTED:`). It reads the message from the file
git hands a `commit-msg` hook, not from the diff, which is why it can see the
message at all; a `pre-commit` hook is asked before the message exists and
cannot. It is not installed by default: `cp .githooks/commit-msg
.git/hooks/` once per clone. A rename, a typo fix, or a revert is not an
implementation decision; `git commit --no-verify` past the hook for exactly
those cases, never to skip citing an implementation.

Never write `INVENTED:` because searching felt slower than coding. Write it
only after the search happened and came back empty, and say what was
searched for so the next reader can judge that for themselves.
