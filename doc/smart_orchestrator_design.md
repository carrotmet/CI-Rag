# Smart Orchestrator 智能协调器设计文档

## 1. 概述

Smart Orchestrator 是 CI-RAG-Router 的核心协调组件，负责：
- **在线 CI 数值判定**：实时评估查询的复杂度(C)和信息充分性(I)
- **动态转区决策**：将查询从非最优区转向最优区执行
- **查询重构**：通过信息补充或问题分解实现转区

## 2. 核心设计思想

### 2.1 最优区定义

| 最优区 | CI 条件 | 执行策略 | 适用场景 |
|:------:|:-------:|:---------|:---------|
| **Zone A** | C=1, I=1 | 推理输出 | LLM专注复杂推理，结构化生成 |
| **Zone C** | C=0, I=1 | 直接输出 | LLM直接回答，检索块输出 |

### 2.2 转区策略

```
Zone D (C0I0) ──信息补充──→ Zone C (C0I1)
     │                            │
     │ 精准补充特定信息            │ 直接输出
     │                            │
     └────────────────────────────┘

Zone B (C1I0) ──策略分支──┬──信息补充──→ Zone A (C1I1)
     │                    │
     │ 复杂+信息不足      │ 保留复杂度，补充关键信息
     │                    │
     └──问题分解──→ 多个 C0I1 ──聚合──→ Zone A
                          │
                          拆解为子问题，分别回答
```

## 3. 组件架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Smart Orchestrator                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │  CI Tracker │    │   Zone      │    │  Query      │     │
│  │  (CI追踪器)  │───→│  Transition │───→│ Reconstructor│    │
│  └─────────────┘    │  Engine     │    │             │     │
│                     │  (转区引擎)  │    │ (查询重构器) │     │
│                     └─────────────┘    └─────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### 3.1 CI Tracker (CI追踪器)

**职责**：
- 执行 L0 → L1 → L2 渐进式 CI 评估
- 追踪 CI 历史变化
- 用户补充信息后重新评估

**关键方法**：
- `evaluate(query)`：初始 CI 评估
- `update_with_info(info)`：补充信息后重评估

### 3.2 Zone Transition Engine (转区引擎)

**职责**：
- 判定当前区域
- 制定转区计划
- 选择转区策略

**转区策略表**：

| 当前区 | 目标区 | 策略 | 说明 |
|:------:|:------:|:-----|:-----|
| D | C | info_completion | 精准补充信息 |
| B | A | complexity_preserving | 补充信息，保持复杂度 |
| B | C | problem_decomposition | 问题分解为子问题 |

### 3.3 Query Reconstructor (查询重构器)

**职责**：
- 生成信息补充提示
- 分解复杂问题为子问题
- 聚合子问题结果

## 4. 转区详细流程

### 4.1 Zone D → Zone C (C0I0 → C0I1)

```
用户查询: "这个药怎么用？"
    │
    ▼
CI评估: C=0.2, I=0.1 → Zone D
    │
    ▼
识别缺失信息: ["药品名称", "患者年龄", "具体症状"]
    │
    ▼
生成澄清提示: "请告知药品名称和患者基本情况"
    │
    ▼
[等待用户补充]
    │
    ▼
用户补充: {"药品": "阿莫西林", "年龄": "成人"}
    │
    ▼
重新评估: C=0.2, I=0.85 → Zone C ✓
    │
    ▼
执行直接输出
```

### 4.2 Zone B → Zone A (C1I0 → C1I1)

```
用户查询: "分析这个症状"
    │
    ▼
CI评估: C=0.8, I=0.2 → Zone B
    │
    ▼
识别关键缺口: ["症状描述", "持续时间", "伴随症状"]
    │
    ▼
精准检索: 症状数据库 + 病历模式匹配
    │
    ▼
补充后评估: C=0.8, I=0.75 → Zone A ✓
    │
    ▼
执行推理输出
```

### 4.3 Zone B → 分解 → Zone C → 聚合

```
用户查询: "如何设计高并发电商系统？"
    │
    ▼
CI评估: C=0.9, I=0.3 → Zone B
    │
    ▼
问题分解:
  ├─ 子问题1: "高并发系统的核心架构模式？" (C=0.3, I=0.8)
  ├─ 子问题2: "电商系统的数据库设计要点？" (C=0.3, I=0.8)
  ├─ 子问题3: "缓存策略在高并发中的作用？" (C=0.3, I=0.8)
  └─ 子问题4: "负载均衡如何实现？" (C=0.3, I=0.8)
    │
    ▼
并行执行 (各子问题在 Zone C)
    │
    ▼
聚合结果 → 完整系统设计方案 (Zone A)
```

