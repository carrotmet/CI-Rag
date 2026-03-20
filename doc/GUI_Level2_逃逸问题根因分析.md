# GUI Level 2 逃逸问题根因分析报告

## 问题现象

查询 **"患者咳嗽有铁锈色痰，胸痛发热"** 在 Level 0 和 Level 1 的判断结果都显示高置信度、不应升级的情况下，仍然执行了 Level 2。

### 实际数据

**Level 0 结果**:
```json
{
  "C": 1,
  "I": 0,
  "sigma_joint": 0.927,
  "escalate": false,  // 明确标记不升级
  "mode": "XGBOOST_HIGH_CONF"
}
```

**Level 1 结果**:
```json
{
  "I": 0.656,
  "sigma_joint": 0.881,  // > 0.7，高置信度
  "escalate": "False",   // 标记不升级（但为字符串类型）
  "conflict_detected": false
}
```

**预期行为**: 由于 escalate 都为 false，不应触发 Level 2。

**实际行为**: Level 2 仍然被执行。

---

## 根因分析

### 根因 1: GUI 设计逻辑问题（主因）

**代码位置**: `tools/ci_test_window.py:563`

```python
# Level 2
if use_l2:  # ❌ 仅根据用户勾选决定，不看 L1 的 escalate 结果
    if not l0_result:
        l0_result = self.router.route(query)
    if not l1_result:
        l1_result = self.execute_level1(query, l0_result)
    
    l2_result = self.execute_level2(query, l0_result, l1_result)  // 直接执行
```

**问题**: GUI 是一个**手动测试工具**，其设计逻辑是：
- "用户勾选哪个 level，就执行哪个 level"
- 而不是："根据上一级的 escalate 标志自动决定是否执行"

**对比生产环境设计**:
```python
# 正确的生产环境逻辑应该是：
if use_l0:
    l0_result = router.route(query)
    if l0_result['escalate']:  # 根据结果自动升级
        l1_result = level1.verify(query, l0_result)
        if l1_result['escalate']:  # 根据结果自动升级
            l2_result = level2.arbitrate(query, l0_result, l1_result)
```

### 根因 2: escalate 类型不一致（潜在问题）

**数据对比**:
- Level 0: `"escalate": false` （布尔值）
- Level 1: `"escalate": "False"` （字符串）

**风险**: 字符串 `"False"` 在 Python 中为真值：
```python
if "False":  # 结果为 True！非空字符串被视为真
    print("会被执行")
```

---

## 为什么这是一个问题？

### 1. 违背架构设计原则

CI-RAG-ROUTER 的核心架构是**渐进式升级**（Progressive Escalation）：
```
Level 0 (σ < 0.7) → Level 1 (σ < 0.7) → Level 2
         ↓                   ↓              ↓
    Hard Route         Verification      Arbitration
```

GUI 的当前实现允许**跳过判断逻辑**，直接执行任意级别，这破坏了"绝不前置 LLM"的核心原则。

### 2. 产生误导性结果

用户看到 Level 2 被执行，会误以为：
- "我的查询置信度不够，需要 LLM 仲裁"
- "Level 1 判断应该升级"

实际上：
- Level 0: σ_joint = 0.927（高置信度）
- Level 1: σ_joint = 0.881（高置信度）
- 都不应该升级到 Level 2

### 3. 成本浪费

不必要的 Level 2 调用：
- API 调用费用：~$0.002/次
- 延迟增加：~1000ms
- 对于批量查询成本显著

---

## 解决方案

### 方案 A: 修复 GUI 逻辑（推荐）

修改 `tools/ci_test_window.py`，使 Level 2 的执行取决于 Level 1 的 `escalate` 结果：

```python
# Level 2 - 根据 Level 1 结果智能决定是否执行
if use_l2:
    # 如果没有前置结果，先生成
    if not l0_result:
        l0_result = self.router.route(query)
    if not l1_result:
        l1_result = self.execute_level1(query, l0_result)
    
    # 检查是否需要升级到 Level 2
    should_escalate_to_l2 = l1_result.get('escalate', False)
    
    # 处理字符串类型的 "False"
    if isinstance(should_escalate_to_l2, str):
        should_escalate_to_l2 = should_escalate_to_l2.lower() == 'true'
    
    # 强制模式：如果用户明确勾选 L2，提示是否强制执行
    if should_escalate_to_l2:
        l2_result = self.execute_level2(query, l0_result, l1_result)
        result['level2'] = l2_result
    else:
        # 显示提示：Level 1 已足够，无需 L2
        l2_result = {
            'skipped': True,
            'reason': 'Level 1 confidence sufficient (σ >= 0.7), no escalation needed',
            'level1_sigma': l1_result.get('sigma_joint', 0)
        }
        result['level2'] = l2_result
```

### 方案 B: 添加"自动升级模式"开关

保留手动测试功能，同时支持自动升级：

```python
# 在 GUI 中添加模式选择
self.auto_escalate_var = tk.BooleanVar(value=True)  # 默认自动升级

ttk.Checkbutton(mode_frame, text="自动升级模式", 
               variable=self.auto_escalate_var).pack(side=tk.LEFT)

# 执行逻辑
if use_l2:
    if self.auto_escalate_var.get():
        # 自动模式：根据 escalate 标志决定
        if l1_result.get('escalate', False):
            l2_result = self.execute_level2(...)
    else:
        # 手动模式：强制执行（测试用途）
        l2_result = self.execute_level2(...)
```

### 方案 C: 修复 Level 1 的 escalate 类型

