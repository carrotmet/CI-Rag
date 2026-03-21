"""
Orchestrator V4 - Zone Transition Validator

V4 Architecture:
- Simplified responsibilities:
  1. Validate if transition criteria are met
  2. Route to target zone or return to source with strategy upgrade flag
- Does NOT generate guides (zones do this internally)
- Does NOT make complex decisions

Flow:
1. Zone (A/B/D) executes one round → requests transition
2. Orchestrator validates CI against target zone criteria
3. If valid → route to target
4. If invalid → return to source, trigger strategy upgrade
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import time
import uuid


class Zone(Enum):
    """ABCD Four Zones"""
    A = "A"  # C=1, I=1: Complex + Well-covered
    B = "B"  # C=1, I=0: Complex + Under-covered
    C = "C"  # C=0, I=1: Simple + Well-covered (Brain/Exit)
    D = "D"  # C=0, I=0: Simple + Under-covered
    
    @property
    def is_optimal(self) -> bool:
        """Check if this is an optimal zone (A or C)"""
        return self in (Zone.A, Zone.C)
    
    @classmethod
    def from_string(cls, zone_str: str) -> 'Zone':
        """Create Zone from string"""
        return cls(zone_str.upper())


@dataclass
class CIState:
    """CI State snapshot (V4)"""
    C: float  # Complexity (0-1 continuous)
    I: float  # Information sufficiency (0-1 continuous)
    sigma_c: float = 0.7  # Confidence in C
    sigma_i: float = 0.7  # Confidence in I
    query: str = ""
    timestamp: float = field(default_factory=time.time)
    
    @property
    def zone(self) -> Zone:
        """Map to discrete zone"""
        C_d = 1 if self.C >= 0.5 else 0
        I_d = 1 if self.I >= 0.5 else 0
        zone_map = {(0, 0): Zone.D, (0, 1): Zone.C, (1, 0): Zone.B, (1, 1): Zone.A}
        return zone_map.get((C_d, I_d), Zone.B)
    
    @property
    def sigma_joint(self) -> float:
        """Conservative joint confidence"""
        return min(self.sigma_c, self.sigma_i)
    
    def to_dict(self) -> Dict:
        return {
            'C': self.C,
            'I': self.I,
            'sigma_c': self.sigma_c,
            'sigma_i': self.sigma_i,
            'sigma_joint': self.sigma_joint,
            'zone': self.zone.value,
            'query': self.query,
            'timestamp': self.timestamp
        }


@dataclass
class TransitionResult:
    """Result of a zone transition request"""
    success: bool  # Whether transition was approved
    action: str  # 'transition_to_c', 'return_to_source', 'force_transition'
    source_zone: Zone
    target_zone: Optional[Zone]
    query: str
    ci_state: CIState
    trigger_strategy_upgrade: bool = False
    force_transition: bool = False  # After max attempts
    message: str = ""
    metadata: Dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class OrchestratorGuide:
    """Guide passed between zones (public resource)"""
    missing_info: List[str] = field(default_factory=list)
    decomposable: bool = False
    recommended: List[str] = field(default_factory=list)
    sub_problem_hints: List[str] = field(default_factory=list)
    confidence: float = 0.7
    validates_classification: bool = True
    source: str = "unknown"
    meta: Dict = field(default_factory=dict)


class OrchestratorV4:
    """
    V4 Orchestrator - Simplified Zone Transition Validator
    
    Responsibilities:
    1. Validate transition criteria
    2. Route to target zone or return to source
    
    NOT responsible for:
    - Guide generation (zones do this internally)
    - Strategy selection (zones use StrategyManager)
    - Direct execution (zones are autonomous)
    """
    
    # Transition thresholds
    I_THRESHOLD_C = 0.7  # Information threshold for Zone C
    C_THRESHOLD_SIMPLE = 0.5  # Complexity threshold for simple
    
    def __init__(self, zone_handlers: Dict[str, Any] = None):
        """
        Args:
            zone_handlers: Dict mapping zone names to handler instances
        """
        self.zone_handlers = zone_handlers or {}
        self.transition_history: List[Dict] = []
        self.max_attempts = 3  # Max attempts before force transition
        
    def request_transition(self, query: str, ci_state: Dict, 
                          source_zone: str, attempt_count: int = 1) -> TransitionResult:
        """
        Main entry: Zone requests transition after executing one round.
        
        V4 Logic:
        1. Determine target zone based on current CI
        2. Validate if transition criteria are met
        3. If valid → approve transition
        4. If invalid → return to source, trigger strategy upgrade
        
        Args:
            query: The query being processed
            ci_state: Current CI state dict with C, I, sigma_c, sigma_i
            source_zone: Source zone (A/B/C/D)
            attempt_count: Number of attempts from this zone
            
        Returns:
            TransitionResult
        """
        source = Zone.from_string(source_zone)
        ci = CIState(
            C=ci_state.get('C_continuous', ci_state.get('C', 0)),
            I=ci_state.get('I_continuous', ci_state.get('I', 0)),
            sigma_c=ci_state.get('sigma_c', 0.7),
            sigma_i=ci_state.get('sigma_i', 0.7),
            query=query
        )
        
        # Determine target zone
        target = self._determine_target_zone(source, ci)
        
        # Validate transition
        is_valid = self._validate_transition(ci, target)
        
        # Check if we should force transition after max attempts
        should_force = attempt_count >= self.max_attempts
        
        # Record transition attempt
        self._record_transition(query, source, target, ci, is_valid, attempt_count)
        
        if is_valid:
            # Transition approved
            return TransitionResult(
                success=True,
                action='transition_to_c' if target == Zone.C else 'transition',
                source_zone=source,
                target_zone=target,
                query=query,
                ci_state=ci,
                trigger_strategy_upgrade=False,
                message=f"Transition approved: {source.value} → {target.value}"
            )
        elif should_force:
            # Force transition after max attempts (with low confidence flag)
            return TransitionResult(
                success=True,
                action='force_transition',
                source_zone=source,
                target_zone=Zone.C,  # Force to C as exit
                query=query,
                ci_state=ci,
                trigger_strategy_upgrade=False,
                force_transition=True,
                message=f"Force transition after {attempt_count} attempts"
            )
        else:
            # Transition rejected, return to source
            return TransitionResult(
                success=False,
                action='return_to_source',
                source_zone=source,
                target_zone=None,
                query=query,
                ci_state=ci,
                trigger_strategy_upgrade=True,
                message=f"Transition rejected: CI C={ci.C}, I={ci.I} doesn't meet {target.value} criteria"
            )
    
    def _determine_target_zone(self, source: Zone, ci: CIState) -> Zone:
        """
        Determine target zone based on source and current CI.
        
        V4 Current:
        - All zones (A, B, D) → Zone C (exit)
        - Zone C stays in C (final output)
        
        V5 Future:
        - Zone B may → Zone A (if C=1, I=1) or Zone D (if C=0, I=0)
        """
        if source == Zone.C:
            return Zone.C  # Already at exit
        
        # Current V4: all zones target C
        # Check if we meet Zone C criteria
        if ci.C < self.C_THRESHOLD_SIMPLE and ci.I >= self.I_THRESHOLD_C:
            return Zone.C
        
        # Future V5: B zone can route to A or D
        # if source == Zone.B:
        #     if ci.C >= 0.5 and ci.I >= 0.7:
        #         return Zone.A  # C1I1
        #     elif ci.C < 0.5 and ci.I < 0.7:
        #         return Zone.D  # C0I0
        
        # Default: stay in source or go to C
        return Zone.C
    
    def _validate_transition(self, ci: CIState, target: Zone) -> bool:
        """
        Validate if current CI meets target zone criteria.
        
        Zone C criteria: C=0 (simple) AND I>=0.7 (well-covered)
        Zone A criteria: C=1 (complex) AND I>=0.7 (well-covered)
        """
        if target == Zone.C:
            # C zone: must be simple and have sufficient info
            return ci.C < self.C_THRESHOLD_SIMPLE and ci.I >= self.I_THRESHOLD_C
        
        elif target == Zone.A:
            # A zone: must be complex and have sufficient info
            return ci.C >= self.C_THRESHOLD_SIMPLE and ci.I >= self.I_THRESHOLD_C
        
        elif target == Zone.D:
            # D zone: simple but insufficient info
            return ci.C < self.C_THRESHOLD_SIMPLE and ci.I < self.I_THRESHOLD_C
        
        elif target == Zone.B:
            # B zone: complex but insufficient info
            return ci.C >= self.C_THRESHOLD_SIMPLE and ci.I < self.I_THRESHOLD_C
        
        return False
    
    def _record_transition(self, query: str, source: Zone, target: Zone,
                          ci: CIState, success: bool, attempt: int):
        """Record transition attempt for analysis"""
        self.transition_history.append({
            'query': query[:100],  # Truncate for storage
            'source': source.value,
            'target': target.value,
            'ci_C': ci.C,
            'ci_I': ci.I,
            'success': success,
            'attempt': attempt,
            'timestamp': time.time()
        })
    
    def process_zone_result(self, zone_result: Any, 
                           source_zone: str) -> TransitionResult:
        """
        Process result from a zone handler and determine next action.
        
        This is a convenience method that extracts CI from zone result.
        
        Args:
            zone_result: ZoneResult from zone handler
            source_zone: Source zone name
            
        Returns:
            TransitionResult
        """
        query = zone_result.query
        ci_state = zone_result.ci_state
        attempt = zone_result.round_number
        
        return self.request_transition(query, ci_state, source_zone, attempt)
    
    def get_zone_handler(self, zone: Zone):
        """Get handler for a zone"""
        return self.zone_handlers.get(zone.value)
    
    def get_statistics(self) -> Dict:
        """Get transition statistics"""
        if not self.transition_history:
            return {'total': 0}
        
        total = len(self.transition_history)
        successful = sum(1 for t in self.transition_history if t['success'])
        forced = sum(1 for t in self.transition_history if t.get('force_transition'))
        
        return {
            'total': total,
            'successful': successful,
            'failed': total - successful,
            'forced': forced,
            'success_rate': successful / total if total > 0 else 0
        }