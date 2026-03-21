# ABCD 四区与 Level 2 数据交互规范

## 1. 概述

本文档定义 ABCD 四个区域与 Level 2 的数据交互规范。

**核心原则**: Level 0/1 已提供 C/I 分类，Level 2 的两种调用模式职责不同：
- **轻量调用**: 只生成转区策略和方案 (guide)，**不返回 C/I**
- **完整调用**: 深度 CI 评估，**返回 C/I**

---

## 2. 两种调用模式的区别

```
┌─────────────────────────────────────────────────────────────┐
│                    Level 2 路由器                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐        ┌──────────────────┐          │
│  │   轻量调用        │        │   完整调用        │          │
│  │  generate_guide  │        │   arbitrate      │          │
│  ├──────────────────┤        ├──────────────────┤          │
│  │  延迟: ~50ms     │        │  延迟: ~100ms    │          │
│  │  Token: ~100     │        │  Token: ~200     │          │
│  │                  │        │                  │          │
│  │  **输出**:       │        │  **输出**:       │          │
│  │  - strategy      │        │  - C (复杂度)    │          │
│  │  - plans         │        │  - I (充分性)    │          │
│  │  - confidence    │        │  - confidence    │          │
│  │                  │        │  - reasoning     │          │
│  │  **不返回 C/I**  │        │                  │          │
│  └────────┬─────────┘        └────────┬─────────┘          │
│           │                           │                     │
│           ▼                           ▼                     │
│  ┌─────────────────┐      ┌──────────────────┐             │
│  │ orchestrator_   │      │   ci_assessment  │             │
│  │    guide        │      │                  │             │
│  │ (转区策略方案)   │      │ (CI 仲裁结果)     │             │
│  └─────────────────┘      └──────────────────┘             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 调用选择矩阵

| 场景 | 调用模式 | 原因 |
|:-----|:---------|:-----|
| Zone A/B/D 需要转区策略 | **轻量调用** | L0/L1 已提供 C/I，只需方案 |
| 验证 L0/L1 分类 | **完整调用** | 需要独立评估 C/I |
| 置信度低需要交叉验证 | **完整调用** | 需要 reasoning 和 details |
| CI Tracker 仲裁分歧 | **完整调用** | 需要独立的 C/I 判断 |

---

## 3. Zone C - 终点区 (不调用 L2)

### 3.1 判定条件
- **C = 0** (低复杂度)
- **I = 1** (信息充分)

### 3.2 处理流程
```
Query (C0I1)
    ↓
[跳过 L2 调用]
    ↓
