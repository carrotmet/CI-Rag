#!/usr/bin/env python3
"""
Training script for Level 0 XGBoost classifiers.

Generates synthetic training data and trains Model C (Complexity) and 
Model I (Information Sufficiency).
"""

import os
import sys
import argparse
import numpy as np
from typing import Tuple

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ci_architecture.level0 import FeatureExtractor
from ci_architecture.level0.classifier import XGBoostClassifier


def generate_synthetic_data(n_samples: int = 1000, 
                           seed: int = 42) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate synthetic training data based on heuristic rules.
    
    This creates labeled data for initial model training before
    real user data is collected.
    """
    np.random.seed(seed)
    
    feature_extractor = FeatureExtractor()
    
    # Generate diverse queries
    queries = []
    
    # Simple queries (Zone C/D)
    simple_templates = [
        "什么是{topic}?",
        "{topic}的定义",
        "查询{value}",
        "{value}是多少",
        "how to {action}",
        "what is {topic}",
    ]
    
    # Complex queries (Zone A/B)
    complex_templates = [
        "分析{industry}公司的{tech}部署{legal}性，考虑{cost}和{risk}",
        "比较{product_a}和{product_b}在{metric}方面的差异，评估{impact}",
        "设计{system}架构，满足{requirement}和{constraint}",
        "解释{concept}在{domain}中的应用，包括{example}和{limitation}",
    ]
    
    # Entity values
    topics = ['Python', 'Kubernetes', 'Docker', 'AI', '云计算', '数据库', 'API']
    industries = ['医药', '金融', '科技', '制造', '教育']
    techs = ['Kubernetes', 'Docker', '云原生', '微服务', 'Serverless']
    legals = ['合规', '法规', '法律', '隐私', '安全']
    
    # Generate simple queries
    for _ in range(n_samples // 2):
        template = np.random.choice(simple_templates)
        query = template.format(
            topic=np.random.choice(topics),
            value=np.random.randint(100, 9999),
            action=np.random.choice(['install', 'use', 'configure'])
        )
        queries.append(query)
    
    # Generate complex queries
    for _ in range(n_samples // 2):
        template = np.random.choice(complex_templates)
        query = template.format(
            industry=np.random.choice(industries),
            tech=np.random.choice(techs),
            legal=np.random.choice(legals),
            cost=np.random.choice(['成本', '预算', 'ROI']),
            risk=np.random.choice(['风险', '安全性', '稳定性']),
            product_a=np.random.choice(['产品A', '方案X']),
            product_b=np.random.choice(['产品B', '方案Y']),
            metric=np.random.choice(['性能', '成本', '可用性']),
            impact=np.random.choice(['业务影响', '技术债务', '维护成本']),
            system=np.random.choice(['系统', '平台', '架构']),
            requirement=np.random.choice(['高并发', '低延迟', '高可用']),
            constraint=np.random.choice(['成本约束', '时间限制', '技术栈']),
            concept=np.random.choice(['微服务', '事件驱动', 'CQRS']),
            domain=np.random.choice(['电商', '金融', '物联网']),
            example=np.random.choice(['案例1', '实际应用']),
            limitation=np.random.choice(['限制条件', '边界情况'])
        )
        queries.append(query)
    
    # Extract features
    X = np.array([feature_extractor.extract(q) for q in queries])
    
    # Generate labels based on heuristics
    # C (Complexity): High if domain_switch >= 2 or len_word > 50
    y_c = np.array([
        1 if (x[4] >= 2 or x[1] > 50 or x[2] > 4.0) else 0
        for x in X
    ])
    
    # I (Information): High for structured queries with identifiers
    y_i = np.array([
        1 if (x[5] == 1 and x[6] > 0.3) or (x[1] >= 10) else 0
        for x in X
    ])
    
    return X, y_c, y_i


def main():
    parser = argparse.ArgumentParser(description='Train Level 0 XGBoost classifiers')
    parser.add_argument('--output-dir', type=str, default='models',
                       help='Output directory for trained models')
    parser.add_argument('--n-samples', type=int, default=1000,
                       help='Number of synthetic samples to generate')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed')
    parser.add_argument('--val-split', type=float, default=0.2,
                       help='Validation split ratio')
    args = parser.parse_args()
    
    print("=" * 60)
    print("Level 0 XGBoost Classifier Training")
    print("=" * 60)
    
    # Generate synthetic data
    print(f"\nGenerating {args.n_samples} synthetic samples...")
    X, y_c, y_i = generate_synthetic_data(args.n_samples, args.seed)
    
    print(f"Feature shape: {X.shape}")
    print(f"C distribution: {np.bincount(y_c)}")
    print(f"I distribution: {np.bincount(y_i)}")
    
    # Split train/val
    n_val = int(len(X) * args.val_split)
    indices = np.random.permutation(len(X))
    train_idx, val_idx = indices[n_val:], indices[:n_val]
    
    X_train, X_val = X[train_idx], X[val_idx]
    y_c_train, y_c_val = y_c[train_idx], y_c[val_idx]
    y_i_train, y_i_val = y_i[train_idx], y_i[val_idx]
    
    print(f"\nTrain size: {len(X_train)}, Val size: {len(X_val)}")
    
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
        output_dir=args.output_dir
    )
    
    if success:
        print(f"\n✓ {message}")
        
        # Test loading
        print("\nVerifying models...")
        classifier = XGBoostClassifier(
            model_c_path=f"{args.output_dir}/xgb_c.json",
            model_i_path=f"{args.output_dir}/xgb_i.json"
        )
        
        if classifier.is_loaded():
            print("✓ Models loaded successfully")
            
            # Test prediction
            test_query = "分析某医药公司的Kubernetes部署合规性"
            from ci_architecture.level0 import FeatureExtractor
            features = FeatureExtractor().extract(test_query)
            result = classifier.predict(features)
            
            print(f"\nTest prediction for: '{test_query}'")
            print(f"  C={result['C_discrete']} (confidence: {result['sigma_c']:.3f})")
            print(f"  I={result['I_discrete']} (confidence: {result['sigma_i']:.3f})")
            print(f"  Joint confidence: {result['sigma_joint']:.3f}")
            print(f"  Escalate: {result['escalate']}")
        else:
            print("✗ Failed to load models")
    else:
        print(f"\n✗ {message}")
        return 1
    
    print("\n" + "=" * 60)
    print("Training complete!")
    print("=" * 60)
    return 0


if __name__ == '__main__':
    sys.exit(main())
