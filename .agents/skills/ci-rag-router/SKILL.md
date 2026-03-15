# CI-RAG-ROUTER 关键概念查询 SKILL

## 概述

本 SKILL 用于 CI-RAG-ROUTER (Confidence-Informed RAG Router) 框架的关键概念查询和开发参考。CI-RAG-ROUTER 是一个三层渐进式升级的查询路由系统，通过置信度感知的架构实现成本-精度-延迟的帕累托最优。

---

## 核心概念速查

### 1. 三层渐进式架构 (Three-Tier Progressive Escalation)

| 层级 | 技术 | 延迟预算 | 处理比例 | 核心职责 |
|------|------|----------|----------|----------|
| **Level 0** | XGBoost 双模型 | <1ms | ~60% | 零Token快速筛选 |
| **Level 1** | 混合检索验证 | ~50ms | ~30% | 多源置信度融合 |
| **Level 2** | LLM 语义精化 | ~100ms | ~10% | 最终仲裁与精化 |

**黄金法则**: "绝不前置LLM" - 昂贵的LLM调用仅用于真正需要分类的查询。

### 2. CI 分类体系 (Complexity & Information)

#### 2.1 复杂度 (C - Complexity)
- **C = 0 (低复杂度)**: 直接查询、简单转换
- **C = 1 (高复杂度)**: 多步推理、领域综合、歧义处理

#### 2.2 信息充分性 (I - Information Sufficiency)
- **I = 0 (信息不足)**: 需要外部检索补充
- **I = 1 (信息充分)**: 可从现有知识源直接回答

#### 2.3 ABCD 四区路由

| 区域 | C | I | 执行策略 | Token预算 | 延迟目标 |
|------|---|---|----------|-----------|----------|
| **A** | ≥0.7 | ≥0.7 | 结构化对抗生成+检索验证 | 2048 | 2-3s |
| **B** | ≥0.7 | <0.3 | 并行RAG+外部补全 | 3072 | 3-5s |
| **C** | <0.3 | ≥0.7 | 直接块输出，最小生成 | 512 | <500ms |
| **D** | <0.3 | <0.3 | 精准单点RAG+严格约束 | 1024 | 1-2s |

### 3. 置信度机制

#### 3.1 统一逃逸阈值 (α = 0.7)
```
Query → Level 0 ──σ<0.7──→ Level 1 ──σ<0.7──→ Level 2 ──σ<0.7──→ Fallback
          │                      │                      │
          σ≥0.7                  σ≥0.7                  σ≥0.7
          ↓                      ↓                      ↓
      Hard Route to ABCD    Hard Route or C-Refinement  Refined Route
```

#### 3.2 保守联合置信度
```python
sigma_joint = min(sigma_c, sigma_i)
```
**原则**: 复杂度和信息充分性都必须被确信评估，才能硬路由。

---

## Level 0: 零Token XGBoost 分类器

### 4. 冷启动策略: 启发式规则 + XGBoost 并行

#### 4.1 架构设计

Level 0 采用**双轨并行架构**，支持平滑从冷启动过渡到模型驱动：

```
Query Input
    │
    ▼
┌─────────────────────────────────────────┐
│           Level 0 Router                │
│  ┌─────────────────────────────────┐   │
│  │   Model State Detection         │   │
│  │   (检查模型文件是否存在且有效)   │   │
│  └─────────────────────────────────┘   │
│              │                          │
│      ┌───────┴───────┐                  │
│      ▼               ▼                  │
│  [未训练]        [已训练]                │
│      │               │                  │
│      ▼               ▼                  │
│  Heuristic    XGBoost + Heuristic       │
│   Only         (并行运行)                │
│      │               │                  │
│      └───────┬───────┘                  │
│              ▼                          │
│        Decision Logic                   │
│   (优先模型预测，规则兜底)              │
└─────────────────────────────────────────┘
```

#### 4.2 模型状态检测

