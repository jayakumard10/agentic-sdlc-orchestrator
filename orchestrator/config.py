"""Central runtime configuration read from environment variables.

Nodes take the workspace path as an explicit parameter (bound via functools.partial
when registered in graph.py) rather than importing this module's constant directly,
so tests can inject a scratch directory instead of touching the real shared volume.
This module is the one place that resolves the default from the environment.
"""

from __future__ import annotations

import os
from pathlib import Path

TARGET_APP_WORKSPACE = Path(os.environ.get("TARGET_APP_WORKSPACE", "/shared/target_app"))
ORCHESTRATOR_MODE = os.environ.get("ORCHESTRATOR_MODE", "replay")
