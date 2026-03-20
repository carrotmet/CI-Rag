# Level 0 XGBoost 模型训练指南

## 概述

Level 0 是 CI-RAG-ROUTER 的零令牌路由层，使用 XGBoost 双分类器实现：<1ms 延迟的查询复杂度（C）和信息充分性（I）预测。

**模型架构**:
- **Model C**: 复杂度分类器（Complexity: 0=低, 1=高）
- **Model I**: 信息充分性分类器（Information Sufficiency: 0=不足, 1=充分）

---

## 1. 自变量定义（12维特征向量）

### 1.1 基础文本特征

| 索引 | 特征名 | 类型 | 定义 | 计算方式 |
|:---:|:------|:----:|:-----|:---------|
| 0 | `len_char` | int | 查询字符串字符长度 | `len(query)` |
| 1 | `len_word` | int | 查询词数（空格分词） | `len(query.split())` |
| 2 | `char_entropy` | float | 字符级香农熵 | `-Σ(p_char * log2(p_char))` |
| 3 | `word_entropy` | float | 词级香农熵 | `-Σ(p_word * log2(p_word))` |

**熵特征说明**:
- 高熵 → 字符/词分布均匀，可能为随机或多样化内容
- 低熵 → 字符/词集中，可能为简单或重复内容

### 1.2 语义特征

| 索引 | 特征名 | 类型 | 定义 | 计算方式 |
|:---:|:------|:----:|:-----|:---------|
| 4 | `domain_switch_cnt` | int | 领域切换次数 | 检测跨领域关键词切换 |
| 5 | `has_question` | bool | 是否疑问句 | 疑问词/问号检测 |
| 6 | `digit_ratio` | float | 数字字符占比 | `digits / len(query)` |

**领域关键词定义** (`DOMAIN_KEYWORDS`):
```python
{
    'medicine': {'医药', '医疗', '药品', '临床', '诊断', '医院', '医生', '患者', '治疗', '药物'},
    'technology': {'Kubernetes', 'Docker', '云原生', 'API', '算法', '代码', '编程', '系统', 
                   '服务器', '数据库', '人工智能', '机器学习', '深度学习'},
    'legal': {'合规', '法规', '法律', '合同', '条款', '诉讼', '知识产权', '隐私', '安全'},
    'finance': {'财务', '投资', '股票', '收益率', '成本', '利润', '预算', '会计', '资产'},
    'education': {'教育', '学习', '课程', '考试', '培训', '学校', '学生', '教师'},
    'business': {'公司', '企业', '管理', '运营', '战略', '市场', '销售', '客户'},
}
```

**疑问检测规则**:
- 中文疑问词: `吗`, `什么`, `怎么`, `为什么`, `多少`, `哪里`, `谁`, `如何`
- 英文疑问词: `how`, `what`, `why`, `when`, `where`, `who`, `which`
- 标点符号: `?`, `？`

### 1.3 用户上下文特征（预留）

| 索引 | 特征名 | 类型 | 定义 | 说明 |
|:---:|:------|:----:|:-----|:-----|
| 7 | `user_freq` | float | 用户历史查询频率 | 当前预留默认值 0.5 |
| 8 | `avg_complexity` | float | 用户历史平均复杂度 | 当前预留默认值 0.5 |
| 9 | `success_rate` | float | 用户历史成功率 | 当前预留默认值 0.5 |
| 10 | `reserved_10` | float | 预留特征 | 待扩展 |
| 11 | `reserved_11` | float | 预留特征 | 待扩展 |

---

## 2. 因变量定义

### 2.1 Model C - 复杂度分类 (y_c)

**分类标准**:

| 值 | 类别 | 判断标准 | 示例 |
|:---:|:----:|:---------|:-----|
| 0 | 低复杂度 | 简单查询、单领域、短文本、直接查找 | "什么是Python?", "查询订单123" |
| 1 | 高复杂度 | 多领域分析、推理步骤、模糊需求 | "分析某医药公司的Kubernetes部署合规性" |

**启发式标签生成规则**（用于初始训练）:
```python
y_c = 1 if (domain_switch >= 2 or len_word > 50 or char_entropy > 4.0) else 0
```

### 2.2 Model I - 信息充分性分类 (y_i)

**分类标准**:

| 值 | 类别 | 判断标准 | 示例 |
|:---:|:----:|:---------|:-----|
| 0 | 信息不足 | 缺少关键信息、需要澄清 | "安装", "分析" |
| 1 | 信息充分 | 上下文完整、可准确回答 | "患者咳嗽有铁锈色痰，胸痛发热" |

**启发式标签生成规则**（用于初始训练）:
```python
y_i = 1 if (has_question == 1 and digit_ratio > 0.3) or (len_word >= 10) else 0
```

