# backend/app/services/world_model/__init__.py
"""World Model — a continuously-updated representation of the user's environment.

The WorldGraph deduplicates observations into typed entities and relations
with provenance; the WorldIngestor translates raw tool/calendar/email/device
events into graph mutations; the SituationEngine derives 'what is happening'
from the graph plus source tables.
"""

from .actions import ActionPlan, SituationActionPlanner
from .evolution import EvolutionEngine
from .graph import WorldGraph, canonical
from .ingest import WorldIngestor
from .memory_sync import MemorySyncService
from .situations import Situation, SituationEngine
from .simulator import Consequence, SimulationResult, WorldSimulator

__all__ = [
    "WorldGraph",
    "WorldIngestor",
    "MemorySyncService",
    "Situation",
    "SituationEngine",
    "ActionPlan",
    "SituationActionPlanner",
    "EvolutionEngine",
    "Consequence",
    "SimulationResult",
    "WorldSimulator",
    "canonical",
]