直接执行 Zone C 输出
```

### 3.3 说明
Zone C 是**终点**，不需要任何 L2 调用。

---

## 4. Zone A - 拆解区 (C1I1)

### 4.1 判定条件
- **C = 1** (高复杂度) - 来自 L0
- **I = 1** (信息充分) - 来自 L1

### 4.2 轻量调用模式 (推荐)

#### 4.2.1 输入
```python
{
    "query": "设计一个支持百万并发的电商系统",
    "current_zone": "A",           # L0/L1 已确定
    "level0_result": {"C": 1},     # 仅传递 C
    "level1_result": {"I": 1}      # 仅传递 I
}
```

#### 4.2.2 输出 - **注意：不包含 C/I**
```json
{
    "// 核心策略": "",
    "missing_info": [],
    "decomposable": true,
    "recommended": ["decompose_only"],
    "confidence": 0.88,
    
    "// Zone A 专用：拆解方案": "",
    "decomposition_plan": {
        "sub_problems": [
            {
                "id": "sp_1",
                "query": "百万并发系统的核心架构模式选择",
                "expected_C": 0,
                "expected_I": 1,
                "dependencies": []
            }
        ],
        "aggregation_prompt": "请将各子系统设计方案整合...",
        "parallel": true,
        "estimated_sub_tokens": 512
    },
    
    "// Zone A 不需要检索": "",
    "retrieval_plan": null,
    
    "// 预估轮数": "Zone A 通常 1 轮拆解即可",
    "estimated_rounds": 1,
    
    "_meta": {
        "source": "level2_light",
        "latency_ms": 52,
        "cost_usd": 0.0001
    }
}
```

### 4.3 完整调用模式 (验证场景)

#### 4.3.1 使用场景
- 轻量调用置信度 `< 0.7`
- 需要交叉验证 L0/L1 分类

#### 4.3.2 输出 - **包含 C/I**
```json
{
    "// 完整调用特有的 CI 评估": "",
    "C": 1,
    "I": 1,
    "confidence": 0.92,
    "reasoning": "查询涉及多个复杂技术领域，需要系统性拆解。信息充足...",
    
    "// 仲裁详情": "",
    "arbitration_details": {
        "probe_consistency": 0.95,
        "cross_validation": {
            "l0_C": 1,
            "l1_I": 1,
            "agreement": true
        }
    },
    
    "// 与轻量调用相同的策略部分": "",
    "recommended_strategy": "decompose_only",
    "decomposition_plan": {...},
    "retrieval_plan": null
}
```

---

## 5. Zone D - 补 I 区 (C0I0)

### 5.1 判定条件
- **C = 0** (低复杂度) - 来自 L0
- **I = 0** (信息不足) - 来自 L1

### 5.2 轻量调用模式 (推荐)

#### 5.2.1 输入
```python
{
    "query": "这个药怎么用？",
    "current_zone": "D",           # L0/L1 已确定
    "level0_result": {"C": 0},     # 仅传递 C
    "level1_result": {"I": 0}      # 仅传递 I
}
```

#### 5.2.2 输出 - **注意：不包含 C/I**
```json
{
    "// 核心策略": "",
    "missing_info": [
        "药品名称",
        "患者年龄"
    ],
    "decomposable": false,
    "recommended": ["retrieve_only"],
    "confidence": 0.85,
    
    "// Zone D 不需要拆解": "",
    "decomposition_plan": null,
    
    "// Zone D 专用：补 I 方案": "",
    "retrieval_plan": {
        "required_info": [
            {"field": "medicine_name", "type": "entity", "critical": true},
            {"field": "patient_age", "type": "number", "critical": true}
        ],
        "suggested_keywords": ["用法用量", "说明书"],
        "clarification_prompt": "请提供药品名称和患者年龄...",
        "expected_enhancement": "C=0, I=1"
    },
    
    "estimated_rounds": 1,
    
    "_meta": {
        "source": "level2_light",
        "latency_ms": 48
    }
}
```

### 5.3 完整调用模式 (验证场景)

#### 5.3.1 输出 - **包含 C/I**
```json
{
    "C": 0,
    "I": 0,
    "confidence": 0.88,
    "reasoning": "查询过于简短，缺少关键实体...",
    
    "arbitration_details": {
        "information_gaps": [
            {"type": "entity", "severity": "critical"}
        ],
        "retrieval_feasibility": 0.3
    },
    
    "recommended_strategy": "clarify",
    "retrieval_plan": {...}
}
```

---

## 6. Zone B - 复杂区 (C1I0)

### 6.1 判定条件
- **C = 1** (高复杂度) - 来自 L0
- **I = 0** (信息不足) - 来自 L1

### 6.2 轻量调用模式 (推荐)

#### 6.2.1 输入
```python
{
    "query": "设计一个高并发电商系统",
    "current_zone": "B",           # L0/L1 已确定
    "level0_result": {"C": 1},     # 仅传递 C
    "level1_result": {"I": 0}      # 仅传递 I
}
```

#### 6.2.2 输出 - **注意：不包含 C/I**
```json
{
    "// 核心策略": "",
    "missing_info": ["QPS", "预算", "数据规模"],
    "decomposable": true,
    "recommended": ["decompose_first", "clarify_first"],
    "confidence": 0.82,
    
    "// Zone B 专用：两种方案都需要": "",
    "decomposition_plan": {
        "sub_problems": [
            {
                "id": "sp_1",
                "query": "架构模式选择 [待补充QPS]",
                "expected_C": 0,
                "expected_I": 0,
                "needs_retrieval": true
            }
        ],
        "aggregation_prompt": "整合各子系统方案...",
        "parallel": true
    },
    
    "retrieval_plan": {
        "required_info": [
            {"field": "qps", "type": "number"},
            {"field": "budget", "type": "enum"}
        ],
        "clarification_prompt": "请提供 QPS 和预算...",
        "alternative_approach": "也可直接给出通用方案"
    },
    
    "// Zone B 专用：策略对比": "",
    "strategy_comparison": {
        "decompose_first": {
            "pros": ["并行处理更快"],
            "cons": ["子问题也可能缺信息"],
            "estimated_rounds": 2
        },
        "clarify_first": {
            "pros": ["信息完整后更准确"],
            "cons": ["用户负担大"],
            "estimated_rounds": 2
        }
    },
    
    "estimated_rounds": 2,
    
    "_meta": {
        "source": "level2_light",
        "latency_ms": 55
    }
}
```

### 6.3 完整调用模式 (策略决策场景)

#### 6.3.1 输出 - **包含 C/I**
```json
{
    "C": 1,
    "I": 0,
    "confidence": 0.85,
    "reasoning": "典型的复杂系统设计问题，建议采用分解优先策略...",
    
    "arbitration_details": {
        "recommended_strategy": "decompose_first",
        "reasoning": "用户更可能接受分步澄清",
        "fallback_ready": true
    },
    
    "decomposition_plan": {...},
    "retrieval_plan": {...}
}
```

---

## 7. 输出字段对比表

### 7.1 轻量调用 vs 完整调用

| 字段 | 轻量调用 | 完整调用 | 说明 |
|:-----|:--------:|:--------:|:-----|
| `C` | ❌ 无 | ✅ 有 | 复杂度评估 |
| `I` | ❌ 无 | ✅ 有 | 信息充分性评估 |
| `confidence` | ✅ 有 | ✅ 有 | 置信度 |
| `reasoning` | ❌ 无 | ✅ 有 | 推理过程 |
| `missing_info` | ✅ 有 | ✅ 有 | 缺失信息 |
| `decomposable` | ✅ 有 | ✅ 有 | 是否可拆解 |
| `recommended` | ✅ 有 | ✅ 有 | 推荐策略 |
| `decomposition_plan` | ✅ 有 | ✅ 有 | 拆解方案 |
| `retrieval_plan` | ✅ 有 | ✅ 有 | 检索方案 |
| `estimated_rounds` | ✅ 有 | ✅ 有 | 预估轮数 |
| `arbitration_details` | ❌ 无 | ✅ 有 | 仲裁详情 |

### 7.2 Zone 专用字段

| 字段 | Zone A | Zone D | Zone B | 说明 |
|:-----|:------:|:------:|:------:|:-----|
| `missing_info` | `[]` | `[...]` | `[...]` | 缺失信息 |
| `decomposable` | `true` | `false` | `true` | 是否可拆解 |
| `recommended` | `["decompose_only"]` | `["retrieve_only"]` | `["decompose_first", ...]` | 推荐策略 |
| `decomposition_plan` | **有** | `null` | **有** | 拆解计划 |
| `retrieval_plan` | `null` | **有** | **有** | 检索计划 |
| `strategy_comparison` | ❌ | ❌ | **有** | 策略对比 |

---

## 8. 调用流程图

### 8.1 协调器调用决策

```
协调器收到 Query
    ↓
