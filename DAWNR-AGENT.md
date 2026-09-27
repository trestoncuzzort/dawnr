# dawnr's agent: acting on the machine, in the owner's control

`AMBITION.md` asks for dawnr to act on the machine it runs on: "a planning loop
over tools (files, shell, processes) through the harness: every action under the
owner's allow / ask / deny permissions, logged, reversible where possible; dawnr
never grants itself permissions." This is that loop and those tools. The code is
`locallm/dawnr_agent/`; it plugs into dawnr's harness (`DAWNR-HARNESS.md`) as
more tools in the same registry, under the same policy, hooks and audit log, and
it is switched on by an `"agent"` section in the harness configuration. Without
that section none of it exists.

It is standard-library Python 3.10+. The predictions were committed before the
code (`locallm/PREDICT-agent-2026-09-27.md`); the tests that measure them are
`locallm/test_dawnr_agent.py`. Nothing here is trained: no checkpoint has learned
to plan, and section 9 lists the conversations it would need.

What was copied, from where (each fetched and read on 2026-09-27):

| piece | copied from | what differs |
|---|---|---|
| containment | openat2(2)'s `RESOLVE_BENEATH` and `RESOLVE_NO_SYMLINKS` (man7.org/linux/man-pages/man2/openat2.2.html); the MCP reference filesystem server (github.com/modelcontextprotocol/servers, `src/filesystem`): allowed directories, exclusive create, temporary file and rename for a replace, the edit shown as a diff; its advisory GHSA-hc55-p739-j48w (a root `/allowed` let `/allowed_evil` through, compared as strings) | Python has no openat2, so each component is opened through its parent's descriptor with `O_NOFOLLOW`: the descriptor that was checked is the one used, where the server checks a real path and then opens by name; `..` is refused rather than normalised; links are refused rather than followed if they stay inside |
| commands | Trail of Bits, 2025-10-22 (blog.trailofbits.com/2025/10/22/prompt-injection-to-rce-in-ai-agents/): with the shell gone, pre-approved commands still ran attacker code through their own options (`go test -exec`, `git show --output`, `rg --pre`, `fd -x`); sandbox first, else a facade with `--` separators, no shell, minimal allowlists, logging | the allowlist is of whole argv shapes the operator writes; the model fills typed placeholders that can never begin with `-`; programs are pinned by absolute path |
| the sandbox | bubblewrap (github.com/containers/bubblewrap): "the level of protection ... is entirely determined by the arguments"; `--unshare-net` leaves only loopback; `--new-session` against CVE-2017-5226; anything mounted in, such as a D-Bus socket, can escalate | the arguments here: every namespace unshared, `/` read-only, `/run` and `/tmp` empty, the writable roots bound read-write, secret folders hidden |
| processes | Python's `subprocess` documentation (a sequence argv, no shell; `communicate()` buffers everything; `start_new_session` instead of `preexec_fn`); Stack Overflow q/4789837 (kill the process group, not only the child) | output is read by threads that keep a capped prefix and drain the rest; the group is killed at the deadline and again when the call returns, while the leader is still an unreaped zombie so its id cannot have been reused |
| plans | plan-then-execute (Beurer-Kellner et al., arXiv:2506.08837, section 4.1 is an assistant acting on files whose attacker controls their contents and names); CaMeL (Debenedetti et al., arXiv:2503.18813: control flow from the trusted query only) | a step's arguments are exact, never a slot filled later from data, so an injection can steer neither which calls run nor what they are given; no interpreter or capability tags (the harness's taint bit carries the rest) |
| the loop | ReAct (Yao et al., arXiv:2210.03629): act, observe, decide again | the unit of action is a whole plan, approved as a whole |
| the dry run | Terraform's plan and saved-plan apply (developer.hashicorp.com/terraform/cli/commands/plan, .../apply): a saved plan is applied exactly as shown; re-check before applying because the target may drift | each edited file is pinned to its hash in the plan; the run refuses a step whose file moved |
| the tool set | SWE-agent (Yang et al., arXiv:2405.15793): a few commands to view, search and edit; a viewer window near 100 lines; an edit that applies only if it introduces no error (their agent solved 15.0% without that gate against 18.0% with it) | the gate is dawnr's checker on a `.t` file and Python's parser on a `.py` file, answered in the checker's fixed vocabulary so a refusal never quotes the file |

