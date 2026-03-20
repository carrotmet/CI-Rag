"""
Smart Orchestrator V2 - Intelligent CI-based query routing with zone transition.

V2 Architecture:
- Zone B/D must carry orchestrator_guide from Level 2
- Orchestrator executes according to guide (does not make decisions)
- Supports multiple strategies: clarify, decompose
- Max transition rounds limit to prevent infinite loops

This is the V2 implementation based on design docs:
- doc/smart_orchestrator_design.md
- doc/orchestrator_v2_implementation_plan.md
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Union
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
    
    @classmethod
    def from_string(cls, zone_str: str) -> 'Zone':
        """Create Zone from string"""
        return cls(zone_str.upper())


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
    strategies: List[str]  # ['clarify', 'decompose'] 优先级排序的策略列表
    steps: List[Dict] = field(default_factory=list)
    sub_problems: List[SubProblem] = field(default_factory=list)
    missing_info_list: List[str] = field(default_factory=list)
    primary_strategy: str = "direct_execute"  # 主策略
    alternative_strategies: List[str] = field(default_factory=list)  # 备选策略
    user_selectable: bool = False  # 用户是否可选择策略


@dataclass
class OrchestratorGuide:
    """V2: Orchestrator Guide from Level 2"""
    missing_info: List[str]  # 缺失信息列表
    decomposable: bool  # 是否可分解
    recommended: List[str]  # 推荐策略列表（按优先级）
    sub_problem_hints: List[str]  # 子问题提示
    confidence: float  # guide 置信度
    validates_classification: bool  # 是否认可当前分类
    source: str = "level2_light"  # 来源
    meta: Dict = field(default_factory=dict)  # 元数据
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'OrchestratorGuide':
        """从字典创建 Guide"""
        return cls(
            missing_info=data.get('missing_info', []),
            decomposable=data.get('decomposable', False),
            recommended=data.get('recommended', ['clarify']),
            sub_problem_hints=data.get('sub_problem_hints', []),
            confidence=data.get('confidence', 0.7),
            validates_classification=data.get('validates_classification', True),
            source=data.get('_meta', {}).get('source', 'unknown'),
            meta=data.get('_meta', {})
        )


class CITracker:
    """V2: CI Online Tracker - Real-time CI evaluation"""
    
    def __init__(self, l0_router=None, l1_router=None, l2_router=None):
        self.l0_router = l0_router
        self.l1_router = l1_router
        self.l2_router = l2_router
        
        # State tracking
        self.ci_history: List[CIState] = []
        self.accumulated_info: Dict = {}
        self.original_query: str = ""
    
    def evaluate_with_guide(self, query: str, context: Dict = None) -> Dict:
        """
        V2: Execute full CI evaluation with guide (L0 → L1 → L2 if needed)
        
        Returns:
            Dict with CI values and orchestrator_guide if Zone B/D
        """
        self.original_query = query
        
        # Level 0 with guide
        if self.l0_router and hasattr(self.l0_router, 'route_with_guide'):
            l0_result = self.l0_router.route_with_guide(query)
            if 'orchestrator_guide' in l0_result:
                return l0_result
        else:
            # Fallback to basic route
            l0_result = self.l0_router.route(query) if self.l0_router else self._heuristic_evaluate(query)
        
        # Level 1 with guide
        if self.l1_router and hasattr(self.l1_router, 'verify_with_guide'):
            l1_result = self.l1_router.verify_with_guide(query, l0_result)
            if 'orchestrator_guide' in l1_result:
                return l1_result
        elif self.l1_router:
            l1_result = self.l1_router.verify(query, l0_result)
        else:
            l1_result = {'I_mean': l0_result.get('I', 0.5)}
        
        # Level 2 (full arbitration)
        if self.l2_router and hasattr(self.l2_router, 'arbitrate'):
            l2_result = self.l2_router.arbitrate(query, l0_result, l1_result)
            # Convert Level2Result to dict
            result = {
                'C': l2_result.C,
                'I': l2_result.I,
                'C_continuous': l2_result.C_continuous,
                'I_continuous': l2_result.I_continuous,
                'sigma_c': l2_result.sigma_c,
                'sigma_i': l2_result.sigma_i,
                'sigma_joint': l2_result.sigma_joint,
                'escalate': l2_result.escalate,
                'mode': l2_result.mode,
                'reasoning': l2_result.reasoning,
                'zone': self._get_zone_from_ci(l2_result.C, l2_result.I)
            }
            
            # Zone B/D: Generate guide if not present
            if result['zone'] in ['B', 'D'] and hasattr(self.l2_router, 'generate_orchestrator_guide'):
                guide = self.l2_router.generate_orchestrator_guide(
                    query=query,
                    current_zone=result['zone'],
                    level0_result=l0_result,
                    level1_result=l1_result
                )
                result['orchestrator_guide'] = guide
            
            return result
        
        # Fallback: Return L0/L1 result
        return l0_result
    
    def _heuristic_evaluate(self, query: str) -> Dict:
        """Simple heuristic CI evaluation when routers unavailable"""
        length = len(query)
        has_question = '?' in query or '吗' in query or '什么' in query
        word_count = len(query.split())
        
        complex_keywords = ['分析', '比较', '设计', '优化', '为什么', '如何', 'impact', '分析']
        C = min(1.0, sum(1 for k in complex_keywords if k in query) * 0.3 + (word_count / 50))
        I = min(1.0, max(0.1, word_count / 20)) if has_question else min(1.0, word_count / 30)
        
        return {
            'C': 1 if C >= 0.5 else 0,
            'I': 1 if I >= 0.5 else 0,
            'C_continuous': round(C, 2),
            'I_continuous': round(I, 2),
            'sigma_c': 0.6,
            'sigma_i': 0.6,
            'sigma_joint': 0.6,
            'escalate': True,
            'mode': 'HEURISTIC_FALLBACK'
        }
    
    def _get_zone_from_ci(self, C: int, I: int) -> str:
        """Map C and I to zone"""
        zone_map = {(0, 0): 'D', (0, 1): 'C', (1, 0): 'B', (1, 1): 'A'}
        return zone_map.get((C, I), 'B')
    
    def update_with_info(self, new_info: Dict) -> CIState:
        """Re-evaluate CI after user provides additional information"""
        self.accumulated_info.update(new_info)
        enhanced_query = self._build_enhanced_query()
        result = self.evaluate_with_guide(enhanced_query)
        
        return CIState(
            C=result.get('C_continuous', result.get('C', 0)),
            I=result.get('I_continuous', result.get('I', 0)),
            sigma_c=result.get('sigma_c', 0.5),
            sigma_i=result.get('sigma_i', 0.5),
            query=enhanced_query
        )
    
    def _build_enhanced_query(self) -> str:
        """Build enhanced query with accumulated information"""
        if not self.accumulated_info:
            return self.original_query
        info_str = "; ".join([f"{k}={v}" for k, v in self.accumulated_info.items()])
        return f"[{info_str}] {self.original_query}"


class ZoneTransitionEngineV2:
    """V2: Zone Transition Engine - Executes according to guide"""
    
    def plan_from_guide(self, 
                        current_ci: CIState, 
                        guide: OrchestratorGuide) -> ReconstructionPlan:
        """
        V2: Create plan from Level 2 guide (not self-decision)
        
        Args:
            current_ci: Current CI state
            guide: OrchestratorGuide from Level 2
            
        Returns:
            ReconstructionPlan with multiple strategies if available
        """
        current_zone = current_ci.zone
        
        # Already in optimal zone
        if current_zone.is_optimal:
            return ReconstructionPlan(
                original_query=current_ci.query,
                original_zone=current_zone,
                target_zone=current_zone,
                strategies=['direct_execute'],
                primary_strategy='direct_execute'
            )
        
        # Get strategies from guide
        strategies = guide.recommended if guide.recommended else ['clarify']
        
        # Build plans for each strategy
        plans = []
        for strategy in strategies:
            if strategy == 'clarify':
                plan = self._build_clarify_plan(current_ci, guide)
                if plan:
                    plans.append(('clarify', plan))
            elif strategy == 'decompose':
                plan = self._build_decompose_plan(current_ci, guide)
                if plan:
                    plans.append(('decompose', plan))
        
        # Create multi-strategy plan
        if not plans:
            # Fallback: conservative execution in current zone
            return ReconstructionPlan(
                original_query=current_ci.query,
                original_zone=current_zone,
                target_zone=current_zone,
                strategies=['fallback'],
                primary_strategy='fallback',
                missing_info_list=guide.missing_info
            )
        
        primary = plans[0]
        alternatives = plans[1:] if len(plans) > 1 else []
        
        return ReconstructionPlan(
            original_query=current_ci.query,
            original_zone=current_zone,
            target_zone=Zone.A if 'clarify' in strategies else Zone.C,
            strategies=strategies,
            primary_strategy=primary[0],
            alternative_strategies=[p[0] for p in alternatives],
            user_selectable=len(plans) > 1,
            missing_info_list=guide.missing_info,
            sub_problems=primary[1].get('sub_problems', []) if isinstance(primary[1], dict) else []
        )
    
    def _build_clarify_plan(self, ci: CIState, guide: OrchestratorGuide) -> Dict:
        """Build clarification plan"""
        return {
            'strategy': 'clarify',
            'target_zone': 'A' if ci.zone == Zone.B else 'C',
            'missing_info': guide.missing_info,
            'prompt_template': self._build_clarification_prompt(guide.missing_info)
        }
    
    def _build_decompose_plan(self, ci: CIState, guide: OrchestratorGuide) -> Dict:
        """Build decomposition plan"""
        # Generate sub-problems from hints
        sub_problems = []
        for i, hint in enumerate(guide.sub_problem_hints[:4]):  # Max 4
            sp = SubProblem(
                id=f"sp_{i+1}",
                query=hint,
                parent_id=None,
                expected_ci=CIState(C=0.2, I=0.8, sigma_c=0.9, sigma_i=0.9),
                dependencies=[] if i == 0 else [f"sp_{i}"]
            )
            sub_problems.append(sp)
        
        return {
            'strategy': 'decompose',
            'target_zone': 'C',  # Decompose to Zone C first, then aggregate to A
            'sub_problems': sub_problems,
            'aggregation_target': 'A'
        }
    
    def _build_clarification_prompt(self, missing_info: List[str]) -> str:
        """Build user-friendly clarification prompt"""
        if not missing_info:
            return "请提供更多详细信息，以便我给出准确的回答。"
        
        items = "\n".join([f"  - {info}" for info in missing_info])
        return f"""为了给出最准确的回答，我需要了解以下信息：

