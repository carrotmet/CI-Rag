# CI-RAG-Router V4 最终架构文档

## 核心设计理念

```
Level 012 逃逸层 → 确定初始区域 → 区域自治 → 协调器转区校验 → Zone C 统一出口

Zone C = 系统大脑 = 统一出口 = 支持多层级推理策略升级
```

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CI-RAG-Router V4 架构                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  用户输入                                                                    │
│      │                                                                       │
│      ▼                                                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      Level 012 逃逸层                                │    │
│  │                      【首次区域判定，协调器不干涉】                    │    │
│  │                                                                     │    │
│  │   ┌─────────┐      ┌─────────┐      ┌─────────────────────────┐   │    │
│  │   │ Level 0 │─────→│ Level 1 │─────→│ Level 2 (裁决/轻量Guide) │   │    │
│  │   │ XGBoost │  σ<0.7│混合检索 │  σ<0.7│  - 完整调用: CI仲裁       │   │    │
│  │   └─────────┘      └─────────┘      │  - 轻量调用: 生成Guide    │   │    │
│  │        σ≥0.7            σ≥0.7        └─────────────────────────┘   │    │
│  │          │                │                      │                 │    │
│  │          └────────────────┴──────────────────────┘                 │    │
│  │                            │                                        │    │
│  │                            ▼                                        │    │
│  │              输出: Zone + CI判定 + (可选)Guide                      │    │
│  │                                                                     │    │
│  │  【注: Level 012 直接决定首次进入区域，不经过协调器】                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                            │                                                │
│                            ▼                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         ABCD 处理层                                  │    │
│  │                     【区域自治，内部Guide检查】                       │    │
│  │                                                                     │    │
│  │  ┌──────────────────────────────────────────────────────────────┐  │    │
│  │  │  Zone C (大脑/出口) C=0, I=1                                   │  │    │
│  │  │  ┌─────────────────────────────────────────────────────────┐  │  │    │
│  │  │  │ 模式1: 父问题直接输出                                      │  │  │    │
│  │  │  │   - 单查询 → 直接推理 → 输出                               │  │  │    │
│  │  │  └─────────────────────────────────────────────────────────┘  │  │    │
│  │  │  ┌─────────────────────────────────────────────────────────┐  │  │    │
│  │  │  │ 模式2: 子问题队列组装输出                                  │  │  │    │
│  │  │  │   - 子问题推理完成 → 放入消息队列                          │  │  │    │
│  │  │  │   - 等待所有子问题完成 → 组装输出                          │  │  │    │
│  │  │  └─────────────────────────────────────────────────────────┘  │  │    │
│  │  │  ┌─────────────────────────────────────────────────────────┐  │  │    │
│  │  │  │ 【未来】C区策略升级路径                                    │  │  │    │
│  │  │  │   Level 1: 直接推理                                        │  │  │    │
│  │  │  │   Level 2: One-shot / CoT 提示词模版                      │  │  │    │
│  │  │  │   Level 3: 引入记忆上下文                                  │  │  │    │
│  │  │  │   Level 4: 引入工具调用                                    │  │  │    │
│  │  │  │   Level 5: 构造子智能体处理子任务                          │  │  │    │
│  │  │  └─────────────────────────────────────────────────────────┘  │  │    │
│  │  └──────────────────────────────────────────────────────────────┘  │    │
│  │                                                                     │    │
│  │  ┌──────────────────────────────────────────────────────────────┐  │    │
│  │  │  Zone D (补I区) C=0, I=0                                     │  │    │
│  │  │  1. 检查Guide: 无 → 调用公共Guide生成方法                     │  │    │
│  │  │  2. 执行一轮检索 (根据Guide)                                  │  │    │
│  │  │  3. 请求协调器转区                                            │  │    │
│  │  │  4. 【策略升级】多次不通过 → 换算法/换范围                     │  │    │
│  │  └──────────────────────────────────────────────────────────────┘  │    │
│  │                                                                     │    │
│  │  ┌──────────────────────────────────────────────────────────────┐  │    │
│  │  │  Zone A (拆解区) C=1, I=1                                    │  │    │
│  │  │  1. 检查Guide: 无 → 调用公共Guide生成方法                     │  │    │
│  │  │  2. 执行一轮拆解 (根据Guide)                                  │  │    │
│  │  │  3. 请求协调器转区                                            │  │    │
│  │  │  4. 【策略升级】多次不通过 → 换拆解角度/粒度                   │  │    │
│  │  └──────────────────────────────────────────────────────────────┘  │    │
│  │                                                                     │    │
│  │  ┌──────────────────────────────────────────────────────────────┐  │    │
│  │  │  Zone B (综合区) C=1, I=0                                    │  │    │
│  │  │  1. 检查Guide: 无 → 调用公共Guide生成方法                     │  │    │
│  │  │  2. 执行一轮: 检索 或 拆解 (根据Guide)                        │  │    │
│  │  │  3. 请求协调器转区                                            │  │    │
│  │  │     【当前】达标 → 转C                                        │  │    │
│  │  │     【未来】C1I1 → 转A, C0I0 → 转D, C0I1 → 转C               │  │    │
│  │  │  4. 【策略升级】多次不通过 → 调整检索/拆解优先级              │  │    │
│  │  └──────────────────────────────────────────────────────────────┘  │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                            │                                                │
│                            ▼                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         协调器 (Orchestrator)                        │    │
│  │                      【职责：转区校验与路由】                          │    │
│  │                                                                     │    │
│  │  原则: 区域执行一轮后请求协调，协调器校验转区条件                      │    │
│  │                                                                     │    │
│  │  输入: 查询 + 当前CI状态 + 目标Zone                                  │    │
│  │  处理:                                                             │    │
│  │    ├── 校验CI是否满足目标Zone条件                                   │    │
│  │    │   ├── 满足 → 执行转区                                          │    │
│  │    │   └── 不满足 → 打回原区域，触发策略升级                         │    │
│  │    └── 【未来】B区可能转A/D                                         │    │
│  │                                                                     │    │
│  │  【不负责】: Guide生成、检索执行、拆解执行、具体策略选择             │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                            │                                                │
│                            ▼                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      公共组件层                                       │    │
│  │                                                                     │    │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │    │
│  │  │ Guide生成器      │  │ 消息队列         │  │ 策略升级管理器   │  │    │
│  │  │ (轻量L2调用)     │  │ (子问题收集)     │  │ (区域策略切换)   │  │    │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘  │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 数据流转详解

