#!/usr/bin/env python3
"""
测试 Level 2 LLM 连接
验证 litellm 和 API key 是否配置正确
"""

import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("[OK] .env 文件已加载")
except ImportError:
    print("[WARN] python-dotenv 未安装，尝试直接读取 .env")
    # 手动读取 .env
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        print("[OK] .env 文件手动加载完成")

def test_import():
    """测试模块导入"""
    print("\n" + "="*50)
    print("步骤 1: 测试模块导入")
    print("="*50)
    
    try:
        from ci_architecture.level2 import LLMClient, Level2Router
        print("[OK] Level 2 模块导入成功")
        return True
    except Exception as e:
        print(f"[FAIL] 导入失败: {e}")
        return False

def test_api_key():
    """测试 API key 是否存在"""
    print("\n" + "="*50)
    print("步骤 2: 检查 API Key")
    print("="*50)
    
    api_key = os.environ.get("CI_LLM_API_KEY")
    if not api_key:
        print("[FAIL] CI_LLM_API_KEY 环境变量未设置")
        print("   请检查 .env 文件是否存在且包含 API key")
        return False
    
    # 隐藏部分 key 显示
    masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
    print(f"[OK] API Key 已设置: {masked_key}")
    print(f"   Key 长度: {len(api_key)} 字符")
    return True

def test_llm_connection():
    """测试 LLM 连接"""
    print("\n" + "="*50)
    print("步骤 3: 测试 LLM 连接")
    print("="*50)
    
    try:
        from ci_architecture.level2 import LLMClient
        
        print("正在初始化 LLMClient...")
        client = LLMClient(model_alias="ci-evaluation")
        
        print(f"使用模型: {client.model_alias}")
        print(f"实际模型: {client.model_config.model}")
        print(f"API Base: {client.model_config.api_base or 'default'}")
        
        # 发送简单测试请求
        print("\n发送测试请求...")
        test_prompt = "回复 'OK' 表示连接成功"
        
        response = client.complete_simple(
            prompt=test_prompt,
            system="你是一个测试助手，请简短回复。"
        )
        
        if response:
            print(f"[OK] 连接成功！")
            print(f"   响应内容: {response[:100]}...")
            
            # 显示指标
            metrics = client.get_metrics()
            print(f"\n[STATS] 请求指标:")
            print(f"   延迟: {metrics['avg_latency_ms']} ms")
            print(f"   Token 输入: {metrics.get('total_requests', 0)}")
            
            return True
        else:
            print("[FAIL] 连接失败: 空响应")
            return False
            
    except Exception as e:
        print(f"[FAIL] 连接失败: {e}")
        import traceback
        print("\n详细错误:")
        print(traceback.format_exc())
        return False

def test_level2_router():
    """测试 Level2Router 完整流程"""
    print("\n" + "="*50)
    print("步骤 4: 测试 Level2Router")
    print("="*50)
    
    try:
        from ci_architecture.level2 import Level2Router
        
        print("正在初始化 Level2Router...")
        router = Level2Router(use_dual_probe=False)  # 单探针模式更快
        
        # 模拟 Level 0 和 Level 1 结果
        level0_result = {
            'C': 1,
            'I': 0,
            'C_continuous': 1.0,
            'I_continuous': 0.3,
            'sigma_c': 0.5,
            'sigma_i': 0.4,
            'sigma_joint': 0.45,
            'escalate': True,
            'mode': 'XGBOOST_LOW_CONF_ESCALATE',
            'features': [0.0] * 12
        }
        
        level1_result = {
            'I_mean': 0.4,
            'sigma_I': 0.35,
            'vector': None,
            'keyword': None,
            'conflict_detected': False,
            'source_weights': {},
            'retrieval_evidence': {'top_documents': []}
        }
        
        test_query = "分析某医药公司的Kubernetes部署合规性，考虑成本、安全性和法规要求"
        
        print(f"\n测试查询: {test_query[:50]}...")
        print("执行 Level 2 仲裁...")
        
        result = router.arbitrate(test_query, level0_result, level1_result)
        
        print(f"\n[OK] Level 2 执行成功！")
        print(f"   C (复杂度): {result.C} ({'高' if result.C == 1 else '低'})")
        print(f"   I (信息充分性): {result.I} ({'充分' if result.I == 1 else '不足'})")
        print(f"   置信度: {result.confidence:.3f}")
        print(f"   模式: {result.mode}")
        print(f"   是否升级: {result.escalate}")
        print(f"   延迟: {result.latency_ms:.2f} ms")
        print(f"   成本: ${result.cost_usd:.6f}")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Level2Router 测试失败: {e}")
        import traceback
        print("\n详细错误:")
        print(traceback.format_exc())
        return False

def main():
    """主测试流程"""
    print("="*50)
    print("CI-RAG-ROUTER Level 2 连接测试")
    print("="*50)
    
    results = []
    
    # 步骤 1: 导入测试
    results.append(("模块导入", test_import()))
    
    # 步骤 2: API key 检查
    results.append(("API Key", test_api_key()))
    
    # 步骤 3: LLM 连接测试
    results.append(("LLM 连接", test_llm_connection()))
    
    # 步骤 4: Level2Router 测试
    results.append(("Level2Router", test_level2_router()))
    
    # 总结
    print("\n" + "="*50)
    print("测试结果总结")
    print("="*50)
    
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    
    print(f"\n总计: {passed}/{total} 项通过")
    
    if passed == total:
        print("\n[SUCCESS] 所有测试通过！Level 2 已就绪")
        return 0
    else:
        print("\n[WARNING] 部分测试失败，请检查配置")
        return 1

if __name__ == "__main__":
    sys.exit(main())