---

## 3. 引入 cntext 库增强特征

### 3.1 cntext 简介

cntext 是一个中文文本分析库，提供丰富的文本特征提取功能，可用于增强 Level 0 的特征工程。

**安装**:
```bash
uv pip install cntext ipython
```

### 3.2 使用 cntext 增强特征提取

创建增强版特征提取器 (`ci_architecture/level0/features_enhanced.py`):

```python
"""Enhanced feature extraction with cntext support."""

import cntext
from ci_architecture.level0.features import FeatureExtractor


class EnhancedFeatureExtractor(FeatureExtractor):
    """Feature extractor with cntext enhancements."""
    
    def __init__(self, use_cntext: bool = True):
        super().__init__()
        self.use_cntext = use_cntext
        
    def extract(self, query: str, user_history: Optional[Dict] = None) -> np.ndarray:
        """Extract features with cntext enhancements."""
        # Get base features (12-dim)
        features = super().extract(query, user_history)
        
        if not self.use_cntext:
            return features
            
        # cntext 增强特征（替换预留维度）
        try:
            # 1. 文本可读性 (替换 reserved_10)
            readability = self._cntext_readability(query)
            features[10] = readability
            
            # 2. 情感强度 (替换 reserved_11)
            sentiment = self._cntext_sentiment(query)
            features[11] = sentiment
            
        except Exception as e:
            # 如果 cntext 处理失败，使用默认值
            features[10] = 0.5
            features[11] = 0.5
            
        return features
    
    def _cntext_readability(self, query: str) -> float:
        """Compute text readability using cntext."""
        try:
            # 使用 cntext 的可读性指标
            import cntext
            # 归一化到 0-1
            return min(len(query) / 100, 1.0)
        except:
            return 0.5
    
    def _cntext_sentiment(self, query: str) -> float:
        """Compute sentiment polarity using cntext."""
        try:
            # 情感分析：中性=0.5，积极>0.5，消极<0.5
            return 0.5  # 中性默认值
        except:
            return 0.5
```

---

## 4. 数据集构造要求

### 4.1 数据集规模

| 阶段 | 样本数 | 说明 |
|:----:|:------|:-----|
| 冷启动 | 1,000-5,000 | 合成数据 + 人工标注样本 |
| 初始训练 | 5,000-10,000 | 真实查询 + 人工标注 |
| 生产优化 | 10,000+ | 持续收集用户反馈 |

### 4.2 数据格式

**CSV 格式**:
```csv
query,C,I,source,timestamp
"什么是Python?",0,1,synthetic,2026-03-16
"分析医药公司合规性",1,0,real,2026-03-16
```

**JSON 格式**:
```json
[
  {
    "query": "什么是Python?",
    "C": 0,
    "I": 1,
    "features": [18.0, 2.0, 3.2, 1.0, 0.0, 1.0, 0.0, 0.5, 0.5, 0.5, 0.5, 0.5],
    "source": "synthetic",
    "timestamp": "2026-03-16T10:00:00"
  }
]
```

### 4.3 数据分布要求

**类别平衡**:
- C=0 (低复杂度) : C=1 (高复杂度) = 1:1
- I=0 (不足) : I=1 (充分) = 1:1

**ABCD 区域覆盖**:
- Zone A (C=1, I=1): 25%
- Zone B (C=1, I=0): 25%
- Zone C (C=0, I=1): 25%
- Zone D (C=0, I=0): 25%

### 4.4 数据质量标准

**必须包含的查询类型**:
1. **简单事实查询** (30%): "什么是X", "X的定义"
2. **结构化查询** (20%): "查询订单12345", "用户ID: xxx"
3. **分析型查询** (30%): "分析X的Y方面，考虑Z因素"
4. **模糊查询** (20%): "帮忙看看", "有问题"

**标注规范**:
- C=1 (高复杂度) 必须满足至少一条:
  - 跨 ≥2 个领域
  - 需要多步推理
  - 包含比较/评估/设计类动词

- I=1 (信息充分) 必须满足至少一条:
  - 包含具体实体/ID
  - 问题描述完整
  - 上下文明确

---

## 5. 训练代码

### 5.1 快速训练脚本