### 阶段1: Level 012 首次判定

```
用户查询
    ↓
Level 0 (XGBoost)
    ├── σ≥0.7 → 确定Zone (A/B/C/D) + CI → 直接进入对应Zone
    └── σ<0.7 → Level 1
                    ↓
            Level 1 (混合检索)
                ├── σ≥0.7 → 确定Zone + CI → 直接进入对应Zone
                └── σ<0.7 → Level 2
                                ↓
                        Level 2 (裁决)
                            ├── 完整调用 → 确定Zone + CI + Guide → 进入对应Zone
                            └── 轻量调用 → 返回上层

【关键】: 此阶段协调器不参与，Level 012直接决定首次进入区域
```

### 阶段2: 区域自治与协调器交互

#### Zone D 流转

```
进入Zone D (C0I0)
    ↓
检查Guide存在?
    ├── 无 → 调用公共Guide生成器 → 获得Guide
    └── 有 → 继续
    ↓
执行一轮检索 (根据Guide)
    ↓
请求协调器: "当前CI状态，请求转C区"
    ↓
协调器校验:
    ├── I≥0.7 (满足C区条件) → 转Zone C → C区输出
    └── I<0.7 (不满足) → 打回Zone D
                        ↓
                    Zone D策略升级:
                      ├── 换检索算法 (向量→关键词→结构化)
                      ├── 换检索范围 (扩展查询词)
                      └── 最多N次后强制转C (带低置信标记)
```

