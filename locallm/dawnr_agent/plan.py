"""plan.py: a plan is a list of tool calls with exact arguments; the dry run shows it; approval binds to exactly it.

The pattern is plan-then-execute (Beurer-Kellner et al., "Design Patterns for
Securing LLM Agents against Prompt Injections", arXiv:2506.08837, section 4.1
is an assistant acting on files whose attacker controls file contents and
names): the calls are fixed before any untrusted text is read, so nothing read
while running them can add a call. That paper notes the pattern still lets an
injection steer the arguments of a planned call; here a step's arguments are
exact, written in the plan, never a slot filled later from data, so the
dry run shows the whole of what can happen. Control flow from the trusted
request only is CaMeL's rule too (Debenedetti et al., arXiv:2503.18813).

The dry run (Terraform's plan: developer.hashicorp.com/terraform/cli/commands/plan)
computes, for each step and without doing it, the decision the harness's
policy will give it (with the taint that earlier steps will add), what it will
touch (the resolved path, the diff of a write, the exact argv of a command),
and pins each file a step edits to its current hash, so the run refuses a step
whose file moved since the person looked (Terraform's saved plan is applied
exactly as shown; "re-check ... before applying"). The digest covers the
pinned steps: an approval is of that digest and nothing else.

Running a plan goes through Harness.call for every step: the operator's
policy, the hooks, the audit log, the approver. When the person approved the
plan, the approver answers yes to exactly the approved call (same tool, same
canonical arguments) and passes anything else to the person as usual; a hook
that rewrote a step's arguments therefore does not inherit the approval. A
step the policy denies stays denied; approval only ever answers an ask.
"""
from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field

from dawnr_harness.tools import CallContext, Session, Tool, ToolResult, validate

from .files import Preview

MAX_PLAN_STEPS = 16
MAX_SHOWN_VALUE = 300


class PlanError(ValueError):
    """A plan the agent cannot use; the message is what the model is told."""


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "goal": {"type": "string", "maxLength": 500},
        "steps": {"type": "array", "minItems": 1, "maxItems": MAX_PLAN_STEPS,
                  "items": {"type": "object",
                            "properties": {"tool": {"type": "string", "minLength": 1, "maxLength": 128},
                                           "arguments": {"type": "object"},
                                           "why": {"type": "string", "maxLength": 300}},
                            "required": ["tool"], "additionalProperties": False}}},
    "required": ["steps"], "additionalProperties": False}


@dataclass(frozen=True)
class Step:
    tool: str
    arguments: dict = field(default_factory=dict)
    why: str = ""

    def call(self) -> dict:
        return {"tool": self.tool, "arguments": self.arguments}


@dataclass
class Plan:
    steps: list
    goal: str = ""

    @classmethod
    def from_json(cls, obj) -> "Plan":
        if isinstance(obj, Plan):
            return obj
        errs = validate(PLAN_SCHEMA, obj)
        if errs:
            raise PlanError("plan: " + "; ".join(errs[:5]))
        return cls([Step(s["tool"], dict(s.get("arguments") or {}), s.get("why", "")) for s in obj["steps"]],
                   obj.get("goal", ""))

    def to_json(self) -> dict:
        out = {"steps": [dict(s.call(), **({"why": s.why} if s.why else {})) for s in self.steps]}
        if self.goal:
            out["goal"] = self.goal
        return out

    def digest(self) -> str:
        return hashlib.sha256(canonical([s.call() for s in self.steps]).encode("ascii")).hexdigest()[:16]


@dataclass
class StepView:
    index: int
    step: Step                 # pinned: the exact call that will run
    decision: str
    why: str
    preview: Preview
    uncertain: bool = False    # after a command, whose effects are not simulated: a preview error is a warning

    @property
    def refused(self) -> bool:
        return self.decision == "deny" or (self.preview.error is not None and not self.uncertain)