```python
class Level0Router:
    def __init__(self, model_c_path: str, model_i_path: str):
        self.heuristic = HeuristicRouter()
        self.xgb = None
        
        # 模型状态检测: 文件存在 + 可加载 + 非空
        if self._check_model_valid(model_c_path) and \
           self._check_model_valid(model_i_path):
            self.xgb = XGBoostRouter(model_c_path, model_i_path)
            self.status = "TRAINED"
        else:
            self.status = "COLD_START"
    
    def _check_model_valid(self, path: str) -> bool:
        """检查模型文件是否有效"""
        if not os.path.exists(path):
            return False
        try:
            model = xgb.Booster()
            model.load_model(path)
            # 验证模型非空 (有树结构)
            return len(model.get_dump()) > 0
        except:
            return False
```

#### 4.3 冷启动阶段 (模型未训练前)

**策略**: 100% 启发式规则，强制升级到 Level 1 收集训练数据

```python
def predict_cold_start(self, features: np.ndarray) -> dict:
    """
    冷启动模式: 仅使用启发式规则，保守策略
    所有查询标记为不确定，强制升级到 Level 1
    """
    heuristic_result = self.heuristic.predict(features)
    
    # 强制降低置信度，确保升级到 Level 1 进行数据收集
    return {
        'C': heuristic_result['C'],
        'I': heuristic_result['I'],
        'sigma_c': 0.5,  # 强制低置信度
        'sigma_i': 0.5,  # 强制低置信度
        'sigma_joint': 0.5,  # < 0.7, 触发升级
        'escalate': True,
        'mode': 'COLD_START_HEURISTIC',
        'note': 'XGBoost模型未训练，强制升级收集数据'
    }
```

**启发式规则实现**:

```python
class HeuristicRouter:
    """基于特征的硬编码规则路由"""
    
    DOMAIN_KEYWORDS = {
        'medicine': ['医药', '医疗', '药品', '临床', '诊断'],
        'technology': ['Kubernetes', 'Docker', '云原生', 'API', '算法'],
        'legal': ['合规', '法规', '法律', '合同', '条款'],
        'finance': ['财务', '投资', '股票', '收益率', '成本'],
    }
    
    def predict(self, features: np.ndarray) -> dict:
        len_word = features[1]
        domain_switch = features[4]
        char_entropy = features[2]
        has_question = features[5]
        digit_ratio = features[6]
        
        # C (复杂度) 判断
        if domain_switch >= 2 or len_word > 50 or char_entropy > 4.0:
            C = 1  # 高复杂度
        elif len_word < 10 and domain_switch == 0:
            C = 0  # 低复杂度
        else:
            C = 0  # 默认低复杂度
        
        # I (信息充分性) 判断
        if has_question and digit_ratio > 0.3:
            I = 1  # 可能包含明确实体，信息较充分
        elif len_word < 5:
            I = 0  # 太短，信息可能不足
        else:
            I = 1  # 默认信息充分
        
        return {'C': C, 'I': I}
```

#### 4.4 并行运行阶段 (模型已训练)

**策略**: XGBoost 和启发式规则并行运行，XGBoost 优先，规则兜底

```python
def predict_parallel(self, features: np.ndarray) -> dict:
    """
    并行模式: XGBoost + 启发式规则
    优先使用 XGBoost，置信度低时使用规则兜底
    """
    # 并行获取两种预测
    xgb_result = self.xgb.predict(features)
    heuristic_result = self.heuristic.predict(features)
    
    # 决策逻辑
    if xgb_result['sigma_joint'] >= 0.7:
        # XGBoost 高置信度，直接使用
        return {
            **xgb_result,
            'mode': 'XGBoost_HIGH_CONF',
            'heuristic_backup': heuristic_result
        }
    elif xgb_result['sigma_joint'] >= 0.5:
        # XGBoost 中等置信度，使用模型但标记
        return {
            **xgb_result,
            'mode': 'XGBoost_MEDIUM_CONF',
            'heuristic_backup': heuristic_result
        }
    else:
        # XGBoost 低置信度，回退到启发式规则
        return {
            'C': heuristic_result['C'],
            'I': heuristic_result['I'],
            'sigma_c': 0.55,
            'sigma_i': 0.55,
            'sigma_joint': 0.55,
            'escalate': True,
            'mode': 'HEURISTIC_FALLBACK',
            'xgb_result': xgb_result  # 保留用于日志分析
        }
```

