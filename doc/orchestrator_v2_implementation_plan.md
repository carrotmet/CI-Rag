# Smart Orchestrator V2 实施规划

## 概述

本文档对比已有协调器（V1）与优化后架构（V2）的实现差异，制定开发计划。

**核心变化**：Zone B/D 必须携带 Level 2 生成的 `orchestrator_guide` 才能进入协调器。

---

## 一、版本对比

### V1 已有实现（当前代码）

```python
# ci_architecture/orchestrator/smart_orchestrator.py

class SmartOrchestrator:
    def process(self, query, session_id=None):
        # 1. CI 评估 (L0→L1→L2)
        ci = self.ci_tracker.evaluate(query)
        
        # 2. Zone 判定
        if ci.zone.is_optimal:
            return self._create_success_response(query, ci, context)
        
        # 3. 协调器自决策转区策略
        plan = self.transition_engine.plan_transition(ci, target)
        #    ^-- 自己判断 missing_info, decomposable
        
        return self._execute_transition(query, plan, ci, context)
```

**V1 问题**：
- 协调器自己判断 `missing_info` 和 `decomposable`
- 没有 Level 2 指导，决策可能不准
- Zone B/D 可以无 guide 进入协调器

### V2 优化架构（目标设计）

```python
# Phase 1: Level 0/1/2 输出必须带 guide (BD区)

Level 0/1/2 Output (Zone B/D):
{
    "zone": "B",
    "C": 0.9,
    "I": 0.1,
    "sigma_joint": 0.85,
    
    # 必须有 (BD区身份证)
    "orchestrator_guide": {
        "source": "level2_light",
        "missing_info": ["item1", "item2"],
        "decomposable": true,
        "recommended": ["clarify", "decompose"],  // 优先级排序的策略列表，可执行任意一种
        "sub_problem_hints": ["hint1", "hint2"],
        "confidence": 0.82,
        "validates_l0": true
    }
}

# Phase 2: 协调器按 guide 执行 (不自己决策)

class SmartOrchestratorV2:
    def process(self, query, session_id=None):
        # 1. CI 评估 (必须返回带 guide 的 result)
        result = self._evaluate_with_guide(query)
        
        # 2. 检查 guide 存在 (Zone B/D 时)
        if result.zone in [Zone.B, Zone.D]:
            assert "orchestrator_guide" in result  # 必须存在
        
        # 3. 按 guide 执行 (不自己判断)
        guide = result.get("orchestrator_guide")
        plan = self._create_plan_from_guide(result, guide)
        
        return self._execute_with_guide(plan)
```

**V2 优势**：
- Level 2 专业判断 `missing_info` 和 `decomposable`
- 协调器只做执行，不做决策
- Zone B/D 必须有 guide，策略可靠

---

## 二、代码改动清单

### 改动 1: Level 2 新增轻量模式

**文件**: `ci_architecture/level2/level2_router.py`

**新增内容**:
```python
class Level2Router:
    # 已有: arbitrate() - 完整仲裁
    
    # 新增: 轻量 guide 生成
    def generate_orchestrator_guide(self, 
                                    query: str, 
                                    current_zone: Zone,
                                    level0_result: Dict,
                                    level1_result: Dict) -> Dict:
        """
        轻量模式: 只生成协调器指南
        
        与完整仲裁的区别:
        - Token: 80 vs 150
        - 延迟: ~50ms vs ~100ms
        - 输出: 只含 guide，不含完整 CI 评估
        """
        # 构建轻量 prompt
        prompt = self._build_light_guide_prompt(
            query, current_zone, level0_result, level1_result
        )
        
        # 调用 LLM (轻量配置)
        response = self.llm.complete(
            prompt,
            max_tokens=100,  # 减少 token
            temperature=0.1
        )
        
        # 解析 guide
        return self._parse_guide_response(response)
    
    def _build_light_guide_prompt(self, query, zone, l0, l1) -> str:
        return f"""
You are a transition advisor. The query has been classified as Zone {zone}.
Your task: provide guidance for the orchestrator to transition to optimal zone.

Query: {query}
Level 0 Assessment: C={l0.get('C')}, I={l0.get('I')}
Level 1 Assessment: I_mean={l1.get('I_mean', 'N/A')}

Output JSON:
{{
    "missing_info": ["item1", "item2"],  // Max 3 items
    "decomposable": true/false,
    "recommended": ["clarify", "decompose"],  // 优先级排序的策略列表，可执行任意一种
    "sub_problem_hints": ["hint1", "hint2"],  // If decomposable
    "confidence": 0.0-1.0,
    "validates_classification": true/false  // Agree with Zone {zone}?
}}

Rules:
1. missing_info: most critical gaps only, max 3
2. decomposable: true only if natural sub-questions exist
3. recommended: 优先级排序的策略列表
   - ["clarify", "decompose"]: 优先尝试信息补充，如用户不愿补充则提供分解选项
   - ["decompose", "clarify"]: 优先分解，适用于结构清晰的多部分问题
   - ["clarify"]: 仅信息补充，不适合分解
   - ["decompose"]: 仅问题分解，不适合补充单一信息
4. If you disagree with Zone {zone}, set validates_classification=false
"""
```

