# Hooks

`.git/hooks/` is not tracked by git, so a hook that lives only there is absent
from every fresh clone and from the lab workstation. These are the tracked copies.

Install them once per checkout:

    git config core.hooksPath .githooks

That makes git read hooks from here instead of `.git/hooks`. Note the tradeoff:
`core.hooksPath` replaces the whole directory, so the Git LFS `pre-push`,
`post-checkout`, `post-commit` and `post-merge` hooks this repository relies on
must be copied here too before switching, or LFS stops working. Until that is
done, install by copy instead:

    cp .githooks/commit-msg .git/hooks/commit-msg && chmod +x .git/hooks/commit-msg

## commit-msg

Refuses a commit that changes Python and cites neither a source nor `INVENTED:`.
AGENTS.md rule 5 is the rule; this is the enforcement. A source is a URL with or
without its scheme, such as `stackoverflow.com/q/39417091`, or an arXiv id. A rename, a typo fix or a
revert is not an implementation: `git commit --no-verify`.
