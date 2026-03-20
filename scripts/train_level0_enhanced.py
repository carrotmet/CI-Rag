#!/usr/bin/env python3
"""
Enhanced training script for Level 0 XGBoost classifiers with cntext support.

Usage:
    python scripts/train_level0_enhanced.py --data data/training_data.csv --use-cntext
"""

import os
import sys
import argparse
import json
import numpy as np
from typing import Tuple, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ci_architecture.level0 import CntextFeatureExtractor
from ci_architecture.level0.classifier import XGBoostClassifier


def generate_synthetic_data(n_samples: int = 2000, 
                           use_cntext: bool = False,
                           seed: int = 42) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate synthetic training data with enhanced features.
    
    Args:
        n_samples: Number of samples to generate
        use_cntext: Whether to use cntext-enhanced features
        seed: Random seed
        
    Returns:
        X: Feature matrix (n_samples, 12)
        y_c: Complexity labels
        y_i: Information sufficiency labels
    """
    np.random.seed(seed)
    
    extractor = CntextFeatureExtractor(use_cntext=use_cntext)
    
    # Simple queries (Zone C/D)
    simple_templates = [
        "什么是{topic}?",
        "{topic}的定义",
        "查询{value}",
        "{value}是多少",
        "how to {action}",
        "what is {topic}",
        "安装",
        "帮助",
        "{number}",
    ]
    
    # Complex queries (Zone A/B)
    complex_templates = [
        "分析{industry}公司的{tech}部署{aspect}，考虑{cost}和{risk}",
        "比较{product_a}和{product_b}在{metric}方面的差异，评估{impact}",
        "设计{system}架构，满足{requirement}和{constraint}",
        "解释{concept}在{domain}中的应用，包括{example}和{limitation}",
    ]
    
    # Vocabulary
    topics = ['Python', 'Kubernetes', 'Docker', 'AI', '云计算', '数据库', 'API']
    industries = ['医药', '金融', '科技', '制造', '教育']
    techs = ['Kubernetes', 'Docker', '云原生', '微服务', 'Serverless']
    aspects = ['合规', '安全', '性能', '成本', '法规']
    costs = ['成本', '预算', 'ROI', '投入产出比']
    risks = ['风险', '安全性', '稳定性', '合规风险']
    
    queries = []
    labels_c = []
    labels_i = []
    
    print(f"Generating {n_samples} synthetic samples...")
    
    # Generate simple queries (C=0)
    for i in range(n_samples // 2):
        template = simple_templates[i % len(simple_templates)]
        query = template.format(
            topic=np.random.choice(topics),
            value=np.random.randint(100, 9999),
            action=np.random.choice(['install', 'use', 'configure']),
            number=np.random.randint(1, 100)
        )
        queries.append(query)
        labels_c.append(0)  # Low complexity
        labels_i.append(1 if len(query) > 10 else 0)
    
    # Generate complex queries (C=1)
    for i in range(n_samples // 2):
        template = complex_templates[i % len(complex_templates)]
        query = template.format(
            industry=np.random.choice(industries),
            tech=np.random.choice(techs),
            aspect=np.random.choice(aspects),
            cost=np.random.choice(costs),
            risk=np.random.choice(risks),
            product_a=np.random.choice(['方案A', '方案X', '架构1']),
            product_b=np.random.choice(['方案B', '方案Y', '架构2']),
            metric=np.random.choice(['性能', '成本', '可用性', '扩展性']),
            impact=np.random.choice(['业务影响', '技术债务', '维护成本']),
            system=np.random.choice(['系统', '平台', '架构', '方案']),
            requirement=np.random.choice(['高并发', '低延迟', '高可用']),
            constraint=np.random.choice(['成本约束', '时间限制', '技术栈']),
            concept=np.random.choice(['微服务', '事件驱动', 'CQRS']),
            domain=np.random.choice(['电商', '金融', '物联网']),
            example=np.random.choice(['实际案例', '最佳实践']),
            limitation=np.random.choice(['限制条件', '边界情况'])
        )
        queries.append(query)
        labels_c.append(1)  # High complexity
        labels_i.append(0 if '?' not in query else 1)
    
    # Extract features
    print("Extracting features...")
    X = np.array([extractor.extract(q) for q in queries])
    y_c = np.array(labels_c)
    y_i = np.array(labels_i)
    
    return X, y_c, y_i


def main():
    parser = argparse.ArgumentParser(description='Train Level 0 XGBoost models (Enhanced)')
    parser.add_argument('--output', type=str, default='models',
                       help='Output directory for trained models')
    parser.add_argument('--n-samples', type=int, default=2000,
                       help='Number of synthetic samples to generate')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed')
    parser.add_argument('--val-split', type=float, default=0.2,
                       help='Validation split ratio')
    parser.add_argument('--use-cntext', action='store_true',
                       help='Use cntext-enhanced features')
    args = parser.parse_args()
    
    print("=" * 60)
    print("Level 0 XGBoost Classifier Training (Enhanced)")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Samples: {args.n_samples}")
    print(f"  Validation split: {args.val_split}")
    print(f"  Use cntext: {args.use_cntext}")
    print(f"  Output dir: {args.output}")
    
    # Generate synthetic data
    X, y_c, y_i = generate_synthetic_data(
        n_samples=args.n_samples,
        use_cntext=args.use_cntext,
        seed=args.seed
    )
    
    print(f"\nDataset statistics:")
    print(f"  Feature shape: {X.shape}")
    print(f"  C distribution: {{0: {(y_c==0).sum()}, 1: {(y_c==1).sum()}}}")
    print(f"  I distribution: {{0: {(y_i==0).sum()}, 1: {(y_i==1).sum()}}}")
    
    # Split train/val
    n_val = int(len(X) * args.val_split)
    indices = np.random.permutation(len(X))
    train_idx, val_idx = indices[n_val:], indices[:n_val]
    
    X_train, X_val = X[train_idx], X[val_idx]
    y_c_train, y_c_val = y_c[train_idx], y_c[val_idx]
    y_i_train, y_i_val = y_i[train_idx], y_i[val_idx]
    
    print(f"\nSplit sizes:")
    print(f"  Train: {len(X_train)}")
    print(f"  Validation: {len(X_val)}")
    
    # Train models
    print("\n" + "=" * 60)
    print("Training models...")
    print("=" * 60)
    
    success, message = XGBoostClassifier.train(
        X_train=X_train,
        y_c_train=y_c_train,
        y_i_train=y_i_train,
        X_val=X_val,
        y_c_val=y_c_val,
        y_i_val=y_i_val,
        output_dir=args.output
    )
    
    if success:
        print(f"\n[OK] {message}")
        
        # Verify models can be loaded
        print("\nVerifying models...")
        classifier = XGBoostClassifier(
            model_c_path=f"{args.output}/xgb_c.json",
            model_i_path=f"{args.output}/xgb_i.json"
        )
        
        if classifier.is_loaded():
            print("[OK] Models loaded successfully")
            
            # Test predictions
            test_queries = [
                "什么是Python?",
                "安装",
                "分析某医药公司的Kubernetes部署合规性",
                "患者咳嗽有铁锈色痰，胸痛发热"
            ]
            
            print("\n" + "=" * 60)
            print("Test Predictions")
            print("=" * 60)
            
            extractor = CntextFeatureExtractor(use_cntext=args.use_cntext)
            
            for query in test_queries:
                features = extractor.extract(query)
                result = classifier.predict(features)
                
                # Map to ABCD zone
                zone_map = {(0, 0): 'D', (0, 1): 'C', (1, 0): 'B', (1, 1): 'A'}
                zone = zone_map[(result['C_discrete'], result['I_discrete'])]
                
                print(f"\nQuery: {query}")
                print(f"  C={result['C_discrete']} (confidence: {result['sigma_c']:.3f})")
                print(f"  I={result['I_discrete']} (confidence: {result['sigma_i']:.3f})")
                print(f"  Zone {zone}, Escalate: {result['escalate']}")
        else:
            print("[FAIL] Failed to load models")
    else:
        print(f"\n[FAIL] {message}")
        return 1
    
    print("\n" + "=" * 60)
    print("Training complete!")
    print("=" * 60)
    return 0


if __name__ == '__main__':
    sys.exit(main())