@dataclass
class DryRun:
    plan: Plan                 # the pinned plan
    views: list
    digest: str

    @property
    def refused(self) -> list:
        return [v for v in self.views if v.refused]

    def _shown_args(self, args: dict) -> str:
        shown = {k: (v if not isinstance(v, str) or len(v) <= MAX_SHOWN_VALUE
                     else f"<{len(v)} characters: {v[:80]}...>") for k, v in args.items()}
        return json.dumps(shown, ensure_ascii=False)

    def render(self, *, for_person: bool, quoted: bool = False) -> str:
        """`quoted` adds the lines of a file that came with a refusal: untrusted text, for a reader who is told so."""
        head = f"plan {self.digest}: {len(self.views)} step{'s' if len(self.views) != 1 else ''}"
        if self.plan.goal:
            head += f" ({self.plan.goal})"
        lines = [head]
        for v in self.views:
            lines.append(f"  {v.index}. {v.step.tool} {self._shown_args(v.step.arguments)}")
            lines.append(f"     {v.decision}: {v.why}")
            if v.preview.error:
                lines.append(f"     {'may be refused' if v.uncertain else 'refused'}: {v.preview.error}")
                if quoted and v.preview.quoted:
                    lines += ["       " + line for line in v.preview.quoted.splitlines()]
            elif v.preview.summary:
                lines.append(f"     {v.preview.summary}")
            if for_person:
                lines += [f"       {d}" for d in v.preview.detail]
            if v.step.why and for_person:
                lines.append(f"     the planner's reason: {v.step.why}")
        if self.refused:
            lines.append(f"nothing will run: step {self.refused[0].index} would be refused")
        else:
            lines.append("nothing has run yet; approving runs exactly these steps in order, stopping at the first "
                         "that fails")
        return "\n".join(lines)


def preview_plan(agent, harness, plan: Plan, session: Session | None = None, context: str = "") -> DryRun:
    """The dry run: every step's decision, preview and pin, computed without running anything."""
    sim = Session(tainted=bool(session and session.tainted))
    overlay: dict = {}
    views, pinned = [], []
    after_command = False
    for i, step in enumerate(plan.steps, 1):
        tool = harness.registry.get(step.tool)
        args = dict(step.arguments)
        if step.tool == "plan":
            view = StepView(i, step, "deny", "a plan cannot contain a plan", Preview(error="a plan inside a plan"))
        elif tool is None:
            view = StepView(i, step, "deny", f"unknown tool {step.tool!r}",
                            Preview(error=f"no tool named {step.tool!r}"))
        else:
            errs = validate(tool.input_schema, args)
            if errs:
                view = StepView(i, step, "deny", "invalid arguments", Preview(error="; ".join(errs[:5])))
            else:
                try:
                    prev = agent.preview(step.tool, args, overlay, context)
                except Exception as e:                             # noqa: BLE001  (a preview's bug refuses the step)
                    prev = Preview(error=f"the dry run of this step failed: {type(e).__name__}")
                if prev.pin:
                    args.update(prev.pin)
                decision, why = harness.policy.decide(tool, sim, args)
                view = StepView(i, Step(step.tool, args, step.why), decision, why, prev,
                                uncertain=after_command and prev.error is not None and decision != "deny")
                if prev.writes:
                    overlay.update(prev.writes)
                if tool.trust == "untrusted":
                    sim.tainted = True
                if prev.quoted:                                    # a file's lines came back with the refusal
                    sim.tainted = True
                    if session is not None:
                        session.tainted = True
                if step.tool == "run_command":
                    after_command = True
        views.append(view)
        pinned.append(view.step)
    pinned_plan = Plan(pinned, plan.goal)
    return DryRun(pinned_plan, views, pinned_plan.digest())


# ------------------------------------------------------------------- running --

@dataclass
class StepOutcome:
    index: int
    step: Step
    status: str                 # ran | failed (the tool ran and reported an error) | refused (the harness did not
    result: ToolResult | None = None                        # run it) | not run (never reached)
    note: str = ""


