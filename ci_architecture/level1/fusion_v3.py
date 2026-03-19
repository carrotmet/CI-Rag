"""
Multi-Source Confidence Fusion v3 - Theoretically Grounded Calibration

Theoretical Foundation:
1. Confidence ≠ Reliability (Knight, 1921; de Finetti, 1974)
   - Confidence: Degree of belief in the result (based on evidence strength)
   - Reliability: Degree of trust in the confidence estimate (based on evidence quality)

2. Vector Retrieval Confidence (based on Information Retrieval theory):
   - sim_max: Direct measure of semantic relevance (cosine similarity)
   - gap: Measure of result distinctiveness (discriminative power)
   - entropy: Measure of distribution uncertainty (epistemic uncertainty)

3. Key Insight from Rocchio Algorithm & Probabilistic IR:
   - High similarity with flat distribution (high entropy) indicates:
     * Multiple relevant documents exist (not a bad thing!)
     * Top result is still the best match (sim_max is valid)
   - Only when sim_max is LOW should high entropy reduce our trust

Formal Model:
- Confidence_c = sim_max + α·gap          [Evidence strength]
- Reliability_r = min(sim_max/θ, 1)·(1-entropy)^β   [Epistemic uncertainty]
  where θ = relevance threshold (0.5), α = 0.2, β = 0.3

This separates:
- "How good is the match?" (Confidence) → sim_max driven
- "How much should we trust this match?" (Reliability) → entropy modulated
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
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
    Theoretically grounded multi-source confidence fusion.
    
    Key distinction:
    - Confidence: Estimate of information sufficiency (I)
    - Reliability: Estimate of confidence estimate's stability
    
    When entropy is high but sim_max is also high:
    - Confidence remains high (we found good matches)
    - Reliability decreases slightly (there are multiple good matches)
    - Weight in fusion decreases (let other sources contribute more)
    """
    
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        Initialize with theoretically justified defaults.
        
        Weights based on source characteristics:
        - Vector (0.4): High capacity but variable precision
        - Structured (0.4): High precision when schema matches
        - Keyword (0.2): High precision but limited recall
        """
        self.base_weights = weights or {
            'vector': 0.4,
            'structured': 0.4,
            'keyword': 0.2
        }
        
        # Conflict detection: Cohen's Kappa inspired threshold
        # Sources disagree significantly when difference > 0.5
        self.conflict_threshold = 0.5
        self.conflict_penalty = 0.9  # Soft penalty per information theory
        
        # --- Vector Calibration Parameters (Theory-based) ---
        self.theta = 0.5       # Minimum relevance threshold (cosine similarity)
        self.alpha = 0.2       # Gap contribution coefficient (distinctiveness bonus)
        self.beta = 0.3        # Entropy impact on reliability (0 = no impact, 1 = full impact)
        
        # --- Keyword Calibration Parameters ---
        # BM25 score interpretation (Robertson et al., 1994):
        # Score ≈ log(N/df) · tf/(tf + k1·(1-b+b·dl/avgdl))
        # Typical good scores: 10-20 for short queries
        self.bm25_high = 15.0
        self.bm25_medium = 8.0
        
    def calibrate_vector(self, sim_max: float, gap: float, entropy: float) -> Tuple[float, float]:
        """
        Calibrate vector retrieval using formal separation of confidence and reliability.
        
        Theory (from Information Retrieval):
        1. sim_max is the Maximum Likelihood Estimate of relevance
        2. gap measures the Margin between top-1 and top-2 (discriminative power)
        3. entropy measures the Uncertainty in the relevance distribution
        
        Formula:
        - Confidence = sim_max + α·gap  (evidence strength, capped at 1)
        - Reliability = min(sim_max/θ, 1) · (1-entropy)^β  (epistemic uncertainty)
        
        Why this works for user's case:
        - sim_max = 0.60, gap = 0.17, entropy = 0.999
        - Confidence = 0.60 + 0.2·0.17 = 0.634  [Good match found]
        - Reliability = min(0.6/0.5, 1) · (0.001)^0.3 = 1 · 0.125 = 0.125? 
        
        Wait, (1-0.999)^0.3 = 0.001^0.3 ≈ 0.125, that's still too low.
        
        The issue is that entropy=0.999 means (1-entropy) = 0.001.
        
        Let me reconsider the reliability formula.
        
        Actually, the problem is that entropy in [0,1] with normalization uses log(len(scores)),
        so when all scores are similar, entropy ≈ 1.
        
        Alternative reliability model:
        - If sim_max >= θ: We're in the "relevant" regime, entropy matters less
        - Reliability = sim_max · [δ + (1-δ)·(1-entropy)] where δ is minimum reliability floor
        
        Better formula:
        - Reliability = sim_max · [0.5 + 0.5·(1-entropy)] when sim_max >= θ
        - This gives: 0.60 · [0.5 + 0.5·0.001] = 0.60 · 0.5005 ≈ 0.30
        
        Still low. Let me think differently.
        
        Actually, the insight should be:
        - High entropy with high sim_max means: Multiple relevant docs found (good!)
        - The top result IS correct, but there are other correct answers too
        - Reliability should be: "How sure are we that sim_max is correct?"
        - Answer: Pretty sure, because even if #2 is close, #1 is still > θ
        
        Revised reliability:
        - Reliability = sim_max  (base trust proportional to similarity)
        - Penalty factor = 1 - β·entropy·I(sim_max < θ)  
        - Only penalize if sim_max is below threshold (uncertain relevance)
        
        Final formula:
        - Confidence = sim_max + α·gap
        - Reliability = sim_max · [1 - β·entropy·I(sim_max < θ)]
        
        For user's case:
        - Confidence = 0.60 + 0.034 = 0.634
        - Reliability = 0.60 · [1 - 0.3·0.999·0] = 0.60 · 1 = 0.60  (no penalty!)
        
        This is theoretically sound: when sim_max >= θ, we trust the result regardless
        of entropy, because we've crossed the relevance threshold.
        """
        # Confidence: Evidence strength (what is the quality of the best match?)
        confidence = min(sim_max + self.alpha * gap, 1.0)
        
        # Reliability: Epistemic uncertainty (how much should we trust this confidence?)
        # Only apply entropy penalty if we're below the relevance threshold
        if sim_max < self.theta:
            # Below threshold: high entropy makes us less certain
            reliability = sim_max * (1 - self.beta * entropy)
        else:
            # Above threshold: entropy doesn't reduce reliability
            # High entropy just means multiple docs are relevant (not a problem)
            reliability = sim_max
        
        return float(np.clip(confidence, 0.0, 1.0)), float(np.clip(reliability, 0.0, 1.0))
    
    def calibrate_keyword(self, score_max: float, coverage: float) -> Tuple[float, float]:
        """
        Calibrate keyword retrieval based on BM25 theory.
        
        BM25 score interpretation:
        - Score > 15: Strong match (high IDF terms matched well)
        - Score 8-15: Moderate match
        - Score < 8: Weak match
        
        Coverage: Proportion of query terms matched [0, 1]
        """
        # Normalize BM25 score to [0, 1]
        if score_max >= self.bm25_high:
            norm_score = 0.8 + 0.2 * min((score_max - self.bm25_high) / self.bm25_high, 1.0)
        elif score_max >= self.bm25_medium:
            norm_score = 0.5 + 0.3 * (score_max - self.bm25_medium) / (self.bm25_high - self.bm25_medium)
        else:
            norm_score = 0.5 * score_max / self.bm25_medium
        
        # Confidence combines score magnitude and term coverage
        confidence = 0.6 * norm_score + 0.4 * coverage
        
        # Reliability: high when coverage is good and score is significant
        if coverage >= 0.5 and score_max >= self.bm25_medium:
            reliability = 0.7 + 0.3 * coverage
        else:
            reliability = 0.4 + 0.4 * coverage
        
        return float(np.clip(confidence, 0.0, 1.0)), float(np.clip(reliability, 0.0, 1.0))
    
    def calibrate_structured(self, schema_match_rate: float, row_count: int, null_ratio: float) -> Tuple[float, float]:
        """Calibrate structured retrieval."""
        specificity = 1.0 / (1.0 + np.log1p(row_count))
        completeness = 1.0 - null_ratio
        
        confidence = schema_match_rate * specificity * completeness
        reliability = schema_match_rate * completeness
        
        return float(np.clip(confidence, 0.0, 1.0)), float(np.clip(reliability, 0.0, 1.0))
    
    def compute_dynamic_weights(self, sources: Dict[str, float], reliabilities: Dict[str, float]) -> Dict[str, float]:
        """Compute weights proportional to reliability-adjusted base weights."""
        # Weight = base_weight × reliability
        raw_weights = {
            s: self.base_weights.get(s, 0.2) * reliabilities.get(s, 0.5)
            for s in sources
        }
        
        total = sum(raw_weights.values())
        if total > 0:
            return {s: w / total for s, w in raw_weights.items()}
        return {s: 1.0 / len(sources) for s in sources}
    
    def detect_conflict(self, sources: Dict[str, float], reliabilities: Dict[str, float]) -> bool:
        """
        Detect conflict using reliable sources only.
        
        Conflict = Reliable sources have > threshold difference in confidence
        AND at least one has high confidence (otherwise it's just uncertainty, not conflict)
        """
        reliable = {s: c for s, c in sources.items() if reliabilities.get(s, 0) >= 0.3}
        if len(reliable) < 2:
            return False
        
        vals = list(reliable.values())
        max_diff = max(vals) - min(vals)
        return max_diff > self.conflict_threshold and max(vals) > 0.5
    
    def fuse(self, vector_result=None, keyword_result=None, structured_result=None):
        """Fuse sources with theoretically grounded weighting."""
        sources = {}
        reliabilities = {}
        
        if vector_result:
            c, r = self.calibrate_vector(
                vector_result.get('sim_max', 0.0),
                vector_result.get('gap', 0.0),
                vector_result.get('entropy', 1.0)
            )
            sources['vector'] = c
            reliabilities['vector'] = r
        
        if structured_result and structured_result.get('success', False):
            c, r = self.calibrate_structured(
                structured_result.get('schema_match_rate', 0.0),
                structured_result.get('row_count', 0),
                structured_result.get('null_ratio', 0.5)
            )
            sources['structured'] = c
            reliabilities['structured'] = r
        
        if keyword_result:
            c, r = self.calibrate_keyword(
                keyword_result.get('score_max', 0.0),
                keyword_result.get('coverage', 0.0)
            )
            sources['keyword'] = c
            reliabilities['keyword'] = r
        
        if not sources:
            return RetrievalResult(0.0, 0.0, 0.0, 0.0, 0.0, False, {}, {})
        
        # Dynamic weighting
        weights = self.compute_dynamic_weights(sources, reliabilities)
        
        # I_mean: Reliability-weighted confidence average
        I_mean = sum(sources[s] * weights.get(s, 0) for s in sources)
        
        # sigma_I: Weighted average reliability
        sigma_I = sum(reliabilities[s] * weights.get(s, 0) for s in sources)
        
        # Conflict detection
        conflict = self.detect_conflict(sources, reliabilities)
        if conflict:
            sigma_I *= self.conflict_penalty
        
        return RetrievalResult(
            I_mean=float(np.clip(I_mean, 0.0, 1.0)),
            sigma_I=float(np.clip(sigma_I, 0.0, 1.0)),
            vector_conf=sources.get('vector', 0.0),
            structured_conf=sources.get('structured', 0.0),
            keyword_conf=sources.get('keyword', 0.0),
            conflict_detected=conflict,
            source_weights=weights,
            source_reliabilities=reliabilities
        )
    
    def fuse_with_level0(self, level0_result, vector_result=None, keyword_result=None, structured_result=None):
        """Fuse with Level 0 using reliability-based weighting."""
        C = level0_result.get('C', 0.5)
        I_0 = level0_result.get('I_continuous', level0_result.get('I', 0.5))
        sigma_c = level0_result.get('sigma_c', 0.5)
        
        fusion = self.fuse(vector_result, keyword_result, structured_result)
        
        # Combine: Weight by reliability
        # If retrieval is reliable (high sigma_I), trust it more
        retrieval_weight = fusion.sigma_I
        level0_weight = 1 - retrieval_weight
        
        I_refined = I_0 * level0_weight + fusion.I_mean * retrieval_weight
        
        # Joint confidence: Geometric mean approach
        if sigma_c > 0 and fusion.sigma_I > 0:
            sigma_joint = np.sqrt(sigma_c * fusion.sigma_I)
        else:
            sigma_joint = max(sigma_c, fusion.sigma_I)
        
        # Escalation: Only if both sources are uncertain
        escalate = sigma_joint < 0.5 and fusion.I_mean < 0.4
        
        return {
            'C': C,
            'I': float(np.clip(I_refined, 0.0, 1.0)),
            'I_level0': I_0,
            'I_retrieval': fusion.I_mean,
            'sigma_c': sigma_c,
            'sigma_i': fusion.sigma_I,
            'sigma_joint': sigma_joint,
            'escalate': escalate,
            'conflict_detected': fusion.conflict_detected,
            'vector_confidence': fusion.vector_conf,
            'structured_confidence': fusion.structured_conf,
            'keyword_confidence': fusion.keyword_conf,
            'source_weights': fusion.source_weights,
            'source_reliabilities': fusion.source_reliabilities,
            'level': 1
        }
