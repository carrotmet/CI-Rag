"""
Smart Orchestrator - Intelligent CI-based query routing with zone transition.

This module implements the core orchestration logic for CI-RAG-Router:
- Online CI evaluation across L0/L1/L2
- Dynamic zone transition (D→C, B→A, B→C via decomposition)
- Query reconstruction through clarification or decomposition
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Tuple, Any
from enum import Enum
import time
import uuid


class Zone(Enum):
    """ABCD Four Zones"""
    A = "A"  # C=1, I=1: Complex + Well-covered → Reasoning output
    B = "B"  # C=1, I=0: Complex + Under-covered → Needs transition
    C = "C"  # C=0, I=1: Simple + Well-covered → Direct output
    D = "D"  # C=0, I=0: Simple + Under-covered → Needs transition
    
    @property
    def is_optimal(self) -> bool:
        """Check if this is an optimal zone (A or C)"""
        return self in (Zone.A, Zone.C)
    
    @property
    def target_zone(self) -> Optional['Zone']:
        """Get default transition target"""
        return {
            Zone.D: Zone.C,  # C0I0 → C0I1: Info completion
            Zone.B: Zone.A,  # C1I0 → C1I1: Preserve complexity, add info
        }.get(self)


@dataclass
class CIState:
    """CI State snapshot"""
    C: float  # Complexity (0-1 continuous)
    I: float  # Information sufficiency (0-1 continuous)
    sigma_c: float  # Confidence in C
    sigma_i: float  # Confidence in I
    query: str = ""  # Associated query
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
        """Convert to dictionary"""
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
class SubProblem:
    """Sub-problem structure for decomposition"""
    id: str
    query: str
    parent_id: Optional[str]
    expected_ci: CIState
    dependencies: List[str] = field(default_factory=list)
    accumulated_info: Dict = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.id:
            self.id = f"sp_{uuid.uuid4().hex[:8]}"


@dataclass
class ReconstructionPlan:
    """Query reconstruction plan"""
    original_query: str
    original_zone: Zone
    target_zone: Zone
    strategy: str  # 'clarify', 'decompose', 'retrieve', 'direct_execute'
    steps: List[Dict] = field(default_factory=list)
    sub_problems: List[SubProblem] = field(default_factory=list)
    missing_info_list: List[str] = field(default_factory=list)
    
    @property
    def is_executable(self) -> bool:
        """Check if plan can be executed immediately"""
        return self.strategy in ['direct_execute', 'decompose'] or len(self.missing_info_list) == 0


class CITracker:
    """
    CI Online Tracker - Real-time CI evaluation across L0/L1/L2
    """
    
    def __init__(self, l0_router=None, l1_router=None, l2_router=None):
        self.l0_router = l0_router
        self.l1_router = l1_router
        self.l2_router = l2_router
        
        # State tracking
        self.ci_history: List[CIState] = []
        self.accumulated_info: Dict = {}
        self.original_query: str = ""
    
    def evaluate(self, query: str, context: Dict = None) -> CIState:
        """
        Execute full CI evaluation (L0 → L1 → L2 if needed)
        
        Returns:
            CIState with C, I, and confidence values
        """
        self.original_query = query
        
        # Level 0 evaluation
        if self.l0_router:
            l0_result = self.l0_router.route(query)
            ci = CIState(
                C=l0_result.get('C_continuous', float(l0_result.get('C', 0))),
                I=l0_result.get('I_continuous', float(l0_result.get('I', 0))),
                sigma_c=l0_result.get('sigma_c', 0.5),
                sigma_i=l0_result.get('sigma_i', 0.5),
                query=query
            )
        else:
            # Fallback: simple heuristic
            ci = self._heuristic_evaluate(query)
        
        # Level 1: If confidence insufficient
        if ci.sigma_joint < 0.7 and self.l1_router:
            l0_result = self.l0_router.route(query) if self.l0_router else {'C': ci.C, 'I': ci.I}
            l1_result = self.l1_router.verify(query, l0_result)
            
            ci = CIState(
                C=ci.C,  # C typically from L0
                I=l1_result.get('I_mean', l1_result.get('I', ci.I)),
                sigma_c=ci.sigma_c,
                sigma_i=l1_result.get('sigma_I', l1_result.get('sigma_i', 0.5)),
                query=query
            )
        
        # Level 2: If still insufficient
        if ci.sigma_joint < 0.7 and self.l2_router:
            l0_result = self.l0_router.route(query) if self.l0_router else {'C': ci.C, 'I': ci.I}
            l1_result = self.l1_router.verify(query, l0_result) if self.l1_router else {'I_mean': ci.I}
            
            l2_result = self.l2_router.arbitrate(query, l0_result, l1_result)
            ci = CIState(
                C=getattr(l2_result, 'C_continuous', getattr(l2_result, 'C', ci.C)),
                I=getattr(l2_result, 'I_continuous', getattr(l2_result, 'I', ci.I)),
                sigma_c=getattr(l2_result, 'sigma_c', 0.5),
                sigma_i=getattr(l2_result, 'sigma_i', 0.5),
                query=query
            )
        
        self.ci_history.append(ci)
        return ci
    
    def _heuristic_evaluate(self, query: str) -> CIState:
        """Simple heuristic CI evaluation when routers unavailable"""
        # Simple heuristics based on query length and structure
        length = len(query)
        has_question = '?' in query or '吗' in query or '什么' in query
        word_count = len(query.split())
        
        # C: complexity based on length and domain keywords
        complex_keywords = ['分析', '比较', '设计', '优化', '为什么', '如何', ' impact ', '分析']
        C = min(1.0, sum(1 for k in complex_keywords if k in query) * 0.3 + (word_count / 50))
        
        # I: information sufficiency (simplified)
        I = min(1.0, max(0.1, word_count / 20)) if has_question else min(1.0, word_count / 30)
        
        return CIState(
            C=round(C, 2),
            I=round(I, 2),
            sigma_c=0.6,
            sigma_i=0.6,
            query=query
        )
    
    def update_with_info(self, new_info: Dict) -> CIState:
        """
        Re-evaluate CI after user provides additional information
        
        Adding information typically increases I and may decrease C
        """
        # Merge accumulated info
        self.accumulated_info.update(new_info)
        
        # Build enhanced query
        enhanced_query = self._build_enhanced_query()
        
        # Re-evaluate
        return self.evaluate(enhanced_query)
    
    def _build_enhanced_query(self) -> str:
        """Build enhanced query with accumulated information"""
        if not self.accumulated_info:
            return self.original_query
        
        info_str = "; ".join([f"{k}={v}" for k, v in self.accumulated_info.items()])
        return f"[{info_str}] {self.original_query}"
    
    def get_history(self) -> List[CIState]:
        """Get CI evaluation history"""
        return self.ci_history.copy()


class ZoneTransitionEngine:
    """
    Zone Transition Engine - Decides how to transition to optimal zones
    """
    
    # Transition strategy configurations
    TRANSITION_STRATEGIES = {
        (Zone.D, Zone.C): {
            'name': 'info_completion',
            'description': '精准补充信息，提升 I 值，保持低复杂度',
            'actions': ['identify_gaps', 'prompt_clarification', 'retrieve_specific']
        },
        (Zone.B, Zone.A): {
            'name': 'complexity_preserving_completion',
            'description': '补充关键信息，保持复杂推理需求',
            'actions': ['identify_critical_gaps', 'domain_retrieval', 'structure_enhance']
        },
        (Zone.B, Zone.C): {
            'name': 'problem_decomposition',
            'description': '拆解为多个简单子问题，分别处理后聚合',
            'actions': ['decompose', 'order_subproblems', 'aggregate']
        }
    }
    
    def __init__(self, llm_client=None):
        self.llm = llm_client
    
    def plan_transition(self, current_ci: CIState, target_zone: Zone = None) -> ReconstructionPlan:
        """
        Create transition plan from current zone to target zone
        
        Args:
            current_ci: Current CI state
            target_zone: Desired target zone (None = use default)
        
        Returns:
            ReconstructionPlan with transition strategy
        """
        current_zone = current_ci.zone
        
        # Already in optimal zone
        if current_zone.is_optimal:
            return ReconstructionPlan(
                original_query=current_ci.query,
                original_zone=current_zone,
                target_zone=current_zone,
                strategy='direct_execute',
                steps=[{'action': 'execute', 'zone': current_zone.value}]
            )
        
        # Determine target zone
        default_target = current_zone.target_zone
        effective_target = target_zone or default_target
        
        # Check for B→C decomposition case
        if current_zone == Zone.B and target_zone == Zone.C:
            # Decomposition strategy
            sub_problems = self._decompose_problem(current_ci)
            return ReconstructionPlan(
                original_query=current_ci.query,
                original_zone=current_zone,
                target_zone=Zone.C,
                strategy='decompose',
                steps=['decompose', 'execute_subproblems', 'aggregate'],
                sub_problems=sub_problems
            )
        
        # Information completion strategies
        transition_key = (current_zone, effective_target)
        strategy_config = self.TRANSITION_STRATEGIES.get(transition_key, {})
        
        # Identify missing information
        missing_info = self._identify_missing_info(current_ci)
        
        return ReconstructionPlan(
            original_query=current_ci.query,
            original_zone=current_zone,
            target_zone=effective_target,
            strategy='clarify',
            steps=strategy_config.get('actions', ['identify_gaps', 'prompt_clarification']),
            missing_info_list=missing_info
        )
    
    def _identify_missing_info(self, ci: CIState) -> List[str]:
        """Identify missing critical information based on I value"""
        missing = []
        
        if ci.I < 0.3:
            # Severely insufficient
            missing.extend([
                '核心实体定义（如具体名称、型号、版本）',
                '关键参数或条件',
                '时间、地点或范围上下文'
            ])
        elif ci.I < 0.7:
            # Moderately insufficient
            missing.extend([
                '补充细节信息',
                '边界条件或约束',
                '预期的输出格式'
            ])
        
        # Add query-specific gaps based on content analysis
        missing.extend(self._analyze_query_gaps(ci.query))
        
        return missing[:5]  # Limit to top 5
    
    def _analyze_query_gaps(self, query: str) -> List[str]:
        """Analyze query content for specific gaps"""
        gaps = []
        query_lower = query.lower()
        
        # Domain-specific gap detection
        if any(kw in query_lower for kw in ['药', '症状', '病', '治疗']):
            if '年龄' not in query and '岁' not in query:
                gaps.append('患者年龄')
            if '时间' not in query and '天' not in query and 'duration' not in query_lower:
                gaps.append('症状持续时间')
        
        if any(kw in query_lower for kw in ['系统', '设计', '架构', '优化']):
            if '规模' not in query and 'qps' not in query_lower and '并发' not in query:
                gaps.append('系统规模或性能指标')
            if '约束' not in query and '限制' not in query:
                gaps.append('技术约束条件')
        
        return gaps
    
    def _decompose_problem(self, ci: CIState) -> List[SubProblem]:
        """
        Decompose C1I0 complex problem into multiple C0I0/C0I1 sub-problems
        
        This is a simplified version. In production, use LLM for intelligent decomposition.
        """
        query = ci.query
        
        # Pattern-based decomposition (simplified)
        # In production, this should use LLM to intelligently decompose
        
        sub_problems = []
        
        # Example decomposition patterns
        if '设计' in query or 'design' in query.lower():
            # System design decomposition
            sub_queries = [
                f"{query}的核心架构模式是什么？",
                f"{query}的数据存储方案应该如何设计？",
                f"{query}的性能优化策略有哪些？",
            ]
        elif '分析' in query or 'analyze' in query.lower():
            # Analysis decomposition
            sub_queries = [
                f"{query}的背景和现状是什么？",
                f"{query}的关键因素有哪些？",
                f"{query}的可能解决方案是什么？",
            ]
        else:
            # Generic decomposition
            sub_queries = [
                f"{query}的定义是什么？",
                f"{query}的核心要素有哪些？",
                f"{query}的应用场景是什么？",
            ]
        
        for i, sq in enumerate(sub_queries[:4]):  # Max 4 sub-problems
            sp = SubProblem(
                id=f"sp_{i+1}",
                query=sq,
                parent_id=None,
                expected_ci=CIState(
                    C=0.2,  # Simple
                    I=0.8,  # Well-covered after clarification
                    sigma_c=0.9,
                    sigma_i=0.9
                ),
                dependencies=[] if i == 0 else [f"sp_{i}"]  # Sequential dependency
            )
            sub_problems.append(sp)
        
        return sub_problems


class QueryReconstructor:
    """
    Query Reconstructor - Executes actual query transformation
    """
    
    def __init__(self):
        self.reconstruction_hooks: List[Callable] = []
    
    def reconstruct(self, plan: ReconstructionPlan, context: Dict = None) -> List[Dict]:
        """
        Execute query reconstruction, return executable query list
        
        Returns:
            List of execution steps
        """
        if plan.strategy == 'direct_execute':
            return [{
                'type': 'execute',
                'query': plan.original_query,
                'zone': plan.target_zone.value,
                'config': self._get_zone_config(plan.target_zone)
            }]
        
        elif plan.strategy == 'clarify':
            # Generate clarification prompt
            clarification = self._build_clarification_prompt(plan.missing_info_list)
            return [{
                'type': 'clarification',
                'prompt': clarification,
                'missing_info': plan.missing_info_list,
                'target_zone': plan.target_zone.value,
                'current_zone': plan.original_zone.value
            }]
        
        elif plan.strategy == 'decompose':
            # Generate sub-problem execution sequence
            return self._build_decomposition_sequence(plan)
        
        return []
    
    def _build_clarification_prompt(self, missing_info: List[str]) -> str:
        """Build user-friendly clarification prompt"""
        if not missing_info:
            return "请提供更多详细信息，以便我给出准确的回答。"
        
        items = "\n".join([f"  • {info}" for info in missing_info])
        return f"""为了给出最准确的回答，我需要了解以下信息：

