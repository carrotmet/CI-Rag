"""Level 2: LLM Semantic Refinement with litellm.

Provides LLM-based arbitration for queries escaping Level 0 and Level 1.
"""

from .llm_client import LLMClient, LLMResponse, LLMConfig, create_llm_client
from .prompt_builder import (
    PromptBuilder,
    CIArbitrationContext,
    Level0Context,
    Level1Context,
    build_level2_context
)
from .response_parser import ResponseParser, ParsedResponse, parse_llm_response
from .dual_probe import (
    DualProbeValidator,
    DualProbeResult,
    ConfidenceCalibrator
)
from .level2_router import Level2Router, Level2Result, arbitrate_with_llm

__all__ = [
    # LLM Client
    "LLMClient",
    "LLMResponse",
    "LLMConfig",
    "create_llm_client",
    
    # Prompt Building
    "PromptBuilder",
    "CIArbitrationContext",
    "Level0Context",
    "Level1Context",
    "build_level2_context",
    
    # Response Parsing
    "ResponseParser",
    "ParsedResponse",
    "parse_llm_response",
    
    # Dual Probe
    "DualProbeValidator",
    "DualProbeResult",
    "ConfidenceCalibrator",
    
    # Router
    "Level2Router",
    "Level2Result",
    "arbitrate_with_llm",
]
