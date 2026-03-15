#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Firecrawl 快速开始示例
最简单的使用方式演示
"""

from firecrawl import Firecrawl

# ============ 配置 ============
API_KEY = "fc-da5cc27f2e3743a991072cae744230a0"

# ============ 初始化 ============
app = Firecrawl(api_key=API_KEY)

print("🔥 Firecrawl 快速开始示例")
print("=" * 50)

# ============ 示例1: 抓取单个网页 ============
print("\n📄 示例1: 抓取单个网页")
print("-" * 50)

url = "https://docs.firecrawl.dev/introduction"
print(f"正在抓取: {url}")

try:
    result = app.scrape(url)
    print(f"✅ 抓取成功!")
    print(f"标题: {result['metadata'].get('title', 'N/A')}")
    print(f"内容长度: {len(result['markdown'])} 字符")
    print(f"\n内容预览 (前500字符):")
    print(result['markdown'][:500])
    print("\n...")
except Exception as e:
    print(f"❌ 抓取失败: {e}")

# ============ 示例2: 搜索并抓取 ============
print("\n" + "=" * 50)
print("🔍 示例2: 搜索并抓取")
print("-" * 50)

query = "职业规划 三层模型"
print(f"搜索关键词: {query}")

try:
    results = app.search(query, params={'limit': 3})
    print(f"✅ 找到 {len(results)} 个结果\n")
    
    for i, item in enumerate(results, 1):
        print(f"[{i}] {item['metadata'].get('title', 'Unknown')}")
        print(f"    URL: {item['metadata']['sourceURL']}")
        print(f"    内容预览: {item['markdown'][:200]}...")
        print()
except Exception as e:
    print(f"❌ 搜索失败: {e}")

# ============ 示例3: 职业规划导航平台实用示例 ============
print("\n" + "=" * 50)
print("💼 示例3: 收集职业信息")
print("-" * 50)

occupation = "软件工程师"
print(f"收集职业: {occupation}")

try:
    # 搜索职业相关信息
    results = app.search(f'{occupation} 工作内容 薪资待遇', params={'limit': 3})
    
    print(f"✅ 找到 {len(results)} 个来源\n")
    
    # 汇总内容
    contents = []
    for item in results:
        contents.append(item['markdown'])
    
    full_content = '\n\n'.join(contents)
    print(f"总内容长度: {len(full_content)} 字符")
    print(f"\n内容摘要:")
    print(full_content[:800])
    print("\n...")
    
except Exception as e:
    print(f"❌ 收集失败: {e}")

print("\n" + "=" * 50)
print("✅ 所有示例执行完成!")
print("\n更多用法请参考: career_info_collector.py")
