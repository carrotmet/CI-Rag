"""Heuristic rule-based router for cold start and fallback scenarios."""

import numpy as np
from typing import Dict, Tuple


class HeuristicRouter:
    """
    Rule-based router using hardcoded heuristics based on features.
    
    Used during cold start (before XGBoost models are trained) and
    as fallback when XGBoost confidence is low.
    """
    
    def __init__(self):
        # Thresholds for decision making
        self.high_complexity_word_threshold = 50
        self.high_complexity_domain_switch = 2
        self.high_entropy_threshold = 4.0
        self.simple_query_word_threshold = 10
        self.information_digit_threshold = 0.3
    
    def predict(self, features: np.ndarray) -> Dict[str, int]:
        """
        Predict C and I using heuristic rules.
        
        Args:
            features: 12-dimensional feature vector
            
        Returns:
            Dict with 'C' (complexity) and 'I' (information sufficiency)
        """
        len_word = int(features[1])
        domain_switch = int(features[4])
        char_entropy = features[2]
        has_question = bool(features[5])
        digit_ratio = features[6]
        
        # C (Complexity) determination
        C = self._determine_complexity(
            len_word=len_word,
            domain_switch=domain_switch,
            char_entropy=char_entropy
        )
        
        # I (Information Sufficiency) determination
        I = self._determine_information_sufficiency(
            len_word=len_word,
            has_question=has_question,
            digit_ratio=digit_ratio
        )
        
        return {'C': C, 'I': I}
    
    def _determine_complexity(self, len_word: int, domain_switch: int, 
                             char_entropy: float) -> int:
        """
        Determine complexity (C).
        
        C = 1 (High): Multi-step reasoning, domain synthesis, ambiguity handling
        C = 0 (Low): Direct lookup or simple transformation
        """
        # High complexity indicators
        if domain_switch >= self.high_complexity_domain_switch:
            return 1  # Cross-domain complexity
        
        if len_word > self.high_complexity_word_threshold:
            return 1  # Long query suggests complexity
        
        if char_entropy > self.high_entropy_threshold:
            return 1  # High entropy may indicate mixed/encoded content
        
        # Default to low complexity
        return 0
    
    def _determine_information_sufficiency(self, len_word: int,
                                          has_question: bool,
                                          digit_ratio: float) -> int:
        """
        Determine information sufficiency (I).
        
        I = 1 (Sufficient): Knowledge base likely contains answer
        I = 0 (Insufficient): Need external retrieval
        """
        # Very short queries may lack context
        if len_word < 5:
            return 0
        
        # Question with specific numeric identifiers suggests
        # structured data lookup potential
        if has_question and digit_ratio > self.information_digit_threshold:
            return 1
        
        # Simple factual questions likely have sufficient info
        if has_question and len_word < 20:
            return 1
        
        # Default to information sufficient for longer queries
        return 1 if len_word >= 10 else 0
    
    def predict_with_confidence(self, features: np.ndarray) -> Dict:
        """
        Predict with confidence scores.
        
        Note: In cold start mode, confidence is artificially lowered
        to force escalation to Level 1 for data collection.
        """
        result = self.predict(features)
        
        # Heuristic-based confidence estimation
        # These are rough estimates - real confidence comes from calibrated XGBoost
        len_word = int(features[1])
        domain_switch = int(features[4])
        
        # Higher confidence for clear-cut cases
        if len_word < 5 or domain_switch >= 3:
            sigma_c = 0.75
            sigma_i = 0.70
        elif len_word > 100:
            sigma_c = 0.70
            sigma_i = 0.65
        else:
            sigma_c = 0.60
            sigma_i = 0.55
        
        sigma_joint = min(sigma_c, sigma_i)
        
        return {
            'C': result['C'],
            'I': result['I'],
            'sigma_c': sigma_joint,
            'sigma_i': sigma_joint,
            'sigma_joint': sigma_joint,
            'escalate': sigma_joint < 0.7,
            'mode': 'HEURISTIC'
        }