{items}

请补充以上信息，我将立即为您提供详细的解答。"""


class SmartOrchestratorV2:
    """
    V2: Smart Orchestrator - Main entry point
    
    Key differences from V1:
    1. Zone B/D must have orchestrator_guide
    2. Executes according to guide (no self-decision)
    3. Supports multiple strategies
    4. Max transition rounds limit
    """
    
    ALPHA = 0.7
    MAX_TRANSITION_ROUNDS = 2  # V2: Limit to prevent infinite loops
    
    def __init__(self, l0_router=None, l1_router=None, l2_router=None, llm_client=None):
        # Components
        self._l0_router = l0_router
        self._l1_router = l1_router
        self._l2_router = l2_router
        self.ci_tracker = CITracker(l0_router, l1_router, l2_router)
        self.transition_engine = ZoneTransitionEngineV2()
        self.llm_client = llm_client
        
        # Session management
        self.session_contexts: Dict[str, Dict] = {}
    
    # Property getters/setters to sync with ci_tracker
    @property
    def l0_router(self):
        return self._l0_router
    
    @l0_router.setter
    def l0_router(self, value):
        self._l0_router = value
        self.ci_tracker.l0_router = value
    
    @property
    def l1_router(self):
        return self._l1_router
    
    @l1_router.setter
    def l1_router(self, value):
        self._l1_router = value
        self.ci_tracker.l1_router = value
    
    @property
    def l2_router(self):
        return self._l2_router
    
    @l2_router.setter
    def l2_router(self, value):
        self._l2_router = value
        self.ci_tracker.l2_router = value
    
    def process(self, query: str, session_id: str = None,
                force_strategy: str = None) -> Dict:
        """
        V2: Main processing pipeline
        
        Args:
            query: User query
            session_id: Session ID for multi-turn
            force_strategy: Force specific strategy (optional)
            
        Returns:
            Dict with status and execution plan
        """
        context = self._get_or_create_context(session_id)
        
        # V2: Check max rounds
        if context.get('transition_round', 0) >= self.MAX_TRANSITION_ROUNDS:
            return self._create_fallback_response(context, "Max transition rounds exceeded")
        
        # Step 1: Evaluate with guide
        result = self.ci_tracker.evaluate_with_guide(query)
        context['transition_round'] = context.get('transition_round', 0) + 1
        
        # Step 2: Check zone
        zone_str = result.get('zone', 'B')
        zone = Zone.from_string(zone_str)
        
        # Step 3: If optimal zone, execute directly
        if zone.is_optimal:
            return self._create_success_response(result, zone, context)
        
        # Step 4: Zone B/D - Must have guide
        if 'orchestrator_guide' not in result:
            # This shouldn't happen in V2, but handle gracefully
            return self._create_fallback_response(context, "Missing orchestrator_guide for Zone B/D")
        
        guide = OrchestratorGuide.from_dict(result['orchestrator_guide'])
        
        # Step 5: Create plan from guide
        ci = CIState(
            C=result.get('C_continuous', result.get('C', 0)),
            I=result.get('I_continuous', result.get('I', 0)),
            sigma_c=result.get('sigma_c', 0.5),
            sigma_i=result.get('sigma_i', 0.5),
            query=query
        )
        
        plan = self.transition_engine.plan_from_guide(ci, guide)
        
        # Force strategy if specified
        if force_strategy and force_strategy in plan.strategies:
            plan.primary_strategy = force_strategy
        
        # Step 6: Return plan for execution
        return self._create_plan_response(plan, result, context)
    
    def continue_with_info(self, session_id: str, provided_info: Dict) -> Dict:
        """Continue processing after user provides additional information"""
        if session_id not in self.session_contexts:
            return {'status': 'error', 'error': f'Session {session_id} not found'}
        
        context = self.session_contexts[session_id]
        
        # Update CI with new information
        ci = self.ci_tracker.update_with_info(provided_info)
        
        # Check if reached optimal zone
        if ci.zone.is_optimal:
            return self._create_success_response_from_ci(ci, context)
        
        # Continue with new evaluation
        return self.process(ci.query, session_id)
    
    def execute_strategy(self, session_id: str, strategy: str) -> Dict:
        """Execute specific strategy for current session"""
        context = self.session_contexts.get(session_id)
        if not context:
            return {'status': 'error', 'error': 'Session not found'}
        
        # Re-process with forced strategy
        query = context.get('original_query', '')
        return self.process(query, session_id, force_strategy=strategy)
    
    def _get_or_create_context(self, session_id: str) -> Dict:
        """Get or create session context"""
        if not session_id:
            return {'transition_round': 0, 'history': [], 'accumulated_info': {}}
        
        if session_id not in self.session_contexts:
            self.session_contexts[session_id] = {
                'session_id': session_id,
                'transition_round': 0,
                'history': [],
                'accumulated_info': {},
                'original_query': ''
            }
        
        return self.session_contexts[session_id]
    
    def _create_success_response(self, result: Dict, zone: Zone, context: Dict) -> Dict:
        """Create success response for optimal zone"""
        config = self._get_zone_config(zone)
        
        return {
            'status': 'success',
            'zone': zone.value,
            'ci': {
                'C': result.get('C'),
                'I': result.get('I'),
                'sigma_joint': result.get('sigma_joint')
            },
            'execution_config': config,
            'transition_round': context.get('transition_round', 0)
        }
    
    def _create_success_response_from_ci(self, ci: CIState, context: Dict) -> Dict:
        """Create success response from CI state"""
        config = self._get_zone_config(ci.zone)
        
        return {
            'status': 'success',
            'zone': ci.zone.value,
            'ci': ci.to_dict(),
            'execution_config': config,
            'transition_round': context.get('transition_round', 0)
        }
    
    def _create_plan_response(self, plan: ReconstructionPlan, 
                              result: Dict, context: Dict) -> Dict:
        """Create response with execution plan"""
        response = {
            'status': 'transition_required',
            'current_zone': plan.original_zone.value,
            'target_zone': plan.target_zone.value,
            'primary_strategy': plan.primary_strategy,
            'available_strategies': plan.strategies,
            'user_selectable': plan.user_selectable,
            'transition_round': context.get('transition_round', 0),
            'max_rounds': self.MAX_TRANSITION_ROUNDS,
            'ci': {
                'C': result.get('C'),
                'I': result.get('I'),
                'sigma_joint': result.get('sigma_joint')
            }
        }
        
        # Add strategy-specific details
        if plan.primary_strategy == 'clarify':
            response['clarification'] = {
                'missing_info': plan.missing_info_list,
                'prompt': self._build_clarification_prompt(plan.missing_info_list)
            }
        elif plan.primary_strategy == 'decompose':
            response['decomposition'] = {
                'sub_problems': [
                    {'id': sp.id, 'query': sp.query}
                    for sp in plan.sub_problems
                ],
                'aggregation_target': 'A'
            }
        
        return response
    
    def _create_fallback_response(self, context: Dict, reason: str) -> Dict:
        """Create fallback response when transition fails"""
        return {
            'status': 'fallback',
            'zone': 'B',
            'reason': reason,
            'transition_round': context.get('transition_round', 0),
            'execution_config': self._get_zone_config(Zone.B)
        }
    
    def _build_clarification_prompt(self, missing_info: List[str]) -> str:
        """Build clarification prompt"""
        if not missing_info:
            return "请提供更多详细信息。"
        
        items = "\n".join([f"  - {info}" for info in missing_info])
        return f"""为了给出最准确的回答，我需要了解以下信息：

{items}

请补充以上信息，我将立即为您解答。"""
    
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
    
    def get_session_history(self, session_id: str) -> List[Dict]:
        """Get session history"""
        tracker_history = self.ci_tracker.get_history() if hasattr(self.ci_tracker, 'get_history') else []
        return [ci.to_dict() for ci in tracker_history]
    
    def clear_session(self, session_id: str):
        """Clear session"""
        if session_id in self.session_contexts:
            del self.session_contexts[session_id]


# Backward compatibility: Export both V1 and V2
try:
    from .smart_orchestrator import SmartOrchestrator as SmartOrchestratorV1
except ImportError:
    SmartOrchestratorV1 = None

__all__ = [
    'SmartOrchestratorV2',
    'SmartOrchestratorV1',
    'Zone',
    'CIState',
    'SubProblem',
    'ReconstructionPlan',
    'OrchestratorGuide',
    'CITracker',
    'ZoneTransitionEngineV2'
]