@dataclass
class RunOutcome:
    dry: DryRun
    approved: bool | None       # True: the person approved the plan; False: they refused it; None: nobody was asked
    outcomes: list = field(default_factory=list)
    stopped: str = ""
    steps_run: int = 0          # calls made through the harness (what the step budget counts), refused ones too
    approvals_asked: int = 0

    @property
    def failed(self) -> bool:
        return bool(self.stopped) and self.stopped != "done"

    @property
    def ran(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "ran")

    def summary(self) -> str:
        who = {True: "approved by the person", False: "refused by the person",
               None: "run under the operator's policy (nobody was asked to approve the plan)"}[self.approved]
        lines = [f"plan {self.dry.digest}: {who}; {self.ran} of {len(self.dry.views)} steps ran"
                 + (f"; stopped: {self.stopped}" if self.stopped and self.stopped != "done" else "")]
        for o in self.outcomes:
            lines.append(f"step {o.index} {o.step.tool}: {o.status}" + (f" ({o.note})" if o.note else ""))
        return "\n".join(lines)


class _ScopedApprover:
    """During one step: yes to exactly the approved call, anything else to the person (or no)."""

    def __init__(self, harness, approved: Step | None, fallback):
        self.harness, self.approved, self.fallback = harness, approved, fallback
        self.asked_person = 0

    def __call__(self, name: str, arguments: dict, why: str) -> bool:
        if (self.approved is not None and name == self.approved.tool
                and canonical(arguments) == canonical(self.approved.arguments)):
            return True
        if self.fallback is None:
            return False
        self.asked_person += 1
        return bool(self.fallback(name, arguments, why))

    def __enter__(self):
        self.saved = self.harness.approver
        self.harness.approver = self
        return self

    def __exit__(self, *exc):
        self.harness.approver = self.saved


_LOCK = threading.RLock()


def execute(harness, dry: DryRun, *, approved: bool | None, session: Session, context: str = "",
            steps_left: int | None = None) -> RunOutcome:
    """Run a dry-run plan's pinned steps through the harness, in order, within the step budget."""
    out = RunOutcome(dry, approved)
    if approved is False:
        out.stopped = "the person did not approve the plan"
        out.outcomes = [StepOutcome(v.index, v.step, "not run") for v in dry.views]
        return out
    if dry.refused:
        v = dry.refused[0]
        out.stopped = f"step {v.index} would be refused ({v.preview.error or v.why})"
        out.outcomes = [StepOutcome(w.index, w.step, "not run") for w in dry.views]
        return out
    fallback = harness.approver
    for k, view in enumerate(dry.views):
        if steps_left is not None and out.steps_run >= steps_left:
            out.stopped = "budget: the step budget is spent"
            out.outcomes += [StepOutcome(w.index, w.step, "not run", note="budget") for w in dry.views[k:]]
            return out
        if approved or fallback is not None:
            with _LOCK, _ScopedApprover(harness, view.step if approved else None, fallback) as scope:
                result = harness.call(view.step.tool, view.step.arguments, context=context, session=session)
            out.approvals_asked += scope.asked_person
        else:                                # nobody to ask: the harness says so in its own words
            with _LOCK:
                result = harness.call(view.step.tool, view.step.arguments, context=context, session=session)
        out.steps_run += 1
        if result.is_error:
            status = "refused" if result.source == "harness" else "failed"
            out.outcomes.append(StepOutcome(view.index, view.step, status, result, _first_line(result.text)))
            out.outcomes += [StepOutcome(w.index, w.step, "not run", note=f"step {view.index} {status}")
                             for w in dry.views[k + 1:]]
            out.stopped = f"step {view.index} {status}"
            return out
        out.outcomes.append(StepOutcome(view.index, view.step, "ran", result))
    out.stopped = "done"
    return out


def _first_line(text: str, limit: int = 200) -> str:
    line = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    return line if len(line) <= limit else line[:limit - 3] + "..."


