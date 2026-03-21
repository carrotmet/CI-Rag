"""
CI-RAG-Router V4 Pipeline

Main integration layer for V4 architecture:
- Level 012 escape layer → Initial zone determination
- Zone handlers (A/B/D) → Autonomous execution
- Orchestrator V4 → Transition validation
- Zone C → Brain/Exit
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
import time
import uuid

from .orchestrator.orchestrator_v4 import OrchestratorV4, Zone, CIState, TransitionResult
from .zones import ZoneAHandler, ZoneBHandler, ZoneCHandler, ZoneDHandler, ZoneResult
from .common import GuideGenerator, StrategyManager, SubProblemQueue


@dataclass
class PipelineResult:
    """Final result from V4 pipeline"""
    query: str
    answer: str
    final_zone: str
    ci_state: Dict
    execution_path: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    latency_ms: float = 0.0


class CIRouterPipelineV4:
    """
    V4 Pipeline - Main entry point
    
    Architecture:
    1. Level 012 → Determine initial zone
    2. Zone (A/B/D) → Execute round, request transition
    3. Orchestrator → Validate, route or return
    4. Zone C → Final output
    """
    
    def __init__(self, 
                 l0_router=None,
                 l1_router=None, 
                 l2_router=None,
                 llm_client=None,
                 retriever=None):
        """
        Initialize V4 pipeline.
        
        Args:
            l0_router: Level 0 router (XGBoost)
            l1_router: Level 1 router (hybrid retrieval)
            l2_router: Level 2 router (LLM arbitration)
            llm_client: LLM client for reasoning
            retriever: Retrieval engine
        """
        # Level routers
        self.l0_router = l0_router
        self.l1_router = l1_router
        self.l2_router = l2_router
        
        # Common components
        self.guide_generator = GuideGenerator(l2_router)
        self.strategy_manager = StrategyManager()
        self.subproblem_queue = SubProblemQueue()
        
        # Zone handlers
        self.zone_handlers = {
            'A': ZoneAHandler(self.guide_generator, self.strategy_manager, llm_client, retriever),
            'B': ZoneBHandler(self.guide_generator, self.strategy_manager, retriever, llm_client),
            'C': ZoneCHandler(self.guide_generator, self.strategy_manager, llm_client, 
                            self.subproblem_queue),
            'D': ZoneDHandler(self.guide_generator, self.strategy_manager, retriever, llm_client)
        }
        
        # Orchestrator
        self.orchestrator = OrchestratorV4(self.zone_handlers)
        
        # Execution tracking
        self.max_total_rounds = 10  # Safety limit
        
    def process(self, query: str, context: Dict = None) -> PipelineResult:
        """
        Process a query through V4 pipeline.
        
        Flow:
        1. Level 012 → Initial zone
        2. Zone handler → Execute round
        3. Orchestrator → Validate transition
        4. Repeat until Zone C reached or max rounds
        
        Args:
            query: User query
            context: Optional context
            
        Returns:
            PipelineResult
        """
        start_time = time.time()
        context = context or {}
        execution_path = []
        
        # Step 1: Level 012 escape layer
        initial_zone, ci_state, guide = self._level012_routing(query)
        
        execution_path.append({
            'step': 'level012',
            'zone': initial_zone,
            'ci': ci_state,
            'guide_present': guide is not None
        })
        
        # If already in Zone C, process directly
        if initial_zone == 'C':
            result = self._process_zone_c_direct(query, ci_state)
            return PipelineResult(
                query=query,
                answer=result.output,
                final_zone='C',
                ci_state=result.ci_state,
                execution_path=execution_path,
                latency_ms=(time.time() - start_time) * 1000
            )
        
        # Step 2-4: Zone execution → Orchestrator loop
        current_zone = initial_zone
        current_guide = guide
        round_count = 0
        
        while round_count < self.max_total_rounds:
            round_count += 1
            
            # Execute one round in current zone
            zone_result = self._execute_zone_round(
                current_zone, query, ci_state, current_guide, round_count
            )
            
            # Build detailed execution record
            step_detail = {
                'step': f'zone_{current_zone}_round_{zone_result.round_number}',
                'zone': current_zone,
                'ci': zone_result.ci_state,
                'strategy': zone_result.strategy_used,
                'subproblems_count': len(zone_result.sub_problems),
                'retrieved_count': len(zone_result.retrieved_info)
            }
            
            # Add detailed retrieval info (top 3)
            if zone_result.retrieved_info:
                step_detail['retrieved_details'] = [
                    {
                        'id': doc.get('id', 'unknown'),
                        'score': doc.get('score', 0),
                        'content': doc.get('content', '')[:150] + '...' if len(doc.get('content', '')) > 150 else doc.get('content', '')
                    }
                    for doc in zone_result.retrieved_info[:3]
                ]
            
            # Add detailed sub-problems
            if zone_result.sub_problems:
                step_detail['subproblems_details'] = [
                    {
                        'id': sp.get('id', 'unknown'),
                        'query': sp.get('query', ''),
                        'is_simple': sp.get('is_simple', False)
                    }
                    for sp in zone_result.sub_problems
                ]
            
            # Add metadata explanations
            if zone_result.metadata:
                step_detail['explanation'] = self._build_step_explanation(
                    current_zone, zone_result
                )
            
            execution_path.append(step_detail)
            
            # Request orchestrator for transition
            transition = self.orchestrator.process_zone_result(zone_result, current_zone)
            
            execution_path.append({
                'step': 'orchestrator',
                'action': transition.action,
                'success': transition.success,
                'source': transition.source_zone.value,
                'target': transition.target_zone.value if transition.target_zone else None,
                'upgrade_triggered': transition.trigger_strategy_upgrade
            })
            
            if transition.success:
                # Transition approved or forced
                if transition.target_zone == Zone.C:
                    # Process in Zone C and exit
                    final_result = self._process_zone_c(
                        query, zone_result, transition
                    )
                    
                    execution_path.append({
                        'step': 'zone_c_output',
                        'zone': 'C',
                        'mode': final_result.metadata.get('mode', 'unknown')
                    })
                    
                    return PipelineResult(
                        query=query,
                        answer=final_result.output,
                        final_zone='C',
                        ci_state=final_result.ci_state,
                        execution_path=execution_path,
                        metadata={
                            'total_rounds': round_count,
                            'forced_transition': transition.force_transition
                        },
                        latency_ms=(time.time() - start_time) * 1000
                    )
                else:
                    # Transition to other zone (future V5)
                    current_zone = transition.target_zone.value
                    ci_state = transition.ci_state.to_dict()
                    current_guide = None
            else:
                # Transition rejected, return to source with strategy upgrade
                if transition.trigger_strategy_upgrade:
                    # Zone will handle strategy upgrade internally
                    ci_state = transition.ci_state.to_dict()
                    current_guide = None  # Will regenerate with new strategy
                else:
                    # Shouldn't happen, but handle gracefully
                    break
        
        # Max rounds reached, force output from Zone C
        return self._force_exit(query, ci_state, execution_path, start_time)
    
    def _level012_routing(self, query: str) -> tuple:
        """
        Level 012 escape layer - determine initial zone.
        
        Returns:
            (zone_name, ci_state_dict, guide_or_None)
        """
        # Try Level 0
        if self.l0_router:
            try:
                l0_result = self.l0_router.route_with_guide(query)
                sigma_joint = l0_result.get('sigma_joint', 0)
                
                if sigma_joint >= 0.7:
                    # High confidence, use L0 result
                    zone = l0_result.get('zone', 'C')
                    ci_state = {
                        'C': l0_result.get('C', 0),
                        'I': l0_result.get('I', 0),
                        'C_continuous': l0_result.get('C_continuous', 0),
                        'I_continuous': l0_result.get('I_continuous', 0),
                        'sigma_c': l0_result.get('sigma_c', 0.7),
                        'sigma_i': l0_result.get('sigma_i', 0.7)
                    }
                    guide = l0_result.get('orchestrator_guide')
                    return zone, ci_state, guide
            except Exception:
                pass
        
        # Try Level 1
        if self.l1_router and self.l0_router:
            try:
                l0_result = self.l0_router.route(query)
                l1_result = self.l1_router.verify_with_guide(query, l0_result)
                sigma_I = l1_result.get('sigma_I', 0)
                
                if sigma_I >= 0.7:
                    zone = l1_result.get('final_zone', 'C')
                    ci_state = {
                        'C': l1_result.get('C', 0),
                        'I': l1_result.get('I', 0),
                        'C_continuous': l0_result.get('C_continuous', 0),
                        'I_continuous': l1_result.get('I_mean', 0.5),
                        'sigma_c': l0_result.get('sigma_c', 0.6),
                        'sigma_i': sigma_I
                    }
                    guide = l1_result.get('orchestrator_guide')
                    return zone, ci_state, guide
            except Exception:
                pass
        
        # Level 2 arbitration
        if self.l2_router and self.l0_router and self.l1_router:
            try:
                l0_result = self.l0_router.route(query)
                l1_result = self.l1_router.verify(query, l0_result)
                l2_result = self.l2_router.arbitrate(query, l0_result, l1_result)
                
                zone = self._ci_to_zone(l2_result.C, l2_result.I)
                ci_state = {
                    'C': l2_result.C,
                    'I': l2_result.I,
                    'C_continuous': l2_result.C_continuous,
                    'I_continuous': l2_result.I_continuous,
                    'sigma_c': l2_result.sigma_c,
                    'sigma_i': l2_result.sigma_i
                }
                
                # Generate guide for B/D zones
                guide = None
                if zone in ['B', 'D']:
                    guide = self.l2_router.generate_orchestrator_guide(
                        query, zone, l0_result, l1_result
                    )
                
                return zone, ci_state, guide
            except Exception:
                pass
        
        # Fallback: simple heuristic
        return self._fallback_routing(query)
    
    def _fallback_routing(self, query: str) -> tuple:
        """Simple fallback routing when routers unavailable"""
        length = len(query)
        has_question = '?' in query or '？' in query or any(
            k in query for k in ['什么', '怎么', '为什么', '如何']
        )
        
        # Simple heuristic
        C = 1 if length > 50 else 0
        I = 0  # Assume insufficient info initially
        
        zone = self._ci_to_zone(C, I)
        
        ci_state = {
            'C': C,
            'I': I,
            'C_continuous': 0.7 if C else 0.3,
            'I_continuous': 0.3,
            'sigma_c': 0.5,
            'sigma_i': 0.5
        }
        
        return zone, ci_state, None
    
    def _execute_zone_round(self, zone_name: str, query: str, 
                           ci_state: Dict, guide: Optional[Dict],
                           round_number: int) -> ZoneResult:
        """Execute one round in a zone"""
        handler = self.zone_handlers[zone_name]
        
        context = {
            'round_number': round_number,
            'strategy': self.strategy_manager.get_initial_strategy(zone_name)
        }
        
        return handler.enter(query, ci_state, guide, context)
    
    def _process_zone_c_direct(self, query: str, ci_state: Dict) -> ZoneResult:
        """Process query directly in Zone C"""
        handler = self.zone_handlers['C']
        return handler.process_direct(query)
    
    def _process_zone_c(self, query: str, zone_result: ZoneResult,
                       transition: TransitionResult) -> ZoneResult:
        """Process in Zone C based on previous zone result"""
        handler = self.zone_handlers['C']
        
        # Determine mode based on what we have
        if zone_result.sub_problems:
            # Sub-problem mode
            parent_id = str(uuid.uuid4())
            sub_ids = [sp['id'] for sp in zone_result.sub_problems]
            self.subproblem_queue.register_parent(parent_id, sub_ids)
            
            # Process each sub-problem
            for sp in zone_result.sub_problems:
                result = handler.process_subproblem(
                    parent_id=parent_id,
                    subproblem_id=sp['id'],
                    query=sp['query']
                )
                
                if result.output:  # Assembly complete
                    return result
            
            # If we get here, return last result (should have progress info)
            return result
        
        elif zone_result.retrieved_info:
            # Assembled mode with retrieved info
            return handler.process_assembled(
                query=query,
                sub_results=[],
                retrieved_info=zone_result.retrieved_info
            )
        else:
            # Direct mode
            return handler.process_direct(query)
    
    def _build_step_explanation(self, zone: str, zone_result) -> str:
        """Build human-readable explanation for zone execution step"""
        ci = zone_result.ci_state
        explanations = []
        
        if zone == 'D':
            # Zone D: Information retrieval
            old_I = 0.0  # Zone D starts with I=0
            new_I = ci.get('I_continuous', 0)
            doc_count = len(zone_result.retrieved_info)
            
            explanations.append(f"Zone D (补I区): 执行'{zone_result.strategy_used}'策略")
            explanations.append(f"  - 检索到 {doc_count} 篇相关文档")
            explanations.append(f"  - 信息充分性(I)从 {old_I:.2f} 提升到 {new_I:.2f}")
            
            if new_I >= 0.7:
                explanations.append(f"  - I >= 0.7, 满足转区条件!")
            else:
                explanations.append(f"  - I < 0.7, 需要继续检索或策略升级")
                
        elif zone == 'A':
            # Zone A: Decomposition
            sub_count = len(zone_result.sub_problems)
            all_simple = zone_result.metadata.get('all_simple', False)
            
            explanations.append(f"Zone A (拆解区): 执行'{zone_result.strategy_used}'策略")
            explanations.append(f"  - 拆解为 {sub_count} 个子问题")
            
            if all_simple:
                explanations.append(f"  - 所有子问题已简化(C=0), 满足转区条件!")
            else:
                explanations.append(f"  - 部分子问题仍复杂(C=1), 需要进一步拆解")
                
        elif zone == 'B':
            # Zone B: Hybrid
            old_C = 1  # Zone B starts with C=1
            new_C = ci.get('C', 1)
            old_I = 0
            new_I = ci.get('I_continuous', 0)
            retrieved_count = len(zone_result.retrieved_info)
            sub_count = len(zone_result.sub_problems)
            
            explanations.append(f"Zone B (综合区): 执行'{zone_result.strategy_used}'策略")
            
            if retrieved_count > 0:
                explanations.append(f"  - 检索到 {retrieved_count} 篇文档")
                explanations.append(f"  - I从 {old_I:.2f} 提升到 {new_I:.2f}")
            
            if sub_count > 0:
                explanations.append(f"  - 拆解为 {sub_count} 个子问题")
            
            if new_C == 0:
                explanations.append(f"  - C从 1 降到 0 (问题已简化)")
                if new_I >= 0.7:
                    explanations.append(f"  - C=0 且 I>={new_I:.2f}, 满足转区条件!")
            else:
                explanations.append(f"  - C仍为1 (仍需处理)")
        
        return "\n".join(explanations)
    
    def _force_exit(self, query: str, ci_state: Dict, 
                   execution_path: List[Dict], start_time: float) -> PipelineResult:
        """Force exit after max rounds"""
        handler = self.zone_handlers['C']
        result = handler.process_direct(query)
        
        execution_path.append({
            'step': 'force_exit',
            'zone': 'C',
            'reason': 'max_rounds_reached'
        })
        
        return PipelineResult(
            query=query,
            answer=result.output,
            final_zone='C',
            ci_state=result.ci_state,
            execution_path=execution_path,
            metadata={'forced': True, 'reason': 'max_rounds'},
            latency_ms=(time.time() - start_time) * 1000
        )
    
    def _ci_to_zone(self, C: int, I: int) -> str:
        """Map CI to zone name"""
        zone_map = {(0, 0): 'D', (0, 1): 'C', (1, 0): 'B', (1, 1): 'A'}
        return zone_map.get((C, I), 'C')
    
    def get_statistics(self) -> Dict:
        """Get pipeline statistics"""
        return {
            'orchestrator': self.orchestrator.get_statistics(),
            'queue': {
                'registered_parents': len(self.subproblem_queue._expected_counts)
            }
        }