L0 Router: 输出 C
    ↓
L1 Router: 输出 I
    ↓
确定 Zone (A/B/C/D)
    ↓
Zone C? ──► 直接输出 (不调用 L2)
    ↓ 否
Zone A/D/B?
    ↓
检查置信度阈值
    ↓
置信度 ≥ 0.7? ──► 轻量调用 generate_orchestrator_guide()
    ↓ 否
完整调用 arbitrate()
    ↓
返回结果 + C/I (用于验证)
```

### 8.2 Zone A 数据流

```
协调器 ───────────────────────────────────────► Level 2
  │                                               │
  │  [轻量模式 - 推荐]                            │
  ├─► generate_orchestrator_guide(zone="A") ─────►│
  │     L0: C=1, L1: I=1                          │
  │                                               │
  │◄──────────────────────────────────────────────┤
  │     Guide (无 C/I):                           │
  │       decomposable: true                      │
  │       decomposition_plan: {...}               │
  │       retrieval_plan: null                    │
  │                                               │
  │  [如置信度<0.7，完整模式]                      │
  ├─► arbitrate() ──────────────────────────────►│
  │                                               │
  │◄──────────────────────────────────────────────┤
  │     Assessment (含 C/I):                      │
  │       C: 1 (验证 L0)                          │
  │       I: 1 (验证 L1)                          │
  │       decomposition_plan: {...}               │