#### Zone A 流转

```
进入Zone A (C1I1)
    ↓
检查Guide存在?
    ├── 无 → 调用公共Guide生成器 → 获得Guide
    └── 有 → 继续
    ↓
执行一轮拆解 (根据Guide)
    ↓
请求协调器: "子问题CI状态，请求转C区"
    ↓
协调器校验:
    ├── 所有子问题C=0 (满足条件) → 转Zone C (子问题模式)
    └── 存在子问题C=1 (不满足) → 打回Zone A
                                    ↓
                                Zone A策略升级:
                                  ├── 换拆解角度 (不同维度)
                                  ├── 换拆解粒度 (粗→细)
                                  └── 对该子问题进一步拆解
```

#### Zone B 流转

```
进入Zone B (C1I0)
    ↓
检查Guide存在?
    ├── 无 → 调用公共Guide生成器 → 获得Guide
    └── 有 → 继续
    ↓
执行一轮: 检索 或 拆解 (根据Guide策略)
    ↓
请求协调器: "当前CI状态，请求转区"
    ↓
协调器校验:
    ├── 【当前实现】C=0 & I≥0.7 → 转Zone C
    ├── 【未来扩展】C=1 & I=1 → 转Zone A
    ├── 【未来扩展】C=0 & I=0 → 转Zone D
    └── 不满足 → 打回Zone B
                    ↓
                Zone B策略升级:
                  ├── 调整检索/拆解优先级
                  ├── 切换策略 (先检索→先拆解)
                  └── 并行执行检索+拆解
```

### 阶段3: Zone C 大脑输出

#### C区两种模式

```python
class ZoneC:
    def process(self, request: ZoneCRequest):
        if request.type == "direct":
            # 模式1: 父问题直接输出
            return self.direct_reasoning(request.query)
        
        elif request.type == "subproblem":
            # 模式2: 子问题队列组装
            # 1. 推理当前子问题
            result = self.reason_subproblem(request.subproblem)
            # 2. 放入消息队列
            self.message_queue.put(request.parent_id, result)
            # 3. 检查是否全部完成
            if self.message_queue.is_complete(request.parent_id):
                # 4. 组装所有子问题结果
                all_results = self.message_queue.get_all(request.parent_id)
                return self.assemble_output(all_results)
            else:
                # 等待其他子问题
                return {"status": "waiting", "subproblem_id": request.subproblem_id}
```

#### 【未来】C区策略升级路径

```
Level 1: 直接推理
    └── 简单问题直接回答
    
Level 2: One-shot / CoT 提示词模版
    └── 标准: "Let's think step by step"
    └── 标准: 结构化输出格式
    
Level 3: 引入记忆上下文
    └── 短期记忆: 对话历史
    └── 长期记忆: 用户偏好、知识库
    
Level 4: 引入工具调用
    └── 计算器、搜索引擎、数据库查询
    └── API调用、代码执行
    
Level 5: 构造子智能体
    └── 专用子Agent处理特定子任务
    └── 多Agent协作、辩论、验证
```

---

## 组件职责边界

### Level 012 逃逸层

| 职责 | 说明 |
|:-----|:-----|
| 首次区域判定 | 根据CI确定Zone (A/B/C/D) |
| 输出 | Zone + CI判定 + (可选)Guide |
| 协调器参与 | **否**，直接进入对应Zone |

### ABD 区域

| 职责 | 说明 |
|:-----|:-----|
| Guide检查 | 进入时检查，无则调用公共生成器 |
| 执行一轮 | 检索(D) / 拆解(A) / 检索或拆解(B) |
| 请求协调器 | 执行一轮后请求转区 |
| 策略升级 | 被打回时调整策略 |

### 协调器

