#!/usr/bin/env python3
"""
Compare old vs new fusion strategies.

Tests the problematic case where vector entropy is high but similarity is decent.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ci_architecture.level1.fusion import ConfidenceFusion as OldFusion
from ci_architecture.level1.fusion_v2 import ConfidenceFusion as NewFusion


def test_problematic_case():
    """Test the case from user's query."""
    print("=" * 70)
    print("Test Case: '晚上喘不过气，能听到哮鸣音'")
    print("=" * 70)
    
    # Simulated results based on user's output
    vector_result = {
        'sim_max': 0.6017,
        'gap': 0.1705,
        'entropy': 0.9986,
        'results': []
    }
    
    keyword_result = {
        'score_max': 14.31,
        'coverage': 0.8,
        'results': [],
        'matched_terms': ['喘不过气', '哮鸣音']
    }
    
    level0_result = {
        'C': 0,
        'I': 0,
        'I_continuous': 0.0,
        'sigma_c': 0.5
    }
    
    # Old fusion
    print("\n[OLD Fusion Strategy]")
    old_fusion = OldFusion()
    old_result = old_fusion.fuse_with_level0(level0_result, vector_result, keyword_result)
    
    print(f"  Vector confidence:    {old_result['vector_confidence']:.6f}")
    print(f"  Keyword confidence:   {old_result['keyword_confidence']:.6f}")
    print(f"  I_mean:               {old_result['I_retrieval']:.6f}")
    print(f"  sigma_I:              {old_result['sigma_i']:.6f}")
    print(f"  Conflict detected:    {old_result['conflict_detected']}")
    print(f"  Source weights:       {old_result['source_weights']}")
    print(f"  → ESCALATE:           {old_result['escalate']}")
    
    # New fusion
    print("\n[NEW Fusion Strategy v2]")
    new_fusion = NewFusion()
    new_result = new_fusion.fuse_with_level0(level0_result, vector_result, keyword_result)
    
    print(f"  Vector confidence:    {new_result['vector_confidence']:.6f}")
    print(f"  Keyword confidence:   {new_result['keyword_confidence']:.6f}")
    print(f"  I_mean:               {new_result['I_retrieval']:.6f}")
    print(f"  sigma_I:              {new_result['sigma_i']:.6f}")
    print(f"  Conflict detected:    {new_result['conflict_detected']}")
    print(f"  Source weights:       {new_result['source_weights']}")
    print(f"  Source reliabilities: {new_result['source_reliabilities']}")
    print(f"  → ESCALATE:           {new_result['escalate']}")
    
    # Comparison
    print("\n" + "=" * 70)
    print("Comparison Summary")
    print("=" * 70)
    print(f"  I_retrieval:   {old_result['I_retrieval']:.4f} → {new_result['I_retrieval']:.4f} "
          f"(+{(new_result['I_retrieval'] - old_result['I_retrieval']):.4f})")
    print(f"  sigma_I:       {old_result['sigma_i']:.4f} → {new_result['sigma_i']:.4f} "
          f"(+{(new_result['sigma_i'] - old_result['sigma_i']):.4f})")
    print(f"  Vector weight: {old_result['source_weights'].get('vector', 0):.2f} → "
          f"{new_result['source_weights'].get('vector', 0):.2f}")


def test_various_cases():
    """Test various edge cases."""
    print("\n\n" + "=" * 70)
    print("Edge Case Tests")
    print("=" * 70)
    
    test_cases = [
        ("High sim, low entropy (ideal)", {
            'vector': {'sim_max': 0.9, 'gap': 0.3, 'entropy': 0.2},
            'keyword': {'score_max': 20, 'coverage': 0.9}
        }),
        ("Low sim, high entropy (poor vector)", {
            'vector': {'sim_max': 0.4, 'gap': 0.05, 'entropy': 0.95},
            'keyword': {'score_max': 15, 'coverage': 0.8}
        }),
        ("Medium sim, very high entropy (user's case)", {
            'vector': {'sim_max': 0.6, 'gap': 0.17, 'entropy': 0.999},
            'keyword': {'score_max': 14, 'coverage': 0.8}
        }),
        ("Only keyword (no vector)", {
            'vector': None,
            'keyword': {'score_max': 12, 'coverage': 0.7}
        }),
        ("Balanced sources", {
            'vector': {'sim_max': 0.75, 'gap': 0.15, 'entropy': 0.5},
            'keyword': {'score_max': 12, 'coverage': 0.75}
        }),
    ]
    
    old_fusion = OldFusion()
    new_fusion = NewFusion()
    
    for name, data in test_cases:
        print(f"\n{name}:")
        
        v = data.get('vector')
        k = data.get('keyword')
        
        old_r = old_fusion.fuse(v, k)
        new_r = new_fusion.fuse(v, k)
        
        print(f"  OLD: I_mean={old_r.I_mean:.3f}, sigma_I={old_r.sigma_I:.3f}, "
              f"conflict={old_r.conflict_detected}")
        print(f"  NEW: I_mean={new_r.I_mean:.3f}, sigma_I={new_r.sigma_I:.3f}, "
              f"conflict={new_r.conflict_detected}, reliabilities={new_r.source_reliabilities}")


if __name__ == '__main__':
    test_problematic_case()
    test_various_cases()