确保 `escalate` 始终是布尔值：

```python
# 在 Level 1 返回结果时
def verify(self, query, level0_result):
    ...
    return {
        'escalate': bool(escalate),  # 强制转换为布尔值
        ...
    }
```

---

## 修复代码实现

以下是修复后的 `execute_routing` 方法：

```python
def execute_routing(self):
    """Execute the routing process based on selected mode"""
    query = self.query_text.get("1.0", tk.END).strip()
    
    if not query:
        messagebox.showwarning("输入为空", "请输入查询语句")
        return
    
    use_l0 = self.use_level0_var.get()
    use_l1 = self.use_level1_var.get()
    use_l2 = self.use_level2_var.get()
    
    if not use_l0 and not use_l1 and not use_l2:
        messagebox.showwarning("模式错误", "请至少选择一种执行模式")
        return
        
    self.status_bar.config(text=f"正在处理: {query[:50]}...")
    self.root.update()
    
    try:
        start_time = time.time()
        result = {}
        l0_result = None
        l1_result = None
        l2_result = None
        escalation_path = []  # 记录升级路径
        
        # Level 0
        if use_l0:
            l0_result = self.router.route(query)
            result['level0'] = l0_result
            escalation_path.append(f"L0(σ={l0_result.get('sigma_joint', 0):.2f})")
            
            # 如果不升级到 L1，但用户勾选了 L1，提示用户
            if not l0_result.get('escalate', False) and use_l1:
                escalation_path.append("L1-skipped(L0-sufficient)")
        
        # Level 1 - 根据 L0 结果或用户勾选执行
        if use_l1 and (l0_result is None or l0_result.get('escalate', False)):
            if l0_result:
                l1_result = self.execute_level1(query, l0_result)
            else:
                l1_result = self.execute_level1(query, {})
            result['level1'] = l1_result
            escalation_path.append(f"L1(σ={l1_result.get('sigma_joint', 0):.2f})")
        elif use_l1:
            # L0 已经足够，但仍执行 L1 用于测试
            l1_result = self.execute_level1(query, l0_result)
            result['level1'] = l1_result
            escalation_path.append(f"L1-forced(σ={l1_result.get('sigma_joint', 0):.2f})")
        
        # Level 2 - 智能升级逻辑
        if use_l2:
            # 确保有前置结果
            if not l0_result:
                l0_result = self.router.route(query)
            if not l1_result and self.documents:
                l1_result = self.execute_level1(query, l0_result)
            
            # 检查是否应该升级到 L2
            should_escalate = False
            if l1_result:
                # 处理可能的字符串类型
                escalate_flag = l1_result.get('escalate', False)
                if isinstance(escalate_flag, str):
                    should_escalate = escalate_flag.lower() == 'true'
                else:
                    should_escalate = bool(escalate_flag)
            
            if should_escalate or not l1_result:
                # 真正需要 L2 的情况
                l2_result = self.execute_level2(query, l0_result, l1_result)
                result['level2'] = l2_result
                escalation_path.append(f"L2(σ={l2_result.get('confidence', 0):.2f})")
            else:
                # L1 已经足够，跳过 L2
                l2_result = {
                    'skipped': True,
                    'reason': 'Level 1 confidence sufficient, no escalation needed',
                    'level1_sigma_joint': l1_result.get('sigma_joint', 0),
                    'suggested_action': 'Use Level 1 result directly'
                }
                result['level2'] = l2_result
                escalation_path.append("L2-skipped(L1-sufficient)")
        
        # 确定显示结果
        if l2_result and not l2_result.get('skipped', False):
            display_result = {**l0_result, **l1_result, **l2_result}
        elif l1_result:
            display_result = {**l0_result, **l1_result}
        elif l0_result:
            display_result = l0_result
        else:
            display_result = {}
        
        # 添加升级路径信息
        result['_escalation_path'] = ' -> '.join(escalation_path)
        
        elapsed = (time.time() - start_time) * 1000
        self.update_results(query, display_result, elapsed, result)
        self.status_bar.config(text=f"完成 ({elapsed:.2f}ms) | Path: {result['_escalation_path']}")
        
    except Exception as e:
        import traceback
        messagebox.showerror("错误", f"路由执行失败:\n{str(e)}\n\n{traceback.format_exc()}")
        self.status_bar.config(text=f"错误: {e}")
```

---

## 修复效果预期

### 修复前
```
用户勾选: L0 + L1 + L2
执行结果: L0 -> L1 -> L2 (全部执行)
显示: "升级到 Level 2" (误导)
```

### 修复后
```
用户勾选: L0 + L1 + L2
执行结果: L0 -> L1 -> [L2 skipped]
显示: "Level 1 已足够，跳过了 Level 2"
状态栏: "L0(σ=0.93) -> L1(σ=0.88) -> L2-skipped(L1-sufficient)"
```

---

## 建议的改进优先级

| 优先级 | 改进项 | 影响 | 工作量 |
|:------:|:-------|:-----|:------:|
| 🔴 P0 | 修复 GUI 升级逻辑 | 避免误导，节约 API 成本 | 2小时 |
| 🟡 P1 | 修复 escalate 类型一致性 | 避免类型错误 | 30分钟 |
| 🟢 P2 | 添加升级路径显示 | 提高可观测性 | 1小时 |
| 🔵 P3 | 添加"强制测试模式"开关 | 保留测试灵活性 | 2小时 |

---

*分析时间: 2026-03-20*  
*问题定位: GUI 设计逻辑与架构预期的偏差*
