"""Tests for Level 0 router."""

import pytest
import os
import numpy as np
from ci_architecture.level0.router import Level0Router, RouterStatus
from ci_architecture.level0.heuristic_router import HeuristicRouter


class TestHeuristicRouter:
    """Test heuristic router."""
    
    def test_simple_query(self):
        """Test simple query routing."""
        router = HeuristicRouter()
        
        # Simple query features
        features = np.zeros(12)
        features[1] = 5  # len_word
        features[4] = 0  # no domain switches
        
        result = router.predict(features)
        
        assert result['C'] == 0  # Low complexity
        assert result['I'] == 0  # Short query, insufficient info
    
    def test_complex_query(self):
        """Test complex query routing."""
        router = HeuristicRouter()
        
        # Complex query features
        features = np.zeros(12)
        features[1] = 60  # long query
        features[4] = 3  # multiple domain switches
        features[5] = 1  # has question
        features[6] = 0.4  # digit ratio
        
        result = router.predict(features)
        
        assert result['C'] == 1  # High complexity
        assert result['I'] == 1  # Has question with digits
    
    def test_confidence_scores(self):
        """Test confidence score generation."""
        router = HeuristicRouter()
        
        features = np.zeros(12)
        features[1] = 10
        
        result = router.predict_with_confidence(features)
        
        assert 'C' in result
        assert 'I' in result
        assert 'sigma_joint' in result
        assert 'mode' in result
        assert result['mode'] == 'HEURISTIC'


class TestLevel0Router:
    """Test unified router."""
    
    def test_cold_start_detection(self):
        """Test cold start mode when models don't exist."""
        # Use non-existent paths
        router = Level0Router(
            model_c_path="nonexistent_c.json",
            model_i_path="nonexistent_i.json"
        )
        
        assert router.get_status() == RouterStatus.COLD_START
        assert router.is_cold_start() == True
    
    def test_cold_start_routing(self):
        """Test routing in cold start mode."""
        router = Level0Router(
            model_c_path="nonexistent_c.json",
            model_i_path="nonexistent_i.json"
        )
        
        result = router.route("什么是Kubernetes?")
        
        assert result['escalate'] == True
        assert result['sigma_joint'] == 0.5  # Forced low confidence
        assert result['status'] == 'COLD_START'
        assert result['mode'] == 'COLD_START_HEURISTIC'
        assert 'note' in result
    
    def test_zone_mapping(self):
        """Test ABCD zone mapping."""
        router = Level0Router(
            model_c_path="nonexistent_c.json",
            model_i_path="nonexistent_i.json"
        )
        
        assert router.get_zone(0, 0) == 'D'
        assert router.get_zone(0, 1) == 'C'
        assert router.get_zone(1, 0) == 'B'
        assert router.get_zone(1, 1) == 'A'
    
    def test_feature_preservation(self):
        """Test that features are included in result."""
        router = Level0Router(
            model_c_path="nonexistent_c.json",
            model_i_path="nonexistent_i.json"
        )
        
        result = router.route("测试查询")
        
        assert 'features' in result
        assert len(result['features']) == 12


class TestIntegration:
    """Integration tests."""
    
    def test_end_to_end_cold_start(self):
        """Test complete cold start flow."""
        from ci_architecture.level0 import route_query
        
        result = route_query(
            "分析某医药公司的Kubernetes部署合规性",
            model_c_path="nonexistent_c.json",
            model_i_path="nonexistent_i.json"
        )
        
        # Should escalate in cold start
        assert result['escalate'] == True
        assert result['sigma_joint'] < 0.7
        
        # Should have reasonable C/I values from heuristic
        assert result['C'] in [0, 1]
        assert result['I'] in [0, 1]
    
    def test_query_variety(self):
        """Test various query types."""
        router = Level0Router(
            model_c_path="nonexistent_c.json",
            model_i_path="nonexistent_i.json"
        )
        
        test_queries = [
            "什么是Python?",  # Simple factual
            "查询订单号12345",  # Lookup with ID
            "分析某医药公司的Kubernetes部署合规性，考虑成本和风险",  # Complex multi-domain
            "安装",  # Very short
        ]
        
        for query in test_queries:
            result = router.route(query)
            assert 'C' in result
            assert 'I' in result
            assert result['escalate'] == True  # All escalate in cold start