{items}

请补充以上信息，我将立即为您提供详细的解答。"""
    
    def _build_decomposition_sequence(self, plan: ReconstructionPlan) -> List[Dict]:
        """Build execution sequence for problem decomposition"""
        sequence = []
        
        # Add sub-problems
        for sp in plan.sub_problems:
            sequence.append({
                'type': 'sub_problem',
                'id': sp.id,
                'query': sp.query,
                'expected_zone': 'C',
                'dependencies': sp.dependencies,
                'config': self._get_zone_config(Zone.C)
            })
        
        # Add aggregation step
        sequence.append({
            'type': 'aggregate',
            'depends_on': [sp.id for sp in plan.sub_problems],
            'target_zone': 'A',
            'config': self._get_zone_config(Zone.A)
        })
        
        return sequence
    
    def _get_zone_config(self, zone: Zone) -> Dict:
        """Get execution configuration for zone"""
        configs = {
            Zone.A: {
                'max_tokens': 2048,
                'temperature': 0.3,
                'retrieval_streams': 2,
                'verification': True,
                'description': '结构化推理输出'
            },
            Zone.B: {
                'max_tokens': 3072,
                'temperature': 0.4,
                'retrieval_streams': 4,
                'verification': True,
                'description': '保守并行检索'
            },
            Zone.C: {
                'max_tokens': 512,
                'temperature': 0.1,
                'retrieval_streams': 1,
                'verification': False,
                'description': '直接块输出'
            },
            Zone.D: {
                'max_tokens': 1024,
                'temperature': 0.2,
                'retrieval_streams': 2,
                'verification': True,
                'description': '精准单点检索'
            }
        }
        return configs.get(zone, configs[Zone.B])


class SmartOrchestrator:
    """
    Smart Orchestrator - Main entry point for intelligent CI-based routing
    
    Key features:
    1. Online CI evaluation across L0/L1/L2
    2. Dynamic zone transition to optimal zones (A or C)
    3. Query reconstruction through clarification or decomposition
    """
    
    ALPHA = 0.7  # Confidence threshold
    MAX_TRANSITION_ROUNDS = 3  # Max transition rounds
    
    def __init__(self, l0_router=None, l1_router=None, l2_router=None, llm_client=None):
        """
        Initialize Smart Orchestrator
        
        Args:
            l0_router: Level 0 router instance
            l1_router: Level 1 router instance  
            l2_router: Level 2 router instance
            llm_client: LLM client for decomposition
        """
        # Sub-components
        self.ci_tracker = CITracker(l0_router, l1_router, l2_router)
        self.transition_engine = ZoneTransitionEngine(llm_client)
        self.reconstructor = QueryReconstructor()
        
        # Session management
        self.session_contexts: Dict[str, Dict] = {}
        self.llm_client = llm_client
    
    def process(self, query: str, session_id: str = None,
                force_zone: Zone = None,
                max_rounds: int = None) -> Dict:
        """
        Main processing pipeline
        
        Args:
            query: User query
            session_id: Session ID for multi-turn conversations
            force_zone: Force specific target zone
            max_rounds: Max transition rounds (default: MAX_TRANSITION_ROUNDS)
        
        Returns:
            Dict with status and execution plan:
            - status='success': Direct execution ready
            - status='clarification_needed': Need user input
            - status='decomposition': Multiple sub-problems generated
        """
        max_rounds = max_rounds or self.MAX_TRANSITION_ROUNDS
        context = self._get_or_create_context(session_id)
        
        # Step 1: Initial CI evaluation
        ci = self.ci_tracker.evaluate(query, context)
        current_zone = ci.zone
        
        print(f"[Orchestrator] Initial: Zone {current_zone.value}, "
              f"C={ci.C:.2f}, I={ci.I:.2f}, σ={ci.sigma_joint:.2f}")
        
        # Step 2: If already in optimal zone, execute directly
        if current_zone.is_optimal:
            return self._create_success_response(query, ci, context)
        
        # Step 3: Create transition plan
        target = force_zone or current_zone.target_zone
        plan = self.transition_engine.plan_transition(ci, target)
        
        print(f"[Orchestrator] Transition: {plan.original_zone.value} → {plan.target_zone.value}, "
              f"strategy={plan.strategy}")
        
        # Step 4: Execute transition
        return self._execute_transition(query, plan, ci, context, max_rounds)
    
    def _execute_transition(self, query: str, plan: ReconstructionPlan,
                           initial_ci: CIState, context: Dict,
                           max_rounds: int) -> Dict:
        """Execute zone transition"""
        
        # Strategy 1: Direct decomposition (B → multiple C)
        if plan.strategy == 'decompose':
            return self._create_decomposition_response(plan, context)
        
        # Strategy 2: Information clarification (D→C or B→A)
        if plan.strategy == 'clarify':
            return self._create_clarification_response(plan, initial_ci)
        
        # Strategy 3: Direct execution (already in optimal zone)
        if plan.strategy == 'direct_execute':
            return self._create_success_response(query, initial_ci, context)
        
        # Fallback
        return self._create_fallback_response(query, initial_ci)
    
    def continue_with_info(self, session_id: str, provided_info: Dict) -> Dict:
        """
        Continue processing after user provides additional information
        
        Args:
            session_id: Session ID
            provided_info: Dict of provided information
        
        Returns:
            Updated processing result
        """
        if session_id not in self.session_contexts:
            return {
                'status': 'error',
                'error': f'Session {session_id} not found'
            }
        
        context = self.session_contexts[session_id]
        
        # Update CI with new information
        ci = self.ci_tracker.update_with_info(provided_info)
        current_zone = ci.zone
        
        print(f"[Orchestrator] After info: Zone {current_zone.value}, "
              f"C={ci.C:.2f}, I={ci.I:.2f}")
        
        # Check if reached optimal zone
        if current_zone.is_optimal:
            return self._create_success_response(ci.query, ci, context)
        
        # Continue transition
        plan = self.transition_engine.plan_transition(ci, None)
        return self._execute_transition(ci.query, plan, ci, context, self.MAX_TRANSITION_ROUNDS)
    
    def execute_decomposition(self, session_id: str) -> Dict:
        """
        Execute decomposition plan (for B → C via sub-problems)
        
        This would be called after user confirms decomposition approach
        """
        context = self.session_contexts.get(session_id, {})
        plan = context.get('pending_plan')
        
        if not plan or plan.strategy != 'decompose':
            return {'status': 'error', 'error': 'No decomposition plan found'}
        
        results = []
        for sp in plan.sub_problems:
            # Evaluate each sub-problem
            sp_ci = self.ci_tracker.evaluate(sp.query)
            
            if sp_ci.zone == Zone.C:
                # Direct output
                result = {
                    'sub_problem_id': sp.id,
                    'zone': 'C',
                    'ci': sp_ci.to_dict(),
                    'config': self.reconstructor._get_zone_config(Zone.C)
                }
            else:
                # May need further clarification
                sp_plan = self.transition_engine.plan_transition(sp_ci, Zone.C)
                result = {
                    'sub_problem_id': sp.id,
                    'zone': sp_ci.zone.value,
                    'needs_clarification': sp_plan.strategy == 'clarify',
                    'missing_info': sp_plan.missing_info_list
                }
            
            results.append(result)
        
        return {
            'status': 'decomposition_ready',
            'sub_problems': results,
            'aggregation_config': self.reconstructor._get_zone_config(Zone.A)
        }
    
    def _create_success_response(self, query: str, ci: CIState, context: Dict) -> Dict:
        """Create success response for optimal zone execution"""
        config = self.reconstructor._get_zone_config(ci.zone)
        
        return {
            'status': 'success',
            'zone': ci.zone.value,
            'ci': ci.to_dict(),
            'query': query,
            'strategy': 'direct_execute',
            'execution_config': config,
            'accumulated_info': self.ci_tracker.accumulated_info
        }
    
    def _create_clarification_response(self, plan: ReconstructionPlan, ci: CIState) -> Dict:
        """Create clarification needed response"""
        reconstructed = self.reconstructor.reconstruct(plan)
        clarification = reconstructed[0] if reconstructed else {}
        
        return {
            'status': 'clarification_needed',
            'current_zone': plan.original_zone.value,
            'target_zone': plan.target_zone.value,
            'ci': ci.to_dict(),
            'prompt': clarification.get('prompt', '请提供更多信息'),
            'missing_info': plan.missing_info_list,
            'strategy': 'info_completion'
        }
    
    def _create_decomposition_response(self, plan: ReconstructionPlan, context: Dict) -> Dict:
        """Create decomposition response"""
        # Store plan in context for later execution
        context['pending_plan'] = plan
        
        sub_problems_summary = [
            {'id': sp.id, 'query': sp.query, 'expected_zone': 'C'}
            for sp in plan.sub_problems
        ]
        
        return {
            'status': 'decomposition_proposed',
            'current_zone': plan.original_zone.value,
            'target_zone': plan.target_zone.value,
            'strategy': 'problem_decomposition',
            'sub_problems': sub_problems_summary,
            'total_sub_problems': len(plan.sub_problems),
            'aggregation_target': 'A',
            'message': f'建议将问题分解为 {len(plan.sub_problems)} 个子问题分别处理，然后聚合结果。'
        }
    
    def _create_fallback_response(self, query: str, ci: CIState) -> Dict:
        """Create fallback response when transition fails"""
        return {
            'status': 'fallback',
            'zone': 'B',
            'ci': ci.to_dict(),
            'query': query,
            'strategy': 'conservative',
            'execution_config': self.reconstructor._get_zone_config(Zone.B),
            'message': '使用保守策略执行'
        }
    
    def _get_or_create_context(self, session_id: str) -> Dict:
        """Get or create session context"""
        if not session_id:
            return {'accumulated_info': {}, 'history': []}
        
        if session_id not in self.session_contexts:
            self.session_contexts[session_id] = {
                'session_id': session_id,
                'accumulated_info': {},
                'history': [],
                'pending_plan': None
            }
        
        return self.session_contexts[session_id]
    
    def get_session_history(self, session_id: str) -> List[Dict]:
        """Get CI evaluation history for session"""
        tracker_history = self.ci_tracker.get_history()
        return [ci.to_dict() for ci in tracker_history]
    
    def clear_session(self, session_id: str):
        """Clear session context"""
        if session_id in self.session_contexts:
            del self.session_contexts[session_id]
