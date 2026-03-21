"""
Zone C Handler - Brain/Exit Zone (C=0, I=1)

V4 Architecture:
- System brain and unified exit point
- Three modes: direct, subproblem queue, assembled
- Supports multi-level reasoning strategy upgrade
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from .base import ZoneHandler, ZoneResult, ZoneType


class ReasoningStrategy(Enum):
    """C Zone reasoning strategies (Level 1-5)"""
    # Level 1: Direct
    DIRECT = "direct"
    
    # Level 2: Enhanced prompting
    CHAIN_OF_THOUGHT = "chain_of_thought"
    FEW_SHOT = "few_shot"
    
    # Level 3: With context
    WITH_MEMORY = "with_memory"
    
    # Level 4: With tools
    WITH_TOOLS = "with_tools"
    
    # Level 5: Agent-based
    AGENT_BASED = "agent_based"


@dataclass
class ZoneCRequest:
    """Request for Zone C processing"""
    request_type: str  # 'direct', 'subproblem', 'assembled'
    query: str
    parent_id: Optional[str] = None
    subproblem_id: Optional[str] = None
    context: Dict = field(default_factory=dict)
    strategy: ReasoningStrategy = ReasoningStrategy.DIRECT


class ZoneCHandler(ZoneHandler):
    """
    Zone C: Simple + Well-covered (C=0, I=1)
    
    System brain and unified exit point.
    
    Modes:
    1. Direct: Parent query direct reasoning output
    2. Subproblem: Process sub-problem, put in queue, wait for assembly
    3. Assembled: B-zone results comprehensive reasoning output
    
    Strategy Levels:
    - L1: Direct reasoning
    - L2: One-shot / CoT templates
    - L3: With memory context
    - L4: With tool calls
    - L5: Agent-based reasoning
    """
    
    def __init__(self, guide_generator=None, strategy_manager=None,
                 llm_client=None, subproblem_queue=None,
                 memory_store=None, tool_registry=None):
        super().__init__(ZoneType.C, guide_generator, strategy_manager)
        self.llm_client = llm_client
        self.subproblem_queue = subproblem_queue
        self.memory_store = memory_store
        self.tool_registry = tool_registry
        
        # Strategy level mapping
        self.strategy_ladder = [
            ReasoningStrategy.DIRECT,
            ReasoningStrategy.CHAIN_OF_THOUGHT,
            ReasoningStrategy.FEW_SHOT,
            ReasoningStrategy.WITH_MEMORY,
            ReasoningStrategy.WITH_TOOLS,
            ReasoningStrategy.AGENT_BASED
        ]
        
    def execute_round(self, query: str, guide: Optional[Dict], context: Dict) -> ZoneResult:
        """
        Zone C doesn't use execute_round in the same way.
        It provides different processing modes.
        """
        raise NotImplementedError(
            "Zone C uses process_direct/process_subproblem/process_assembled instead"
        )
    
    def process_direct(self, query: str, strategy: ReasoningStrategy = None,
                      context: Dict = None) -> ZoneResult:
        """
        Mode 1: Direct reasoning for parent query.
        
        Args:
            query: Original query
            strategy: Reasoning strategy to use
            context: Additional context
            
        Returns:
            ZoneResult with final answer
        """
        context = context or {}
        strategy = strategy or ReasoningStrategy.CHAIN_OF_THOUGHT
        
        # Select and execute strategy
        answer = self._reason_with_strategy(query, strategy, context)
        
        return ZoneResult(
            success=True,
            zone=self.zone_type,
            query=query,
            ci_state={
                'C': 0,
                'I': 1,
                'C_continuous': 0.1,
                'I_continuous': 0.95,
                'sigma_c': 0.9,
                'sigma_i': 0.9,
                'sigma_joint': 0.9
            },
            output=answer,
            strategy_used=strategy.value,
            metadata={
                'mode': 'direct',
                'strategy_level': self._get_strategy_level(strategy)
            }
        )
    
    def process_subproblem(self, parent_id: str, subproblem_id: str,
                          query: str, strategy: ReasoningStrategy = None,
                          context: Dict = None) -> ZoneResult:
        """
        Mode 2: Process sub-problem and put in queue.
        
        Args:
            parent_id: Parent problem ID
            subproblem_id: Sub-problem ID
            query: Sub-problem query
            strategy: Reasoning strategy
            context: Additional context
            
        Returns:
            ZoneResult - if complete, includes assembled output
        """
        context = context or {}
        strategy = strategy or ReasoningStrategy.DIRECT
        
        # 1. Reason about this sub-problem
        answer = self._reason_with_strategy(query, strategy, context)
        
        # 2. Put in queue if available
        if self.subproblem_queue:
            is_complete = self.subproblem_queue.put_simple(
                parent_id=parent_id,
                subproblem_id=subproblem_id,
                query=query,
                answer=answer,
                ci_state={'C': 0, 'I': 1}
            )
            
            # 3. Check if all sub-problems complete
            if is_complete:
                all_results = self.subproblem_queue.get_all(parent_id)
                assembled = self._assemble_output(parent_id, all_results)
                
                return ZoneResult(
                    success=True,
                    zone=self.zone_type,
                    query=query,  # Original parent query should be in context
                    ci_state={
                        'C': 0,
                        'I': 1,
                        'C_continuous': 0.1,
                        'I_continuous': 0.95,
                        'sigma_c': 0.9,
                        'sigma_i': 0.95,
                        'sigma_joint': 0.9
                    },
                    output=assembled,
                    strategy_used=strategy.value,
                    metadata={
                        'mode': 'subproblem_assembled',
                        'parent_id': parent_id,
                        'subproblem_count': len(all_results)
                    }
                )
            else:
                # Not complete yet
                progress = self.subproblem_queue.get_progress(parent_id)
                return ZoneResult(
                    success=True,
                    zone=self.zone_type,
                    query=query,
                    ci_state={'C': 0, 'I': 1, 'C_continuous': 0.1, 'I_continuous': 0.95, 
                             'sigma_c': 0.9, 'sigma_i': 0.95, 'sigma_joint': 0.9},
                    output=None,  # No final output yet
                    strategy_used=strategy.value,
                    metadata={
                        'mode': 'subproblem_waiting',
                        'parent_id': parent_id,
                        'subproblem_id': subproblem_id,
                        'progress': progress
                    }
                )
        else:
            # No queue available, just return the answer
            return ZoneResult(
                success=True,
                zone=self.zone_type,
                query=query,
                ci_state={'C': 0, 'I': 1, 'C_continuous': 0.1, 'I_continuous': 0.95,
                         'sigma_c': 0.9, 'sigma_i': 0.95, 'sigma_joint': 0.9},
                output=answer,
                strategy_used=strategy.value,
                metadata={'mode': 'subproblem_direct', 'subproblem_id': subproblem_id}
            )
    
    def process_assembled(self, query: str, sub_results: List[Dict],
                         retrieved_info: List[Dict] = None,
                         strategy: ReasoningStrategy = None) -> ZoneResult:
        """
        Mode 3: Comprehensive reasoning with B-zone results.
        
        Args:
            query: Original query
            sub_results: Sub-problem results from Zone B
            retrieved_info: Retrieved information from Zone B
            strategy: Reasoning strategy
            
        Returns:
            ZoneResult with final answer
        """
        strategy = strategy or ReasoningStrategy.CHAIN_OF_THOUGHT
        
        # Build comprehensive context
        context = {
            'sub_results': sub_results,
            'retrieved_info': retrieved_info or []
        }
        
        # Comprehensive reasoning
        answer = self._comprehensive_reason(query, context, strategy)
        
        return ZoneResult(
            success=True,
            zone=self.zone_type,
            query=query,
            ci_state={
                'C': 0,
                'I': 1,
                'C_continuous': 0.1,
                'I_continuous': 0.95,
                'sigma_c': 0.9,
                'sigma_i': 0.95,
                'sigma_joint': 0.9
            },
            output=answer,
            strategy_used=strategy.value,
            metadata={
                'mode': 'assembled',
                'subproblem_count': len(sub_results),
                'retrieval_count': len(retrieved_info) if retrieved_info else 0
            }
        )
    
    def select_strategy(self, query: str, complexity_hint: float = None) -> ReasoningStrategy:
        """
        Select appropriate reasoning strategy based on query complexity.
        
        Args:
            query: The query to assess
            complexity_hint: Optional complexity hint (0-1)
            
        Returns:
            Selected ReasoningStrategy
        """
        if complexity_hint is None:
            complexity_hint = self._estimate_complexity(query)
        
        if complexity_hint < 0.3:
            return ReasoningStrategy.DIRECT
        elif complexity_hint < 0.5:
            return ReasoningStrategy.CHAIN_OF_THOUGHT
        elif complexity_hint < 0.7:
            return ReasoningStrategy.FEW_SHOT
        elif complexity_hint < 0.8:
            return ReasoningStrategy.WITH_MEMORY
        elif complexity_hint < 0.9:
            return ReasoningStrategy.WITH_TOOLS
        else:
            return ReasoningStrategy.AGENT_BASED
    
    def _reason_with_strategy(self, query: str, strategy: ReasoningStrategy,
                             context: Dict) -> str:
        """Execute reasoning with selected strategy"""
        
        if strategy == ReasoningStrategy.DIRECT:
            return self._reason_direct(query, context)
        elif strategy == ReasoningStrategy.CHAIN_OF_THOUGHT:
            return self._reason_cot(query, context)
        elif strategy == ReasoningStrategy.FEW_SHOT:
            return self._reason_few_shot(query, context)
        elif strategy == ReasoningStrategy.WITH_MEMORY:
            return self._reason_with_memory(query, context)
        elif strategy == ReasoningStrategy.WITH_TOOLS:
            return self._reason_with_tools(query, context)
        else:  # AGENT_BASED
            return self._reason_agent_based(query, context)
    
    def _reason_direct(self, query: str, context: Dict) -> str:
        """Level 1: Direct reasoning"""
        if self.llm_client:
            prompt = f"Question: {query}\n\nAnswer directly:"
            return self.llm_client.complete(prompt)
        return f"[Direct answer for: {query}]"
    
    def _reason_cot(self, query: str, context: Dict) -> str:
        """Level 2: Chain-of-thought reasoning"""
        if self.llm_client:
            prompt = f"Question: {query}\n\nLet's think step by step:\n"
            return self.llm_client.complete(prompt)
        return f"[CoT reasoning for: {query}]"
    
    def _reason_few_shot(self, query: str, context: Dict) -> str:
        """Level 2: Few-shot prompting"""
        # Would include examples in practice
        return self._reason_cot(query, context)
    
    def _reason_with_memory(self, query: str, context: Dict) -> str:
        """Level 3: With memory context"""
        memory = ""
        if self.memory_store:
            memory = self.memory_store.retrieve(query)
        
        if self.llm_client:
            prompt = f"Context: {memory}\n\nQuestion: {query}\n\nAnswer:"
            return self.llm_client.complete(prompt)
        return f"[Memory-enhanced answer for: {query}]"
    
    def _reason_with_tools(self, query: str, context: Dict) -> str:
        """Level 4: With tool calls"""
        # Tool integration placeholder
        return self._reason_cot(query, context)
    
    def _reason_agent_based(self, query: str, context: Dict) -> str:
        """Level 5: Agent-based reasoning"""
        # Multi-agent coordination placeholder
        return self._reason_cot(query, context)
    
    def _comprehensive_reason(self, query: str, context: Dict,
                             strategy: ReasoningStrategy) -> str:
        """Comprehensive reasoning with sub-results and retrieved info"""
        sub_results = context.get('sub_results', [])
        retrieved = context.get('retrieved_info', [])
        
        # Build synthesis prompt
        parts = ["Based on the following information:"]
        
        if sub_results:
            parts.append("\nSub-problem analyses:")
            for r in sub_results:
                parts.append(f"- {r.get('query', 'Unknown')}: {r.get('answer', 'No answer')}")
        
        if retrieved:
            parts.append("\nRetrieved information:")
            for doc in retrieved:
                parts.append(f"- {doc.get('content', 'N/A')}")
        
        parts.append(f"\nSynthesize a comprehensive answer to: {query}")
        
        synthesis_prompt = "\n".join(parts)
        
        if self.llm_client:
            return self.llm_client.complete(synthesis_prompt)
        
        return f"[Synthesized answer for: {query}]"
    
    def _assemble_output(self, parent_id: str, results: List) -> str:
        """Assemble all sub-problem results into final output"""
        parts = [f"Answer to complex question (assembled from {len(results)} sub-problems):\n"]
        
        for r in results:
            parts.append(f"\n## {r.query}\n{r.answer}")
        
        # Add synthesis
        parts.append("\n\n## Synthesis\n")
        
        if self.llm_client:
            synthesis_prompt = "Synthesize these answers:\n" + "\n".join(
                f"- {r.query}: {r.answer}" for r in results
            )
            parts.append(self.llm_client.complete(synthesis_prompt))
        else:
            parts.append("[Synthesis of above sub-problem answers]")
        
        return "\n".join(parts)
    
    def _estimate_complexity(self, query: str) -> float:
        """Estimate query complexity (0-1)"""
        # Simple heuristic based on length and keywords
        length_factor = min(len(query) / 200, 1.0)
        
        complex_keywords = ['分析', '比较', '评估', '为什么', '如何', '影响', '关系']
        keyword_factor = sum(1 for k in complex_keywords if k in query) / len(complex_keywords)
        
        return (length_factor * 0.5) + (keyword_factor * 0.5)
    
    def _get_strategy_level(self, strategy: ReasoningStrategy) -> int:
        """Get level (1-5) for a strategy"""
        levels = {
            ReasoningStrategy.DIRECT: 1,
            ReasoningStrategy.CHAIN_OF_THOUGHT: 2,
            ReasoningStrategy.FEW_SHOT: 2,
            ReasoningStrategy.WITH_MEMORY: 3,
            ReasoningStrategy.WITH_TOOLS: 4,
            ReasoningStrategy.AGENT_BASED: 5
        }
        return levels.get(strategy, 1)