"""Multi-Source Confidence Fusion with calibration.

Implements weighted Bayesian fusion of vector and keyword retrieval signals.
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
    keyword_conf: float
    conflict_detected: bool
    source_weights: Dict[str, float]


class ConfidenceFusion:
    """
    Fuse multi-source retrieval signals into unified I estimate.
    
    Default weights:
    - Vector: 0.6 (semantic relevance)
    - Keyword: 0.4 (exact match reliability)
    
    Conflict detection triggers when sources disagree significantly.
    """
    
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        Initialize fusion with source weights.
        
        Args:
            weights: Dict with 'vector' and 'keyword' weights
        """
        self.weights = weights or {
            'vector': 0.6,
            'keyword': 0.4
        }
        
        # Conflict detection thresholds
        self.conflict_threshold = 0.4
        self.conflict_penalty = 0.6
        
        # Calibration parameters (can be learned from data)
        self.vector_threshold_high = 0.7
        self.vector_threshold_low = 0.3
        self.keyword_threshold_high = 0.5
    
    def calibrate_vector(self, sim_max: float, gap: float, entropy: float) -> float:
        """
        Calibrate vector retrieval confidence.
        
        Args:
            sim_max: Max similarity score
            gap: Gap between top-1 and top-2
            entropy: Distribution entropy
            
        Returns:
            Calibrated confidence [0, 1]
        """
        # Base confidence from max similarity
        base_conf = sim_max
        
        # Quality factors
        # - Low entropy = concentrated relevance = higher confidence
        # - Large gap = clear best match = higher confidence
        quality_factor = (1 - entropy) * (0.5 + 0.5 * min(gap * 5, 1.0))
        
        # Combine
        confidence = base_conf * quality_factor
        
        return float(np.clip(confidence, 0.0, 1.0))
    
    def calibrate_keyword(self, score_max: float, coverage: float) -> float:
        """
        Calibrate keyword retrieval confidence.
        
        Args:
            score_max: Max BM25 score
            coverage: Ratio of query terms matched
            
        Returns:
            Calibrated confidence [0, 1]
        """
        # Normalize BM25 score (approximate)
        # BM25 scores can vary widely, so we use sigmoid-like scaling
        score_normalized = min(score_max / 10.0, 1.0)  # Assume 10 is high score
        
        # Coverage bonus - more terms matched = higher confidence
        coverage_factor = coverage
        
        # Combine
        confidence = score_normalized * 0.7 + coverage_factor * 0.3
        
        return float(np.clip(confidence, 0.0, 1.0))
    
    def fuse(self, 
             vector_result: Optional[Dict] = None,
             keyword_result: Optional[Dict] = None) -> RetrievalResult:
        """
        Fuse sources into unified I estimate.
        
        Args:
            vector_result: Vector retrieval result with sim_max, gap, entropy
            keyword_result: Keyword retrieval result with score_max, coverage
            
        Returns:
            RetrievalResult with fused I_mean and sigma_I
        """
        # Calibrate each source
        available_sources = {}
        
        if vector_result:
            conf_vector = self.calibrate_vector(
                vector_result.get('sim_max', 0.0),
                vector_result.get('gap', 0.0),
                vector_result.get('entropy', 1.0)
            )
            available_sources['vector'] = conf_vector
        
        if keyword_result:
            conf_keyword = self.calibrate_keyword(
                keyword_result.get('score_max', 0.0),
                keyword_result.get('coverage', 0.0)
            )
            available_sources['keyword'] = conf_keyword
        
        if not available_sources:
            return RetrievalResult(
                I_mean=0.0,
                sigma_I=0.0,
                vector_conf=0.0,
                keyword_conf=0.0,
                conflict_detected=False,
                source_weights={}
            )
        
        # Normalize weights for available sources
        total_weight = sum(self.weights.get(s, 0) for s in available_sources)
        normalized_weights = {
            s: self.weights.get(s, 0) / total_weight
            for s in available_sources
        }
        
        # Weighted mean for I estimation
        I_mean = sum(
            conf * normalized_weights[s]
            for s, conf in available_sources.items()
        )
        
        # Conflict detection
        if len(available_sources) >= 2:
            conf_values = list(available_sources.values())
            max_diff = max(conf_values) - min(conf_values)
            conflict_detected = max_diff > self.conflict_threshold
        else:
            conflict_detected = False
        
        # Confidence calculation
        # Base confidence: use vector entropy if available
        if vector_result:
            vector_entropy = vector_result.get('entropy', 0.5)
            base_sigma = 1 - vector_entropy
        else:
            base_sigma = 0.5
        
        # Apply conflict penalty
        sigma_penalty = self.conflict_penalty if conflict_detected else 1.0
        sigma_I = base_sigma * sigma_penalty
        
        return RetrievalResult(
            I_mean=float(np.clip(I_mean, 0.0, 1.0)),
            sigma_I=float(np.clip(sigma_I, 0.0, 1.0)),
            vector_conf=available_sources.get('vector', 0.0),
            keyword_conf=available_sources.get('keyword', 0.0),
            conflict_detected=conflict_detected,
            source_weights=normalized_weights
        )
    
    def fuse_with_level0(self,
                        level0_result: Dict,
                        vector_result: Optional[Dict] = None,
                        keyword_result: Optional[Dict] = None) -> Dict:
        """
        Fuse Level 1 retrieval results with Level 0 context.
        
        Args:
            level0_result: Result from Level 0 with C, I, sigma
            vector_result: Optional vector retrieval result
            keyword_result: Optional keyword retrieval result
            
        Returns:
            Updated result with refined I estimate
        """
        # Get base values from Level 0
        C = level0_result.get('C', 0.5)
        I_0 = level0_result.get('I_continuous', level0_result.get('I', 0.5))
        sigma_c = level0_result.get('sigma_c', 0.5)
        
        # Fuse retrieval sources
        fusion = self.fuse(vector_result, keyword_result)
        
        # Combine Level 0 I with retrieval-based I
        # Weight by confidence - if retrieval is confident, use it more
        retrieval_weight = fusion.sigma_I
        level0_weight = 1 - retrieval_weight
        
        I_refined = I_0 * level0_weight + fusion.I_mean * retrieval_weight
        
        # Update joint confidence
        sigma_i = fusion.sigma_I
        sigma_joint = min(sigma_c, sigma_i)
        
        return {
            'C': C,
            'I': float(np.clip(I_refined, 0.0, 1.0)),
            'I_level0': I_0,
            'I_retrieval': fusion.I_mean,
            'sigma_c': sigma_c,
            'sigma_i': sigma_i,
            'sigma_joint': sigma_joint,
            'escalate': sigma_joint < 0.7 or fusion.conflict_detected,
            'conflict_detected': fusion.conflict_detected,
            'vector_confidence': fusion.vector_conf,
            'keyword_confidence': fusion.keyword_conf,
            'source_weights': fusion.source_weights,
            'level': 1
        }