| 职责 | 说明 |
|:-----|:-----|
| 转区校验 | 检查CI是否满足目标Zone条件 |
| 转区执行 | 满足则路由到目标Zone |
| 打回处理 | 不满足则打回原区域 |
| **不负责** | Guide生成、具体执行、策略选择 |

### Zone C (大脑/出口)

| 职责 | 说明 |
|:-----|:-----|
| 父问题 | 直接推理输出 |
| 子问题 | 推理后放入队列，等待组装 |
| 组装输出 | 所有子问题完成后整合输出 |
| 策略升级 | 根据问题难度选择推理策略 |

### 公共组件

| 组件 | 职责 |
|:-----|:-----|
| Guide生成器 | 轻量L2调用，生成区域Guide |
| 消息队列 | 子问题结果收集与状态管理 |
| 策略升级管理器 | 区域策略切换与升级控制 |

---

## 接口定义 V4

> **变量命名规范**：本文档变量名与代码严格保持一致，详见下方"核心数据结构"

### 核心数据结构（与代码一致）

```python
# CI 状态 (代码中: CIState dataclass)
@dataclass
class CIState:
    C: float                    # 复杂度 (0-1 连续值)
    I: float                    # 信息充分性 (0-1 连续值)
    sigma_c: float              # C 的置信度
    sigma_i: float              # I 的置信度
    query: str = ""             # 关联查询
    timestamp: float            # 时间戳
    
    @property
    def sigma_joint(self) -> float:      # 联合置信度
        return min(self.sigma_c, self.sigma_i)
    
    @property
    def zone(self) -> Zone:              # 映射到离散Zone
        C_d = 1 if self.C >= 0.5 else 0
        I_d = 1 if self.I >= 0.5 else 0
        return {(0,0): Zone.D, (0,1): Zone.C, (1,0): Zone.B, (1,1): Zone.A}.get((C_d, I_d), Zone.B)

# Zone 枚举 (代码中: Zone Enum)
class Zone(Enum):
    A = "A"                     # C=1, I=1
    B = "B"                     # C=1, I=0
    C = "C"                     # C=0, I=1
    D = "D"                     # C=0, I=0
    
    @property
    def is_optimal(self) -> bool:        # 是否为最优区
        return self in (Zone.A, Zone.C)

# OrchestratorGuide (代码中: OrchestratorGuide dataclass)
@dataclass
class OrchestratorGuide:
    missing_info: List[str]           # 缺失信息列表
    decomposable: bool                # 是否可分解
    recommended: List[str]            # 推荐策略列表（按优先级）
    sub_problem_hints: List[str]      # 子问题提示
    confidence: float                 # guide 置信度
    validates_classification: bool    # 是否认可当前分类
    source: str = "level2_light"      # 来源
    meta: Dict = field(default_factory=dict)  # 元数据

# SubProblem (代码中: SubProblem dataclass)
@dataclass
class SubProblem:
    id: str                           # 子问题ID (如 "sp_1")
    query: str                        # 子问题查询
    parent_id: Optional[str]          # 父问题ID
    expected_ci: CIState              # 预期CI状态
    dependencies: List[str] = field(default_factory=list)
    accumulated_info: Dict = field(default_factory=dict)

# ReconstructionPlan (代码中: ReconstructionPlan dataclass)
@dataclass
class ReconstructionPlan:
    original_query: str
    original_zone: Zone
    target_zone: Zone
    strategies: List[str]                    # 策略列表
    steps: List[Dict] = field(default_factory=list)
    sub_problems: List[SubProblem] = field(default_factory=list)
    missing_info_list: List[str] = field(default_factory=list)
    primary_strategy: str = "direct_execute" # 主策略
    alternative_strategies: List[str] = field(default_factory=list)
    user_selectable: bool = False
```

### Level 012 输出字段对照表

**Level 0 Router 输出字段** (`route()` 返回值):