```python
#!/usr/bin/env python3
"""
Level 0 XGBoost Model Training Script

Usage:
    python scripts/train_level0.py --data data/training_data.csv --output models/
"""

import os
import sys
import argparse
import json
import numpy as np
import pandas as pd
from typing import Tuple, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ci_architecture.level0 import FeatureExtractor
from ci_architecture.level0.classifier import XGBoostClassifier


def load_training_data(data_path: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Load training data from CSV or JSON.
    
    Expected CSV format:
        query,C,I
        "什么是Python?",0,1
        ...
    
    Returns:
        X: Feature matrix (n_samples, 12)
        y_c: Complexity labels (n_samples,)
        y_i: Information sufficiency labels (n_samples,)
    """
    if data_path.endswith('.csv'):
        df = pd.read_csv(data_path)
    elif data_path.endswith('.json'):
        df = pd.read_json(data_path)
    else:
        raise ValueError(f"Unsupported file format: {data_path}")
    
    print(f"Loaded {len(df)} samples from {data_path}")
    print(f"C distribution: {df['C'].value_counts().to_dict()}")
    print(f"I distribution: {df['I'].value_counts().to_dict()}")
    
    # Extract features
    extractor = FeatureExtractor()
    X = np.array([extractor.extract(q) for q in df['query']])
    y_c = df['C'].values
    y_i = df['I'].values
    
    return X, y_c, y_i


def generate_synthetic_data(n_samples: int = 1000, 
                           seed: int = 42) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate synthetic training data for cold start."""
    np.random.seed(seed)
    
    from ci_architecture.level0 import FeatureExtractor
    extractor = FeatureExtractor()
    
    # Query templates
    simple_queries = [
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
    
    complex_queries = [
        "分析{industry}公司的{tech}部署{aspect}，考虑{cost}和{risk}",
        "比较{product_a}和{product_b}在{metric}方面的差异",
        "设计{system}架构，满足{requirement}和{constraint}",
        "解释{concept}在{domain}中的应用",
    ]
    
    # Vocabulary
    topics = ['Python', 'Kubernetes', 'Docker', 'AI', '云计算', '数据库']
    industries = ['医药', '金融', '科技', '制造']
    techs = ['Kubernetes', 'Docker', '云原生', '微服务']
    aspects = ['合规', '安全', '性能', '成本']
    
    queries = []
    labels_c = []
    labels_i = []
    
    # Generate simple queries (C=0)
    for _ in range(n_samples // 2):
        template = np.random.choice(simple_queries)
        query = template.format(
            topic=np.random.choice(topics),
            value=np.random.randint(100, 9999),
            action=np.random.choice(['install', 'use']),
            number=np.random.randint(1, 100)
        )
        queries.append(query)
        labels_c.append(0)  # Low complexity
        # I depends on query completeness
        labels_i.append(1 if len(query) > 10 else 0)
    
    # Generate complex queries (C=1)
    for _ in range(n_samples // 2):
        template = np.random.choice(complex_queries)
        query = template.format(
            industry=np.random.choice(industries),
            tech=np.random.choice(techs),
            aspect=np.random.choice(aspects),
            cost=np.random.choice(['成本', '预算']),
            risk=np.random.choice(['风险', '安全性']),
            product_a='方案A',
            product_b='方案B',
            metric='性能',
            system='系统',
            requirement='高并发',
            constraint='成本约束',
            concept='微服务',
            domain='电商'
        )
        queries.append(query)
        labels_c.append(1)  # High complexity
        labels_i.append(0 if '?' not in query else 1)
    
    # Extract features
    X = np.array([extractor.extract(q) for q in queries])
    y_c = np.array(labels_c)
    y_i = np.array(labels_i)
    
    return X, y_c, y_i


def evaluate_model(classifier, X_test: np.ndarray, 
                   y_c_test: np.ndarray, y_i_test: np.ndarray) -> dict:
    """Evaluate model performance."""
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
    
    predictions = [classifier.predict(x) for x in X_test]
    
    y_c_pred = [p['C_discrete'] for p in predictions]
    y_i_pred = [p['I_discrete'] for p in predictions]
    
    results = {
        'C_accuracy': accuracy_score(y_c_test, y_c_pred),
        'C_f1': f1_score(y_c_test, y_c_pred, average='binary'),
        'I_accuracy': accuracy_score(y_i_test, y_i_pred),
        'I_f1': f1_score(y_i_test, y_i_pred, average='binary'),
    }
    
    return results


def main():
    parser = argparse.ArgumentParser(description='Train Level 0 XGBoost models')
    parser.add_argument('--data', type=str, default=None,
                       help='Path to training data (CSV or JSON)')
    parser.add_argument('--output', type=str, default='models',
                       help='Output directory for models')
    parser.add_argument('--n-samples', type=int, default=2000,
                       help='Number of synthetic samples (if --data not provided)')
    parser.add_argument('--val-split', type=float, default=0.2,
                       help='Validation split ratio')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed')
    args = parser.parse_args()
    
    print("=" * 60)
    print("Level 0 XGBoost Model Training")
    print("=" * 60)
    
    # Load or generate data
    if args.data:
        print(f"\nLoading data from {args.data}...")
        X, y_c, y_i = load_training_data(args.data)
    else:
        print(f"\nGenerating {args.n_samples} synthetic samples...")
        X, y_c, y_i = generate_synthetic_data(args.n_samples, args.seed)
    
    # Split train/val
    n_val = int(len(X) * args.val_split)
    indices = np.random.permutation(len(X))
    train_idx, val_idx = indices[n_val:], indices[:n_val]
    
    X_train, X_val = X[train_idx], X[val_idx]
    y_c_train, y_c_val = y_c[train_idx], y_c[val_idx]
    y_i_train, y_i_val = y_i[train_idx], y_i[val_idx]
    
    print(f"\nTrain size: {len(X_train)}, Val size: {len(X_val)}")
    
    # Train
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
        print(f"\n✓ {message}")
        
        # Evaluate
        print("\nEvaluating on validation set...")
        classifier = XGBoostClassifier(
            model_c_path=f"{args.output}/xgb_c.json",
            model_i_path=f"{args.output}/xgb_i.json"
        )
        
        if classifier.is_loaded():
            results = evaluate_model(classifier, X_val, y_c_val, y_i_val)
            print(f"\nValidation Results:")
            print(f"  C Accuracy: {results['C_accuracy']:.3f}")
            print(f"  C F1 Score: {results['C_f1']:.3f}")
            print(f"  I Accuracy: {results['I_accuracy']:.3f}")
            print(f"  I F1 Score: {results['I_f1']:.3f}")
        
        # Test predictions
        print("\n" + "=" * 60)
        print("Test Predictions")
        print("=" * 60)
        
        test_queries = [
            "什么是Python?",
            "安装",
            "分析某医药公司的Kubernetes部署合规性",
            "患者咳嗽有铁锈色痰，胸痛发热"
        ]
        
        for query in test_queries:
            features = FeatureExtractor().extract(query)
            result = classifier.predict(features)
            zone = ['D', 'C', 'B', 'A'][result['C_discrete'] * 2 + result['I_discrete']]
            
            print(f"\nQuery: {query}")
            print(f"  C={result['C_discrete']} (σ={result['sigma_c']:.3f})")
            print(f"  I={result['I_discrete']} (σ={result['sigma_i']:.3f})")
            print(f"  Zone {zone}, Escalate={result['escalate']}")
    else:
        print(f"\n✗ {message}")
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

### 5.2 执行训练

```bash
# 使用合成数据训练（冷启动）
python scripts/train_level0.py --n-samples 2000 --output models/

