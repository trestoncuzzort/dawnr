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
| processes | Python's `subprocess` documentation (a sequence argv, no shell; `communicate()` buffers everything; `start_new_session` instead of `preexec_fn`); Stack Overflow q/4789837 (kill the process group, not only the child) | output is read through a selector that keeps a capped prefix and drains the rest, for at most half a second after the command exits; the group is killed at the deadline and when the command exits, while the leader is still an unreaped zombie so its id cannot have been reused |
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
| reading a secret | names (`.ssh`, `*.pem`, `.env`, ...) matched case-insensitively; every file under the home directory with a secret name, at any depth, also by identity (a bounded breadth-first scan when the agent is built), so a hard link under an innocent name is refused | `test_secrets_are_never_read_by_name_or_by_identity`, `test_a_nested_home_secret_hard_linked_into_a_root_is_refused`, `test_a_nested_literal_secret_name_hard_linked_into_a_root_is_refused`, `test_every_secret_pattern_is_known_by_identity_anywhere_under_home`, `HomeScan` |
| a hard link into a root to any file outside the roots, or to a secret name inside them (an archive unpacked into a root can make one: CWE-62 lists CVE-2021-21272, hard links in a tarball reaching outside the folder it was unpacked into) | no list: a file's contents leave only when every name it has (its link count) is found inside the roots under a name the model could read itself, the roots being searched for them; a search that stops at its cap refuses, and the descriptor is examined again after the search; the file actually opened must be inside a root by its real path. Search skips such a file, a command is not given it as a `{path}`, and a write replaces it without reading or keeping its bytes, so no undo can bring them into the root | `test_a_hard_link_to_a_file_outside_the_roots_is_refused_whatever_its_name`, `test_a_hard_link_whose_other_name_in_a_root_is_secret_is_refused`, `test_search_does_not_show_a_file_hard_linked_from_outside`, `test_replacing_a_hard_link_from_outside_keeps_no_copy_to_undo_into_the_root`, `test_overlapping_roots_do_not_count_one_name_twice`, `test_a_name_added_inside_the_roots_while_the_names_are_counted_is_caught`, `test_the_search_for_a_files_other_names_fails_closed_at_its_cap`, `test_a_path_hard_linked_from_outside_the_roots_is_not_given_to_a_command`, `test_a_file_swapped_for_a_link_between_check_and_open_is_refused_by_its_real_path`; and `test_a_hard_link_between_two_names_inside_the_roots_is_read` for what must still work |
| rewriting `.git/config`, a hook, the configuration, the audit log, the agent's journal, the enforcement code | protected by name (`.git`, and the operator's list) and by identity (everything the configuration names, and `dawnr_harness`, `dawnr_agent`, `engine.py`, `chat.py`, `chat_cli.py`, `chat_pane.py`, `t_tool.py`); protected paths are read but never written, and never handed to a command | `test_protected_paths_are_read_but_never_written`, `Plans.test_the_model_cannot_reach_permissions_or_configuration` |
| a file its owner made read-only | a rename needs only the directory's permission, so the file's own mode is checked and kept | `test_a_file_its_owner_made_read_only_is_not_replaced` |
| shell metacharacters | no shell, ever: an argv list | `Commands.test_no_shell_and_a_scrubbed_environment` |
| an option smuggled into an argument (`-exec`, `--output=`, `--pre`) | a placeholder value may not begin with `-`; options exist only where the operator wrote them | `test_denied_means_never_started` |
| a program replaced by the agent | programs resolved once, pinned by absolute path, refused if inside a writable root; the command PATH excludes the roots and relative entries | `test_a_program_inside_a_writable_root_is_not_used` |
| secrets in the harness's environment | commands get a scrubbed environment: PATH, HOME, locale, the operator's additions | `test_no_shell_and_a_scrubbed_environment` |
| a command that never ends, forks, or floods | a deadline that kills the process group; a capped output; the call returns half a second after the command exits even if a descendant holds its pipes; under bubblewrap nothing outlives the call | `test_deadline_kills_the_whole_process_group`, `test_output_is_capped`, `Sandbox.test_a_command_that_leaves_a_new_session_behind_does_not_outlive_the_call` |
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
refuses when the file changed since, rather than clobber the later change. The
one exception: a write that replaces a file with a name outside the roots (a
hard link) does not read or keep its bytes, which are still under that other
name, so that change cannot be undone; keeping them would let an undo write
them into the root as a new file with one name.

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

