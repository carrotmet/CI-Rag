"""
Strategy Manager for V4 architecture.

Manages strategy upgrades when zones are rejected by orchestrator.
Each zone has its own strategy ladder.
"""

from typing import Dict, List, Optional
from enum import Enum


class StrategyType(Enum):
    """Strategy types for zone processing"""
    # Zone D strategies (information retrieval)
    RETRIEVE_VECTOR = "retrieve_vector"
    RETRIEVE_KEYWORD = "retrieve_keyword"
    RETRIEVE_HYBRID = "retrieve_hybrid"
    RETRIEVE_EXPANDED = "retrieve_expanded"
    RETRIEVE_STRUCTURED = "retrieve_structured"
    
    # Zone A strategies (decomposition)
    DECOMPOSE_BY_ASPECT = "decompose_by_aspect"
    DECOMPOSE_BY_STEP = "decompose_by_step"
    DECOMPOSE_BY_COMPONENT = "decompose_by_component"
    DECOMPOSE_FINE_GRAINED = "decompose_fine_grained"
    
    # Zone B strategies (hybrid)
    RETRIEVE_FIRST = "retrieve_first"
    DECOMPOSE_FIRST = "decompose_first"
    PARALLEL_RETRIEVE_DECOMPOSE = "parallel_retrieve_decompose"
    
    # Zone C strategies (reasoning)
    DIRECT_ANSWER = "direct_answer"
    CHAIN_OF_THOUGHT = "chain_of_thought"
    FEW_SHOT = "few_shot"
    WITH_MEMORY = "with_memory"
    WITH_TOOLS = "with_tools"
    AGENT_BASED = "agent_based"


class StrategyManager:
    """
    Manages strategy upgrades for zones.
    
    V4 Architecture:
    - Each zone has a strategy ladder
    - When orchestrator rejects transition, zone upgrades strategy
    - After max attempts, force transition with low-confidence flag
    """
    
    def __init__(self):
        # Strategy ladders for each zone (in order of preference)
        self.zone_strategies = {
            'A': [
                'decompose_by_aspect',
                'decompose_by_step', 
                'decompose_by_component',
                'decompose_fine_grained'
            ],
            'B': [
                'retrieve_first',
                'decompose_first',
                'parallel_retrieve_decompose'
            ],
            'C': [
                'direct_answer',
                'chain_of_thought',
                'few_shot',
                'with_memory',
                'with_tools',
                'agent_based'
            ],
            'D': [
                'retrieve_vector',
                'retrieve_keyword',
                'retrieve_hybrid',
                'retrieve_expanded',
                'retrieve_structured'
            ]
        }
        
        # Max attempts before forced transition
        self.max_attempts = 3
    
    def get_initial_strategy(self, zone: str) -> str:
        """
        Get initial strategy for a zone.
        
        Args:
            zone: Zone type (A/B/C/D)
            
        Returns:
            Strategy name
        """
        strategies = self.zone_strategies.get(zone, ['default'])
        return strategies[0] if strategies else 'default'
    
    def upgrade_strategy(self, zone: str, current_strategy: str, 
                        rejection_reason: str) -> str:
        """
        Get next strategy when current one is rejected.
        
        Args:
            zone: Zone type (A/B/C/D)
            current_strategy: Current strategy name
            rejection_reason: Why transition was rejected
            
        Returns:
            New strategy name
        """
        strategies = self.zone_strategies.get(zone, [])
        
        if not strategies:
            return current_strategy
        
        try:
            current_idx = strategies.index(current_strategy)
            next_idx = min(current_idx + 1, len(strategies) - 1)
            return strategies[next_idx]
        except ValueError:
            # Current strategy not in list, return first
            return strategies[0]
    
    def should_force_transition(self, zone: str, attempt_count: int) -> bool:
        """
        Check if should force transition after multiple failures.
        
        Args:
            zone: Zone type
            attempt_count: Number of attempts so far
            
        Returns:
            True if should force transition
        """
        return attempt_count >= self.max_attempts
    
    def get_strategy_description(self, strategy: str) -> str:
        """Get human-readable description of a strategy"""
        descriptions = {
            # Zone D
            'retrieve_vector': 'Vector similarity retrieval',
            'retrieve_keyword': 'Keyword-based retrieval',
            'retrieve_hybrid': 'Hybrid vector + keyword retrieval',
            'retrieve_expanded': 'Expanded query retrieval',
            'retrieve_structured': 'Structured data retrieval',
            # Zone A
            'decompose_by_aspect': 'Decompose by different aspects',
            'decompose_by_step': 'Decompose by execution steps',
            'decompose_by_component': 'Decompose by components',
            'decompose_fine_grained': 'Fine-grained decomposition',
            # Zone B
            'retrieve_first': 'Retrieve information first',
            'decompose_first': 'Decompose problem first',
            'parallel_retrieve_decompose': 'Parallel retrieve and decompose',
            # Zone C
            'direct_answer': 'Direct reasoning answer',
            'chain_of_thought': 'Chain-of-thought reasoning',
            'few_shot': 'Few-shot prompting',
            'with_memory': 'With memory context',
            'with_tools': 'With tool calls',
            'agent_based': 'Agent-based reasoning'
        }
        return descriptions.get(strategy, strategy)