| 字段 | 类型 | 说明 | 代码对应 |
|:-----|:-----|:-----|:---------|
| `C` | int | 离散复杂度 (0/1) | `result['C']` |
| `I` | int | 离散信息充分性 (0/1) | `result['I']` |
| `C_continuous` | float | 连续复杂度 (0-1) | `result['C_continuous']` |
| `I_continuous` | float | 连续信息充分性 (0-1) | `result['I_continuous']` |
| `sigma_c` | float | C 置信度 | `result['sigma_c']` |
| `sigma_i` | float | I 置信度 | `result['sigma_i']` |
| `sigma_joint` | float | 联合置信度 | `result['sigma_joint']` |
| `escalate` | bool | 是否升级 L1 | `result['escalate']` |
| `zone` | str | 区域 "A"/"B"/"C"/"D" | `result['zone']` |
| `mode` | str | 路由模式 | `result['mode']` |
| `status` | str | 状态 | `result['status']` |
| `orchestrator_guide` | Dict | Zone B/D Guide | `result['orchestrator_guide']` |

**Level 1 Router 输出字段** (`verify()` 返回值):

| 字段 | 类型 | 说明 | 代码对应 |
|:-----|:-----|:-----|:---------|
| `I_mean` | float | 融合后的 I 值 | `result['I_mean']` |
| `sigma_I` | float | I 的置信度 | `result['sigma_I']` |
| `C` | int | 从 L0 继承的 C | `result['C']` |
| `I` | int | 离散 I | `result['I']` |
| `final_zone` | str | 最终区域 | `result['final_zone']` |
| `retrieval_evidence` | Dict | 检索证据 | `result['retrieval_evidence']` |
| `orchestrator_guide` | Dict | Zone B/D Guide | `result['orchestrator_guide']` |

**Level 2 Router 输出字段** (`Level2Result` dataclass):

| 字段 | 类型 | 说明 | 代码对应 |
|:-----|:-----|:-----|:---------|
| `C` | int | 离散复杂度 | `Level2Result.C` |
| `I` | int | 离散信息充分性 | `Level2Result.I` |
| `C_continuous` | float | 连续复杂度 | `Level2Result.C_continuous` |
| `I_continuous` | float | 连续信息充分性 | `Level2Result.I_continuous` |
| `confidence` | float | 总体置信度 | `Level2Result.confidence` |
| `sigma_c` | float | C 置信度 | `Level2Result.sigma_c` |
| `sigma_i` | float | I 置信度 | `Level2Result.sigma_i` |
| `sigma_joint` | float | 联合置信度 | `Level2Result.sigma_joint` |
| `escalate` | bool | 是否逃逸 | `Level2Result.escalate` |
| `escalate_reason` | str | 逃逸原因 | `Level2Result.escalate_reason` |
| `mode` | str | 仲裁模式 | `Level2Result.mode` |
| `reasoning` | str | 推理过程 | `Level2Result.reasoning` |
| `probe_consistency` | float | 双探针一致性 | `Level2Result.probe_consistency` |
| `conflict_with_l1` | bool | 与 L1 冲突 | `Level2Result.conflict_with_l1` |
| `latency_ms` | float | 延迟 | `Level2Result.latency_ms` |
| `cost_usd` | float | 成本 | `Level2Result.cost_usd` |
| `model_used` | str | 使用的模型 | `Level2Result.model_used` |
| `parse_failures` | int | 解析失败次数 | `Level2Result.parse_failures` |

### 区域入口接口

```python
class ZoneHandler(ABC):
    """区域处理基类"""
    
    def __init__(self):
        self.guide_generator = GuideGenerator()
        self.strategy_manager = StrategyManager()
    
    def enter(self, query: str, ci: CIState, guide: Optional[Guide]):
        """
        区域入口:
        1. 检查/生成Guide
        2. 执行一轮处理
        3. 请求协调器转区
        """
        # 1. Guide检查
        if guide is None:
            guide = self.guide_generator.generate(self.zone_type, query, ci)
        
        # 2. 执行一轮
        result = self.execute_round(query, guide)
        
        # 3. 请求协调器
        return orchestrator.request_transition(
            query=result.query,
            current_ci=result.ci,
            source_zone=self.zone_type
        )
    
    @abstractmethod
    def execute_round(self, query: str, guide: Guide) -> RoundResult:
        """执行一轮区域特定逻辑"""
        pass
```