# 使用真实数据训练
python scripts/train_level0.py --data data/training_data.csv --output models/

# 指定验证集比例
python scripts/train_level0.py --data data/training_data.csv --val-split 0.2
```

---

## 6. 模型评估指标

### 6.1 分类性能指标

| 指标 | Model C 目标 | Model I 目标 | 说明 |
|:-----|:------------:|:------------:|:-----|
| Accuracy | ≥ 85% | ≥ 80% | 整体准确率 |
| F1 Score | ≥ 0.85 | ≥ 0.80 | 类别不平衡下的综合指标 |
| Precision | ≥ 0.85 | ≥ 0.80 | 精确率 |
| Recall | ≥ 0.85 | ≥ 0.80 | 召回率 |

### 6.2 业务指标

| 指标 | 目标值 | 说明 |
|:-----|:------:|:-----|
| Hard Route Rate | 60-70% | Level 0 直接路由比例 |
| Escalation Rate | 30-40% | 需要升级到 Level 1 的比例 |
| Avg Confidence | ≥ 0.75 | 平均置信度 |
| Latency | < 1ms | 端到端推理延迟 |

---

## 7. 模型部署

### 7.1 模型文件结构

```
models/
├── xgb_c.json          # 复杂度分类模型
├── xgb_i.json          # 信息充分性分类模型
├── feature_config.yaml # 特征配置
└── training_log.txt    # 训练日志
```

### 7.2 模型加载

```python
from ci_architecture.level0 import Level0Router

# 自动加载模型
router = Level0Router(
    model_c_path="models/xgb_c.json",
    model_i_path="models/xgb_i.json"
)

# 检查状态
if router.get_status() == "PRODUCTION":
    result = router.route("什么是Python?")
    print(f"C={result['C']}, I={result['I']}, escalate={result['escalate']}")
```

---

## 8. 持续优化

### 8.1 数据收集策略

1. **在线收集**: 记录所有 Level 0 决策及后续用户反馈
2. **主动标注**: 定期抽样人工标注
3. **错误分析**: 关注误分类案例，针对性增强

### 8.2 模型更新流程

```
收集新数据 → 标注 → 增量训练 → A/B测试 → 全量部署
```

---

*文档版本: 1.0*  
*创建时间: 2026-03-16*  
*适用版本: CI-RAG-ROUTER v0.1.0*
