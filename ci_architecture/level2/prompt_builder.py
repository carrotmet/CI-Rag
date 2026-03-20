"""Prompt Builder for Level 2 LLM semantic refinement.

Assembles comprehensive context for CI arbitration and routing decisions.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class Level0Context:
    """Level 0 routing context."""
    C: int  # Complexity: 0=Low, 1=High
    I: int  # Information sufficiency: 0=Insufficient, 1=Sufficient
    C_continuous: float
    I_continuous: float
    sigma_c: float
    sigma_i: float
    sigma_joint: float
    escalate: bool
    mode: str
    features: List[float]


@dataclass
class Level1Context:
    """Level 1 retrieval context."""
    I_mean: float
    sigma_I: float
    vector: Optional[Dict] = None
    keyword: Optional[Dict] = None
    conflict_detected: bool = False
    source_weights: Dict[str, float] = None
    
    def __post_init__(self):
        if self.source_weights is None:
            self.source_weights = {}


@dataclass
class CIArbitrationContext:
    """Complete context for CI arbitration."""
    query: str
    level0: Level0Context
    level1: Level1Context
    retrieval_evidence: Dict[str, Any]
    parse_failures: int = 0


class PromptBuilder:
    """
    Build prompts for Level 2 LLM arbitration.
    
    Supports multiple prompt types:
    - CI evaluation: Refine C and I values with retrieval evidence
    - Complex analysis: Deep reasoning for ambiguous queries
    - Dual probe: Consistency validation
    """
    
    # System prompts for different scenarios
    CI_EVALUATION_SYSTEM = """You are a CI (Complexity-Information) routing expert. 
Your task is to evaluate query complexity and information sufficiency based on provided evidence.

Output must be valid JSON with this structure:
{
    "C": 0 or 1,  // Complexity: 0=Low (simple lookup/factual), 1=High (multi-step reasoning/analysis)
    "I": 0 or 1,  // Information sufficiency: 0=Insufficient (needs more context), 1=Sufficient
    "confidence": 0.0-1.0,  // Your confidence in this assessment
    "reasoning": "Brief explanation of your decision",
    "missing_info": ["list", "of", "missing", "information"]  // Only if I=0
}

Guidelines:
- C=1 (High complexity): Multi-domain analysis, reasoning steps, ambiguous requirements
- C=0 (Low complexity): Direct lookup, simple transformation, factual recall
- I=1 (Sufficient): Query contains enough context for accurate response
- I=0 (Insufficient): Query is vague, lacks key details, or needs clarification"""

    COMPLEX_ANALYSIS_SYSTEM = """You are an expert query analyzer for complex routing decisions.
Analyze the query depth and provide structured assessment.

Output must be valid JSON:
{
    "C": 0 or 1,
    "I": 0 or 1,
    "complexity_score": 0.0-1.0,  // Continuous complexity (0-1)
    "information_score": 0.0-1.0,  // Continuous information sufficiency (0-1)
    "confidence": 0.0-1.0,
    "reasoning": "Detailed analysis",
    "recommended_zone": "A/B/C/D",  // ABCD routing zone
    "missing_info": []
}"""

    DUAL_PROBE_SYSTEM = """You are a consistency validator. Evaluate the query independently.

