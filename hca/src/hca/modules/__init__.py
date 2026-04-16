"""Authoritative runtime module entry points.

Experimental cognition stubs remain importable from their direct module paths,
but they are intentionally excluded from the public hca.modules export surface.
"""

from hca.modules.planner import Planner
from hca.modules.critic import Critic
from hca.modules.perception_text import TextPerception
from hca.modules.tool_reasoner import ToolReasoner

__all__ = [
    "Planner",
    "Critic",
    "TextPerception",
    "ToolReasoner",
]