def outcome_result(outcome: RunOutcome, *, dry_run_only: bool = False) -> ToolResult:
    """A plan's outcome as one tool answer: the harness's summary (trusted), then each step's own output, marked
    with the trust of the call that produced it (untrusted output stays untrusted)."""
    if dry_run_only:
        return ToolResult(outcome.dry.render(for_person=False) + "\ndry run: nothing was run.")
    notes, untrusted = [], []
    for o in outcome.outcomes:
        if o.result is None:
            continue
        for is_untrusted, text in o.result.spans():
            (untrusted if is_untrusted else notes).append(f"step {o.index} ({o.step.tool}):\n{text}")
    return ToolResult(outcome.summary(), is_error=outcome.failed, notes=notes, untrusted_notes=untrusted)


def journal_mark(agent) -> int:
    """How much the journal holds: it grows with every change made through the agent."""
    try:
        return agent.ops.journal.path.stat().st_size
    except (AttributeError, OSError):
        return 0


def moved(agent, harness, outcome: RunOutcome, mark: int) -> bool:
    """Whether a run changed something an earlier plan would now see differently: a change in the journal since
    `mark`, or a consequential tool that ran. A plan proposed again after that is not a repeat. (OpenHands calls
    an agent stuck on the same action with the same observation, openhands/controller/stuck.py at 0.39.0; here a
    repeat is stopped before it runs, so what is compared is whether anything it could observe has changed.
    Receipt c52f7789a75e.)"""
    if journal_mark(agent) != mark:
        return True
    for o in outcome.outcomes:
        tool = harness.registry.get(o.step.tool) if o.status == "ran" else None
        if tool is not None and tool.consequential:
            return True
    return False


# ------------------------------------------------------------------ the tool --

@dataclass
class _SessionState:
    steps: int = 0
    rounds: int = 0
    digests: set = field(default_factory=set)               # the plans proposed since anything last changed
    just: str = ""                                          # the plan that made that change, for one round


def plan_tool(agent) -> Tool:
    """`plan {"steps": [...]}` from a model: the dry run, the person's approval of the whole, then the steps."""
    states: dict = {}

    def run(args: dict, ctx: CallContext) -> ToolResult:
        harness = agent.harness
        session = ctx.session if ctx is not None and ctx.session is not None else harness.session()
        if session.id not in states and len(states) >= 1024:
            states.pop(next(iter(states)))                 # the oldest conversation's counters
        state = states.setdefault(session.id, _SessionState())
        try:
            plan = Plan.from_json(args)
        except PlanError as e:
            return ToolResult(str(e), is_error=True)
        if state.rounds >= agent.budget.max_rounds:
            return ToolResult(f"not run: {agent.budget.max_rounds} plans already this conversation (the budget); "
                              "answer with what you have", is_error=True)
        dry = preview_plan(agent, harness, plan, session, ctx.context if ctx else "")
        if dry.digest in state.digests or dry.digest == state.just:
            return ToolResult(f"not run: plan {dry.digest} was already proposed in this conversation", is_error=True)
        state.rounds += 1
        state.digests.add(dry.digest)
        if agent.plan_approver is None or agent.dry_run:
            harness.messages.append(dry.render(for_person=True))    # the person sees it, if not asked about it
        if agent.dry_run:
            return outcome_result(RunOutcome(dry, None), dry_run_only=True)
        approved = None
        if agent.plan_approver is not None and not dry.refused:
            try:
                approved = bool(agent.plan_approver(dry))
            except Exception:                                      # noqa: BLE001  (a broken prompt is a no)
                approved = False
        mark = journal_mark(agent)
        outcome = execute(harness, dry, approved=approved, session=session, context=ctx.context if ctx else "",
                          steps_left=max(0, agent.budget.max_steps - state.steps))
        state.steps += outcome.steps_run
        agent.record_plan(dry, outcome, session)
        state.digests, state.just = (set(), dry.digest) if moved(agent, harness, outcome, mark) else (state.digests, "")
        return outcome_result(outcome)

    return Tool("plan", "Propose steps: tool calls with exact arguments. They are shown to the person before any runs, "
                "then run in order through the same permissions, stopping at the first that fails.",
                PLAN_SCHEMA, run, permission="allow", trust="trusted", network=False, consequential=False,
                origin="agent")
