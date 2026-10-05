"""loop.py: the planning loop: task, plan, steps as tool calls, observations, re-plan, within a budget and a stop rule.

The shape is ReAct's (Yao et al., arXiv:2210.03629: reasoning and acting
interleaved, each action's observation fed back before the next decision),
with the unit of action a whole plan rather than one call: the planner
proposes a plan (plan.py), the person sees the dry run and approves the
whole, the steps run through the harness, and their outputs, marked with
their trust, go back to the planner, which proposes the next plan or
answers. A re-plan made after untrusted text entered is new control flow:
its consequential steps need the person again (the harness's taint rule),
and with nobody present they are refused. That is what keeps a file's
injected instruction from becoming an action, whatever the planner believes.

The stop rule, checked in this order, every round:

  done         the planner answered, and the Stop hooks (dawnr's checker on
               the final program) let it end; a block is fed back as an
               observation and costs a round
  rounds       max_rounds plans have been proposed
  budget       max_steps tool calls have run (a plan is cut at the budget;
               the calls past it do not run)
  failures     max_failures rounds in a row ended with a refusal or a failed step
  no progress  the planner proposed a plan it had already proposed, with nothing changed since, for the second
               time. The first time the plan is not run and the planner is told so, once: its result would be
               the one it has. After a round that changed something (a file, or anything a consequential tool
               did) the earlier plans may be proposed again: running the test again after a fix is not a
               repeat. The plan that made the change, proposed again straight after it, is
  refused      the person refused a plan
  time         max_seconds of wall clock
  dry run      the loop was asked only to show the first plan
  planner      the planner raised or returned something that is not a plan

The approver answers for the person: true, false, or a sentence. A sentence
is neither: the plan is not run and goes back to the planner with it (the
front door's second look at a plan that would lose a file's contents), and
the same plan proposed again is then put to the person like any other.

The planner is anything callable as planner(state) -> Plan | Finish (or the
dict forms {"steps": [...]} and {"answer": "..."}). A model plans through
ModelPlanner, which renders the loop in dawnr's chat format and reads a
`plan {...}` call back; the scripted planners are for tests and for running a
plan written by hand.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

from .plan import DryRun, Plan, PlanError, RunOutcome, canonical, execute, journal_mark, moved, preview_plan


@dataclass
class Budget:
    max_steps: int = 12
    max_rounds: int = 4
    max_failures: int = 2
    max_seconds: float | None = None

    def __post_init__(self):
        for k in ("max_steps", "max_rounds", "max_failures"):
            v = getattr(self, k)
            if not isinstance(v, int) or isinstance(v, bool) or v < 0:
                raise ValueError(f"budget {k} must be a non-negative integer, not {v!r}")


@dataclass
class Finish:
    answer: str


@dataclass
class Round:
    plan: Plan | None = None               # as the planner wrote it
    dry: DryRun | None = None
    outcome: RunOutcome | None = None
    answer: str | None = None
    note: str = ""                         # the harness's word to the planner about this round (trusted)


@dataclass
class LoopState:
    task: str
    index: str
    budget: Budget
    rounds: list = field(default_factory=list)
    steps_used: int = 0

    @property
    def steps_left(self) -> int:
        return max(0, self.budget.max_steps - self.steps_used)

    def observations(self) -> list:
        """(untrusted?, text) of everything the planner has been told, in order."""
        out = []
        for r in self.rounds:
            if r.outcome is not None:
                out.append((False, r.outcome.summary()))
                for o in r.outcome.outcomes:
                    if o.result is not None:
                        out += [(u, f"step {o.index} ({o.step.tool}):\n{t}") for u, t in o.result.spans()]
            elif r.dry is not None:
                out.append((False, r.dry.render(for_person=False)))
            if r.note:
                out.append((False, r.note))
        return out


@dataclass
class LoopResult:
    task: str
    index: str
    rounds: list
    stop: str
    answer: str | None
    steps_run: int
    approvals_asked: int = 0
    plan_approvals: int = 0

    def conversation(self) -> dict:
        """The loop as one conversation in dawnr's chat format (chat.render_conversation): the task with the
        index; the assistant's plan calls, the harness's summaries and each step's output (untrusted ones
        marked), then the answer. The shape the loop's training conversations take (DAWNR-AGENT.md)."""
        parts = []
        for r in self.rounds:
            if r.plan is not None:
                parts.append({"type": "tool", "text": "plan " + json.dumps(r.plan.to_json(), ensure_ascii=False)})
                if r.outcome is not None:
                    parts.append({"type": "tool_output", "text": r.outcome.summary()})
                    for o in r.outcome.outcomes:
                        if o.result is None:
                            continue
                        for untrusted, text in o.result.spans():
                            part = {"type": "tool_output", "text": f"step {o.index} ({o.step.tool}):\n{text}"}
                            if untrusted:
                                part["untrusted"] = True
                            parts.append(part)
                elif r.dry is not None:
                    parts.append({"type": "tool_output", "text": r.dry.render(for_person=False)})
            if r.answer is not None:
                parts.append({"type": "text", "text": r.answer})
            if r.note:
                parts.append({"type": "tool_output", "text": r.note})
        user = (self.index + "\n\n" + self.task) if self.index else self.task
        return {"messages": [{"role": "user", "content": user}, {"role": "assistant", "content": parts}]}


# a plan proposed again with nothing changed since: not run, and said once (OpenHands stops at the fourth identical
# action and observation, openhands/controller/stuck.py; here the second is not run at all, and the third ends it)
REPEATED = ("Not run: exactly this was already run, and nothing has changed since, so it would give the same result. "
            "Send something different, or answer with what you have.")


