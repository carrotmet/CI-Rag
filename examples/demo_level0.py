#!/usr/bin/env python3
"""
Level 0 Demo - CI-RAG-ROUTER

Demonstrates the cold start behavior and routing decisions.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ci_architecture.level0 import Level0Router


def main():
    print("=" * 70)
    print("CI-RAG-ROUTER Level 0 Demo")
    print("=" * 70)
    
    # Initialize router (will detect cold start mode)
    print("\nInitializing Level 0 Router...")
    router = Level0Router()
    
    print(f"Router Status: {router.get_status().value}")
    print(f"Cold Start Mode: {router.is_cold_start()}")
    
    # Test queries
    test_queries = [
        "什么是Python?",
        "查询订单号12345的状态",
        "分析某医药公司的Kubernetes部署合规性，考虑成本、安全性和法规要求",
        "如何配置Docker容器?",
        "比较微服务架构和单体架构在性能、可维护性和部署复杂度方面的差异",
        "安装",
    ]
    
    print("\n" + "=" * 70)
    print("Processing Test Queries")
    print("=" * 70)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n[{i}] Query: \"{query}\"")
        print("-" * 50)
        
        result = router.route(query)
        
        # Display results
        zone = router.get_zone(result['C'], result['I'])
        
        print(f"  Features:")
        print(f"    - Length (chars): {result['features'][0]:.0f}")
        print(f"    - Word count: {result['features'][1]:.0f}")
        print(f"    - Domain switches: {result['features'][4]:.0f}")
        print(f"    - Has question: {bool(result['features'][5])}")
        print(f"    - Digit ratio: {result['features'][6]:.3f}")
        
        print(f"  CI Assessment:")
        print(f"    - Complexity (C): {result['C']} ({'High' if result['C'] == 1 else 'Low'})")
        print(f"    - Info Sufficiency (I): {result['I']} ({'Sufficient' if result['I'] == 1 else 'Insufficient'})")
        print(f"    - Zone: {zone}")
        
        print(f"  Confidence:")
        print(f"    - σ_c: {result['sigma_c']:.3f}")
        print(f"    - σ_i: {result['sigma_i']:.3f}")
        print(f"    - σ_joint: {result['sigma_joint']:.3f}")
        
        print(f"  Decision:")
        print(f"    - Mode: {result['mode']}")
        print(f"    - Escalate to Level 1: {result['escalate']}")
        
        if 'note' in result:
            print(f"    - Note: {result['note']}")
    
    print("\n" + "=" * 70)
    print("Demo Complete")
    print("=" * 70)
    
    if router.is_cold_start():
        print("\n📋 Next Steps:")
        print("  1. Train XGBoost models: python scripts/train_level0.py")
        print("  2. Reload router to switch from COLD_START to PRODUCTION mode")
        print("  3. In cold start mode, all queries escalate to Level 1 for data collection")


if __name__ == '__main__':
    main()