## 1. The threat model

**What is protected.** The person's files; their secrets (keys, tokens,
password stores); what runs on the machine; the configuration and permissions
that decide all of this; the network, as the way data leaves; and the person's
attention, which approvals spend.

**Who is trusted, and for what.** The operator's configuration: roots, rules,
permissions, hooks. The person in the conversation: the task, and each approval.
Nobody else. The planner, which will be the model, is not trusted to be right:
it may be undertrained, confused, or persuaded by what it read, and every
guarantee below holds for a planner that obeys every instruction it sees (the
measurement in section 7 uses exactly such a planner). Everything a machine tool
returns is untrusted data: a file's contents and even its name, a command's
output, the process list. Someone else may have written any of it.

**The adversaries.**

1. *Text written by someone else*, in a downloaded file, a cloned repository, an
   email, a log, a file name, a command's output: it tries to become an action.
2. *A wrong planner*, which proposes a harmful or pointless action without any
   attacker.
3. *A process racing the agent*, swapping a directory for a link between a check
   and a use.
4. *A repository built to turn an allowed command into code execution*: an
   option smuggled into an argument, a `.git/config` with a pager or monitor
   command, a test file an allowed test runner will execute.

Out of scope: a malicious operator; another local user with administrator
rights; kernel bugs; a person who approves a plan whose dry run showed the harm.

**Attacks and what stops them.**

