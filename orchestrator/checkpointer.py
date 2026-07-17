"""Checkpointer construction: a single source of truth for the msgpack serde config.

`GraphState` nests several custom Pydantic submodels (CodebaseImpact, CoderOutput,
etc.). Without an explicit allowlist, LangGraph's checkpoint serializer falls back to
an "unregistered type" path it warns will be blocked in a future version. Building
the allowlist here - by discovering every BaseModel defined in state.py - keeps it
self-maintaining as state.py grows, and keeps MemorySaver (tests) and PostgresSaver
(production) configured identically instead of drifting apart.
"""

from __future__ import annotations

import inspect

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pydantic import BaseModel

import state as state_module


def _discover_state_model_allowlist() -> list[tuple[str, str]]:
    allowlist: list[tuple[str, str]] = []
    for name, obj in inspect.getmembers(state_module, inspect.isclass):
        if issubclass(obj, BaseModel) and obj.__module__ == state_module.__name__:
            allowlist.append((state_module.__name__, name))
    return allowlist


def build_serde() -> JsonPlusSerializer:
    return JsonPlusSerializer(allowed_msgpack_modules=_discover_state_model_allowlist())


def build_memory_checkpointer() -> MemorySaver:
    """In-memory checkpointer for unit/smoke tests only.

    The running orchestrator always uses PostgresSaver (see build_postgres_checkpointer,
    added in Phase 3) so a pending approval gate survives a container restart.
    """
    return MemorySaver(serde=build_serde())
