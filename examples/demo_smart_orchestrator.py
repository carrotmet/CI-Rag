"""
Smart Orchestrator Demo

Demonstrates the intelligent zone transition capabilities of Smart Orchestrator.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ci_architecture.orchestrator import (
    SmartOrchestrator,
    CIState,
    Zone
)


def demo_zone_d_to_c():
    """Demo: Zone D (C0I0) → Zone C (C0I1) via information completion"""
    print("=" * 60)
    print("Demo 1: Zone D → Zone C (信息补充)")
    print("=" * 60)
    
    orchestrator = SmartOrchestrator()
    
    # Initial query with insufficient information
    query = "这个药怎么用？"
    print(f"\n用户查询: '{query}'")
    
    result = orchestrator.process(query, session_id="demo_d_to_c")
    
    print(f"\n初始评估结果:")
    print(f"  状态: {result['status']}")
    print(f"  当前区域: {result.get('current_zone', 'N/A')}")
    print(f"  目标区域: {result.get('target_zone', 'N/A')}")
    
    if result['status'] == 'clarification_needed':
        print(f"\n需要补充的信息:")
        for info in result['missing_info']:
            print(f"  - {info}", flush=True)
        
        print(f"\n系统提示:\n{result['prompt'].replace(chr(8226), '-')}")
        
        # Simulate user providing information
        print("\n" + "-" * 40)
        print("模拟用户补充信息...")
        print("-" * 40)
        
        provided_info = {
            "药品": "阿莫西林",
            "患者年龄": "35岁成人",
            "症状": "感冒引起的喉咙痛"
        }
        print(f"用户提供: {provided_info}")
        
        # Continue with new information
        result2 = orchestrator.continue_with_info("demo_d_to_c", provided_info)
        
        print(f"\n补充信息后评估:")
        print(f"  状态: {result2['status']}")
        print(f"  区域: {result2.get('zone', 'N/A')}")
        print(f"  CI: C={result2['ci']['C']:.2f}, I={result2['ci']['I']:.2f}")
        
        if result2['status'] == 'success':
            print(f"\n✓ 成功转入最优区 {result2['zone']}，可直接输出！")
            print(f"  执行配置: {result2['execution_config']}")


def demo_zone_b_to_a():
    """Demo: Zone B (C1I0) → Zone A (C1I1) via info completion"""
    print("\n" + "=" * 60)
    print("Demo 2: Zone B → Zone A (保留复杂度的信息补充)")
    print("=" * 60)
    
    orchestrator = SmartOrchestrator()
    
    query = "分析这个症状并给出治疗建议"
    print(f"\n用户查询: '{query}'")
    
    result = orchestrator.process(query, session_id="demo_b_to_a")
    
    print(f"\n初始评估结果:")
    print(f"  状态: {result['status']}")
    print(f"  当前区域: {result.get('current_zone', 'N/A')}")
    
    if result['status'] == 'clarification_needed':
        print(f"\n需要补充的关键信息:")
        for info in result['missing_info']:
            print(f"  - {info}")
        
        # Simulate providing information
        print("\n" + "-" * 40)
        print("模拟用户补充详细信息...")
        print("-" * 40)
        
        provided_info = {
            "症状描述": "咳嗽、铁锈色痰、胸痛",
            "持续时间": "3天",
            "患者年龄": "45岁男性",
            "体温": "38.5度"
        }
        print(f"用户提供: {provided_info}")
        
        result2 = orchestrator.continue_with_info("demo_b_to_a", provided_info)
        
        print(f"\n补充信息后评估:")
        print(f"  状态: {result2['status']}")
        print(f"  区域: {result2.get('zone', 'N/A')}")
        print(f"  CI: C={result2['ci']['C']:.2f}, I={result2['ci']['I']:.2f}")
        
        if result2['status'] == 'success' and result2['zone'] == 'A':
            print(f"\n✓ 成功转入 Zone A (C1I1)！")
            print(f"  保持高复杂度(C={result2['ci']['C']:.2f})")
            print(f"  信息已充足(I={result2['ci']['I']:.2f})")
            print(f"  执行策略: {result2['execution_config']['description']}")


def demo_zone_b_decomposition():
    """Demo: Zone B (C1I0) → Zone C (C0I1) via problem decomposition"""
    print("\n" + "=" * 60)
    print("Demo 3: Zone B → Zone C (问题分解)")
    print("=" * 60)
    
    orchestrator = SmartOrchestrator()
    
    query = "如何设计一个高并发电商系统？"
    print(f"\n用户查询: '{query}'")
    print(f"\n这是一个复杂问题(C高)，但信息相对充分(I中等)")
    print(f"策略选择: 分解为多个简单子问题")
    
    # Force decomposition strategy by specifying target_zone=C
    result = orchestrator.process(
        query, 
        session_id="demo_b_decomp",
        force_zone=Zone.C  # Force transition to C via decomposition
    )
    
    print(f"\n初始评估结果:")
    print(f"  状态: {result['status']}")
    
    if result['status'] == 'decomposition_proposed':
        print(f"\n✓ 系统建议问题分解")
        print(f"  原区域: {result['current_zone']}")
        print(f"  目标区域: {result['target_zone']}")
        print(f"  策略: {result['strategy']}")
        
        print(f"\n生成的子问题:")
        for i, sp in enumerate(result['sub_problems'], 1):
            print(f"  {i}. [{sp['id']}] {sp['query']}")
            print(f"     预期区域: {sp['expected_zone']}")
        
        print(f"\n{result['message']}")
        
        # Simulate executing decomposition
        print("\n" + "-" * 40)
        print("模拟执行问题分解...")
        print("-" * 40)
        
        exec_result = orchestrator.execute_decomposition("demo_b_decomp")
        
        print(f"\n子问题执行计划:")
        for sub in exec_result['sub_problems']:
            print(f"  - {sub['sub_problem_id']}: Zone {sub['zone']}")
        
        print(f"\n聚合配置:")
        print(f"  目标区域: {exec_result['aggregation_target']}")
        print(f"  配置: {exec_result['aggregation_config']}")


def demo_direct_optimal():
    """Demo: Direct execution when already in optimal zone"""
    print("\n" + "=" * 60)
    print("Demo 4: 直接在最优区执行")
    print("=" * 60)
    
    orchestrator = SmartOrchestrator()
    
    # A query that is simple and well-defined (Zone C)
    query = "什么是Python中的列表推导式？"
    print(f"\n用户查询: '{query}'")
    
    result = orchestrator.process(query, session_id="demo_direct")
    
    print(f"\n评估结果:")
    print(f"  状态: {result['status']}")
    print(f"  区域: {result.get('zone', 'N/A')}")
    
    if result['status'] == 'success':
        print(f"\n✓ 已在最优区 {result['zone']}！")
        print(f"  CI: C={result['ci']['C']:.2f}, I={result['ci']['I']:.2f}")
        print(f"  执行策略: {result['execution_config']['description']}")
        print(f"  Token预算: {result['execution_config']['max_tokens']}")


def demo_ci_tracker_history():
    """Demo: CI Tracker history tracking"""
    print("\n" + "=" * 60)
    print("Demo 5: CI 追踪历史")
    print("=" * 60)
    
    orchestrator = SmartOrchestrator()
    
    queries = [
        "这个药怎么用？",  # D
        "这个药怎么用？药品:阿莫西林",  # D→?
        "这个药怎么用？药品:阿莫西林; 年龄:35岁",  # C?
    ]
    
    session_id = "demo_history"
    
    for i, query in enumerate(queries, 1):
        print(f"\n轮次 {i}: '{query}'")
        
        if i == 1:
            result = orchestrator.process(query, session_id=session_id)
        else:
            # Parse provided info from query
            if ";" in query:
                base_query, info_part = query.split(";", 1)
                info_dict = {}
                for pair in info_part.split(";"):
                    if ":" in pair:
                        k, v = pair.split(":", 1)
                        info_dict[k.strip()] = v.strip()
                result = orchestrator.continue_with_info(session_id, info_dict)
            else:
                result = orchestrator.process(query, session_id=session_id)
        
        print(f"  结果: Zone {result.get('zone', result.get('current_zone', '?'))}, "
              f"status={result['status']}")
    
    # Show history
    history = orchestrator.get_session_history(session_id)
    print(f"\nCI 历史轨迹 ({len(history)} 次评估):")
    for i, h in enumerate(history, 1):
        print(f"  {i}. Zone {h['zone']}, C={h['C']:.2f}, I={h['I']:.2f}, σ={h['sigma_joint']:.2f}")


def main():
    """Run all demos"""
    print("\n" + "=" * 60)
    print("Smart Orchestrator 智能协调器演示")
    print("=" * 60)
    print("\n本演示展示 CI-RAG-Router 的智能转区能力:")
    print("  1. Zone D→C: 信息补充转区")
    print("  2. Zone B→A: 保留复杂度的信息补充")
    print("  3. Zone B→C: 问题分解")
    print("  4. 直接最优区执行")
    print("  5. CI 历史追踪")
    
    import sys
    auto_mode = '--auto' in sys.argv
    
    if not auto_mode:
        input("\n按 Enter 开始演示...")
    else:
        print("\n[自动模式]\n")
    
    demo_zone_d_to_c()
    
    if not auto_mode:
        input("\n按 Enter 继续...")
    demo_zone_b_to_a()
    
    if not auto_mode:
        input("\n按 Enter 继续...")
    demo_zone_b_decomposition()
    
    if not auto_mode:
        input("\n按 Enter 继续...")
    demo_direct_optimal()
    
    if not auto_mode:
        input("\n按 Enter 继续...")
    demo_ci_tracker_history()
    
    print("\n" + "=" * 60)
    print("演示完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
