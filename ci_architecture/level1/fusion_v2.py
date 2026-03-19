"""
Multi-Source Confidence Fusion v2 - Improved calibration and smoothing.

Key improvements:
1. Smarter entropy handling - high entropy with good sim_max is not bad
2. Gap-based distinctiveness bonus
3. Source reliability-based weighting
4. Smooth degradation - when one source is weak, others compensate
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List
import numpy as np


@dataclass
class RetrievalResult:
    """Unified retrieval result."""
    I_mean: float
    sigma_I: float
    vector_conf: float
    structured_conf: float
    keyword_conf: float
    conflict_detected: bool
    source_weights: Dict[str, float]
    source_reliabilities: Dict[str, float]


class ConfidenceFusion:
    """
    Fuse multi-source retrieval signals into unified I estimate.
    
    v2 Improvements:
    - Entropy is informative but not decisive for confidence
    - Gap provides distinctiveness information
    - Sim_max is the primary confidence indicator
    - Reliability-weighted fusion adjusts source weights dynamically
    """
    
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        Initialize fusion with source weights.
        
        Args:
            weights: Dict with 'vector', 'structured', 'keyword' base weights
        """
        self.base_weights = weights or {
            'vector': 0.4,
            'structured': 0.4,
            'keyword': 0.2
        }
        
        # Conflict detection thresholds
        self.conflict_threshold = 0.5
        self.conflict_absolute_low = 0.3
        self.conflict_penalty = 0.85  # Softer penalty
        
        # Vector calibration parameters
        self.sim_high_threshold = 0.7
        self.sim_medium_threshold = 0.5
        self.gap_significant = 0.1  # Gap > 0.1 is considered significant
        
        # Reliability thresholds
        self.min_reliability = 0.1
    
    def calibrate_vector(self, sim_max: float, gap: float, entropy: float) -> Tuple[float, float]:
        """
        Calibrate vector retrieval confidence with smarter entropy handling.
        
        Logic:
        - sim_max is the PRIMARY indicator of result quality
        - gap indicates distinctiveness (how much better is top result)
        - entropy indicates distribution sharpness, but high entropy with 
          good sim_max just means multiple relevant docs exist (not bad!)
        
        Args:
            sim_max: Max similarity score (0-1)
            gap: Gap between top-1 and top-2
            entropy: Distribution entropy (0-1)
            
        Returns:
            Tuple of (confidence, reliability)
        """
        # Base confidence from sim_max (primary factor)
        # Use sim_max directly as it's already normalized cosine similarity
        base_conf = sim_max
        
        # Gap bonus: if gap is significant, add small bonus
        # This indicates the top result is clearly better than others
        if gap >= self.gap_significant:
            gap_bonus = min(gap * 0.3, 0.15)  # Max 0.15 bonus
        else:
            gap_bonus = 0
        
        # Entropy affects reliability, not confidence directly
        # High entropy means distribution is flat (multiple similar scores)
        # This is only problematic if sim_max is low
        if sim_max >= self.sim_medium_threshold:
            # Good sim_max: entropy is less concerning (multiple relevant docs)
            # Reliability decreases slightly with entropy but not dramatically
            reliability = 0.7 + 0.3 * (1 - entropy)  # 0.7 to 1.0 range
        else:
            # Low sim_max: high entropy is more concerning (unclear best match)
            reliability = (1 - entropy) * 0.5 + 0.3  # 0.3 to 0.8 range
        
        # Combined confidence
        confidence = min(base_conf + gap_bonus, 1.0)
        
        return float(np.clip(confidence, 0.0, 1.0)), float(np.clip(reliability, 0.0, 1.0))
    
    def calibrate_keyword(self, score_max: float, coverage: float) -> Tuple[float, float]:
        """
        Calibrate keyword retrieval confidence.
        
        Returns:
            Tuple of (confidence, reliability)
        """
        # Normalize BM25 score
        # BM25 scores: 0-5 (low), 5-10 (medium), 10+ (high)
        if score_max >= 10:
            score_normalized = 0.8 + min((score_max - 10) / 20, 0.2)  # 0.8-1.0
        elif score_max >= 5:
            score_normalized = 0.5 + (score_max - 5) / 5 * 0.3  # 0.5-0.8
        else:
            score_normalized = score_max / 10  # 0-0.5
        
        # Coverage indicates how many query terms were matched
        coverage_factor = coverage
        
        # Confidence combines normalized score and coverage
        confidence = score_normalized * 0.6 + coverage_factor * 0.4
        
        # Reliability: high coverage + decent score = reliable
        if coverage >= 0.6 and score_max >= 5:
            reliability = 0.7 + 0.3 * coverage
        else:
            reliability = 0.4 + 0.4 * coverage
        
        return float(np.clip(confidence, 0.0, 1.0)), float(np.clip(reliability, 0.0, 1.0))
    
    def calibrate_structured(self, schema_match_rate: float, row_count: int, null_ratio: float) -> Tuple[float, float]:
        """
        Calibrate structured retrieval confidence.
        
        Returns:
            Tuple of (confidence, reliability)
        """
        # Base confidence from schema match
        base_conf = schema_match_rate
        
        # Specificity factor - fewer results = more specific
        specificity = 1.0 / (1.0 + np.log1p(row_count))
        
        # Completeness factor
        completeness = 1.0 - null_ratio
        
        # Combined confidence
        confidence = base_conf * specificity * completeness
        
        # Reliability based on schema match quality
        reliability = schema_match_rate * completeness
        
        return float(np.clip(confidence, 0.0, 1.0)), float(np.clip(reliability, 0.0, 1.0))
    
    def compute_dynamic_weights(self, 
                                 sources: Dict[str, float],
                                 reliabilities: Dict[str, float]) -> Dict[str, float]:
        """
        Compute dynamic weights based on source reliabilities.
        
        If a source has low reliability, reduce its weight and redistribute.
        """
        # Filter out unreliable sources
        reliable_sources = {
            s: conf for s, conf in sources.items() 
            if reliabilities.get(s, 0) >= self.min_reliability
        }
        
        if not reliable_sources:
            # All sources are unreliable, use normalized raw confidences
            total_conf = sum(sources.values())
            if total_conf > 0:
                return {s: conf / total_conf for s, conf in sources.items()}
            return {s: 1.0 / len(sources) for s in sources}
        
        # Compute effective weights: base_weight * reliability
        effective_weights = {}
        for s in reliable_sources:
            base_w = self.base_weights.get(s, 0.2)
            rel = reliabilities[s]
            effective_weights[s] = base_w * rel
        
        # Normalize
        total = sum(effective_weights.values())
        if total > 0:
            return {s: w / total for s, w in effective_weights.items()}
        return {s: 1.0 / len(reliable_sources) for s in reliable_sources}
    
    def detect_conflict(self, 
                       sources: Dict[str, float],
                       reliabilities: Dict[str, float]) -> bool:
        """
        Smarter conflict detection.
        
        Conflict occurs when:
        1. Reliable sources disagree significantly (diff > threshold)
        2. At least one source has decent confidence (> absolute_low)
        """
        if len(sources) < 2:
            return False
        
        # Only consider reliable sources for conflict detection
        reliable_confs = {
            s: conf for s, conf in sources.items() 
            if reliabilities.get(s, 0) >= self.min_reliability
        }
        
        if len(reliable_confs) < 2:
            return False
        
        conf_values = list(reliable_confs.values())
        max_conf = max(conf_values)
        min_conf = min(conf_values)
        max_diff = max_conf - min_conf
        
        # Conflict if: significant difference AND at least one is confident
        return max_diff > self.conflict_threshold and max_conf > self.conflict_absolute_low
    
    def fuse(self, 
             vector_result: Optional[Dict] = None,
             keyword_result: Optional[Dict] = None,
             structured_result: Optional[Dict] = None) -> RetrievalResult:
        """
        Fuse sources into unified I estimate with reliability weighting.
        """
        # Calibrate each source, getting both confidence and reliability
        sources = {}
        reliabilities = {}
        
        if vector_result:
            conf, rel = self.calibrate_vector(
                vector_result.get('sim_max', 0.0),
                vector_result.get('gap', 0.0),
                vector_result.get('entropy', 1.0)
            )
            sources['vector'] = conf
            reliabilities['vector'] = rel
        
        if structured_result and structured_result.get('success', False):
            conf, rel = self.calibrate_structured(
                structured_result.get('schema_match_rate', 0.0),
                structured_result.get('row_count', 0),
                structured_result.get('null_ratio', 0.5)
            )
            sources['structured'] = conf
            reliabilities['structured'] = rel
        
        if keyword_result:
            conf, rel = self.calibrate_keyword(
                keyword_result.get('score_max', 0.0),
                keyword_result.get('coverage', 0.0)
            )
            sources['keyword'] = conf
            reliabilities['keyword'] = rel
        
        if not sources:
            return RetrievalResult(
                I_mean=0.0,
                sigma_I=0.0,
                vector_conf=0.0,
                keyword_conf=0.0,
                structured_conf=0.0,
                conflict_detected=False,
                source_weights={},
                source_reliabilities={}
            )
        
        # Compute dynamic weights based on reliabilities
        dynamic_weights = self.compute_dynamic_weights(sources, reliabilities)
        
        # Weighted mean for I estimation
        I_mean = sum(
            conf * dynamic_weights.get(s, 0)
            for s, conf in sources.items()
        )
        
        # Conflict detection
        conflict_detected = self.detect_conflict(sources, reliabilities)
        
        # Confidence calculation - use weighted average of confidences
        if dynamic_weights:
            avg_confidence = sum(
                conf * dynamic_weights.get(s, 0)
                for s, conf in sources.items()
            )
            # Also consider average reliability
            avg_reliability = sum(
                reliabilities.get(s, 0) * dynamic_weights.get(s, 0)
                for s in dynamic_weights
            )
            # Final sigma combines confidence and reliability
            base_sigma = 0.6 * avg_confidence + 0.4 * avg_reliability
        else:
            base_sigma = 0.5
        
        # Apply conflict penalty (softer)
        sigma_penalty = self.conflict_penalty if conflict_detected else 1.0
        sigma_I = base_sigma * sigma_penalty
        
        return RetrievalResult(
            I_mean=float(np.clip(I_mean, 0.0, 1.0)),
            sigma_I=float(np.clip(sigma_I, 0.0, 1.0)),
            vector_conf=sources.get('vector', 0.0),
            structured_conf=sources.get('structured', 0.0),
            keyword_conf=sources.get('keyword', 0.0),
            conflict_detected=conflict_detected,
            source_weights=dynamic_weights,
            source_reliabilities=reliabilities
        )
    
    def fuse_with_level0(self,
                        level0_result: Dict,
                        vector_result: Optional[Dict] = None,
                        keyword_result: Optional[Dict] = None,
                        structured_result: Optional[Dict] = None) -> Dict:
        """
        Fuse Level 1 retrieval results with Level 0 context.
        """
        # Get base values from Level 0
        C = level0_result.get('C', 0.5)
        I_0 = level0_result.get('I_continuous', level0_result.get('I', 0.5))
        sigma_c = level0_result.get('sigma_c', 0.5)
        
        # Fuse retrieval sources
        fusion = self.fuse(vector_result, keyword_result, structured_result)
        
        # Combine Level 0 I with retrieval-based I
        # If retrieval has good confidence, trust it more
        if fusion.sigma_I >= 0.6:
            # Retrieval is reliable, use it primarily
            retrieval_weight = 0.7
            level0_weight = 0.3
        elif fusion.sigma_I >= 0.4:
            # Moderate confidence, balanced weighting
            retrieval_weight = 0.5
            level0_weight = 0.5
        else:
            # Low retrieval confidence, trust Level 0 more
            retrieval_weight = 0.3
            level0_weight = 0.7
        
        I_refined = I_0 * level0_weight + fusion.I_mean * retrieval_weight
        
        # Update joint confidence
        sigma_i = fusion.sigma_I
        # Use the higher of the two confidences if both are reasonable
        if sigma_c > 0.4 and sigma_i > 0.4:
            sigma_joint = max(sigma_c, sigma_i) * 0.9  # Slight penalty for uncertainty
        else:
            sigma_joint = min(sigma_c, sigma_i)
        
        # Escalation decision
        # Don't escalate if we have good retrieval results even with moderate sigma
        should_escalate = sigma_joint < 0.6 and fusion.I_mean < 0.5
        
        return {
            'C': C,
            'I': float(np.clip(I_refined, 0.0, 1.0)),
            'I_level0': I_0,
            'I_retrieval': fusion.I_mean,
            'sigma_c': sigma_c,
            'sigma_i': sigma_i,
            'sigma_joint': sigma_joint,
            'escalate': should_escalate,
            'conflict_detected': fusion.conflict_detected,
            'vector_confidence': fusion.vector_conf,
            'structured_confidence': fusion.structured_conf,
            'keyword_confidence': fusion.keyword_conf,
            'source_weights': fusion.source_weights,
            'source_reliabilities': fusion.source_reliabilities,
            'level': 1
        }