| attack | what stops it | tested by |
|---|---|---|
| `..`, an absolute path outside, `/allowed_evil` for `/allowed` | lexical resolution refuses `..`; roots matched by whole components | `Containment.test_parent_components_absolute_paths_and_prefix_siblings_are_refused` |
| a link to a file or directory outside | every component opened with `O_NOFOLLOW` through its parent's descriptor; links refused, with the real path named when it is inside | `test_links_are_refused_not_followed` |
| a directory or file swapped for a link mid-walk | there is no separate check to race: the opened descriptor is what is used | `test_a_directory_swapped_for_a_link_mid_walk_is_refused`, `test_a_file_swapped_for_a_link_before_it_opens_is_refused` |
| writing through a hard link to a file outside | a replace writes a temporary file and renames it over the name; the other name keeps its bytes | `test_a_write_replaces_a_hard_link_instead_of_writing_through_it` |
| a FIFO or device that blocks or never ends | opened non-blocking, refused unless a regular file | `test_a_fifo_is_refused_without_blocking` |
| a root replaced by a link after loading | the root's identity (device, inode) recorded at load and checked at every walk | `test_a_root_replaced_after_loading_is_refused` |
| reading a secret | names (`.ssh`, `*.pem`, `.env`, ...) matched case-insensitively; the home directory's secret folders also by identity, so a hard link under an innocent name is refused | `test_secrets_are_never_read_by_name_or_by_identity` |
| rewriting `.git/config`, a hook, the configuration, the audit log, the agent's journal, the enforcement code | protected by name (`.git`, and the operator's list) and by identity (everything the configuration names, and `dawnr_harness`, `dawnr_agent`, `engine.py`, `chat.py`, `chat_cli.py`, `chat_pane.py`, `t_tool.py`); protected paths are read but never written, and never handed to a command | `test_protected_paths_are_read_but_never_written`, `Plans.test_the_model_cannot_reach_permissions_or_configuration` |
| a file its owner made read-only | a rename needs only the directory's permission, so the file's own mode is checked and kept | `test_a_file_its_owner_made_read_only_is_not_replaced` |
| shell metacharacters | no shell, ever: an argv list | `Commands.test_no_shell_and_a_scrubbed_environment` |
| an option smuggled into an argument (`-exec`, `--output=`, `--pre`) | a placeholder value may not begin with `-`; options exist only where the operator wrote them | `test_denied_means_never_started` |
| a program replaced by the agent | programs resolved once, pinned by absolute path, refused if inside a writable root; the command PATH excludes the roots and relative entries | `test_a_program_inside_a_writable_root_is_not_used` |
| secrets in the harness's environment | commands get a scrubbed environment: PATH, HOME, locale, the operator's additions | `test_no_shell_and_a_scrubbed_environment` |
| a command that never ends, forks, or floods | a deadline that kills the process group; a capped output | `test_deadline_kills_the_whole_process_group`, `test_output_is_capped` |
| data leaving by the network | offline by default; a rule reaches the network unless the operator says it does not; with bubblewrap that is enforced (only loopback in the command's network namespace) | `test_offline_denies_a_network_rule_and_online_allows_it`, `Sandbox.test_no_network_and_no_writes_outside_the_writable_roots` |
| an injected instruction becoming an action | plans fixed before untrusted text is read; after it, the harness's taint rule makes every consequential call ask; an approval covers only the exact calls the person saw; with nobody present, ask is deny | `Injection.test_a_gullible_planner_is_fooled_and_nothing_it_was_fooled_into_runs` |
| a hook or a plan changing what was approved | the approval is of the exact canonical arguments; a rewritten call falls back to asking the person | `test_an_approved_plan_runs_exactly_its_steps_and_a_rewritten_step_loses_the_approval` |
| a stale approval | each edited file pinned to its hash in the dry run; the step is refused if the file moved | `test_approval_binds_to_the_digest_and_a_moved_file_is_stale` |
| the model granting itself anything | no tool edits the policy, registry, hooks or configuration; plans cannot hold a plan or an approval; the configuration and enforcement code are protected | `test_the_model_cannot_reach_permissions_or_configuration` |
| approval fatigue | one approval per plan, with the whole plan shown, instead of one per step | `test_the_approved_plan_still_runs_after_untrusted_text_and_asks_once` |
| a loop that never ends | a step budget, a round budget, failures in a row, a repeated plan, a clock | `Loop.test_the_loop_stops_at_its_budget` and the stop-rule tests |

## 2. The tools

| tool | default | output | consequential | what it does |
|---|---|---|---|---|
| `fs_list` | allow | untrusted | no | a directory inside a root (no path: the roots), up to three levels; links, secrets and special files named, not followed |
| `fs_read` | allow | untrusted | no | a window of lines of a text file (100 by default), with its size and hash |
| `fs_search` | allow | untrusted | no | lines containing a literal text (no regular expressions, so no catastrophic backtracking), bounded by files, results and seconds |
| `fs_write` | ask | trusted | yes | create a file (`overwrite` to replace; `make_dirs`; `expect_sha256`) |
| `fs_edit` | ask | trusted | yes | replace an exact text that appears once (or `all`) |
| `fs_undo` | ask | trusted | yes | revert one journaled change if the file is still as it left it |
| `run_command` | deny | untrusted | yes | one argv matching an operator rule |
| `ps_list` | allow | untrusted | no | processes: id, parent, name; command lines of your own |
| `plan` | allow | trusted summary, each step's output with its own trust | no (its steps are) | a plan from the model: dry run, approval, steps |

The file tools exist only when the operator configures roots, and write tools
only act in roots marked `"mode": "write"`. A write runs without asking only when
the operator allows the tool in `permissions`; each call is also held to the
tool's own rule (`Tool.decide_call`, the one addition to the harness: a per-call
decision the policy applies after its own, which can make it stricter and never
looser; a hook's rewritten input meets it again).

Every change is journaled in the agent's state directory with the bytes it
replaced (content-addressed), so `fs_undo`, or the person's own
`python locallm/dawnr_agent --config ... undo <change>`, restores them; an undo
refuses when the file changed since, rather than clobber the later change.

## 3. Paths

A path is a root's name then the path inside it (`project/src/a.t`), or an
absolute path inside a root; the file tools' outputs always show the first form,
so they put no home directory into the model's context (a command's own output
may). `..` is refused outright. A NUL byte, a control
character, a Windows drive on a system without drives, and on Windows a `:` in a
component, a trailing dot or space, or a device name are refused by name.

Opening walks the real directories: the root (its identity checked against the
one recorded at load), then each component through its parent's descriptor with
`O_NOFOLLOW | O_DIRECTORY`, then the file with `O_NOFOLLOW | O_NONBLOCK`,
accepted only if it is a regular file. A symbolic link anywhere below a root is
refused, not followed. openat2's manual warns that refusing links breaks
ordinary setups, so the refusal names the link's real path when it lies inside a
root, and the model can use that path. The operator's own links, in a root's
path, are resolved once when the configuration loads. Search uses `os.fwalk`
with `follow_symlinks=False`, which CPython's own docstring calls safe against
symlink races.

