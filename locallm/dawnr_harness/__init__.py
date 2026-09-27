"""dawnr's harness: tools, hooks, skills, MCP and the internet around the model (DAWNR-HARNESS.md).

Standard-library Python 3.10+; offline unless the operator's configuration
says otherwise. Imports here are light: the web, skills and MCP modules load
only when a configuration uses them.
"""
from .runtime import DEFAULT_HOOKS, Harness, StopResult, build_harness  # noqa: F401
from .tools import (CallContext, CallError, Policy, Registry, Session, Tool, ToolResult, format_call,  # noqa: F401
                    parse_call, validate)