Output must be valid JSON:
{
    "C": 0 or 1,
    "I": 0 or 1,
    "confidence": 0.0-1.0,
    "key_factors": ["factor1", "factor2"]  // Key decision factors
}"""

    def __init__(self):
        """Initialize prompt builder."""
        pass

    def build_ci_evaluation_prompt(self, context: CIArbitrationContext) -> str:
        """
        Build prompt for CI evaluation with full context.
        
        Args:
            context: Complete arbitration context
            
        Returns:
            Formatted prompt string
        """
        lines = [
            "=== Query ===",
            context.query,
            "",
            "=== Level 0 Assessment ===",
            f"Complexity (C): {context.level0.C} ({'High' if context.level0.C == 1 else 'Low'})",
            f"Information (I): {context.level0.I} ({'Sufficient' if context.level0.I == 1 else 'Insufficient'})",
            f"Confidence: σ_c={context.level0.sigma_c:.3f}, σ_i={context.level0.sigma_i:.3f}, σ_joint={context.level0.sigma_joint:.3f}",
            f"Mode: {context.level0.mode}",
            "",
            "=== Level 1 Retrieval Evidence ===",
            f"Fused I_mean: {context.level1.I_mean:.3f}",
            f"Fused σ_I: {context.level1.sigma_I:.3f}",
        ]
        
        if context.level1.conflict_detected:
            lines.append("⚠️ Conflict detected between retrieval sources")
        
        # Add vector retrieval evidence
        if context.level1.vector:
            vec = context.level1.vector
            lines.extend([
                "",
                "Vector Retrieval:",
                f"  - Max similarity: {vec.get('sim_max', 0):.3f}",
                f"  - Gap: {vec.get('gap', 0):.3f}",
                f"  - Entropy: {vec.get('entropy', 0):.3f}",
            ])
        
        # Add keyword retrieval evidence
        if context.level1.keyword:
            kw = context.level1.keyword
            lines.extend([
                "",
                "Keyword Retrieval:",
                f"  - Max score: {kw.get('score_max', 0):.2f}",
                f"  - Coverage: {kw.get('coverage', 0):.2f}",
                f"  - Matched terms: {', '.join(kw.get('matched_terms', [])[:10])}",
            ])
        
        # Add top documents
        top_docs = context.retrieval_evidence.get('top_documents', [])
        if top_docs:
            lines.extend([
                "",
                "=== Top Relevant Documents ===",
            ])
            for i, doc in enumerate(top_docs[:5], 1):
                source = doc.get('source', 'unknown')
                score = doc.get('score', 0)
                content = doc.get('content', '')[:150]
                lines.append(f"{i}. [{source}] (score: {score:.3f}) {content}...")
        
        lines.extend([
            "",
            "=== Task ===",
            "Based on the above evidence, evaluate:",
            "1. Is this query HIGH complexity (multi-step, reasoning, ambiguous) or LOW complexity (simple lookup)?",
            "2. Does the query have SUFFICIENT information for accurate response, or is it missing key context?",
            "",
            "Provide your assessment in the required JSON format.",
        ])
        
        return "\n".join(lines)

    def build_complex_analysis_prompt(self, query: str, 
                                       level0_result: Dict,
                                       retrieval_summary: str) -> str:
        """
        Build prompt for complex query deep analysis.
        
        Args:
            query: Original query
            level0_result: Level 0 routing result
            retrieval_summary: Summary of retrieval results
            
        Returns:
            Formatted prompt
        """
        return f"""Analyze this complex query for routing decision.

Query: {query}

Level 0 Assessment:
- Complexity (C): {level0_result.get('C', '-')}
- Information (I): {level0_result.get('I', '-')}
- Confidence: {level0_result.get('sigma_joint', 0):.3f}

Retrieval Summary:
{retrieval_summary}

Provide detailed analysis in JSON format.
"""

    def build_dual_probe_prompt(self, query: str, 
                                 probe_id: int = 1) -> str:
        """
        Build prompt for dual probe validation.
        
        Args:
            query: Query to evaluate
            probe_id: Probe identifier (1 or 2)
            
        Returns:
            Formatted prompt
        """
        variation = ""
        if probe_id == 2:
            variation = """\nApproach this evaluation from a different angle:
- Focus on the practical feasibility of answering this query accurately
- Consider what domain expertise might be required\n"""
        
        return f"""Evaluate this query for CI routing:

Query: {query}

Assess:
1. COMPLEXITY: Does this require multi-step reasoning, domain expertise, or analysis? (C=1) 
   Or is it a simple lookup, factual recall, or straightforward transformation? (C=0)

