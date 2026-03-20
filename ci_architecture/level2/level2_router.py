"""Level 2 Router: LLM Semantic Refinement.

Final arbitration tier for queries that escape Level 0 and Level 1.
Target: ~100ms latency, <10% of total queries.
"""

import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .llm_client import LLMClient, LLMResponse
from .prompt_builder import (PromptBuilder, CIArbitrationContext,
                             build_level2_context)
from .response_parser import ResponseParser, ParsedResponse
from .dual_probe import DualProbeValidator, ConfidenceCalibrator, DualProbeResult


@dataclass
class Level2Result:
    """Result from Level 2 arbitration."""
    # CI values
    C: int
    I: int
    C_continuous: float
    I_continuous: float
    
    # Confidence
    confidence: float
    sigma_c: float
    sigma_i: float
    sigma_joint: float
    
    # Status
    escalate: bool
    escalate_reason: Optional[str]
    
    # Provenance
    mode: str
    reasoning: str
    probe_consistency: float
    conflict_with_l1: bool
    
    # Metadata
    latency_ms: float
    cost_usd: float
    model_used: str
    parse_failures: int


class Level2Router:
    """
    Level 2: LLM Semantic Refinement Router.
    
    Responsibilities:
    1. Execute LLM-based CI assessment
    2. Dual probe validation for critical decisions
    3. Cross-validate with Level 1 retrieval evidence
    4. Final routing decision with fallback handling
    
    Escape conditions (trigger fallback):
    - Parse failures >= 3
    - Dual probe inconsistency
    - Confidence < 0.3 after calibration
    """
    
    DEFAULT_ALPHA = 0.7  # Escape threshold
    DEFAULT_MAX_PARSE_FAILURES = 3
    
    def __init__(self,
                 config_path: Optional[str] = None,
                 alpha: float = DEFAULT_ALPHA,
                 use_dual_probe: bool = True,
                 consistency_threshold: float = 0.8):
        """
        Initialize Level 2 router.
        
        Args:
            config_path: Path to LLM config YAML
            alpha: Confidence threshold for escape
            use_dual_probe: Enable dual probe validation
            consistency_threshold: Minimum probe consistency
        """
        self.alpha = alpha
        self.use_dual_probe = use_dual_probe
        self.consistency_threshold = consistency_threshold
        
        # Components
        self.llm = LLMClient(config_path=config_path, model_alias="ci-evaluation")
        self.prompt_builder = PromptBuilder()
        self.response_parser = ResponseParser(max_parse_failures=self.DEFAULT_MAX_PARSE_FAILURES)
        self.dual_probe = DualProbeValidator(
            llm_client=self.llm,
            consistency_threshold=consistency_threshold
        )
        self.calibrator = ConfidenceCalibrator(conflict_penalty=0.6)
        
        # Metrics
        self.total_requests = 0
        self.total_escapes = 0
        self.total_cost = 0.0
        self.total_latency = 0.0
    
    def arbitrate(self,
                  query: str,
                  level0_result: Dict,
                  level1_result: Dict) -> Level2Result:
        """
        Execute Level 2 arbitration.
        
        Args:
            query: Original query
            level0_result: Result from Level 0
            level1_result: Result from Level 1
            
        Returns:
            Level2Result with final CI assessment
        """
        import time
        start_time = time.time()
        self.total_requests += 1
        
        # Build context
        context = build_level2_context(query, level0_result, level1_result)
        
        # Check parse failure history
        if self.response_parser.should_fallback():
            self.total_escapes += 1
            return self._create_fallback_result(
                context, "Max parse failures exceeded", start_time
            )
        
        # Route based on configuration
        if self.use_dual_probe:
            result = self._arbitrate_with_dual_probe(context)
        else:
            result = self._arbitrate_single(context)
        
        # Calculate latency
        latency_ms = (time.time() - start_time) * 1000
        self.total_latency += latency_ms
        result.latency_ms = latency_ms
        
        # Update cost
        self.total_cost += result.cost_usd
        
        # Track escapes
        if result.escalate:
            self.total_escapes += 1
        
        return result
    
    def _arbitrate_single(self, context: CIArbitrationContext) -> Level2Result:
        """Single LLM arbitration (faster, less robust)."""
        # Build prompt
        system_prompt = self.prompt_builder.get_system_prompt("ci_evaluation")
        user_prompt = self.prompt_builder.build_ci_evaluation_prompt(context)
        
        # Execute LLM
        response = self.llm.complete([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])
        
        if not response.success:
            return self._create_fallback_result(
                context, f"LLM error: {response.error}", None,
                cost=response.cost_usd, model=response.model
            )
        
        # Parse response
        parsed = self.response_parser.parse(response.content)
        
        # Calibrate with Level 1
        calibrated = self.calibrator.cross_validate_with_retrieval(
            parsed,
            context.level1.I_mean,
            context.level1.sigma_I
        )
        
        # Determine escalation
        escalate = calibrated['confidence'] < self.alpha
        escalate_reason = None if not escalate else "Low confidence after calibration"
        
        # Build result
        return Level2Result(
            C=calibrated['C'],
            I=calibrated['I'],
            C_continuous=1.0 if calibrated['C'] == 1 else 0.0,
            I_continuous=calibrated['I_continuous'],
            confidence=calibrated['confidence'],
            sigma_c=calibrated['confidence'],  # Simplified
            sigma_i=calibrated['confidence'],
            sigma_joint=calibrated['confidence'],
            escalate=escalate,
            escalate_reason=escalate_reason,
            mode="L2_SINGLE_PROBE",
            reasoning=calibrated['reasoning'],
            probe_consistency=1.0,  # Single probe = perfect consistency
            conflict_with_l1=calibrated['conflict_detected'],
            latency_ms=0,  # Will be set by caller
            cost_usd=response.cost_usd,
            model_used=response.model,
            parse_failures=parsed.parse_failures
        )
    
    def _arbitrate_with_dual_probe(self, context: CIArbitrationContext) -> Level2Result:
        """Dual probe arbitration (more robust, slower)."""
        # Execute dual probe validation
        probe_result = self.dual_probe.validate(context.query)
        
        # Calculate cost (2x single probe)
        cost = self.llm.get_metrics()['total_cost_usd'] * 2  # Approximate
        model = self.llm.model_alias
        
        # Check probe success
        if not probe_result.success:
            return self._create_fallback_result(
                context, "Dual probe failed", None,
                cost=cost, model=model
            )
        
        # Check consistency
        if probe_result.needs_escalation:
            # Inconsistent probes - use conservative values
            calibrated_conf = probe_result.confidence * 0.6
            escalate = calibrated_conf < self.alpha
            
            return Level2Result(
                C=probe_result.C,
                I=probe_result.I,
                C_continuous=1.0 if probe_result.C == 1 else 0.0,
                I_continuous=0.8 if probe_result.I == 1 else 0.3,
                confidence=calibrated_conf,
                sigma_c=calibrated_conf,
                sigma_i=calibrated_conf,
                sigma_joint=calibrated_conf,
                escalate=True,  # Always escalate on inconsistency
                escalate_reason=f"Dual probe inconsistent (consistency={probe_result.consistency:.2f})",
                mode="L2_DUAL_PROBE_INCONSISTENT",
                reasoning=probe_result.reasoning,
                probe_consistency=probe_result.consistency,
                conflict_with_l1=False,
                latency_ms=0,
                cost_usd=cost,
                model_used=model,
                parse_failures=0
            )
        
        # Consistent probes - calibrate with Level 1
        # Create synthetic parsed response for calibration
        synthetic_response = ParsedResponse(
            C=probe_result.C,
            I=probe_result.I,
            confidence=probe_result.confidence,
            reasoning=probe_result.reasoning,
            missing_info=[],
            raw_content="",
            success=True
        )
        
        calibrated = self.calibrator.cross_validate_with_retrieval(
            synthetic_response,
            context.level1.I_mean,
            context.level1.sigma_I
        )
        
        # Determine escalation
        escalate = calibrated['confidence'] < self.alpha
        escalate_reason = None if not escalate else "Low confidence after L1 cross-validation"
        
        return Level2Result(
            C=calibrated['C'],
            I=calibrated['I'],
            C_continuous=1.0 if calibrated['C'] == 1 else 0.0,
            I_continuous=calibrated['I_continuous'],
            confidence=calibrated['confidence'],
            sigma_c=calibrated['confidence'],
            sigma_i=calibrated['confidence'],
            sigma_joint=calibrated['confidence'],
            escalate=escalate,
            escalate_reason=escalate_reason,
            mode="L2_DUAL_PROBE",
            reasoning=probe_result.reasoning,
            probe_consistency=probe_result.consistency,
            conflict_with_l1=calibrated['conflict_detected'],
            latency_ms=0,
            cost_usd=cost,
            model_used=model,
            parse_failures=0
        )
    
    def _create_fallback_result(self,
                                context: CIArbitrationContext,
                                reason: str,
                                start_time: Optional[float],
                                cost: float = 0.0,
                                model: str = "none") -> Level2Result:
        """Create conservative fallback result."""
        latency_ms = 0
        if start_time:
            import time
            latency_ms = (time.time() - start_time) * 1000
        
        return Level2Result(
            C=1,  # Conservative: high complexity
            I=0,  # Conservative: insufficient info
            C_continuous=1.0,
            I_continuous=0.3,
            confidence=0.3,
            sigma_c=0.3,
            sigma_i=0.3,
            sigma_joint=0.3,
            escalate=True,
            escalate_reason=f"Fallback: {reason}",
            mode="L2_FALLBACK",
            reasoning=f"Level 2 failed: {reason}. Using conservative defaults.",
            probe_consistency=0.0,
            conflict_with_l1=False,
            latency_ms=latency_ms,
            cost_usd=cost,
            model_used=model,
            parse_failures=self.response_parser.parse_failure_count
        )
    
    def is_available(self) -> bool:
        """Check if Level 2 is available (API key configured)."""
        api_key = os.environ.get("CI_LLM_API_KEY")
        if api_key:
            return True
        # Check config file
        try:
            config = self.llm.config
            model_list = config.get("model_list", [])
            for model in model_list:
                params = model.get("litellm_params", {})
                if params.get("api_key") and not params["api_key"].startswith("$"):
                    return True
        except:
            pass
        return False
    
    def get_metrics(self) -> Dict:
        """Get Level 2 usage metrics."""
        escape_rate = self.total_escapes / max(self.total_requests, 1)
        avg_latency = self.total_latency / max(self.total_requests, 1)
        
        return {
            "total_requests": self.total_requests,
            "total_escapes": self.total_escapes,
            "escape_rate": round(escape_rate, 4),
            "total_cost_usd": round(self.total_cost, 6),
            "avg_latency_ms": round(avg_latency, 2),
            "llm_metrics": self.llm.get_metrics()
        }
    
    def reset_metrics(self):
        """Reset metrics counters."""
        self.total_requests = 0
        self.total_escapes = 0
        self.total_cost = 0.0
        self.total_latency = 0.0
    
    # ==================== V2: 轻量 Guide 生成方法 ====================
    
    def generate_orchestrator_guide(self,
                                    query: str,
                                    current_zone: str,
                                    level0_result: Dict,
                                    level1_result: Dict) -> Dict:
        """
        V2: 轻量模式 - 生成协调器指南 (Orchestrator Guide)
        
        与完整仲裁 arbitrate() 的区别:
        - Token: ~80 vs ~150
        - 延迟: ~50ms vs ~100ms  
        - 输出: 只含 guide，不含完整 CI 评估
        - 用途: Zone B/D 必须携带 guide 进入协调器
        
        Args:
            query: 原始查询
            current_zone: 当前区域 ("B" 或 "D")
            level0_result: Level 0 结果
            level1_result: Level 1 结果
            
        Returns:
            orchestrator_guide 字典
        """
        import time
        start_time = time.time()
        
        # 构建轻量 prompt
        system_prompt = self._build_light_guide_system_prompt()
        user_prompt = self._build_light_guide_user_prompt(
            query, current_zone, level0_result, level1_result
        )
        
        # 调用 LLM (轻量配置)
        response = self.llm.complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=150,  # 减少 token
            temperature=0.1
        )
        
        latency_ms = (time.time() - start_time) * 1000
        
        if not response.success:
            # 失败时返回默认 guide
            return self._create_default_guide(current_zone, f"LLM error: {response.error}")
        
        # 解析 guide
        guide = self._parse_guide_response(response.content)
        
        # 添加元数据
        guide['_meta'] = {
            'source': 'level2_light',
            'latency_ms': latency_ms,
            'cost_usd': response.cost_usd,
            'model': response.model
        }
        
        return guide
    
    def _build_light_guide_system_prompt(self) -> str:
        """构建轻量 guide 生成的 system prompt."""
        return """You are a transition advisor for CI-RAG-Router.
Your task: analyze Zone B/D queries and provide guidance for transitioning to optimal zones (A or C).

Output must be valid JSON:
{
    "missing_info": ["item1", "item2"],  // Critical info gaps, max 3 items
    "decomposable": true/false,          // Can split into sub-problems?
    "recommended": ["clarify", "decompose"],  // Strategy options in priority order
    "sub_problem_hints": ["hint1", "hint2"],  // Suggested sub-problems if decomposable
    "confidence": 0.0-1.0,               // Confidence in this guide
    "validates_classification": true/false  // Agree with current Zone B/D classification?
}

Rules:
1. missing_info: Most critical gaps only. Be specific (e.g., "patient age" not "more info").
2. decomposable: true only if natural sub-questions exist (e.g., multi-part questions).
3. recommended: Priority-ordered list of strategies:
   - ["clarify", "decompose"]: Try info completion first, fallback to decomposition
   - ["decompose", "clarify"]: Multi-part questions, decompose first
   - ["clarify"]: Single missing piece, not decomposable
   - ["decompose"]: Clearly multi-part, no single info can help
4. sub_problem_hints: Concrete sub-question suggestions if decomposable.
5. Be concise. This is for machine consumption, not human reading."""
    
    def _build_light_guide_user_prompt(self, query: str, zone: str, 
                                       l0_result: Dict, l1_result: Dict) -> str:
        """构建轻量 guide 生成的 user prompt."""
        l0_c = l0_result.get('C', 'N/A')
        l0_i = l0_result.get('I', 'N/A')
        l0_sigma = l0_result.get('sigma_joint', 'N/A')
        
        l1_i_mean = l1_result.get('I_mean', 'N/A') if l1_result else 'N/A'
        l1_sigma = l1_result.get('sigma_I', 'N/A') if l1_result else 'N/A'
        
        return f"""Analyze this query for zone transition:

Current Classification: Zone {zone}
Query: {query}

Level 0 Assessment:
- C (Complexity): {l0_c}
- I (Information): {l0_i}
- Confidence: {l0_sigma}

Level 1 Assessment:
- I_mean: {l1_i_mean}
- sigma_I: {l1_sigma}

Provide transition guidance to help the orchestrator reach Zone A or C."""
    
    def _parse_guide_response(self, content: str) -> Dict:
        """解析 LLM 返回的 guide JSON."""
        import json
        import re
        
        try:
            # 尝试直接解析
            guide = json.loads(content)
        except json.JSONDecodeError:
            # 尝试从文本中提取 JSON
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                try:
                    guide = json.loads(json_match.group())
                except:
                    return self._create_default_guide("B", "Parse error")
            else:
                return self._create_default_guide("B", "No JSON found")
        
        # 确保必要字段存在
        guide.setdefault('missing_info', [])
        guide.setdefault('decomposable', False)
        guide.setdefault('recommended', ['clarify'])
        guide.setdefault('sub_problem_hints', [])
        guide.setdefault('confidence', 0.7)
        guide.setdefault('validates_classification', True)
        
        # 限制 missing_info 数量
        guide['missing_info'] = guide['missing_info'][:3]
        
        return guide
    
    def _create_default_guide(self, zone: str, reason: str) -> Dict:
        """创建默认 guide (当 LLM 失败时)."""
        return {
            'missing_info': ['具体信息'],  # 通用提示
            'decomposable': zone == 'B',  # B 区默认可分解
            'recommended': ['clarify'] if zone == 'D' else ['clarify', 'decompose'],
            'sub_problem_hints': [],
            'confidence': 0.5,
            'validates_classification': True,
            '_meta': {
                'source': 'default_fallback',
                'reason': reason
            }
        }


# Convenience function
def arbitrate_with_llm(query: str,
                       level0_result: Dict,
                       level1_result: Dict,
                       config_path: Optional[str] = None) -> Level2Result:
    """
    One-shot Level 2 arbitration.
    
    Args:
        query: Original query
        level0_result: Level 0 result
        level1_result: Level 1 result
        config_path: Optional config path
        
    Returns:
        Level2Result
    """
    router = Level2Router(config_path=config_path)
    return router.arbitrate(query, level0_result, level1_result)
