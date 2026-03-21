# CI-RAG-Router V4

基于置信度的智能 RAG 路由系统 (Confidence-Informed RAG Router)

## 架构概览

```
Level 012 逃逸层 → Zone A/B/D 自治执行 → Orchestrator V4 转区校验 → Zone C 统一出口
```

### V4 架构特点

- **Level 012 逃逸层**: 快速判定初始 Zone (A/B/C/D)
- **Zone A (拆解区)**: C=1, I=1 - 复杂问题拆解为子问题
- **Zone B (综合区)**: C=1, I=0 - 混合策略 (检索或拆解)
- **Zone C (大脑/出口)**: C=0, I=1 - 统一出口，支持三种模式
- **Zone D (补I区)**: C=0, I=0 - 信息检索
- **Orchestrator V4**: 简化职责，仅转区校验 (C=0, I>=0.7)

## 快速开始

### 安装依赖

```bash
# 使用 uv 创建虚拟环境
uv venv --python 3.10
.venv\Scripts\activate

# 安装依赖
uv pip install -r requirements.txt
```

### 启动 GUI

```bash
# 启动 V4 测试 GUI
.venv\Scripts\python tools\ci_test_window_v4.py

# 或使用启动脚本
start_gui.ps1
```

### 运行测试

```bash
# V4 架构测试
python tests\test_v4_architecture.py

# V4 综合验证
python tests\test_v4_validation.py

# GUI 覆盖测试
python tests\test_gui_v4_coverage.py
```

## 核心组件

### V4 Pipeline

```python
from ci_architecture.v4_pipeline import CIRouterPipelineV4

pipeline = CIRouterPipelineV4()
result = pipeline.process("你的查询")

print(f"最终Zone: {result.final_zone}")
print(f"执行路径: {result.execution_path}")
print(f"答案: {result.answer}")
```

### Zone 处理器

```python
from ci_architecture.zones import ZoneAHandler, ZoneBHandler, ZoneCHandler, ZoneDHandler

# Zone D - 信息检索
zd = ZoneDHandler()
result = zd.enter(query, {'C': 0, 'I': 0})

# Zone A - 问题拆解  
za = ZoneAHandler()
result = za.enter(query, {'C': 1, 'I': 1})

# Zone C - 统一出口
zc = ZoneCHandler()
result = zc.process_direct(query)
```

### Orchestrator V4

```python
from ci_architecture.orchestrator.orchestrator_v4 import OrchestratorV4

orch = OrchestratorV4()
result = orch.request_transition(query, ci_state, source_zone)

# 转区成功条件: C=0 且 I>=0.7
if result.success:
    print(f"转区到 {result.target_zone}")
else:
    print(f"触发策略升级: {result.trigger_strategy_upgrade}")
```

## 项目结构

```
ci_architecture/
├── v4_pipeline.py              # V4 集成管道
├── orchestrator/
│   ├── orchestrator_v4.py      # V4 协调器 (转区校验)
│   └── smart_orchestrator_v2.py # V2 协调器 (保留)
├── zones/
│   ├── base.py                 # Zone 基类
│   ├── zone_a.py               # Zone A - 拆解区
│   ├── zone_b.py               # Zone B - 综合区
│   ├── zone_c.py               # Zone C - 大脑/出口
│   └── zone_d.py               # Zone D - 补I区
├── common/
│   ├── guide_generator.py      # Guide 生成器
│   ├── strategy_manager.py     # 策略升级管理
│   └── subproblem_queue.py     # 子问题队列
├── level0/                     # Level 0: XGBoost路由
├── level1/                     # Level 1: 混合检索
└── level2/                     # Level 2: LLM仲裁

tools/
├── ci_test_window_v4.py        # V4 GUI 测试工具
└── ci_test_window.py           # V2 GUI (保留)

tests/
├── test_v4_architecture.py     # V4 基础测试 (13项)
├── test_v4_validation.py       # V4 综合验证 (7项)
└── test_gui_v4_coverage.py     # GUI 覆盖测试

doc/
├── CI-RAG-ROUTER-ARCHITECTURE-v4.md  # V4 架构文档
├── V4_GUI_INTEGRATION.md             # GUI 集成文档
└── V4_IMPLEMENTATION_SUMMARY.md      # 实现总结
```

## CI 状态映射

| C (复杂度) | I (信息度) | Zone | 处理策略 |
|:----------:|:----------:|:----:|:---------|
| 0 | 0 | **D** | 信息检索 |
| 0 | 1 | **C** | 直接回答 |
| 1 | 0 | **B** | 混合策略 |
| 1 | 1 | **A** | 问题拆解 |

## 转区条件

转区到 **Zone C (统一出口)** 的条件:
- `C = 0` (问题已简化)
- `I >= 0.7` (信息充分)

如果不满足条件:
1. 返回原 Zone
2. 触发**策略升级**
3. 使用更激进的检索/拆解策略
4. 最多尝试 3 次后强制转区

## Zone C 三种模式

1. **直接模式**: 简单问题直接推理输出
2. **子问题队列模式**: 子问题结果收集，完成后组装输出
3. **组装模式**: 综合检索结果和子问题答案输出

## 文档

- [V4 架构文档](doc/CI-RAG-ROUTER-ARCHITECTURE-v4.md)
- [GUI 集成文档](doc/V4_GUI_INTEGRATION.md)
- [实现总结](doc/V4_IMPLEMENTATION_SUMMARY.md)

## 测试覆盖

| 测试类别 | 测试项 | 状态 |
|:---------|:-------|:----:|
| 基础单元测试 | 13项 | ✅ |
| 综合验证测试 | 7项 | ✅ |
| GUI 覆盖测试 | 5项 | ✅ |
| **总计** | **25项** | **✅ 通过** |

## 开发状态

- **版本**: V4
- **状态**: 初期实现完成
- **测试**: 全部通过
- **日期**: 2026-03-21

## License

MIT