### 5. 12维特征向量

| 特征 | 名称 | 说明 | CI信号 |
|------|------|------|--------|
| 0 | `len_char` | 字符长度 | 规模指标 |
| 1 | `len_word` | 词数（空格分割） | 语义密度 |
| 2 | `char_entropy` | 字符级香农熵 | 随机性/异常检测 |
| 3 | `word_entropy` | 词级香农熵 | 词汇多样性 |
| 4 | `domain_switch_cnt` | 领域切换次数 | 跨域复杂度 |
| 5 | `has_question` | 是否疑问句 | 信息需求意图 |
| 6 | `digit_ratio` | 数字比例 | 定量精度需求 |
| 7-11 | `user_historical_freq` | 用户历史频率等 | 个性化 |

### 6. 双XGBoost模型设计

#### 6.1 Model C: 复杂度分类器
```python
xgb.XGBClassifier(
    max_depth=6,
    n_estimators=150,
    learning_rate=0.05,
    tree_method='hist',  # CPU优化
    objective='binary:logistic'
)
```

#### 6.2 Model I: 信息充分性分类器
- 训练目标: 预测知识源是否包含足够信息
- 强依赖历史特征和领域特定指标

#### 6.3 渐进式启用策略

| 阶段 | 模型状态 | 策略 | 升级到 Level 1 比例 |
|------|----------|------|-------------------|
| **Week 1** | 未训练 | 100% 启发式规则，强制升级 | ~80% |
| **Week 2** | 初始训练 | XGBoost + 规则并行，保守阈值 (α=0.6) | ~60% |
| **Week 3-4** | 校准优化 | XGBoost 主导，α=0.7 | ~40% |
| **Month 2+** | 成熟 | 完整 XGBoost + 规则兜底 | ~30% |

---

## Level 1: 混合检索验证

### 6. 三种并行检索模态

| 模态 | 技术栈 | 典型延迟 | 核心指标 |
|------|--------|----------|----------|
| **向量语义检索** | sentence-transformers + FAISS | 15-25ms | `sim_max`, `gap`, `entropy` |
| **结构化数据查询** | SQL/KG + 意图识别 | 10-30ms | schema匹配率, 行数, 空值率 |
| **关键词倒排索引** | jieba + BM25 | 5-10ms | TF-IDF分数, 布尔匹配 |

### 7. 向量检索配置

```python
# 推荐模型: paraphrase-multilingual-MiniLM-L12-v2
# - 384维, 支持50+语言（含中英）
# - CPU推理: ~5000 queries/sec

# FAISS索引选择
| 数据规模 | 索引类型 | 搜索延迟 | 召回率 |
|----------|----------|----------|--------|
| <100K | IndexFlatL2 | 1-2ms | 100% |
| 100K-10M | IndexIVFFlat | 5-10ms | >99% |
| 10M-100M | IndexIVFPQ | 10-20ms | ~95% |
```

### 8. 置信度融合权重

```python
FUSION_WEIGHTS = {
    'vector': 0.4,      # 语义相关性
    'structured': 0.5,  # 结构化查询可靠性
    'keyword': 0.1      # 关键词匹配（较低权重）
}
```

### 9. 冲突检测

**触发条件**:
- 数值分歧: `max(conf) - min(conf) > 0.5`
- 质性不匹配: 一源强正(>0.8)，另一源强负(<0.3)

**惩罚**: `sigma_I *= 0.6` → 强制升级到Level 2

### 10. C验证与微调

```python
# 历史复杂度调整
delta = damping * (hist_mean - c0)  # damping = 0.3
delta = clip(delta, -0.2, +0.2)     # 有界调整
c1 = c0 + delta
sigma_c1 = min(0.95, sigma_c0 * 1.1)  # 置信度提升，上限0.95
```

---

## Level 2: LLM 语义精化

### 11. LLM接口配置

```python
# 使用 litellm 统一API
primary_model = "gpt-4"
fallback_models = ["gpt-3.5-turbo", "claude-3-haiku"]
temperature = 0.1  # 确定性置信度估计
max_tokens = 150   # 结构化输出约束
```

