# CI-RAG-Router V4 GUI 集成文档

## 概述

V4 GUI (`tools/ci_test_window_v4.py`) 是 CI-RAG-Router V4 架构的图形化测试工具，提供了完整的 V4 功能可视化和测试覆盖。

## 启动方式

```bash
# 使用 PowerShell
.venv\Scripts\python tools\ci_test_window_v4.py

# 或双击运行
start_gui.ps1
```

## 功能特性

### 1. 系统状态面板

显示所有组件的初始化状态：
- Level 0 (XGBoost 路由)
- Level 1 (混合检索)
- Level 2 (LLM 仲裁)
- **V4 Pipeline** (新增)
- **V4 Orchestrator** (新增)
- V2 Orchestrator (保留)

### 2. 执行模式选择

#### 标准模式
- **Level 0**: XGBoost 快速路由
- **Level 1**: 混合检索 (向量+关键词+结构化)
- **Level 2**: LLM 仲裁

#### V4 架构模式 (新增)
- **V4 Pipeline** (推荐): 完整 V4 架构流程
  - Level 012 逃逸层 → Zone 判定 → Orchestrator 校验 → Zone C 输出
- **V4 Orchestrator**: 单独测试转区校验功能
- **V2 Orchestrator**: 旧版 Guide-based 协调器

### 3. V4 架构测试点 (新增)

8个快速测试按钮，覆盖所有 V4 测试点：

| 按钮 | 测试功能 | 预期结果 |
|:-----|:---------|:---------|
| CI映射 | CI到Zone映射 | C/I正确映射到ABCD四区 |
| Zone D检索 | 信息检索区 | 返回检索文档列表 |
| Zone A拆解 | 问题拆解区 | 生成3+子问题 |
| Zone B混合 | 综合处理区 | 选择检索/拆解策略 |
| Zone C直接 | 直接输出模式 | 返回推理结果 |
| Zone C队列 | 子问题队列模式 | 展示队列组装流程 |
| 策略升级 | 策略升级链 | 展示策略升级路径 |
| 转区校验 | Orchestrator校验 | 展示通过/拒绝逻辑 |

### 4. 结果展示标签页

#### 新增标签页

1. **V4 Pipeline**: 显示完整 V4 执行结果
   - 执行路径追踪
   - Zone 转换记录
   - 最终输出

2. **Zone执行**: 四个子标签页
   - Zone A (拆解): 子问题生成详情
   - Zone B (综合): 策略选择和执行
   - Zone C (大脑/出口): 三种模式输出
   - Zone D (补I): 检索结果和I值变化

3. **协调器V4**: V4 Orchestrator 执行结果
   - 转区请求详情
   - CI 条件校验
   - 通过/拒绝决策

#### 保留标签页

- 摘要: CI评估、置信度、决策
- 特征详情: Level 0 特征提取
- 检索结果(L1): 向量/关键词检索
- LLM仲裁(L2): Level 2 结果
- 协调器V2: 旧版协调器
- 原始数据: JSON 输出
- 历史记录: 查询历史

## V4 测试覆盖对照表

| V4 架构测试点 | GUI测试按钮 | 结果展示位置 |
|:-------------|:------------|:-------------|
| CI State映射 | CI映射按钮 | 弹出窗口 |
| Zone D执行 | Zone D检索按钮 | Zone执行标签页 |
| Zone A执行 | Zone A拆解按钮 | Zone执行标签页 |
| Zone B执行 | Zone B混合按钮 | Zone执行标签页 |
| Zone C直接模式 | Zone C直接按钮 | Zone执行标签页 |
| Zone C队列模式 | Zone C队列按钮 | Zone执行标签页 |
| 策略升级 | 策略升级按钮 | 弹出窗口 |
| 转区校验 | 转区校验按钮 | 协调器V4标签页 |
| V4 Pipeline | V4 Pipeline模式 | V4 Pipeline标签页 |
| Orchestrator V4 | V4 Orchestrator模式 | 协调器V4标签页 |

## 使用示例

### 示例 1: 测试 V4 Pipeline 完整流程

1. 选择执行模式: **V4 Pipeline (推荐)**
2. 输入查询: `"什么是Python？"`
3. 点击 **执行** 按钮
4. 查看 **V4 Pipeline** 标签页的执行路径

预期输出:
```
Level 012判定 -> Zone D -> 检索执行 -> Orchestrator校验 -> Zone C -> 直接输出
```

### 示例 2: 测试单个 Zone

1. 点击 **V4 架构测试点** 区域的 **Zone D检索** 按钮
2. 查看弹出窗口的测试结果

预期输出:
```
Zone D (补I区) 测试结果:
检索文档数: 6
新I值: 0.67
策略: retrieve_expanded
请求转区: True
```

### 示例 3: 测试转区校验逻辑

1. 选择执行模式: **V4 Orchestrator**
2. 点击 **执行 V4 协调器** 按钮
3. 查看 **协调器V4** 标签页

预期输出:
```
查询: test
来源Zone: D
当前CI: C=0.2, I=0.8
转区结果: APPROVED
动作: transition_to_c
目标Zone: C
```

## 文件说明

```
tools/
├── ci_test_window.py          # 原版 GUI (V2)
├── ci_test_window_v4.py       # V4 增强版 GUI
└── run_gui.ps1                # 启动脚本
```

## 技术实现

### V4 组件集成

```python
from ci_architecture.v4_pipeline import CIRouterPipelineV4
from ci_architecture.orchestrator.orchestrator_v4 import OrchestratorV4
from ci_architecture.zones import ZoneAHandler, ZoneBHandler, ZoneCHandler, ZoneDHandler
from ci_architecture.common import GuideGenerator, StrategyManager, SubProblemQueue
```

### GUI 类结构

```
CIRouterTestWindowV4
├── init_routers()          # 初始化V4 Pipeline和Orchestrator
├── build_ui()              # 构建UI界面
│   ├── build_v4_test_frame()      # V4测试点按钮
│   ├── build_v4_pipeline_tab()    # V4 Pipeline结果
│   ├── build_zone_execution_tab() # Zone执行可视化
│   └── build_orchestrator_v4_tab() # V4 Orchestrator
└── V4测试方法
    ├── test_ci_mapping()
    ├── test_zone_d()
    ├── test_zone_a()
    ├── test_zone_b()
    ├── test_zone_c_direct()
    ├── test_zone_c_queue()
    ├── test_strategy_upgrade()
    └── test_transition_validation()
```

## 测试验证

运行 GUI 集成测试:

```bash
python -c "
from tools.ci_test_window_v4 import CIRouterTestWindowV4, V4_AVAILABLE
print(f'V4_AVAILABLE: {V4_AVAILABLE}')
"
```

预期输出:
```
V4_AVAILABLE: True
```

## 与 V4 架构文档对齐

| 架构文档章节 | GUI对应功能 |
|:-------------|:------------|
| Level 012 逃逸层 | V4 Pipeline模式执行 |
| Zone A/B/D 自治 | Zone执行标签页 |
| Orchestrator转区校验 | 协调器V4标签页 + 转区校验按钮 |
| Zone C统一出口 | Zone C直接/队列按钮 |
| 策略升级 | 策略升级按钮 |
| 子问题队列 | Zone C队列按钮 |

---

*文档版本: V4*  
*更新日期: 2026-03-21*