**工作量**: 
- 新增方法: 2 个
- 修改文件: 1 个
- 预估: 2-3 小时

---

### 改动 2: Level 2 输出结构扩展

**文件**: `ci_architecture/level2/prompt_builder.py`

**修改内容**:

```python
# 当前 COMPLEX_ANALYSIS_SYSTEM (约92行)
# 新增字段: orchestrator_guide

COMPLEX_ANALYSIS_SYSTEM_V2 = """You are an expert query analyzer...

Output must be valid JSON:
{{
    "C": 0 or 1,
    "I": 0 or 1,
    "complexity_score": 0.0-1.0,
    "information_score": 0.0-1.0,
    "confidence": 0.0-1.0,
    "reasoning": "Detailed analysis",
    "recommended_zone": "A/B/C/D",
    "missing_info": [],
    
    // 新增: 协调器指南 (Zone B/D 时必须)
    "orchestrator_guide": {{
        "missing_info": ["item1", "item2"],  // Max 3
        "decomposable": true/false,
        "recommended": ["clarify", "decompose"],  // 优先级排序的策略列表，可执行任意一种
        "sub_problem_hints": [],
        "guide_confidence": 0.0-1.0
    }}
}}

Guidelines for orchestrator_guide:
- Only meaningful when recommended_zone is B or D
- missing_info: specific items needed to reach optimal zone
- decomposable: can this be split into simpler sub-problems?
- recommended: suggest best transition strategy
"""
```

**新增 Prompt** (轻量模式专用):
```python
# 新增于 prompt_builder.py

LIGHT_GUIDE_SYSTEM = """You are a transition advisor...
[内容见改动1]
"""
```

**工作量**:
- 修改 prompt: 2 个
- 新增 prompt: 1 个
- 预估: 1 小时

---

### 改动 3: Level 0/1 强制触发轻量 L2 (Zone B/D)

**文件**: `ci_architecture/level0/router.py`, `ci_architecture/level1/level1_router.py`

**Level 0 修改**:
```python
class Level0Router:
    def __init__(self, ...):
        # 已有初始化
        ...
        # 新增: 轻量 L2 路由器引用 (可选注入)
        self.light_l2_router = None
    
    def route_with_guide(self, query: str) -> Dict:
        """
        新版路由: Zone B/D 必须带 guide
        """
        # 1. 原有路由逻辑
        result = self.route(query)  # 已有方法
        
        # 2. Zone B/D 检查
        zone = self.get_zone(result['C'], result['I'])
        
        if zone in ['B', 'D'] and self.light_l2_router:
            # 强制触发轻量 L2
            guide = self.light_l2_router.generate_orchestrator_guide(
                query=query,
                current_zone=zone,
                level0_result=result,
                level1_result={}  # L0 阶段无 L1
            )
            result['orchestrator_guide'] = guide
        
        return result
```

**Level 1 修改**:
```python
class Level1Router:
    def verify_with_guide(self, query: str, level0_result: Dict) -> Dict:
        """
        新版验证: Zone B/D 必须带 guide
        """
        # 1. 原有验证逻辑
        result = self.verify(query, level0_result)
        
        # 2. 确定最终 Zone
        final_zone = self._determine_zone(result)
        
        if final_zone in ['B', 'D'] and self.light_l2_router:
            # 强制触发轻量 L2
            guide = self.light_l2_router.generate_orchestrator_guide(...)
            result['orchestrator_guide'] = guide
        
        return result
```

**工作量**:
- 修改文件: 2 个
- 新增方法: 每个文件 1 个
- 预估: 3-4 小时 (含测试)

---

### 改动 4: 协调器重构 (按 guide 执行)

**文件**: `ci_architecture/orchestrator/smart_orchestrator.py`

**重大修改**: 重写转区决策逻辑