A hard link is not a link to follow: it is a second name for the same file, and
link(2) says "it is impossible to tell which name was the 'original'". So before
any of a file's contents leave (a read, a search hit, an edit, a dry run's
diff), two more checks run on the opened descriptor. Its real path, as the
kernel reports it (`/proc/self/fd`, else `os.path.realpath`), must be inside a
root. And if its link count is above one, the roots are searched for its names
(`os.fwalk` again, no link followed), and it is read only if all of them are
found there, none secret by name and none below a secret or the agent's hidden
directory: the comparison GNU tar's `--check-links` makes between the links it
archived and `st_nlink`. The CERT C rule POS01-C and Postfix's `safe_open()`
refuse every file with more than one link; this refuses only those with a name
the model could not use itself, so a file with two names inside the roots is
still read. The search stops at 200,000 entries or 5 s (`limits`
`link_scan_entries`, `link_scan_seconds`) and then refuses, and the descriptor is
examined again after it (link count and change time, as `safe_open()` compares
its two stats), so a name added during the search refuses the read too.

The home directory is also scanned once, when the agent is built, for every
secret name at any depth: breadth-first (like `bfs`, so a cap cuts the deepest
levels, never a whole folder near the top), no link followed except a secret
name that is itself a link (dotfiles kept elsewhere), not into a root, not onto
a file system that holds neither the home directory nor a root (a hard link
cannot cross one), at most 200,000 entries or 2 s (`home_scan_entries`,
`home_scan_seconds`). What it finds is refused by identity, which also covers a
secret moved into a root after the scan. When it stops early, loading says so
(`harness.problems`, and `roots` prints how far it got).

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

### Any command, over an overlay (`sh`, 2026-10-05)

The allowlist above is safe because it is short, and for the same reason it cannot rename a file. With
`"shell": true` the agent also offers `sh`, which runs any shell line and is safe for where it runs
(`locallm/dawnr_agent/shell.py`): inside the same bubblewrap sandbox, with each writable root mounted as an
overlay over itself, so that the command changes the folder freely and every change lands in a directory of the
agent's own. The folder is not touched. Afterwards the changes are read back by the kernel's rules for an
overlay's upper directory (a file written, a whiteout for a name removed, an opaque directory for one replaced
whole):

- a command that changed nothing was a read: its output is returned, marked untrusted, and nothing is asked;
- one that changed something is asked for, and the reason shown is what it changed, so the person approves
  effects and not a command line; in a plan, the dry run is that run;
- approved, the changes are applied through the journaled file operations, each file's old bytes kept, and one
  `undo` of the person's puts a whole command's changes back, the last first;
- refused: a file that moved since the command ran (nothing more is applied), a change set of more than 400
  files, a file over the journal's size limit, a link or a device (listed, never applied).

