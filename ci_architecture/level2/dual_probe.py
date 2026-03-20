"""Dual Probe Validation for Level 2 confidence verification.

Implements consistency checking through independent LLM probes.
"""

from typing import Dict, Tuple, Optional
from dataclasses import dataclass

from .llm_client import LLMClient, LLMResponse
from .prompt_builder import PromptBuilder
from .response_parser import ResponseParser, ParsedResponse


@dataclass
class DualProbeResult:
    """Result from dual probe validation."""
    C: int
    I: int
    confidence: float
    consistency: float  # 0.0 - 1.0
    probe1: ParsedResponse
    probe2: ParsedResponse
    reasoning: str
    success: bool
    needs_escalation: bool  # True if inconsistent


class DualProbeValidator:
    """
    Validate LLM assessments through dual independent probes.
    
    Consistency check:
    - Both probes agree on C (±0.35)
    - Both probes agree on I (±0.35)
    - Confidence values similar (±0.2, ±0.30)
    - Total consistency >= 0.8
    
    If inconsistent: escalate to fallback with reduced confidence
    """
    
    DEFAULT_CONSISTENCY_THRESHOLD = 0.8
    
    def __init__(self, 
                 llm_client: Optional[LLMClient] = None,
                 consistency_threshold: float = DEFAULT_CONSISTENCY_THRESHOLD):
        """
        Initialize dual probe validator.
        
        Args:
            llm_client: LLM client instance
            consistency_threshold: Minimum consistency score (0-1)
        """
        self.llm = llm_client or LLMClient(model_alias="dual-probe")
        self.prompt_builder = PromptBuilder()
        self.response_parser = ResponseParser()
        self.consistency_threshold = consistency_threshold
    
    def validate(self, query: str, 
                 system_prompt: Optional[str] = None) -> DualProbeResult:
        """
        Execute dual probe validation.
        
        Args:
            query: Query to evaluate
            system_prompt: Optional system prompt override
            
        Returns:
            DualProbeResult with consistency assessment
        """
        # Get system prompt
        if system_prompt is None:
            system_prompt = self.prompt_builder.get_system_prompt("dual_probe")
        
        # Execute probe 1
        prompt1 = self.prompt_builder.build_dual_probe_prompt(query, probe_id=1)
        response1 = self.llm.complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt1}
            ]
        )
        parsed1 = self.response_parser.parse(response1.content)
        
        # Execute probe 2 (different angle)
        prompt2 = self.prompt_builder.build_dual_probe_prompt(query, probe_id=2)
        response2 = self.llm.complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt2}
            ]
        )
        parsed2 = self.response_parser.parse(response2.content)
        
        # Calculate consistency
        consistency = self._calculate_consistency(parsed1, parsed2)
        
        # Determine final values
        C, I, confidence = self._aggregate_results(parsed1, parsed2, consistency)
        
        # Check if escalation needed
        needs_escalation = consistency < self.consistency_threshold
        
        # Build reasoning
        reasoning = self._build_reasoning(parsed1, parsed2, consistency)
        
        return DualProbeResult(
            C=C,
            I=I,
            confidence=confidence,
            consistency=consistency,
            probe1=parsed1,
            probe2=parsed2,
            reasoning=reasoning,
            success=parsed1.success and parsed2.success,
            needs_escalation=needs_escalation
        )
    
    def _calculate_consistency(self, 
                               probe1: ParsedResponse, 
                               probe2: ParsedResponse) -> float:
        """
        Calculate consistency score between two probes.
        
        Returns:
            Score 0.0 - 1.0
        """
        return ResponseParser.calculate_consistency(probe1, probe2)
    
    def _aggregate_results(self, 
                          probe1: ParsedResponse,
                          probe2: ParsedResponse,
                          consistency: float) -> Tuple[int, int, float]:
        """
        Aggregate results from two probes.
        
        Strategy:
        - If consistent: average confidence, use agreed values
        - If inconsistent: conservative values, penalize confidence
        """
        if consistency >= self.consistency_threshold:
            # High consistency - trust the results
            C = probe1.C if probe1.C == probe2.C else 1  # Conservative: high complexity
            I = probe1.I if probe1.I == probe2.I else 0  # Conservative: insufficient
            confidence = (probe1.confidence + probe2.confidence) / 2
        else:
            # Low consistency - conservative fallback
            C = 1  # Assume high complexity
            I = 0  # Assume insufficient info
            # Penalize confidence
            confidence = min(probe1.confidence, probe2.confidence) * 0.6
        
        return C, I, max(0.0, min(1.0, confidence))
    
    def _build_reasoning(self,
                        probe1: ParsedResponse,
                        probe2: ParsedResponse,
                        consistency: float) -> str:
        """Build combined reasoning from both probes."""
        parts = [
            f"Probe 1: C={probe1.C}, I={probe1.I}, conf={probe1.confidence:.3f}",
            f"Probe 2: C={probe2.C}, I={probe2.I}, conf={probe2.confidence:.3f}",
            f"Consistency: {consistency:.2f} (threshold: {self.consistency_threshold})",
        ]
        
        if consistency >= self.consistency_threshold:
            parts.append("Probes consistent - results trusted")
        else:
            parts.append("Probes inconsistent - using conservative values")
        
        return " | ".join(parts)
    
    def quick_validate(self, query: str) -> Tuple[bool, float]:
        """
        Quick validation returning only consistency status.
        
        Returns:
            (is_consistent, consistency_score)
        """
        result = self.validate(query)
        return not result.needs_escalation, result.consistency