```python
# V1: 自己决策
class ZoneTransitionEngine:
    def plan_transition(self, current_ci: CIState, target_zone: Zone = None) -> ReconstructionPlan:
        # 自己识别 missing_info (启发式)
        missing_info = self._identify_missing_info(current_ci)
        # 自己判断是否可分解
        decomposable = self._check_decomposable(current_ci.query)
        ...

# V2: 按 guide 执行
class ZoneTransitionEngineV2:
    def plan_from_guide(self, 
                        current_ci: CIState, 
                        guide: Dict) -> ReconstructionPlan:
        """
        按 Level 2 guide 生成计划
        """
        # 不再自己判断，直接按 guide 执行
        missing_info = guide['missing_info']
        decomposable = guide['decomposable']
        recommended = guide['recommended']
        
        # V2: 支持多策略可选
        strategies = guide.get('recommended', ['clarify'])
        
        # 构建多策略计划，协调器可灵活选择
        plans = []
        for strategy in strategies:
            if strategy == 'clarify':
                plans.append(self._build_clarify_plan(current_ci, guide))
            elif strategy == 'decompose':
                plans.append(self._build_decompose_plan(current_ci, guide))
        
        # 返回多策略计划，由协调器或用户选择
        return MultiStrategyPlan(
            primary=plans[0] if plans else None,
            alternatives=plans[1:] if len(plans) > 1 else [],
            user_selectable=len(plans) > 1
        )
```

**SmartOrchestrator 修改**:
```python
class SmartOrchestrator:
    def process(self, query: str, session_id: str = None, ...) -> Dict:
        # 1. 评估 (必须带 guide)
        result = self._evaluate_with_guide(query, context)
        
        # 2. 检查 guide (Zone B/D 时强制)
        if result['zone'] in ['B', 'D']:
            if 'orchestrator_guide' not in result:
                raise ValueError("Zone B/D must have orchestrator_guide")
        
        # 3. 按 guide 执行 (不再自己决策)
        guide = result.get('orchestrator_guide')
        if guide:
            plan = self.transition_engine.plan_from_guide(result, guide)
        else:
            # Zone A/C 直接执行
            plan = ReconstructionPlan(..., strategy='direct_execute')
        
        return self._execute_plan(plan)
    
    def _evaluate_with_guide(self, query: str, context: Dict) -> Dict:
        """
        统一评估入口: 确保 Zone B/D 带 guide
        """
        # 走 L0→L1→L2 流程
        # 每个层级自己负责在 Zone B/D 时附加 guide
        
        l0_result = self.l0_router.route_with_guide(query)
        
        if l0_result.get('orchestrator_guide'):
            # L0 已判定为 B/D 并生成 guide
            return l0_result
        
        # 继续 L1
        l1_result = self.l1_router.verify_with_guide(query, l0_result)
        
        if l1_result.get('orchestrator_guide'):
            return l1_result
        
        # 继续 L2 (完整仲裁)
        l2_result = self.l2_router.arbitrate(query, l0_result, l1_result)
        
        # L2 输出必须包含 guide (如果 Zone B/D)
        return l2_result
```

**工作量**:
- 重写方法: 3-4 个核心方法
- 修改类: 2 个 (ZoneTransitionEngine, SmartOrchestrator)
- 预估: 6-8 小时 (含联调)

---

### 改动 5: 缓存机制 (性能优化)

**文件**: 新增 `ci_architecture/common/cache.py` (或利用现有缓存)

```python
# 轻量 L2 guide 缓存

class GuideCache:
    """
    缓存轻量 L2 生成的 guide
    Key: query_embedding (近似匹配)
    Value: orchestrator_guide
    """
    
    def __init__(self, ttl=3600):
        self.cache = {}
        self.ttl = ttl
    
    def get(self, query: str) -> Optional[Dict]:
        # 使用 embedding 相似度匹配
        query_emb = self._embed(query)
        for key, (value, expiry) in self.cache.items():
            if time.time() > expiry:
                continue
            if self._similarity(query_emb, key) > 0.95:
                return value
        return None
    
    def set(self, query: str, guide: Dict):
        query_emb = self._embed(query)
        self.cache[query_emb] = (guide, time.time() + self.ttl)
```

**工作量**:
- 新增文件: 1 个
- 预估: 2-3 小时

---

### 改动 6: 轮次限制与终止条件

**文件**: `ci_architecture/orchestrator/smart_orchestrator.py`

```python
class SmartOrchestrator:
    MAX_TRANSITION_ROUNDS = 2  # 新增常量
    
    def process(self, query, session_id=None):
        context = self._get_or_create_context(session_id)
        
        # 检查轮次
        if context.get('transition_round', 0) >= self.MAX_TRANSITION_ROUNDS:
            # 强制终止，用当前 Zone 执行
            return self._execute_with_current_zone(context)
        
        # 正常流程
        result = self._evaluate_with_guide(query, context)
        
        # 记录轮次
        context['transition_round'] = context.get('transition_round', 0) + 1
        
        ...
```

**工作量**:
- 新增逻辑: 轮次检查
- 预估: 1 小时

---

## 三、文件改动汇总