## 5. 关键数据结构

### 5.1 CIState

```python
@dataclass
class CIState:
    C: float              # 复杂度 (0-1)
    I: float              # 信息充分性 (0-1)
    sigma_c: float        # 复杂度置信度
    sigma_i: float        # 信息置信度
    timestamp: float      # 时间戳
```

### 5.2 SubProblem

```python
@dataclass
class SubProblem:
    id: str               # 子问题ID
    query: str            # 子问题查询
    parent_id: Optional[str]
    expected_ci: CIState  # 预期 CI
    dependencies: List[str]
```

### 5.3 ReconstructionPlan

```python
@dataclass
class ReconstructionPlan:
    original_query: str
    original_zone: Zone
    target_zone: Zone
    strategies: List[str]  # ['clarify', 'decompose'] 优先级排序的策略列表
    steps: List[Dict]
    sub_problems: List[SubProblem]
    missing_info_list: List[str]
```

## 6. API 设计

### 6.1 主处理接口

```python
def process(self, 
            query: str, 
            session_id: str = None,
            force_zone: Zone = None) -> Dict:
    """
    主处理流程
    
    Returns:
        成功: {'status': 'success', 'zone': 'A'/'C', ...}
        需补充: {'status': 'clarification_needed', 'missing_info': [...], ...}
    """
```

### 6.2 继续处理接口

```python
def continue_with_info(self, 
                       session_id: str,
                       provided_info: Dict) -> Dict:
    """
    用户补充信息后继续处理
    """
```

## 7. 配置参数

| 参数 | 默认值 | 说明 |
|:-----|:-------|:-----|
| ALPHA | 0.7 | 置信度阈值 |
| MAX_TRANSITION_ROUNDS | 3 | 最大转区轮数 |
| MAX_SUB_PROBLEMS | 5 | 最大子问题数 |
| DECOMPOSITION_THRESHOLD | 0.8 | 分解触发阈值(C>I时) |

## 8. 状态流转图

```
┌─────────┐
│  Initial│
│  CI Eval│
└────┬────┘
     │
     ▼
┌─────────┐    ┌─────────┐    ┌─────────┐
│ Zone A  │    │ Zone C  │    │ Zone B  │
│ (C1I1)  │    │ (C0I1)  │    │ (C1I0)  │
│ 直接执行 │    │ 直接执行 │───→│ 需转区   │
└─────────┘    └─────────┘    └────┬────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                    ▼              ▼              ▼
              ┌─────────────────────────────────────┐
              │      Zone B 转区策略 (多选)          │
              ├─────────────────────────────────────┤
              │  ┌─────────┐      ┌─────────┐      │
              │  │补充信息→A│ 或/且 │分解为C0I1│      │
              │  │(clarify)│      │(decompose)│     │
              │  └─────────┘      └─────────┘      │
              │       │                  │         │
              │       └────────┬─────────┘         │
              │                ▼                   │
              │      可先后尝试或让用户选择        │
              │                │                   │
              │                ▼                   │
              │         达到 Zone A/C            │
              └─────────────────────────────────────┘
```

## 9. 与现有组件集成

```
┌─────────────────────────────────────────────────────────┐
│                    Smart Orchestrator                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐         │
│   │ Level 0  │    │ Level 1  │    │ Level 2  │         │
│   │ Router   │    │ Router   │    │ Router   │         │
│   │ (现有)   │    │ (现有)   │    │ (现有)   │         │
│   └────┬─────┘    └────┬─────┘    └────┬─────┘         │
│        │               │               │               │
│        └───────────────┴───────────────┘               │
│                        │                                │
│                   CI Tracker                           │
│                        │                                │
│                   Zone Engine                          │
│                        │                                │
│                Query Reconstructor                     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## 10. 实施计划

1. **Phase 1**: 基础 CI Tracker 实现
2. **Phase 2**: Zone Transition Engine
3. **Phase 3**: Query Reconstructor
4. **Phase 4**: SmartOrchestrator 主类整合
5. **Phase 5**: 与 GUI 集成测试

---

**文档版本**: 1.0  
**创建日期**: 2026-03-16  
**状态**: 设计中