class ConfidenceCalibrator:
    """
    Calibrate LLM confidence based on retrieval agreement.
    
    Adjusts confidence when LLM result conflicts with Level 1 evidence.
    """
    
    def __init__(self, conflict_penalty: float = 0.6):
        """
        Initialize calibrator.
        
        Args:
            conflict_penalty: Multiplier applied when conflict detected
        """
        self.conflict_penalty = conflict_penalty
    
    def calibrate(self,
                  llm_C: int,
                  llm_I: float,
                  llm_confidence: float,
                  level1_C: int,
                  level1_I: float,
                  level1_confidence: float) -> Tuple[float, bool]:
        """
        Calibrate confidence based on cross-validation with Level 1.
        
        Args:
            llm_C: LLM complexity assessment
            llm_I: LLM information sufficiency (continuous 0-1)
            llm_confidence: LLM confidence
            level1_C: Level 1 complexity (0 or 1)
            level1_I: Level 1 information sufficiency (continuous 0-1)
            level1_confidence: Level 1 confidence
            
        Returns:
            (calibrated_confidence, conflict_detected)
        """
        conflict = False
        
        # Check C disagreement (discrete vs discrete)
        if abs(llm_C - level1_C) >= 1:
            conflict = True
        
        # Check I disagreement (continuous threshold at 0.7)
        llm_I_discrete = 1 if llm_I >= 0.7 else 0
        level1_I_discrete = 1 if level1_I >= 0.7 else 0
        if llm_I_discrete != level1_I_discrete:
            conflict = True
        
        # Apply calibration
        if conflict:
            calibrated = llm_confidence * self.conflict_penalty
            # Blend with Level 1 confidence
            calibrated = 0.6 * calibrated + 0.4 * level1_confidence
        else:
            # Agree - boost slightly
            calibrated = min(1.0, llm_confidence * 1.05)
        
        return max(0.0, min(1.0, calibrated)), conflict
    
    def cross_validate_with_retrieval(self,
                                      llm_result: ParsedResponse,
                                      retrieval_I_mean: float,
                                      retrieval_confidence: float) -> Dict:
        """
        Cross-validate LLM result with retrieval evidence.
        
        Returns:
            Dict with calibrated values and conflict info
        """
        # Convert LLM I to continuous
        llm_I_continuous = 0.8 if llm_result.I == 1 else 0.3
        
        calibrated_conf, conflict = self.calibrate(
            llm_C=llm_result.C,
            llm_I=llm_I_continuous,
            llm_confidence=llm_result.confidence,
            level1_C=0,  # Level 1 doesn't directly assess C
            level1_I=retrieval_I_mean,
            level1_confidence=retrieval_confidence
        )
        
        return {
            'C': llm_result.C,
            'I': llm_result.I,
            'I_continuous': llm_I_continuous,
            'confidence': calibrated_conf,
            'original_confidence': llm_result.confidence,
            'conflict_detected': conflict,
            'reasoning': llm_result.reasoning
        }