| 文件路径 | 改动类型 | 改动内容 | 预估工时 |
|:---------|:---------|:---------|:--------:|
| `ci_architecture/level2/level2_router.py` | 新增 | 轻量 guide 生成方法 | 2-3h |
| `ci_architecture/level2/prompt_builder.py` | 修改+新增 | 扩展输出结构、新增轻量 prompt | 1h |
| `ci_architecture/level0/router.py` | 修改+新增 | 强制触发轻量 L2 | 2h |
| `ci_architecture/level1/level1_router.py` | 修改+新增 | 强制触发轻量 L2 | 2h |
| `ci_architecture/orchestrator/smart_orchestrator.py` | 重写 | 按 guide 执行、轮次限制 | 6-8h |
| `ci_architecture/common/cache.py` | 新增 | Guide 缓存机制 | 2-3h |
| **总计** | | | **15-19h** |

---

## 四、接口变更对比

### Level 2 Router 接口

| 方法 | V1 | V2 | 变更 |
|:-----|:---|:---|:-----|
| `arbitrate()` | 完整仲裁 | 完整仲裁 + 输出 guide | 扩展输出 |
| `generate_orchestrator_guide()` | 无 | 新增轻量方法 | 新增 |

### Level 0/1 Router 接口

| 方法 | V1 | V2 | 变更 |
|:-----|:---|:---|:-----|
| `route()` | 基础路由 | 保留 | 不变 |
| `route_with_guide()` | 无 | Zone B/D 带 guide | 新增 |
| `verify()` | 基础验证 | 保留 | 不变 |
| `verify_with_guide()` | 无 | Zone B/D 带 guide | 新增 |

### SmartOrchestrator 接口

| 方法 | V1 | V2 | 变更 |
|:-----|:---|:---|:-----|
| `process()` | 自决策转区 | 按 guide 执行 | 重写内部逻辑 |
| `continue_with_info()` | 继续处理 | 继续处理 + 轮次检查 | 增强 |

---

## 五、数据格式对比

### Level 2 输出格式

**V1**:
```json
{
    "C": 1,
    "I": 0,
    "confidence": 0.85,
    "reasoning": "...",
    "recommended_zone": "B"
}
```

**V2**:
```json
{
    "C": 1,
    "I": 0,
    "confidence": 0.85,
    "reasoning": "...",
    "recommended_zone": "B",
    "orchestrator_guide": {
        "missing_info": ["患者年龄", "症状持续时间"],
        "decomposable": true,
        "recommended": "clarify",
        "sub_problem_hints": ["症状分析", "治疗方案"],
        "guide_confidence": 0.82,
        "validates_classification": true
    }
}
```

---

## 六、实施阶段规划

### Phase 1: Level 2 扩展 (2-3天)
- [ ] 实现 `generate_orchestrator_guide()` 轻量方法
- [ ] 扩展完整仲裁输出结构 (含 guide)
- [ ] 编写轻量模式 prompt
- [ ] 单元测试

### Phase 2: Level 0/1 触发 (2天)
- [ ] 实现 `route_with_guide()`
- [ ] 实现 `verify_with_guide()`
- [ ] 集成轻量 L2 调用
- [ ] 单元测试

### Phase 3: 协调器重构 (3-4天)
- [ ] 重写 `ZoneTransitionEngine` (按 guide 执行)
- [ ] 重写 `SmartOrchestrator.process()`
- [ ] 实现轮次限制
- [ ] 集成测试

### Phase 4: 缓存与优化 (1-2天)
- [ ] 实现 GuideCache
- [ ] 性能测试
- [ ] 调优

### Phase 5: 集成测试 (2天)
- [ ] 端到端测试
- [ ] 边界 case 测试
- [ ] 文档更新

**总计**: 10-13 个工作日

---

## 七、风险与缓解

| 风险 | 影响 | 缓解策略 |
|:-----|:-----|:---------|
| 轻量 L2 Token 仍过多 | 成本超预算 | 限制输出长度、启用缓存 |
| Zone B/D 比例高 | 大量触发 L2 | 优化 L0/L1 减少误判 |
| Guide 质量不稳定 | 转区策略失败 | 增加 guide_confidence 阈值 |
| 兼容性问题 | 现有代码受影响 | 保留 V1 接口、新增 V2 接口 |

---

## 八、向后兼容性

**策略**: V1 接口保留，V2 作为新增功能

```python
# V1 接口保留 (向后兼容)
class Level0Router:
    def route(self, query): ...  # 不变

# V2 接口新增
class Level0Router:
    def route(self, query): ...  # 保留
    def route_with_guide(self, query): ...  # 新增
```

**迁移路径**:
1. 并行开发 V2
2. 灰度测试
3. 逐步切换
4. 废弃 V1 (可选)

---

**文档版本**: 1.0  
**创建日期**: 2026-03-16  
**状态**: 规划中
