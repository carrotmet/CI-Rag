# Level 2 CI 不一致及简单问题逃逸根因分析与整改方案

## 问题概述

### 问题1: Level 2 提示词中 Level 1 输入数据与原始 Level 1 结果 CI 不一致

**现象**: 在 GUI 的 Level 2 "提示词构建"标签页中，显示的 Level 1 输入数据（如 I_mean=0.500）与原始 Level 1 结果中的实际值（如 I=0.64）不一致。

### 问题2: 简单问题无法有效判断，强制走完三级链路

**现象**: 对于简单查询（如"1+1=?"），即使 Level 0 和 Level 1 已能正确处理，仍会触发 Level 2，导致所有查询都走完完整的三级链路。

---

## 根因分析

### 问题1 根因: 字段名映射错误

**代码位置**: `ci_architecture/level2/prompt_builder.py:325-332`

```python
level1 = Level1Context(
    I_mean=level1_result.get('I_mean', 0.5),  # ❌ 错误：实际字段是 'I'
    sigma_I=level1_result.get('sigma_I', 0.0),  # ❌ 错误：实际字段是 'sigma_i'
    ...
)
```

**调用链路分析**:

```
Level1Router.verify()
  → fusion.fuse_with_level0() 返回: {'I': x, 'sigma_i': y, ...}  ← 字段名: I, sigma_i
  → 添加 retrieval_evidence
  → 返回 final_result

build_level2_context() 读取:
  → level1_result.get('I_mean', 0.5)  ← 找不到，使用默认值 0.5
  → level1_result.get('sigma_I', 0.0)  ← 找不到，使用默认值 0.0
```

**实际 Level 1 返回的字段** (`fusion_v3.py:319-330`):
```python
return {
    'C': C,
    'I': float(np.clip(I_refined, 0.0, 1.0)),      # ← 融合后的 I 值
    'I_level0': I_0,
    'I_retrieval': fusion.I_mean,                  # ← 检索的 I_mean
    'sigma_c': sigma_c,
    'sigma_i': fusion.sigma_I,                     # ← 融合后的置信度
    'sigma_joint': sigma_joint,
    'escalate': escalate,
    ...
}
```

**问题总结**: `build_level2_context` 期望读取 `I_mean` 和 `sigma_I`，但 `fuse_with_level0` 返回的是 `I` 和 `sigma_i`，导致字段名不匹配，始终使用默认值。

---

### 问题2 根因: 多级逃逸机制失效

#### 根因 2.1: Level 0 冷启动模式强制升级

**代码位置**: `ci_architecture/level0/router.py:134-157`

```python
def _route_cold_start(self, features: np.ndarray) -> Dict:
    """Cold start routing: heuristic only, force escalation."""
    heuristic_result = self.heuristic.predict(features)
    
    return {
        'C': heuristic_result['C'],
        'I': heuristic_result['I'],
        'sigma_c': 0.5,  # ❌ 强制低置信度
        'sigma_i': 0.5,  # ❌ 强制低置信度
        'sigma_joint': 0.5,  # ❌ < 0.7, 触发升级
        'escalate': True,  # ❌ 强制升级
        ...
    }
```

**问题**: 冷启动模式下，所有查询强制 `escalate=True`，无法区分简单/复杂问题。

#### 根因 2.2: 简单问题的 Level 1 检索质量差

**测试案例**: "1+1=?"

**Level 1 检索结果分析**:
- 向量检索最高相似度: 0.133 (医疗文档与数学问题完全不相关)
- 关键词匹配: 只匹配到 "1" (在医疗文档中出现)
- I_retrieval: 0.183 (极低)
- sigma_joint: 0.441 (< 0.7，触发升级)

**问题**: 使用医疗数据集测试通用查询，导致检索质量差，置信度计算失效。

#### 根因 2.3: 阈值设置不合理

**当前阈值**:
- Level 0 → Level 1: `sigma_joint < 0.7`
- Level 1 → Level 2: `sigma_joint < 0.7` 或 `I_mean < 0.5`

**问题**:
1. 阈值过高（0.7），对于简单问题难以达到
2. Level 0 冷启动时 `sigma_joint` 强制为 0.5，必然触发升级
3. 没有针对简单问题的快速通道

#### 根因 2.4: 缺少简单问题识别机制

**当前特征工程** (`ci_architecture/level0/features.py`):
- 特征: 长度、熵、领域切换、疑问词等
- **缺少**: 简单模式识别（如数学表达式、简单事实查询）

**问题**: 启发式规则无法识别 "1+1=?"、"什么是Python?" 等明显简单的查询。

