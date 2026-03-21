"""
Base zone handler for V4 architecture.

Zone responsibilities (V4):
1. Check/Generate Guide on entry
2. Execute one round of processing
3. Request orchestrator for zone transition
4. Handle strategy upgrade on rejection
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import time


class ZoneType(Enum):
    """ABCD Four Zones"""
    A = "A"  # C=1, I=1: Complex + Well-covered → Decomposition
    B = "B"  # C=1, I=0: Complex + Under-covered → Hybrid
    C = "C"  # C=0, I=1: Simple + Well-covered → Brain/Exit
    D = "D"  # C=0, I=0: Simple + Under-covered → Information retrieval
    
    @property
    def is_optimal(self) -> bool:
        """Check if this is an optimal zone (A or C)"""
        return self in (ZoneType.A, ZoneType.C)


@dataclass
class ZoneResult:
    """Result from a zone execution round"""
    success: bool
    zone: ZoneType
    query: str
    ci_state: Dict[str, Any]  # C, I, sigma_c, sigma_i, etc.
    output: Optional[str] = None
    sub_problems: List[Dict] = field(default_factory=list)
    retrieved_info: List[Dict] = field(default_factory=list)
    strategy_used: str = ""
    round_number: int = 1
    transition_requested: bool = False
    transition_approved: bool = False
    target_zone: Optional[ZoneType] = None
    metadata: Dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class ZoneHandler(ABC):
    """
    Base class for zone handlers (V4).
    
    Architecture:
    - Zones are autonomous: execute one round internally
    - After execution, request orchestrator for transition
    - Handle strategy upgrade if rejected by orchestrator
    """
    
    def __init__(self, zone_type: ZoneType, guide_generator=None, strategy_manager=None):
        self.zone_type = zone_type
        self.guide_generator = guide_generator
        self.strategy_manager = strategy_manager
        self.max_rounds = 3  # Max internal rounds before forced transition
        
    @abstractmethod
    def execute_round(self, query: str, guide: Optional[Dict], context: Dict) -> ZoneResult:
        """
        Execute one round of zone-specific processing.
        
        Args:
            query: The query to process
            guide: Orchestrator guide (may be None)
            context: Additional context (round number, history, etc.)
            
        Returns:
            ZoneResult with processing outcome
        """
        pass
    
    def enter(self, query: str, ci_state: Dict, guide: Optional[Dict] = None, 
              context: Dict = None) -> ZoneResult:
        """
        Main entry point for zone processing (V4 flow).
        
        Flow:
        1. Check/Generate Guide
        2. Execute one round
        3. Return result (orchestrator will handle transition)
        
        Args:
            query: The query to process
            ci_state: Current CI state dict with C, I, sigma_c, sigma_i
            guide: Optional orchestrator guide
            context: Additional processing context
            
        Returns:
            ZoneResult
        """
        context = context or {}
        round_number = context.get('round_number', 1)
        
        # Step 1: Check/Generate Guide
        if guide is None and self.guide_generator:
            zone_str = self.zone_type.value
            guide = self.guide_generator.generate(
                zone=zone_str,
                query=query,
                ci_state=ci_state
            )
        
        # Step 2: Execute one round
        result = self.execute_round(query, guide, context)
        result.round_number = round_number
        
        # Step 3: Mark that we're requesting transition
        result.transition_requested = True
        
        return result
    
    def handle_rejection(self, result: ZoneResult, rejection_reason: str) -> ZoneResult:
        """
        Handle transition rejection from orchestrator.
        Trigger strategy upgrade and return updated result.
        
        Args:
            result: Previous zone result
            rejection_reason: Why transition was rejected
            
        Returns:
            Updated ZoneResult with new strategy
        """
        if self.strategy_manager:
            new_strategy = self.strategy_manager.upgrade_strategy(
                self.zone_type,
                result.strategy_used,
                rejection_reason
            )
            result.strategy_used = new_strategy
            result.metadata['strategy_upgraded'] = True
            result.metadata['upgrade_reason'] = rejection_reason
        
        result.transition_approved = False
        return result
    
    def can_self_transition(self, ci_state: Dict) -> bool:
        """
        Check if zone can handle internal re-decomposition.
        For example, if a sub-problem still has C=1, zone A can re-decompose
        without involving orchestrator.
        
        Args:
            ci_state: Current CI state
            
        Returns:
            True if can handle internally
        """
        # Default: zones don't self-transition, they ask orchestrator
        return False
    
    def get_zone_type_from_ci(self, C: float, I: float) -> ZoneType:
        """
        Map CI values to zone type.
        
        Args:
            C: Complexity (0-1 continuous)
            I: Information sufficiency (0-1 continuous)
            
        Returns:
            ZoneType
        """
        C_d = 1 if C >= 0.5 else 0
        I_d = 1 if I >= 0.5 else 0
        zone_map = {
            (0, 0): ZoneType.D,
            (0, 1): ZoneType.C,
            (1, 0): ZoneType.B,
            (1, 1): ZoneType.A
        }
        return zone_map.get((C_d, I_d), ZoneType.B)