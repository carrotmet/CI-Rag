#!/usr/bin/env python3
"""
演示如何在 GUI 中使用 V2 协调器

V2 协调器特性:
1. Zone B/D 必须携带 orchestrator_guide
2. 支持多策略 [clarify, decompose]
3. 最大 2 轮转区限制
4. 按 Level 2 Guide 执行，不自决策

Usage:
    python tools/ci_test_window.py
    
    然后在界面中:
    1. 勾选 "使用 V2 协调器 (带 Guide)"
    2. 输入查询语句
    3. 点击 "执行 (Enter)" 或 "执行 V2 协调器"
"""

print("""
=== CI-RAG-Router V2 协调器 GUI 使用说明 ===

1. 启动 GUI:
   python tools/ci_test_window.py

2. 启用 V2 协调器:
   - 在 "执行模式" 区域勾选 "使用 V2 协调器 (带 Guide)"
   - 状态栏会显示 "当前: V2 协调器模式 (Guide-based)"

3. 输入查询:
   - 示例: "How to use this medicine?"
   - 或点击 "示例查询 ▼" 选择预设查询

4. 执行:
   - 按 Enter 键
   - 或点击 "执行 (Enter)"
   - 或切换到 "协调器 (V2)" 选项卡点击 "执行 V2 协调器"

5. 查看结果:
   - "协调器 (V2)" 选项卡会显示:
     * 初始 Zone 判定
     * orchestrator_guide (由 Level 2 生成)
     * 推荐策略 [clarify/decompose]
     * 转区计划和执行结果

6. 多策略支持:
   - 如果 Guide 推荐多个策略，会显示 "用户可选择: 是"
   - 可以查看 clarify 和 decompose 两种方案的详情

7. 模拟多轮交互:
   - 点击 "模拟多轮交互" 按钮
   - 查看 V2 协调器如何处理多轮信息补充

=== V2 vs V1 对比 ===

特性              V1                    V2
--------------------------------------------------
决策方式      协调器自决策         Level 2 Guide 指导
Zone B/D      可直接进入           必须有 orchestrator_guide
策略选择      单一策略             多策略可选 [clarify, decompose]
转区轮数      无限制               最大 2 轮
missing_info  启发式识别           Level 2 专业判断
""")
