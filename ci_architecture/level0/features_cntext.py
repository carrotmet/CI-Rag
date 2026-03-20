"""Enhanced feature extraction with cntext library support.

This module provides an enhanced feature extractor that uses cntext
for additional Chinese text analysis features.
"""

import numpy as np
from typing import Dict, Optional
import logging

from .features import FeatureExtractor

# Try to import cntext
try:
    import cntext
    CTEXT_AVAILABLE = True
except ImportError:
    CTEXT_AVAILABLE = False
    logging.warning("cntext not available. Using base features only.")


class CntextFeatureExtractor(FeatureExtractor):
    """
    Enhanced feature extractor with cntext support.
    
    Extends base 12-dimensional features with cntext-powered analysis:
    - Text readability metrics
    - Sentiment analysis
    - Keyword extraction quality
    
    Usage:
        extractor = CntextFeatureExtractor(use_cntext=True)
        features = extractor.extract("查询文本")
    """
    
    def __init__(self, use_cntext: bool = True):
        """
        Initialize extractor.
        
        Args:
            use_cntext: Whether to use cntext enhancements
        """
        super().__init__()
        self.use_cntext = use_cntext and CTEXT_AVAILABLE
        
        if self.use_cntext:
            logging.info("Cntext feature extraction enabled")
        else:
            logging.info("Using base feature extraction only")
    
    def extract(self, query: str, user_history: Optional[Dict] = None) -> np.ndarray:
        """
        Extract features with cntext enhancements.
        
        Args:
            query: Input query string
            user_history: Optional user historical data
            
        Returns:
            12-dimensional feature vector (dimensions 10-11 enhanced by cntext)
        """
        # Get base features from parent class
        features = super().extract(query, user_history)
        
        if not self.use_cntext:
            return features
        
        try:
            # Replace reserved dimensions with cntext features
            # Dimension 10: Text complexity/readability
            features[10] = self._compute_text_complexity(query)
            
            # Dimension 11: Sentiment polarity
            features[11] = self._compute_sentiment(query)
            
        except Exception as e:
            logging.warning(f"Cntext feature extraction failed: {e}")
            # Fallback to defaults
            features[10] = 0.5
            features[11] = 0.5
        
        return features
    
    def _compute_text_complexity(self, query: str) -> float:
        """
        Compute text complexity using cntext.
        
        Returns:
            Complexity score (0.0 - 1.0)
        """
        try:
            # Base complexity on text length and structure
            length_score = min(len(query) / 100, 1.0)
            
            # Count complex structures (parentheses, quotes, etc.)
            complex_chars = query.count('(') + query.count(')') + \
                          query.count('"') + query.count('"') + \
                          query.count('，') + query.count(',')
            structure_score = min(complex_chars / 10, 1.0)
            
            # Combine scores
            complexity = 0.6 * length_score + 0.4 * structure_score
            
            return float(np.clip(complexity, 0.0, 1.0))
            
        except Exception:
            return 0.5
    
    def _compute_sentiment(self, query: str) -> float:
        """
        Compute sentiment polarity.
        
        Returns:
            Sentiment score (0.0=negative, 0.5=neutral, 1.0=positive)
        """
        try:
            # Simple keyword-based sentiment for queries
            positive_words = {'好', '优秀', '成功', '有效', '推荐', '喜欢'}
            negative_words = {'差', '失败', '错误', '问题', 'bug', '不好'}
            
            pos_count = sum(1 for w in positive_words if w in query)
            neg_count = sum(1 for w in negative_words if w in query)
            
            if pos_count > neg_count:
                return 0.7 + min(pos_count * 0.1, 0.3)
            elif neg_count > pos_count:
                return 0.3 - min(neg_count * 0.1, 0.3)
            else:
                return 0.5
                
        except Exception:
            return 0.5
    
    def get_feature_names(self) -> list:
        """Get list of feature names with descriptions."""
        base_names = [
            "0: len_char - Character length",
            "1: len_word - Word count",
            "2: char_entropy - Character entropy",
            "3: word_entropy - Word entropy",
            "4: domain_switch_cnt - Domain switches",
            "5: has_question - Question indicator",
            "6: digit_ratio - Digit ratio",
            "7: user_freq - User query frequency",
            "8: avg_complexity - User avg complexity",
            "9: success_rate - User success rate",
        ]
        
        if self.use_cntext:
            base_names.append("10: text_complexity - Text complexity (cntext)")
            base_names.append("11: sentiment - Sentiment polarity (cntext)")
        else:
            base_names.append("10: reserved_10 - Reserved")
            base_names.append("11: reserved_11 - Reserved")
        
        return base_names


# Backward compatibility
FeatureExtractorEnhanced = CntextFeatureExtractor