---

## 整改方案

### 整改1: 修复 Level 2 字段名映射错误

**文件**: `ci_architecture/level2/prompt_builder.py`

**修改内容**:
```python
level1 = Level1Context(
    I_mean=level1_result.get('I', level1_result.get('I_mean', 0.5)),  # ✅ 兼容两种字段名
    sigma_I=level1_result.get('sigma_i', level1_result.get('sigma_I', 0.0)),  # ✅ 兼容两种字段名
    I_continuous=level1_result.get('I', 0.5),  # ✅ 添加连续值
    ...
)
```

**同时修改提示词构建**，确保显示正确的融合后值：
```python
lines = [
    ...
    f"Fused I: {context.level1.I_continuous:.3f}",  # ✅ 使用融合后的 I
    f"Fused sigma_I: {context.level1.sigma_I:.3f}",
    ...
]
```

---

### 整改2: Level 0 冷启动模式增加简单问题识别

**文件**: `ci_architecture/level0/heuristic_router.py`

**新增简单问题检测规则**:
```python
def is_simple_query(self, features: np.ndarray, query: str) -> bool:
    """
    检测明显简单的查询，允许在冷启动模式下直接路由。
    
    简单查询特征:
    1. 数学表达式（如 "1+1=?"）
    2. 极短查询（< 5 字符）且为事实性问题
    3. 明确的定义性问题（以"什么是"、"谁是"开头）
    4. 无领域关键词的通用查询
    """
    import re
    
    # 数学表达式
    math_pattern = r'^[\d\+\-\*\/\=\?\s\(\)]+$'
    if re.match(math_pattern, query):
        return True
    
    # 极短查询
    if len(query) < 10 and query.endswith('?'):
        return True
    
    # 定义性问题
    definition_patterns = ['什么是', '谁是', '什么是', '什么是']
    if any(p in query for p in definition_patterns):
        return True
    
    return False
```

**修改冷启动路由逻辑**:
```python
def _route_cold_start(self, features: np.ndarray, query: str) -> Dict:
    heuristic_result = self.heuristic.predict(features)
    
    # ✅ 新增: 简单问题直接路由，不强制升级
    if self.heuristic.is_simple_query(features, query):
        return {
            'C': 0,
            'I': 1,
            'sigma_c': 0.8,  # 高置信度
            'sigma_i': 0.8,
            'sigma_joint': 0.8,  # > 0.7，不触发升级
            'escalate': False,  # ✅ 不升级
            'mode': 'COLD_START_SIMPLE',
            'note': 'Simple query detected, direct routing.'
        }
    
    # 原有逻辑：复杂问题强制升级
    return {
        'sigma_c': 0.5,
        'sigma_i': 0.5,
        'sigma_joint': 0.5,
        'escalate': True,
        ...
    }
```

---

### 整改3: 调整逃逸阈值策略

**文件**: `ci_architecture/config.py`

**新增分级阈值配置**:
```python
class Level0Config(BaseSettings):
    ...
    # 分级阈值策略
    alpha_simple: float = 0.5   # 简单问题阈值（更容易退出）
    alpha_normal: float = 0.7   # 正常阈值
    alpha_complex: float = 0.8  # 复杂问题阈值（更严格）
    
    # 简单问题判断条件
    simple_query_max_length: int = 20
    simple_query_max_entropy: float = 3.0
```

---

### 整改4: Level 1 增加检索质量检测

**文件**: `ci_architecture/level1/fusion_v3.py`

**新增检索质量检查**:
```python
def check_retrieval_quality(self, vector_result, keyword_result) -> Dict:
    """
    检查检索质量，识别低质量检索（如跨领域查询）。
    
    返回:
        {'quality': 'high'|'low'|'none', 'reason': str}
    """
    # 向量检索质量
    vector_sim = vector_result.get('sim_max', 0) if vector_result else 0
    
    # 关键词检索质量
    keyword_score = keyword_result.get('score_max', 0) if keyword_result else 0
    
    # 如果两者都很低，可能是跨领域查询
    if vector_sim < 0.3 and keyword_score < 3.0:
        return {
            'quality': 'low',
            'reason': f'Low retrieval quality (vector_sim={vector_sim:.3f}, keyword_score={keyword_score:.2f})'
        }
    
    if vector_sim < 0.2:
        return {'quality': 'none', 'reason': 'No relevant documents found'}
    
    return {'quality': 'high', 'reason': 'Good retrieval quality'}
```