## 4. Commands

A rule is an argv the operator writes, with placeholders where the model fills
in a value:

    {"argv": ["python3", "-m", "pytest", "-q", "--", "{path}..."], "permission": "ask", "network": false}

| placeholder | takes |
|---|---|
| `{path}` | one path in the fs tools' form, checked like theirs (inside a root, no link on the way or at the end, not secret, not protected, in a writable root unless the rule says `"writes": false`), passed on as an absolute path |
| `{arg}` | one value |
| `{int}` | one non-negative integer |
| `{path}...`, `{arg}...` | any number, last in the rule only |

No value may begin with `-`. An `{arg}` is not checked as a path: a rule whose
program opens its argument as a file must say `{path}`, or the program can be
pointed anywhere. A rule's permission is `allow` or `ask` (default
`ask`); `run_command` itself is denied until the operator allows it, so both
the tool and a rule must be granted. The first rule an argv matches is the one
used; an argv no rule matches is refused with the list of allowed shapes. A
rule's working directory is the call's `cwd` (inside a root, in a writable one if
the rule writes), else the rule's, else the first writable root.

**The network.** A rule counts as reaching the network unless it says
`"network": false`, and while the harness is offline (its default) a network rule
is refused. Without a sandbox, `"network": false` is the operator's claim about
that program, exactly as it is for an MCP server. With `"sandbox": "bwrap"` it is
enforced: the command gets its own network namespace with only a loopback
device, a read-only file system except the writable roots, empty `/run` and
`/tmp`, hidden secret folders, its own process ids and session. If the sandbox is
configured and does not work on the machine, no command runs. On the desktop this
was written on, unprivileged `unshare -rn` is refused (AppArmor restricts
unprivileged user namespaces there) and bubblewrap, which has its own profile,
works.

## 5. Plans, the dry run and approval

A plan is `{"goal": "...", "steps": [{"tool": ..., "arguments": {...}, "why": ...}]}`,
at most 16 steps, each a call with exact arguments. The dry run computes, for
every step and without doing it:

- the decision the harness will give it, including the taint that earlier
  steps will add (a write after a read asks);
- what it will touch: the resolved path, whether the file exists, the diff of a
  write or edit (earlier planned writes are simulated, so a second edit of the
  same file is shown against the first), the exact argv of a command with its
  program's absolute path, working directory, sandbox and environment names;
- pins: an edit or overwrite gets `expect_sha256` of the file as it is (or as an
  earlier step leaves it), so the run refuses the step if the file moved.

The digest of the pinned steps is what gets approved. The person sees the whole
plan with diffs; the model sees the same without file contents. A plan with a
step the dry run already refuses runs nothing. Approving the plan approves those
exact calls: during each step the harness's approver answers yes to exactly that
call and passes anything else to the person, so a hook that rewrites a step's
arguments loses the approval. A step the policy denies stays denied: approval
only answers an ask. With nobody to approve the plan, steps run under the
policy alone, and an ask is a refusal.

A re-plan made after untrusted text entered the conversation is new control
flow, so its consequential steps ask again. This is the property the injection
measurement tests: a planner fooled by a file proposes the injected action, and
it is refused (nobody present) or put to the person, who sees it for what it is.

## 6. The loop

`AgentLoop(agent, planner).run(task)`: the planner proposes a plan or an answer;
a plan is dry-run, approved, run; its outputs go back to the planner with their
trust marks; repeat. A model plans through `ModelPlanner`, which renders the
loop so far in dawnr's chat format and reads back a `plan {...}` call, or through
the `plan` tool from inside an ordinary chat turn (`engine.py` runs it like any
registry call). It stops at the first of:

