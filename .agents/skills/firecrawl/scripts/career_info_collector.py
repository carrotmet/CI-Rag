#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
职业信息自动收集器 - Firecrawl 工具脚本
用于收集职业、专业、行业趋势等数据
"""

from firecrawl import Firecrawl
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
import json
import hashlib
from datetime import datetime
import time


@dataclass
class CareerInfo:
    """职业信息数据结构"""
    occupation_name: str
    description: str
    sources: List[dict]
    collected_at: str
    content_hash: str
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MajorInfo:
    """专业信息数据结构"""
    major_name: str
    introduction: str
    courses: List[str]
    career_prospects: str
    sources: List[dict]
    collected_at: str


class CareerInfoCollector:
    """职业信息收集器 - 职业规划导航平台专用"""
    
    def __init__(self, api_key: str = "fc-da5cc27f2e3743a991072cae744230a0"):
        self.app = Firecrawl(api_key=api_key)
        self.request_count = 0
        self.last_request_time = None
    
    def _rate_limit(self, delay: float = 1.0):
        """简单的速率限制"""
        if self.last_request_time:
            elapsed = (datetime.now() - self.last_request_time).total_seconds()
            if elapsed < delay:
                time.sleep(delay - elapsed)
        self.last_request_time = datetime.now()
        self.request_count += 1
    
    def collect_occupation(self, occupation_name: str, search_limit: int = 5) -> CareerInfo:
        """
        收集特定职业的详细信息
        
        Args:
            occupation_name: 职业名称（如"软件工程师"）
            search_limit: 搜索结果数量限制
        
        Returns:
            CareerInfo 对象
        """
        print(f"🔍 正在收集职业信息: {occupation_name}")
        
        # 构建搜索查询
        queries = [
            f'{occupation_name} 工作内容 职责',
            f'{occupation_name} 薪资待遇 发展前景',
            f'{occupation_name} 技能要求 入行条件'
        ]
        
        all_sources = []
        all_contents = []
        
        for query in queries:
            try:
                self._rate_limit(1.0)
                results = self.app.search(query, params={'limit': search_limit})
                
                for result in results:
                    source_url = result['metadata']['sourceURL']
                    # 去重检查
                    if not any(s['url'] == source_url for s in all_sources):
                        all_sources.append({
                            'url': source_url,
                            'title': result['metadata'].get('title', 'Unknown'),
                            'description': result['metadata'].get('description', '')
                        })
                        all_contents.append(result['markdown'])
                        
            except Exception as e:
                print(f"  ⚠️ 搜索失败 '{query}': {e}")
        
        # 合并内容
        full_content = '\n\n---\n\n'.join(all_contents)
        content_hash = hashlib.md5(full_content.encode()).hexdigest()[:16]
        
        print(f"✅ 收集完成: {occupation_name} (来源: {len(all_sources)} 个)")
        
        return CareerInfo(
            occupation_name=occupation_name,
            description=full_content[:10000],  # 限制长度
            sources=all_sources,
            collected_at=datetime.now().isoformat(),
            content_hash=content_hash
        )
    
    def collect_major(self, major_name: str, university: str = None) -> MajorInfo:
        """
        收集专业相关信息
        
        Args:
            major_name: 专业名称（如"计算机科学与技术"）
            university: 特定大学（可选）
        
        Returns:
            MajorInfo 对象
        """
        print(f"🔍 正在收集专业信息: {major_name}")
        
        # 构建查询
        queries = [
            f'{major_name} 专业介绍 培养目标',
            f'{major_name} 课程设置 主要课程',
            f'{major_name} 就业方向 毕业去向'
        ]
        
        if university:
            queries.append(f'{university} {major_name} 专业')
        
        all_sources = []
        all_contents = []
        
        for query in queries:
            try:
                self._rate_limit(1.0)
                results = self.app.search(query, params={'limit': 3})
                
                for result in results:
                    source_url = result['metadata']['sourceURL']
                    if not any(s['url'] == source_url for s in all_sources):
                        all_sources.append({
                            'url': source_url,
                            'title': result['metadata'].get('title', 'Unknown')
                        })
                        all_contents.append(result['markdown'])
                        
            except Exception as e:
                print(f"  ⚠️ 搜索失败 '{query}': {e}")
        
        print(f"✅ 收集完成: {major_name} (来源: {len(all_sources)} 个)")
        
        return MajorInfo(
            major_name=major_name,
            introduction='\n'.join(all_contents)[:5000],
            courses=[],
            career_prospects='',
            sources=all_sources,
            collected_at=datetime.now().isoformat()
        )
    
    def batch_collect_occupations(self, occupations: List[str]) -> List[CareerInfo]:
        """批量收集多个职业的信息"""
        results = []
        print(f"\n📋 开始批量收集 {len(occupations)} 个职业信息\n")
        
        for i, occupation in enumerate(occupations, 1):
            print(f"[{i}/{len(occupations)}] ", end="")
            try:
                info = self.collect_occupation(occupation)
                results.append(info)
            except Exception as e:
                print(f"✗ 失败: {occupation} - {e}")
        
        print(f"\n✅ 批量收集完成: {len(results)}/{len(occupations)} 成功")
        return results
    
    def collect_industry_trends(self, industry: str, year: int = 2025) -> Dict:
        """
        收集行业趋势信息
        
        Args:
            industry: 行业名称
            year: 年份
        """
        print(f"🔍 正在收集 {industry} 行业趋势 ({year})")
        
        queries = [
            f'{industry} 行业趋势 {year} 发展前景',
            f'{industry} 行业报告 市场分析',
            f'{industry} 人才需求 就业机会'
        ]
        
        all_data = []
        
        for query in queries:
            try:
                self._rate_limit(1.0)
                results = self.app.search(query, params={'limit': 3})
                all_data.extend(results)
            except Exception as e:
                print(f"  ⚠️ 搜索失败: {e}")
        
        return {
            'industry': industry,
            'year': year,
            'data': all_data,
            'collected_at': datetime.now().isoformat()
        }
    
    def scrape_url(self, url: str) -> Optional[str]:
        """
        抓取特定URL的内容
        
        Args:
            url: 网页URL
        
        Returns:
            Markdown 格式的内容
        """
        try:
            self._rate_limit(0.5)
            result = self.app.scrape(url)
            return result.get('markdown', '')
        except Exception as e:
            print(f"⚠️ 抓取失败 {url}: {e}")
            return None


def save_to_json(data, filename: str):
    """保存数据到JSON文件"""
    if isinstance(data, list) and len(data) > 0 and hasattr(data[0], 'to_dict'):
        data = [item.to_dict() for item in data]
    elif hasattr(data, 'to_dict'):
        data = data.to_dict()
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"💾 数据已保存到: {filename}")


# ============ 使用示例 ============

if __name__ == "__main__":
    # 初始化收集器
    collector = CareerInfoCollector()
    
    # 示例1: 收集单个职业
    print("=" * 50)
    print("示例1: 收集单个职业信息")
    print("=" * 50)
    
    info = collector.collect_occupation("软件工程师")
    print(f"\n职业: {info.occupation_name}")
    print(f"来源数: {len(info.sources)}")
    print(f"内容长度: {len(info.description)} 字符")
    print(f"内容预览:\n{info.description[:500]}...")
    
    # 保存到文件
    save_to_json(info, "software_engineer_info.json")
    
    # 示例2: 批量收集多个职业
    print("\n" + "=" * 50)
    print("示例2: 批量收集多个职业")
    print("=" * 50)
    
    occupations = ["数据分析师", "产品经理", "UI设计师"]
    batch_results = collector.batch_collect_occupations(occupations)
    
    save_to_json(batch_results, "batch_occupations.json")
    
    # 示例3: 收集专业信息
    print("\n" + "=" * 50)
    print("示例3: 收集专业信息")
    print("=" * 50)
    
    major_info = collector.collect_major("计算机科学与技术")
    print(f"\n专业: {major_info.major_name}")
    print(f"介绍: {major_info.introduction[:300]}...")
    
    save_to_json(major_info, "computer_science_major.json")
    
    # 示例4: 抓取特定URL
    print("\n" + "=" * 50)
    print("示例4: 抓取特定网页")
    print("=" * 50)
    
    url = "https://docs.firecrawl.dev/introduction"
    content = collector.scrape_url(url)
    if content:
        print(f"成功抓取 {url}")
        print(f"内容长度: {len(content)} 字符")
        print(f"预览:\n{content[:500]}...")
    
    print("\n✅ 所有示例执行完成!")