class AgentLoop:
    def __init__(self, agent, planner, *, budget: Budget | None = None, plan_approver=None, dry_run: bool = False):
        self.agent = agent
        self.harness = agent.harness
        self.planner = planner
        self.budget = budget or agent.budget
        self.plan_approver = plan_approver if plan_approver is not None else agent.plan_approver
        self.dry_run = dry_run

    def _proposal(self, state: LoopState):
        got = self.planner(state)
        if isinstance(got, (Plan, Finish)):
            return got
        if isinstance(got, dict) and "answer" in got and "steps" not in got:
            if not isinstance(got["answer"], str):
                raise PlanError("an answer is a string")
            return Finish(got["answer"])
        if isinstance(got, dict):
            return Plan.from_json(got)
        raise PlanError(f"the planner returned {type(got).__name__}, not a plan or an answer")

    def run(self, task: str, context: str = "") -> LoopResult:
        session = self.harness.session()
        state = LoopState(task, self.harness.index(), self.budget)
        context = context or task
        started = time.monotonic()
        seen: set = set()                                          # the plans proposed since anything last changed
        just = ""                                                  # the plan that made that change, for one round
        told = False                                               # a repeat has been sent back once already
        failures = asked = approvals = 0
        stop, answer = "", None
        while not stop:
            if len(state.rounds) >= self.budget.max_rounds:
                stop = "rounds"
                break
            if self.budget.max_seconds is not None and time.monotonic() - started > self.budget.max_seconds:
                stop = "time"
                break
            try:
                proposal = self._proposal(state)
            except Exception as e:                                 # noqa: BLE001  (a planner fault ends the loop)
                state.rounds.append(Round(note=f"the planner failed: {type(e).__name__}: {e}"))
                stop = "planner"
                break
            if isinstance(proposal, Finish):
                decision = self.harness.stop(proposal.answer, context=context, session=session)
                if decision.block:
                    state.rounds.append(Round(answer=proposal.answer, note=decision.reason))
                    failures += 1
                    if failures >= self.budget.max_failures:
                        stop = "failures"
                    continue
                state.rounds.append(Round(answer=proposal.answer))
                stop, answer = "done", proposal.answer
                break
            dry = preview_plan(self.agent, self.harness, proposal, session, context)
            if dry.digest in seen or dry.digest == just:
                if not told and not self.dry_run:
                    told = True
                    state.rounds.append(Round(plan=proposal, dry=dry, note=REPEATED))
                    continue
                state.rounds.append(Round(plan=proposal, dry=dry, note=f"plan {dry.digest} was already proposed; "
                                                                        "the loop stops rather than repeat it"))
                stop = "no progress"
                break
            seen.add(dry.digest)
            if self.dry_run:
                state.rounds.append(Round(plan=proposal, dry=dry, note="dry run: nothing was run"))
                stop = "dry run"
                break
            approved = None
            if self.plan_approver is not None and not dry.refused:
                approvals += 1
                try:
                    approved = self.plan_approver(dry)
                except Exception:                                  # noqa: BLE001
                    approved = False
                if isinstance(approved, str) and approved:         # neither yes nor no: back to the planner, with this
                    seen.discard(dry.digest)                       # said; the same plan sent again is not a repeat
                    state.rounds.append(Round(plan=proposal, dry=dry, note=approved))
                    continue
                approved = bool(approved)
            mark = journal_mark(self.agent)
            outcome = execute(self.harness, dry, approved=approved, session=session, context=context,
                              steps_left=state.steps_left)
            asked += outcome.approvals_asked
            state.steps_used += outcome.steps_run
            self.agent.record_plan(dry, outcome, session)
            seen, just = (set(), dry.digest) if moved(self.agent, self.harness, outcome, mark) else (seen, "")
            state.rounds.append(Round(plan=proposal, dry=dry, outcome=outcome))
            if approved is False:
                stop = "refused"
            elif outcome.stopped.startswith("budget"):
                stop = "budget"
            elif outcome.failed:
                failures += 1
                if failures >= self.budget.max_failures:
                    stop = "failures"
            else:
                failures = 0
        return LoopResult(task, state.index, state.rounds, stop, answer, state.steps_used, asked, approvals)


# ----------------------------------------------------------------- planners --

class ScriptedPlanner:
    """Proposals in order (Plan, Finish or their dict forms); an answer of "" when they run out."""

    def __init__(self, proposals):
        self.proposals = list(proposals)
        self.calls = 0

    def __call__(self, state: LoopState):
        self.calls += 1
        if not self.proposals:
            return Finish("")
        return self.proposals.pop(0)


_PLAN_CALL = re.compile(r"(?:<\|tool_start\|>\s*|\A\s*)plan\s*(\{.*?)\s*(?:<\|tool_end\|>|\Z)", re.S)


class ModelPlanner:
    """A model as the planner: complete(conversation) -> the assistant's next text, read as a plan call or an answer.

    The conversation is the loop so far in dawnr's chat format, so the model sees what it would see in a chat
    turn: the index, the task, its own earlier plan calls, the harness's summaries, the step outputs with the
    untrusted mark. A reply holding `plan {json}` (inside the harness's call tokens or bare) is a plan; any
    other reply is the answer."""

    def __init__(self, complete):
        self.complete = complete

    def __call__(self, state: LoopState):
        partial = LoopResult(state.task, state.index, state.rounds, "", None, state.steps_used)
        text = self.complete(partial.conversation())
        m = _PLAN_CALL.search(text or "")
        if m:
            try:
                obj = json.loads(m.group(1))
            except ValueError as e:
                raise PlanError(f"the plan call's arguments are not JSON: {e}") from None
            return Plan.from_json(obj)
        return Finish((text or "").strip())


__all__ = ["AgentLoop", "Budget", "Finish", "LoopResult", "LoopState", "ModelPlanner", "Round", "ScriptedPlanner",
           "canonical"]