### 协调器接口

```python
class Orchestrator:
    def request_transition(self, 
                          query: str,
                          current_ci: CIState,
                          source_zone: Zone) -> TransitionResult:
        """
        区域请求转区
        
        逻辑:
        1. 根据source_zone和current_ci确定目标Zone
        2. 校验是否满足转区条件
        3. 满足→转区，不满足→打回
        """
        # 确定目标Zone
        target_zone = self.determine_target_zone(source_zone, current_ci)
        
        # 校验条件
        if self.validate_transition(current_ci, target_zone):
            # 执行转区
            return self.route_to_zone(query, target_zone)
        else:
            # 打回原区域，触发策略升级
            return TransitionResult(
                success=False,
                action="return_to_source",
                source_zone=source_zone,
                trigger_strategy_upgrade=True
            )
    
    def determine_target_zone(self, source: Zone, ci: CIState) -> Zone:
        """确定目标Zone (与代码逻辑一致)"""
        # 【当前】所有区域都转C
        # 【未来】B区可能转A/D
        # 代码中使用: ci.C (float 连续值) 和 ci.I (float 连续值)
        # 转C区条件: C=0 (简单) 且 I>=0.7 (信息较充分)
        if source in [Zone.A, Zone.B, Zone.D]:
            if ci.C == 0 and ci.I >= 0.7:
                return Zone.C
        return source  # 不满足条件，保持原Zone
    
    def validate_transition(self, ci: CIState, target: Zone) -> bool:
        """校验转区条件 (与代码中 zone.is_optimal 逻辑一致)"""
        if target == Zone.C:
            # 代码中 Zone.C.is_optimal = True
            # 条件: C == 0 且 I >= 0.7
            return ci.C == 0 and ci.I >= 0.7
        elif target == Zone.A:
            # 代码中 Zone.A.is_optimal = True
            return ci.C == 1 and ci.I >= 0.7
        return False
```

### Zone C 接口

```python
class ZoneC:
    """系统大脑与出口"""
    
    def process_direct(self, query: str) -> Response:
        """父问题直接推理"""
        strategy = self.select_strategy(query)
        return self.reason_with_strategy(query, strategy)
    
    def process_subproblem(self, 
                          parent_id: str,
                          subproblem_id: str,
                          query: str) -> Response:
        """子问题处理"""
        # 1. 推理
        result = self.reason(query)
        
        # 2. 放入队列
        self.subproblem_queue.put(parent_id, subproblem_id, result)
        
        # 3. 检查是否完成
        if self.subproblem_queue.is_complete(parent_id):
            # 全部完成，组装输出
            all_results = self.subproblem_queue.get_all(parent_id)
            return self.assemble_output(parent_id, all_results)
        else:
            return {"status": "subproblem_completed", "waiting_others": True}
    
    def select_strategy(self, query: str) -> ReasoningStrategy:
        """根据问题难度选择推理策略"""
        complexity = self.estimate_complexity(query)
        if complexity < 0.3:
            return ReasoningStrategy.DIRECT
        elif complexity < 0.6:
            return ReasoningStrategy.COT
        elif complexity < 0.8:
            return ReasoningStrategy.FEW_SHOT
        else:
            return ReasoningStrategy.AGENT
```

---

## 未来扩展路线

### 近期 (V4.x)
- [ ] 子问题消息队列实现
- [ ] 区域策略升级基础框架
- [ ] C区多级推理策略

### 中期 (V5)
- [ ] B区转A/D路径实现
- [ ] 协调器智能路由决策
- [ ] C区工具调用集成

### 远期 (V6)
- [ ] C区子智能体构造
- [ ] 多Agent协作机制
- [ ] 自适应策略学习