2. INFORMATION: Does the query contain enough context for a complete and accurate response? (I=1)
   Or is it vague, missing key details, or requires clarification? (I=0)
{variation}
Provide your assessment in the required JSON format.
"""

    def build_simple_evaluation_prompt(self, query: str) -> str:
        """
        Build minimal prompt for quick evaluation.
        
        Args:
            query: Query to evaluate
            
        Returns:
            Formatted prompt
        """
        return f"""Query: {query}

Classify this query:
- C (Complexity): 0=Low (simple/factual), 1=High (complex/reasoning)
- I (Information): 0=Insufficient (needs clarification), 1=Sufficient (complete context)

Respond with JSON: {{"C": 0/1, "I": 0/1, "confidence": 0.0-1.0, "reasoning": "brief"}}"""

    def get_system_prompt(self, prompt_type: str = "ci_evaluation") -> str:
        """
        Get system prompt for specified type.
        
        Args:
            prompt_type: Type of prompt (ci_evaluation, complex_analysis, dual_probe)
            
        Returns:
            System prompt string
        """
        prompts = {
            "ci_evaluation": self.CI_EVALUATION_SYSTEM,
            "complex_analysis": self.COMPLEX_ANALYSIS_SYSTEM,
            "dual_probe": self.DUAL_PROBE_SYSTEM,
        }
        return prompts.get(prompt_type, self.CI_EVALUATION_SYSTEM)

    @staticmethod
    def format_retrieval_evidence(evidence: Dict) -> str:
        """Format retrieval evidence for display in prompt."""
        parts = []
        
        vector = evidence.get('vector')
        if vector:
            parts.append(f"Vector: sim_max={vector.get('sim_max', 0):.3f}, "
                        f"gap={vector.get('gap', 0):.3f}")
        
        keyword = evidence.get('keyword')
        if keyword:
            parts.append(f"Keyword: score_max={keyword.get('score_max', 0):.2f}, "
                        f"coverage={keyword.get('coverage', 0):.2f}")
        
        return " | ".join(parts) if parts else "No retrieval evidence"


# Convenience functions
def build_level2_context(query: str, 
                         level0_result: Dict,
                         level1_result: Dict) -> CIArbitrationContext:
    """
    Build complete Level 2 context from Level 0 and Level 1 results.
    
    Args:
        query: Original query
        level0_result: Result from Level 0 router
        level1_result: Result from Level 1 retrieval
        
    Returns:
        CIArbitrationContext
    """
    level0 = Level0Context(
        C=level0_result.get('C', 0),
        I=level0_result.get('I', 0),
        C_continuous=level0_result.get('C_continuous', 0.0),
        I_continuous=level0_result.get('I_continuous', 0.0),
        sigma_c=level0_result.get('sigma_c', 0.0),
        sigma_i=level0_result.get('sigma_i', 0.0),
        sigma_joint=level0_result.get('sigma_joint', 0.0),
        escalate=level0_result.get('escalate', True),
        mode=level0_result.get('mode', 'UNKNOWN'),
        features=level0_result.get('features', [])
    )
    
    # 修复字段名映射: Level 1 实际返回 'I' 和 'sigma_i'，而非 'I_mean' 和 'sigma_I'
    # 兼容两种命名方式以支持不同调用场景
    level1 = Level1Context(
        I_mean=level1_result.get('I', level1_result.get('I_mean', 0.5)),
        sigma_I=level1_result.get('sigma_i', level1_result.get('sigma_I', 0.0)),
        vector=level1_result.get('vector'),
        keyword=level1_result.get('keyword'),
        conflict_detected=level1_result.get('conflict_detected', False),
        source_weights=level1_result.get('source_weights', {})
    )
    
    retrieval_evidence = level1_result.get('retrieval_evidence', {})
    
    return CIArbitrationContext(
        query=query,
        level0=level0,
        level1=level1,
        retrieval_evidence=retrieval_evidence,
        parse_failures=level1_result.get('parse_failures', 0)
    )
