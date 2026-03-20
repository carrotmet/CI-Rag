"""
Smart Orchestrator - Intelligent CI-based query routing with zone transition.

V1: Original implementation (backward compatible)
V2: Guide-based execution with Level 2 orchestrator_guide support
"""

# V1 (Original)
from .smart_orchestrator import (
    SmartOrchestrator,
    CIState,
    Zone,
    SubProblem,
    ReconstructionPlan,
    CITracker,
    ZoneTransitionEngine,
    QueryReconstructor,
)

# V2 (Guide-based)
from .smart_orchestrator_v2 import (
    SmartOrchestratorV2,
    ZoneTransitionEngineV2,
    OrchestratorGuide,
)

__all__ = [
    # V1
    "SmartOrchestrator",
    "CIState",
    "Zone",
    "SubProblem",
    "ReconstructionPlan",
    "CITracker",
    "ZoneTransitionEngine",
    "QueryReconstructor",
    # V2
    "SmartOrchestratorV2",
    "ZoneTransitionEngineV2",
    "OrchestratorGuide",
]