---

## 相关文档

- `architecture_simplified.md` - 简化架构概念
- `CI-RAG-ROUTER-ARCHITECTURE-v3.md` - V3架构（区域自治）
- `B区优化方案分析.md` - B区设计分析

---

## 附录：代码变量快速参考表

### 文件路径与变量定义对照

| 变量/类 | 定义文件 | 代码行号 | 说明 |
|:--------|:---------|:---------|:-----|
| `Zone` Enum | `orchestrator/smart_orchestrator_v2.py` | 22-45 | ABCD四区枚举 |
| `CIState` | `orchestrator/smart_orchestrator_v2.py` | 48-82 | CI状态类 |
| `SubProblem` | `orchestrator/smart_orchestrator_v2.py` | 85-97 | 子问题类 |
| `ReconstructionPlan` | `orchestrator/smart_orchestrator_v2.py` | 100-112 | 重建计划类 |
| `OrchestratorGuide` | `orchestrator/smart_orchestrator_v2.py` | 115-139 | Guide类 |
| `CITracker` | `orchestrator/smart_orchestrator_v2.py` | 142-262 | CI追踪器 |
| `ZoneTransitionEngineV2` | `orchestrator/smart_orchestrator_v2.py` | 265-375 | 转区引擎V2 |
| `SmartOrchestratorV2` | `orchestrator/smart_orchestrator_v2.py` | 378-678 | 协调器主类 |
| `Level2Result` | `level2/level2_router.py` | 18-47 | L2结果类 |
| `Level2Router` | `level2/level2_router.py` | 50-523 | L2路由器类 |
| `Level0Router` | `level0/router.py` | 27-303 | L0路由器类 |
| `Level1Router` | `level1/level1_router.py` | 17-344 | L1路由器类 |

### 常用变量命名规范

| 场景 | 代码变量名 | 类型 | 示例 |
|:-----|:-----------|:-----|:-----|
| CI离散值 | `C`, `I` | int (0/1) | `C=1, I=0` |
| CI连续值 | `C_continuous`, `I_continuous` | float | `C_continuous=0.85` |
| 置信度 | `sigma_c`, `sigma_i`, `sigma_joint` | float | `sigma_joint=0.92` |
| 区域 | `zone` | Zone Enum | `Zone.A`, `Zone.B` |
| Zone字符串 | `zone.value` | str | `"A"`, `"B"`, `"C"`, `"D"` |
| Guide缺失信息 | `missing_info` | List[str] | `["患者年龄", "症状"]` |
| Guide策略 | `recommended` | List[str] | `["clarify", "decompose"]` |
| 子问题ID | `id` | str | `"sp_1"`, `"sp_abc123"` |
| 子问题查询 | `query` | str | `"什么是XX？"` |
| 父问题ID | `parent_id` | Optional[str] | `"parent_001"` 或 `None` |
| 转区轮数 | `transition_round` | int | 0, 1, 2 |

### 代码中关键方法签名

```python
# Level 0 Router
route(query: str, user_history: Optional[Dict]) -> Dict
route_with_guide(query: str, user_history: Optional[Dict]) -> Dict

# Level 1 Router  
verify(query: str, level0_result: Dict, k: int = 10) -> Dict
verify_with_guide(query: str, level0_result: Dict, k: int = 10) -> Dict

# Level 2 Router
arbitrate(query: str, level0_result: Dict, level1_result: Dict) -> Level2Result
generate_orchestrator_guide(query: str, current_zone: str, 
                           level0_result: Dict, level1_result: Dict) -> Dict

# SmartOrchestratorV2
process(query: str, session_id: str = None, force_strategy: str = None) -> Dict
continue_with_info(session_id: str, provided_info: Dict) -> Dict
```

---

*文档版本: 4.0*  
*更新日期: 2026-03-21*  
*状态: 最终架构定义 - 协调器仅转区校验，C区大脑出口*  
*变量规范: 与代码严格一致*