**修改融合逻辑**:
```python
def fuse_with_level0(self, level0_result, ...):
    ...
    
    # ✅ 新增: 检查检索质量
    quality_check = self.check_retrieval_quality(vector_result, keyword_result)
    
    if quality_check['quality'] == 'none':
        # 检索质量极差，回退到 Level 0 判断
        return {
            'C': level0_result.get('C', 0),
            'I': level0_result.get('I', 0),
            'sigma_c': level0_result.get('sigma_c', 0.5),
            'sigma_i': level0_result.get('sigma_i', 0.5),
            'sigma_joint': level0_result.get('sigma_joint', 0.5),
            'escalate': level0_result.get('escalate', True),
            'retrieval_quality': 'poor',
            'note': 'Poor retrieval quality, fallback to Level 0'
        }
    
    ...
```

---

### 整改5: GUI 增加阈值实时调整功能

**文件**: `tools/ci_test_window.py`

**新增阈值调整控件**:
```python
def build_threshold_controls(self, parent_frame):
    """添加阈值调整控件，便于测试不同阈值效果。"""
    threshold_frame = ttk.LabelFrame(parent_frame, text="逃逸阈值调整", padding="5")
    
    # Level 0 → Level 1 阈值
    ttk.Label(threshold_frame, text="L0→L1 阈值:").grid(row=0, column=0)
    self.l0_threshold = tk.DoubleVar(value=0.7)
    ttk.Scale(threshold_frame, from_=0.3, to=0.9, variable=self.l0_threshold, 
              orient=tk.HORIZONTAL, length=150).grid(row=0, column=1)
    ttk.Label(threshold_frame, textvariable=self.l0_threshold).grid(row=0, column=2)
    
    # Level 1 → Level 2 阈值
    ttk.Label(threshold_frame, text="L1→L2 阈值:").grid(row=1, column=0)
    self.l1_threshold = tk.DoubleVar(value=0.7)
    ttk.Scale(threshold_frame, from_=0.3, to=0.9, variable=self.l1_threshold,
              orient=tk.HORIZONTAL, length=150).grid(row=1, column=1)
    ttk.Label(threshold_frame, textvariable=self.l1_threshold).grid(row=1, column=2)
```

---

## 验证方案

### 验证1: 字段名修复验证

**测试查询**: "患者咳嗽有铁锈色痰，胸痛发热"

**预期结果**:
- Level 2 提示词中 Level 1 输入应显示: I=0.64 (而非 0.50)
- Level 2 提示词中 Level 1 输入应显示: sigma_I=0.84 (而非 0.00)

### 验证2: 简单问题识别验证

**测试用例**:
1. "1+1=?" → 应在 Level 0 直接退出（C=0, escalate=False）
2. "什么是Python?" → 应在 Level 0 直接退出
3. "安装" → 应在 Level 0 直接退出
4. "分析某医药公司的Kubernetes部署合规性..." → 应触发 Level 2

### 验证3: 阈值调整验证

**测试方法**:
1. 将 L0→L1 阈值调整为 0.5
2. 测试简单问题 "1+1=?"
3. 预期: Level 0 sigma_joint=0.5 >= 阈值，不触发升级

---

## 整改优先级

| 优先级 | 整改项 | 影响 | 工作量 |
|:------:|--------|------|--------|
| 🔴 P0 | 修复字段名映射错误 | 解决数据不一致问题 | 30分钟 |
| 🟠 P1 | Level 0 简单问题识别 | 解决简单问题逃逸 | 2小时 |
| 🟡 P2 | 检索质量检测 | 提高系统鲁棒性 | 2小时 |
| 🟢 P3 | GUI 阈值调整 | 便于调试和优化 | 1小时 |
| 🔵 P4 | 分级阈值配置 | 长期优化 | 1小时 |

---

## 附: 关键代码路径汇总

| 文件 | 相关函数/行 | 问题描述 |
|------|------------|----------|
| `ci_architecture/level2/prompt_builder.py:325-332` | `build_level2_context` | 字段名映射错误 |
| `ci_architecture/level0/router.py:134-157` | `_route_cold_start` | 强制升级所有查询 |
| `ci_architecture/level0/heuristic_router.py` | `predict` | 缺少简单问题识别 |
| `ci_architecture/level1/fusion_v3.py:319-330` | `fuse_with_level0` | 返回字段名不一致 |
| `ci_architecture/level1/level1_router.py:158-187` | `verify` | 调用融合后返回结果 |

---

*文档版本: 1.0*  
*创建时间: 2026-03-16*  
*分析人: AI Assistant*
