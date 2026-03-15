"""Tests for Level 1 hybrid retrieval."""

import pytest
import numpy as np
from ci_architecture.level1.fusion import ConfidenceFusion


class TestConfidenceFusion:
    """Test confidence fusion."""
    
    def test_fuse_vector_only(self):
        """Test fusion with only vector results."""
        fusion = ConfidenceFusion()
        
        vector_result = {
            'sim_max': 0.85,
            'gap': 0.15,
            'entropy': 0.3
        }
        
        result = fusion.fuse(vector_result=vector_result)
        
        assert 0 <= result.I_mean <= 1
        assert 0 <= result.sigma_I <= 1
        assert result.vector_conf > 0
        assert result.keyword_conf == 0
        
    def test_fuse_keyword_only(self):
        """Test fusion with only keyword results."""
        fusion = ConfidenceFusion()
        
        keyword_result = {
            'score_max': 8.5,
            'coverage': 0.8
        }
        
        result = fusion.fuse(keyword_result=keyword_result)
        
        assert 0 <= result.I_mean <= 1
        assert 0 <= result.sigma_I <= 1
        assert result.vector_conf == 0
        assert result.keyword_conf > 0
        
    def test_fuse_both_sources(self):
        """Test fusion with both sources."""
        fusion = ConfidenceFusion()
        
        vector_result = {
            'sim_max': 0.80,
            'gap': 0.20,
            'entropy': 0.25
        }
        
        keyword_result = {
            'score_max': 7.5,
            'coverage': 0.75
        }
        
        result = fusion.fuse(vector_result, keyword_result)
        
        assert 0 <= result.I_mean <= 1
        assert 0 <= result.sigma_I <= 1
        assert result.vector_conf > 0
        assert result.keyword_conf > 0
        assert 'vector' in result.source_weights
        assert 'keyword' in result.source_weights
        
    def test_conflict_detection(self):
        """Test conflict detection."""
        fusion = ConfidenceFusion()
        
        # Create large difference between sources
        vector_result = {
            'sim_max': 0.95,  # High confidence
            'gap': 0.30,
            'entropy': 0.1
        }
        
        keyword_result = {
            'score_max': 1.0,  # Low confidence
            'coverage': 0.2
        }
        
        result = fusion.fuse(vector_result, keyword_result)
        
        # Should detect conflict due to large discrepancy
        assert result.conflict_detected == True
        
    def test_calibrate_vector(self):
        """Test vector calibration."""
        fusion = ConfidenceFusion()
        
        # High similarity, low entropy, large gap = high confidence
        conf = fusion.calibrate_vector(sim_max=0.9, gap=0.3, entropy=0.2)
        assert conf > 0.7
        
        # Low similarity, high entropy = low confidence
        conf = fusion.calibrate_vector(sim_max=0.4, gap=0.05, entropy=0.8)
        assert conf < 0.5
        
    def test_calibrate_keyword(self):
        """Test keyword calibration."""
        fusion = ConfidenceFusion()
        
        # High score, good coverage = high confidence
        conf = fusion.calibrate_keyword(score_max=12.0, coverage=0.9)
        assert conf > 0.7
        
        # Low score, poor coverage = low confidence
        conf = fusion.calibrate_keyword(score_max=2.0, coverage=0.3)
        assert conf < 0.5


class TestMedicalDataset:
    """Test with medical dataset."""
    
    def test_dataset_loading(self):
        """Test medical dataset loading."""
        from data.medical_symptoms import get_medical_dataset, TEST_QUERIES
        
        docs = get_medical_dataset()
        assert len(docs) > 0
        assert all('content' in d for d in docs)
        assert all('metadata' in d for d in docs)
        
        # Check test queries
        assert len(TEST_QUERIES) > 0
        
    def test_dataset_categories(self):
        """Test dataset has multiple categories."""
        from data.medical_symptoms import get_medical_dataset
        
        docs = get_medical_dataset()
        categories = set(d['metadata']['category'] for d in docs)
        
        # Should have multiple medical specialties
        assert len(categories) >= 5
