"""dawnr's agent: inspecting, editing and testing repositories through the harness (DAWNR-AGENT.md).

Files inside operator-configured roots (list, read, search; write, edit and
undo in writable roots), commands from an operator allowlist (denied by
default), the process list, and a planning loop whose plans are shown in a dry
run and approved as a whole before anything runs. Every step goes through the
harness's policy, hooks and audit log (dawnr_harness); nothing here can change
a permission or the configuration. Standard-library Python 3.10+.
"""
from .config import Agent, AgentConfigError, build_agent, register_agent  # noqa: F401
from .loop import AgentLoop, Budget, Finish, LoopResult, ModelPlanner, ScriptedPlanner  # noqa: F401
from .plan import DryRun, Plan, PlanError, Step, execute, preview_plan  # noqa: F401