```

---

## 9. 数据结构定义

### 9.1 轻量调用输出结构

```python
class OrchestratorGuide(BaseModel):
    """轻量调用输出 - 不包含 C/I"""
    
    # 策略部分
    missing_info: List[str]          # 缺失信息列表
    decomposable: bool               # 是否可拆解
    recommended: List[str]           # 推荐策略
    confidence: float                # 置信度
    
    # Zone 专用方案
    decomposition_plan: Optional[DecompositionPlan]  # Zone A/B
    retrieval_plan: Optional[RetrievalPlan]          # Zone D/B
    strategy_comparison: Optional[StrategyComparison]  # Zone B
    
    # 预估
    estimated_rounds: int            # 预估轮数
    
    # 元信息
    _meta: Dict                      # 延迟、成本等

class DecompositionPlan(BaseModel):
    sub_problems: List[SubProblem]
    aggregation_prompt: str
    parallel: bool
    estimated_sub_tokens: int

class RetrievalPlan(BaseModel):
    required_info: List[RequiredInfo]
    suggested_keywords: List[str]
    clarification_prompt: str
    expected_enhancement: str        # "C=x, I=y"
```

### 9.2 完整调用输出结构

```python
class CIAssessment(BaseModel):
    """完整调用输出 - 包含 C/I"""
    
    # CI 评估 (轻量调用没有)
    C: int                           # 0 或 1
    I: int                           # 0 或 1
    confidence: float
    reasoning: str                   # 推理过程
    
    # 仲裁详情 (轻量调用没有)
    arbitration_details: Dict
    
    # 策略部分 (与轻量调用相同)
    recommended_strategy: str
    decomposition_plan: Optional[DecompositionPlan]
    retrieval_plan: Optional[RetrievalPlan]
```

---

## 10. 调用决策总结

| Zone | 默认调用 | 完整调用条件 | 理由 |
|:-----|:---------|:-------------|:-----|
| **A** | 轻量 | 置信度<0.7 | L0/L1 已提供 C=1,I=1 |
| **D** | 轻量 | 置信度<0.7 | L0/L1 已提供 C=0,I=0 |
| **B** | 轻量 | 策略不明确 | L0/L1 已提供 C=1,I=0 |
| **C** | 不调用 | - | 直接输出 |

---

## 11. 常见错误

### 错误 1: 轻量调用返回 C/I
```python
# ❌ 错误
guide = l2_router.generate_orchestrator_guide(...)
if guide["C"] == 1:  # 轻量调用没有 C！
    ...

# ✅ 正确
zone = determine_zone(level0_result["C"], level1_result["I"])
guide = l2_router.generate_orchestrator_guide(zone=zone, ...)
# 使用 zone，而不是 guide["C"]
```

### 错误 2: 完整调用重复传 C/I
```python
# ❌ 错误
result = l2_router.arbitrate(query, C=1, I=0)

# ✅ 正确
result = l2_router.arbitrate(query)  # L2 自己评估 C/I
C = result["C"]  # 获取 L2 的独立评估
```

---

**文档版本**: 1.1  
**修正内容**: 明确区分轻量调用(无 C/I)与完整调用(有 C/I)  
**适用范围**: Level 2 Router V2.1+