class CalibratedScorer:
    """
    Transform raw retrieval scores to calibrated probabilities.
    
    Can be trained with IsotonicRegression on validation data.
    """
    
    def __init__(self):
        self.vector_calibrator = None
        self.keyword_calibrator = None
        self.fitted = False
    
    def fit(self,
            vector_scores: np.ndarray,
            vector_accuracies: np.ndarray,
            keyword_scores: np.ndarray,
            keyword_accuracies: np.ndarray) -> None:
        """
        Fit calibrators on validation data.
        
        Args:
            vector_scores: Raw vector similarity scores
            vector_accuracies: Binary accuracy labels (1 if relevant, 0 otherwise)
            keyword_scores: Raw keyword BM25 scores
            keyword_accuracies: Binary accuracy labels
        """
        try:
            from sklearn.isotonic import IsotonicRegression
            
            self.vector_calibrator = IsotonicRegression(out_of_bounds='clip')
            self.vector_calibrator.fit(vector_scores, vector_accuracies)
            
            self.keyword_calibrator = IsotonicRegression(out_of_bounds='clip')
            self.keyword_calibrator.fit(keyword_scores, keyword_accuracies)
            
            self.fitted = True
        except ImportError:
            print("Warning: scikit-learn not available, using heuristic calibration")
            self.fitted = False
    
    def calibrate_vector(self, score: float) -> float:
        """Calibrate vector score."""
        if not self.fitted or self.vector_calibrator is None:
            return score
        return float(self.vector_calibrator.predict([score])[0])
    
    def calibrate_keyword(self, score: float) -> float:
        """Calibrate keyword score."""
        if not self.fitted or self.keyword_calibrator is None:
            # Simple normalization for BM25
            return min(score / 10.0, 1.0)
        return float(self.keyword_calibrator.predict([score])[0])