### 12. 强制JSON输出格式

```json
{
  "C": 0.00-1.00,
  "I": 0.00-1.00,
  "confidence": 0.00-1.00,
  "missing_info": ["..."],
  "reasoning": "..."
}
```

### 13. 双探针一致性验证

```python
# 执行2次独立评估
consistency_threshold = 0.8  # Jaccard相似度

# 置信度调整
if avg_similarity >= 0.8: adjustment = 1.1
elif avg_similarity >= 0.5: adjustment = 0.9
else: adjustment = 0.6  # 强烈降级
```

---

## 关键依赖库

| 库 | 版本 | 用途 |
|----|------|------|
| **xgboost** | ≥2.0.0 | Level 0 双模型分类 |
| **sentence-transformers** | ≥2.2.0 | 语义嵌入生成 |
| **faiss-cpu** | ≥1.7.0 | 高效向量搜索 |
| **jieba** | ≥0.42.1 | 中文分词 |
| **litellm** | ≥1.0.0 | 统一LLM API |
| **scikit-learn** | ≥1.3.0 | 置信度校准(IsotonicRegression) |
| **networkx** | ≥3.0 | 知识图谱遍历(可选) |

---

## 监控指标

### 14. 逃逸率金字塔

| 指标 | 目标范围 | 异常触发 |
|------|----------|----------|
| L0 → L1 逃逸率 | 30-40% | >50% 或 <20% |
| L1 → L2 逃逸率 | 20-30% (占L1) | >40% |
| L2 → Fallback 率 | <10% (占L2) | >20% |

### 15. 校准误差

```python
# 期望校准误差 (ECE)
Target: ECE < 0.05

# C修正率 (Level 1对Level 0的修正)
Target: < 20%
```

---

## 回退策略

### 16. 强制保守默认 (Zone B)

```python
# 当 sigma < ALPHA 在Level 2后
default = {
    'C': 1.0,   # 假设最大复杂度
    'I': 0.0,   # 假设信息不足
    'zone': 'B',
    'strategy': 'CONSERVATIVE',
    'parallel_rag_streams': 4,
    'verification_rounds': 2
}
```

### 17. 查询拒绝条件

- Level 2置信度 < 0.3
- 双探针一致性 < 0.3
- 解析失败 ≥ 3次重试

---

## 快速参考: 核心公式

```python
# 保守联合置信度
sigma_joint = min(sigma_c, sigma_i)

# 硬路由决策
if sigma_joint >= ALPHA:  # 0.7
    route_to_zone(C_discrete, I_discrete)
else:
    escalate_to_next_level()

# 特征熵计算
H(X) = -sum(p(x_i) * log2(p(x_i)))

# BM25打分
score = idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avg_len))
```

---

## 使用示例

### 查询CI分析流程

```
输入: "分析某医药公司的Kubernetes部署合规性"

Level 0:
  - 特征提取: len_word=8, domain_switch_cnt=2 (medicine→tech→legal)
  - XGBoost预测: C=1, I=0, sigma_c=0.85, sigma_i=0.60
  - sigma_joint = min(0.85, 0.60) = 0.60 < 0.7 → 升级到Level 1

Level 1:
  - 向量检索: sim_max=0.75, gap=0.15, entropy=0.4
  - 结构化查询: schema_match=0.8, row_count=5, null_ratio=0.1
  - 置信度融合: I_mean=0.65, sigma_I=0.55
  - C验证: 历史匹配确认C=1, sigma_c1=0.75
  - sigma_joint = min(0.75, 0.55) = 0.55 < 0.7 → 升级到Level 2

Level 2:
  - LLM评估: C=0.85, I=0.45, confidence=0.82
  - 双探针验证: consistency=0.85 → confidence *= 1.1 = 0.90
  - sigma_joint = 0.90 >= 0.7 → 硬路由到 Zone B

输出: Zone B (C=1, I=0) - 并行RAG + 外部补全
```

---

## 相关文档

- `RAG-CI-ROUTER.md` - 完整实现手册
- `doc/development-plan.md` - 开发计划