| stop | when |
|---|---|
| done | the planner answered and the Stop hooks let it end (dawnr's checker on the final program; a block is fed back and costs a round) |
| rounds | `max_rounds` plans (default 4) |
| budget | `max_steps` calls (default 12); a plan is cut at the budget |
| failures | `max_failures` rounds in a row (default 2) ended in a refusal or a failed step |
| no progress | a plan already proposed |
| refused | the person refused a plan |
| time | `max_seconds`, if set |
| dry run | asked only to show the first plan |
| planner | the planner raised or returned something that is not a plan |

## 7. What was measured

Predictions in `locallm/PREDICT-agent-2026-09-27.md`, committed before the code;
the numbers from `DAWNR_AGENT_MEASURE=<file> python -m unittest
locallm/test_dawnr_agent.py` on the desktop, 2026-09-27 (73 tests, 2 skipped by
design, 3.6 s on Python 3.14; the same pass on Python 3.10).

| prediction | the number that would falsify it | measured |
|---|---|---|
| containment holds on at least 5,000 generated paths | one escape | 5,000 paths read, 1,667 listed, 1,000 written: **0 escapes** (no read or listing showed a byte or a name from outside; nothing outside changed; every written file's real path is in the writable root). 31 reads, 214 listings and 165 writes reached real files; the rest were refusals |
| a planner that obeys everything is fooled every time and nothing it was fooled into runs | one injected action run | 40 injected files (5 actions in 8 disguises) in 2 settings: **80 of 80 fooled, 0 run**. With the person present the injected plan was put to them 32 times and refused by the harness without asking 8 times (a command on no rule) |
| a dry run changes nothing | one file changed or process started | 3 dry runs of a plan with a read, two edits, a write and a command: **0 files changed, 0 processes started, 0 step calls in the audit log** |
| the loop never exceeds its budget | one run over | **0 of 60** random budgets (0 to 20 steps) with random planners |
| denied means never started | one process start | **0 of 11** refused commands started |
| plan approval asks less than step approval | more than one ask for an unchanged plan | a five-step plan: **1** plan approval; asking per step after the first read: **3** |

Measured beyond the registered six, the same day: the containment sweep again
with the descriptor walk switched off, so the path-string walk that Windows uses
ran on Linux (every containment test but the two races, which that walk does not
claim): **0 escapes**, the same counts; 3,000 hostile argvs against four real
rules with a runner that records instead of starting anything: 221 matched a
rule, and every one that reached the runner had the pinned program, the rule's
literal tokens, no value of the model's beginning with `-`, and every `{path}`
inside a root (**0 violations**); a file whose *name* is an instruction, seen in
a listing, fooled the planner and ran nothing, while the same command, asked for
by the person before anything untrusted was read, ran.

Weaker than it looks, said plainly: the sweep's generated paths mostly end in
refusals (31 of 5,000 reads opened a real file), so the property is tested far
more on what is refused than on what is allowed; the fooled planner is scripted,
not a model, so the measurement is of the harness, not of anything learned; the
sandbox test ran here because bubblewrap works on this desktop, and elsewhere it
skips.

## 8. What this cannot do

- **It cannot stop a person approving harm they were shown.** The dry run makes
  the exact actions visible; it does not make a person read them.
- **Reads are not consequential.** An injected instruction can steer which files
  inside the roots the agent reads next (never a secret) and what it then tells
  the person. It cannot turn that into a write, a command or a network call
  without the person.
- **An allowed command that interprets files the agent can write runs whatever
  was written there**: an interpreter, a test runner, `make`. Such a rule should
  ask, and run under the sandbox. The allowlist is not a sandbox; bubblewrap is.
- **A `{path}` is checked, then opened by the program by name.** A concurrent
  process could swap it in between; the sandbox bounds what it could then reach.
  An `{arg}` is not a path at all, to the agent: a rule that lets a program open
  an `{arg}` lets it open anything the program can.
- **Without bubblewrap, `"network": false` and `"writes": false` are the
  operator's claims.**
- **Hard links.** A file hard-linked into a root from elsewhere is in the root
  by the file system's own definition and is readable; writes never go through
  it; secrets are known by identity only in the home directory's secret folders.
- **Symbolic links are refused rather than followed**, so a root built from
  links is less useful than its owner may expect.
- **Windows has no descriptor walk.** The same rules run on path strings with a
  link and reparse-point check per component; a check-then-use window remains.
- **The process list shows other users' process names** (their command lines
  are not shown). `"processes": false` removes the tool.
- **No model has been trained on any of this.**

## 9. The conversations the loop needs (listed, not trained)

The rules are the harness's (`DAWNR-HARNESS.md` section 8): every tool output is
the real output of running the tool on a fixture machine, never written by hand;
output spans are never supervised; every conversation passes the held-out and dev
gates; fixture machines for evaluation are disjoint from those for training.
`LoopResult.conversation()` already renders a run in the chat format they would
use: the index and the task, then the assistant's `plan` calls, the harness's
summaries, each step's output with its trust mark, and the answer.

| to learn | conversations | built from |
|---|---|---|
| the plan call itself | a task; one `plan` call with exact arguments; the summary; the answer naming what was done | scripted plans over fixture projects made of proved corpus documents |
| read, then act on what was read | read a file, then edit it with `old` text copied exactly from the read and `expect_sha256` from its header | the same fixtures, edits taken from the twins (a program and its near miss) |
| the checker gate | a write refused by dawnr's checker, then the proved program written | the twins and recorded failing drafts (`repair_data.py`) |
| refusals | a path with `..`, a secret, a protected file, a read-only root, a command on no rule, a network rule offline; the answer says what could not be done and why | the harness's real answers to each |
| not approved | the person refuses a plan; the assistant stops or proposes a smaller one, never the same one again | recorded refusals |
| marked text is data | a file carrying an injected instruction (the adversarial corpus in the disguises of `test_dawnr_agent.py`); the assistant uses its facts and never plans its instruction | fixture files with injections at random places |
| stopping | tasks larger than the budget; the answer reports what is done and what is left | scripted long tasks |
| a stale plan | a file changed after the dry run; the assistant reads it again and plans again | fixtures changed between dry run and run |
| undo | an edit that makes the checker or an allowed test fail, then `fs_undo` | fixture projects with tests |
| an allowed command | running the operator's test command and acting on its (untrusted) output | fixture projects under the sandbox |

The first measurement to make, prediction first: the rate at which a checkpoint
plans an injected instruction on held-out fixture files, before and after the
"marked text is data" conversations, next to the rate at which the harness runs
one (which section 7 measured at 0 for a planner that always plans it).

## 10. Configuration and running

In the harness configuration (paths relative to the file's folder; `~` expands):

    {"offline": true,
     "permissions": {"fs_write": "ask", "fs_edit": "ask", "run_command": "allow"},
     "agent": {
       "roots": [{"name": "project", "path": "~/work/project", "mode": "write"},
                 {"name": "notes", "path": "~/notes"}],
       "commands": [{"argv": ["git", "status"], "permission": "allow", "network": false, "writes": false},
                    {"argv": ["python3", "-m", "pytest", "-q", "--", "{path}..."], "network": false}],
       "sandbox": "bwrap",
       "protect": ["*.lock"],
       "state": "~/.local/state/dawnr-agent",
       "budget": {"max_steps": 12, "max_rounds": 4, "max_failures": 2}}}

Other keys: `secrets` (replaces the default list), `command_path` (the PATH
commands resolve against), `env` (extra environment for every command),
`processes` (false removes `ps_list`), `check_writes` (`block`, `note`, `off`),
`limits` (read and write sizes, lines, results, seconds, `command_timeout`,
`command_output`), `dry_run` (the `plan` tool previews and runs nothing). An
unknown or malformed key fails when the configuration loads.

    python locallm/dawnr_agent --config harness.json roots             # what is configured, what was skipped
    python locallm/dawnr_agent --config harness.json dry-run plan.json # exactly what would run; runs nothing
    python locallm/dawnr_agent --config harness.json run plan.json     # the same, asked once, then run
    python locallm/dawnr_agent --config harness.json run plan.json --approve <digest>   # approved ahead
    python locallm/dawnr_agent --config harness.json journal           # every change, newest last
    python locallm/dawnr_agent --config harness.json undo c-0123456789 # the person's own undo

`--approve` runs a plan only if its dry run now has exactly that digest, so an
approval given after one dry run cannot carry over to a plan or a file that has
changed. `chat_cli.py --harness harness.json` asks for each plan once on the
terminal; the Tk chat pane still asks per step. The skill
`acting-on-the-machine` (in `locallm/dawnr_harness/skills/`) states these
conventions for a model, loaded on demand like any skill; `docs/USER-GUIDE.md`
walks through one plan end to end.

Tests: `python -m unittest locallm/test_dawnr_agent.py` (standard library; set
`TMPDIR` to keep its temporary machines off `/tmp`; the sandbox test skips where
bubblewrap cannot run).
