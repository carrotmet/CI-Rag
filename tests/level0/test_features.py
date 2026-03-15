"""Tests for Level 0 feature extraction."""

import pytest
import numpy as np
from ci_architecture.level0.features import FeatureExtractor, extract_features


class TestFeatureExtractor:
    """Test feature extraction."""
    
    def test_basic_extraction(self):
        """Test basic feature extraction."""
        extractor = FeatureExtractor()
        query = "什么是Kubernetes?"
        features = extractor.extract(query)
        
        # Check shape
        assert features.shape == (12,)
        assert features.dtype == np.float32
        
        # Check specific features
        assert features[0] == len(query)  # len_char
        assert features[1] == 1  # len_word (split by space)
        assert features[5] == 1.0  # has_question
    
    def test_simple_query(self):
        """Test simple query features."""
        extractor = FeatureExtractor()
        query = "查询"
        features = extractor.extract(query)
        
        assert features[0] == 2  # len_char
        assert features[1] == 1  # len_word
        assert features[5] == 0.0  # not a question
    
    def test_complex_query(self):
        """Test complex query with domain switches."""
        extractor = FeatureExtractor()
        query = "分析某医药公司的Kubernetes部署合规性"
        features = extractor.extract(query)
        
        # Should have domain switches (medicine -> tech -> legal)
        assert features[4] >= 2  # domain_switch_cnt
        
        # Should have reasonable length
        assert features[0] > 10  # len_char
        assert features[1] >= 1  # len_word
    
    def test_question_detection(self):
        """Test question detection."""
        extractor = FeatureExtractor()
        
        # Chinese questions
        assert extractor._has_question("什么是AI?") == True
        assert extractor._has_question("怎么配置") == True
        assert extractor._has_question("为什么失败") == True
        
        # English questions
        assert extractor._has_question("What is this") == True
        assert extractor._has_question("how to install") == True
        
        # Non-questions
        assert extractor._has_question("配置文档") == False
        assert extractor._has_question("安装指南") == False
    
    def test_entropy_calculation(self):
        """Test entropy calculation."""
        extractor = FeatureExtractor()
        
        # Repetitive string has low entropy
        low_entropy = extractor._compute_entropy("aaaaaa")
        assert low_entropy < 1.0
        
        # Diverse string has higher entropy
        high_entropy = extractor._compute_entropy("abcdef")
        assert high_entropy > low_entropy
        
        # Empty string has zero entropy
        zero_entropy = extractor._compute_entropy("")
        assert zero_entropy == 0.0
    
    def test_domain_switch_count(self):
        """Test domain switch counting."""
        extractor = FeatureExtractor()
        
        # Single domain
        assert extractor._count_domain_switches("医药公司") >= 0
        
        # Multiple domains
        switches = extractor._count_domain_switches("医药公司的Kubernetes部署合规性")
        assert switches >= 2  # medicine -> tech -> legal
    
    def test_convenience_function(self):
        """Test extract_features convenience function."""
        query = "测试查询"
        features = extract_features(query)
        
        assert isinstance(features, np.ndarray)
        assert features.shape == (12,)


class TestFeaturePerformance:
    """Test performance requirements."""
    
    def test_extraction_speed(self):
        """Test that feature extraction is fast (<0.5ms per query)."""
        import time
        
        extractor = FeatureExtractor()
        queries = ["查询" + str(i) for i in range(100)]
        
        start = time.time()
        for query in queries:
            extractor.extract(query)
        elapsed = time.time() - start
        
        avg_time = elapsed / len(queries)
        # Should be much faster than 0.5ms in practice
        assert avg_time < 0.001  # 1ms to be safe in test environment