The idea is `try`'s (github.com/binpash/try, MIT, OSDI'26). `try` overlays the whole system with the network
open and calls itself a "semisolate"; here only the roots are overlaid, inside the sandbox. What a command does
that is not a file in a root does not exist afterwards: it cannot install a package, change a setting or leave a
program running. Tried on the desktop this was written on (bubblewrap 0.11.1, Linux 7.0): a line that renamed a
file, appended to another, made two folders and an executable script was asked for as six changes and applied
as six journal rows; `locallm/test_dawnr_shell.py` holds that, the refusals, and that the network, the rest of the
disk and the secret folders are out of reach. It needs Linux 5.11 and bubblewrap 0.8; where the overlay cannot be
mounted the tool is not offered. Not yet measured: a model driving it on a set of tasks.

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
locallm/test_dawnr_agent.py` on the desktop, 2026-09-27 (75 tests, 2 skipped by
design, 6.6 s on Python 3.14; the same pass on Python 3.10).

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

A failure found while measuring, and fixed: a command whose child put itself in
a new session and kept the output pipes open held the call until the reader
threads' joins gave up, 10.06 s for a command that ran 0.3 s, and reported that
as its runtime. Output is now read with a selector and the call returns half a
second after the command exits whatever it left behind (0.86 s for the same
command). Under bubblewrap the child that escaped the process-group kill does
not outlive the call (it stopped writing when the call returned); without the
sandbox it does (it kept writing), which section 8 says.

Measured on the second review of hard links, the same day (test numbers from
`python -m unittest locallm/test_dawnr_agent.py`: 102 tests, 2 skipped, on
Python 3.14 and 3.10; the registered numbers above came out identical). The
first fix had scanned only the home directory's top level; a key in a subfolder
hard-linked into a root was read whole. Every new test failed before this fix
but the one that checks two names inside the roots are still read, which guards
against refusing too much and passed before and after; and twelve pieces of the
fix, each removed on its own, fail at least one test (a thirteenth, one of the
two ways a folder two roots share is counted once, is backed up by the other:
removing both fails). The home tree of the desktop this was written on is
10,065,366 entries in 358,916 directories, and walking all of it took 78 s, so
the scan is bounded: 200,000 entries, breadth-first, took 0.40 s warm and 1.0 s
on the first run, read every level to depth 5 whole, and found 111 secret files
and directories. The read-time search, on a root of 225,610 entries holding a
file with one name outside it: stopped at the 200,000-entry cap after 1.04 s and
refused; with a 400,000 cap it saw the whole root in 0.61 s and refused with the
exact reason. A file with one name costs no search (0.3 ms per read). One more
leak was found on the way and closed: `fs_write` over such a file kept its old
bytes for undo, and `fs_undo` then wrote them into the root as a file with one
name, which a link-count check alone would have read.

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
  operator's claims**, and a command that puts itself in a new session escapes
  the process-group kill; under bubblewrap it cannot, because the command's
  process namespace ends with it.
- **Hard links: what still gets through.** A file with a name outside the roots
  is not read (section 3), but the roots are the boundary, so:
  - *A file moved into a root* (linked in, then its outside name removed) has
    one name, inside the root, and is read like any file there. If it had a
    secret name under the home directory when the agent was built, and the scan
    reached it, its identity still refuses it; a secret made after the scan, or
    deeper than the scan reached, and then moved in, is read.
  - *A hard link made after the scan* is caught at read time, because its other
    name is still outside; only removing that name first (the move above) gets
    it through.
  - *The count and the read are not one step.* A name added or removed during
    the search changes the link count or change time and refuses the read; a
    change after that last look, while the bytes are read, is not seen (the file
    read was inside the roots at the look).
  - *Both scans are bounded.* Past the search's cap a file with more than one
    name is refused even when every name is inside a large root. Files that
    share a store outside the roots are refused by design: pnpm's
    `node_modules` (its files are "hard-linked from" the store, pnpm.io's
    Motivation page), uv with `--link-mode hardlink` (its default on Windows,
    by `uv help pip install`), and a local `git clone`'s objects (two links
    each, measured here).
  - *Not the file tools:* `fs_list` still shows such a file's name and size; a
    command given a directory reads whatever it opens below it, hard links
    included (the check covers a `{path}` that names a file); a bind or FUSE
    mount inside a root is inside it by the file system's own definition.
  - *Without `/proc/self/fd`* (macOS, Windows) the real path is
    `os.path.realpath` of the path used: one more check-then-use window. With
    it, the path is the kernel's spelling, compared with the root's as
    configured; a root spelled differently from the kernel (possible on a
    case-insensitive file system) would be refused file by file. Not measured
    here: no such file system was at hand.
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
`command_output`, and the caps of the two scans in section 3:
`link_scan_entries`, `link_scan_seconds`, `home_scan_entries`,
`home_scan_seconds`), `dry_run` (the `plan` tool previews and runs nothing). An
unknown or malformed key fails when the configuration loads. The operator's
`secrets` replace the default names for the by-name check; the home scan looks
for both.

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
