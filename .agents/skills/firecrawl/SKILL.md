---
name: firecrawl
description: 高效的网页数据抓取工具，将任意网页转换为干净的Markdown格式。支持单页抓取、搜索抓取、整站爬取和网站地图生成，适用于数据收集、内容分析和知识库构建。
---

# Firecrawl 网页数据抓取工具

> 将混乱的网页转换为结构化的Markdown，让AI轻松理解网络内容

---

## 快速入门

### 1. 安装

```bash
pip install firecrawl-py
```

### 2. 基础使用

```python
from firecrawl import Firecrawl

# 初始化客户端
app = Firecrawl(api_key="fc-da5cc27f2e3743a991072cae744230a0")

# 抓取单个页面
result = app.scrape('https://example.com')
print(result['markdown'])
```

---

## 核心功能

### 1. 单页抓取 (Scrape)

将单个网页转换为干净的 Markdown。

```python
# 基础抓取
result = app.scrape('https://docs.firecrawl.dev/introduction')

# 获取结构化数据
markdown_content = result['markdown']
metadata = result['metadata']  # 包含标题、描述、URL等信息
```

**适用场景：**
- 抓取技术文档
- 获取文章正文
- 提取产品信息
- 收集参考资料

---

### 2. 搜索抓取 (Search)

搜索关键词并抓取相关网页内容。

```python
# 搜索并抓取前5个结果
results = app.search('职业规划三层模型', params={'limit': 5})

for item in results:
    print(f"标题: {item['metadata']['title']}")
    print(f"URL: {item['metadata']['sourceURL']}")
    print(f"内容: {item['markdown'][:500]}...")
    print("---")
```

**适用场景：**
- 快速收集某主题的网上资料
- 构建领域知识库
- 竞品分析
- 行业调研

---

### 3. 整站爬取 (Crawl)

爬取整个网站的所有页面。

```python
# 爬取整个网站
crawl_result = app.crawl('https://docs.firecrawl.dev')

# 获取所有页面
for page in crawl_result:
    print(f"URL: {page['metadata']['sourceURL']}")
    print(f"内容长度: {len(page['markdown'])} 字符")
```

**高级选项：**
```python
# 限制爬取范围
crawl_result = app.crawl('https://example.com', params={
    'includePaths': ['/docs/*', '/blog/*'],  # 只爬取这些路径
    'excludePaths': ['/admin/*', '/private/*'],  # 排除这些路径
    'maxDepth': 2,  # 最大爬取深度
    'limit': 100    # 最多抓取100页
})
```

**适用场景：**
- 构建完整的技术文档库
- 备份网站内容
- 大规模内容分析

---

### 4. 网站地图 (Map)

获取网站的所有页面URL列表。

```python
# 生成网站地图
map_result = app.map('https://example.com')

# 获取所有URL
urls = map_result['links']
print(f"发现 {len(urls)} 个页面")

for url in urls[:10]:  # 显示前10个
    print(url)
```

**适用场景：**
- 了解网站结构
- 选择性地抓取特定页面
- 网站健康检查

---

## 与职业规划导航平台的结合使用

### 场景1：收集职业信息

```python
from firecrawl import Firecrawl
import json

app = Firecrawl(api_key="fc-da5cc27f2e3743a991072cae744230a0")

def collect_career_info(occupation_name: str) -> dict:
    """收集特定职业的详细信息"""
    
    # 搜索相关职业信息
    search_results = app.search(f'{occupation_name} 职业发展 薪资待遇', params={'limit': 3})
    
    career_data = {
        'occupation': occupation_name,
        'sources': [],
        'content_summary': ''
    }
    
    for item in search_results:
        source = {
            'url': item['metadata']['sourceURL'],
            'title': item['metadata']['title'],
            'content': item['markdown']
        }
        career_data['sources'].append(source)
        career_data['content_summary'] += item['markdown'][:1000] + '\n\n'
    
    return career_data

# 使用示例
data = collect_career_info('软件工程师')
print(json.dumps(data, ensure_ascii=False, indent=2))
```

---

### 场景2：收集专业介绍资料

```python
def collect_major_info(major_name: str, university_url: str = None) -> dict:
    """收集专业相关信息"""
    
    app = Firecrawl(api_key="fc-da5cc27f2e3743a991072cae744230a0")
    
    # 搜索专业介绍
    search_results = app.search(f'{major_name} 专业介绍 课程设置 就业方向', params={'limit': 5})
    
    major_data = {
        'major_name': major_name,
        'introduction': '',
        'courses': [],
        'career_prospects': '',
        'sources': []
    }
    
    for item in search_results:
        content = item['markdown']
        
        # 简单提取（实际可使用LLM进行结构化提取）
        if '课程' in content or '培养' in content:
            major_data['courses'].append(content[:2000])
        if '就业' in content or '前景' in content:
            major_data['career_prospects'] += content[:2000]
        
        major_data['sources'].append({
            'url': item['metadata']['sourceURL'],
            'title': item['metadata']['title']
        })
    
    return major_data
```

---

### 场景3：更新行业趋势数据

```python
def update_industry_trends(industry: str) -> list:
    """更新特定行业的最新趋势"""
    
    app = Firecrawl(api_key="fc-da5cc27f2e3743a991072cae744230a0")
    
    # 搜索最新行业报告
    results = app.search(f'{industry} 行业趋势 2024 2025 报告', params={'limit': 5})
    
    trends = []
    for item in results:
        trends.append({
            'source_url': item['metadata']['sourceURL'],
            'title': item['metadata']['title'],
            'content': item['markdown'],
            'description': item['metadata'].get('description', ''),
            'fetched_at': datetime.now().isoformat()
        })
    
    return trends
```

---

### 场景4：抓取职业测评工具说明

```python
def collect_assessment_tools() -> dict:
    """收集职业规划相关测评工具信息"""
    
    app = Firecrawl(api_key="fc-da5cc27f2e3743a991072cae744230a0")
    
    tools = {
        'holland': app.search('Holland职业兴趣测评 官方说明', params={'limit': 3}),
        'mbti': app.search('MBTI性格测试 职业应用 官方', params={'limit': 3}),
        'casve': app.search('CASVE决策模型 职业规划 应用', params={'limit': 3})
    }
    
    tool_data = {}
    for tool_name, results in tools.items():
        tool_data[tool_name] = [
            {
                'title': r['metadata']['title'],
                'url': r['metadata']['sourceURL'],
                'content': r['markdown'][:3000]
            }
            for r in results
        ]
    
    return tool_data
```

---

## 高级用法

### 批量抓取与并发控制

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from firecrawl import Firecrawl

def batch_scrape(urls: list, max_workers: int = 3) -> list:
    """批量抓取多个URL"""
    
    app = Firecrawl(api_key="fc-da5cc27f2e3743a991072cae744230a0")
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(app.scrape, url): url for url in urls
        }
        
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                data = future.result()
                results.append({
                    'url': url,
                    'success': True,
                    'data': data
                })
            except Exception as e:
                results.append({
                    'url': url,
                    'success': False,
                    'error': str(e)
                })
    
    return results
```

---

### 增量更新策略

```python
import hashlib
from datetime import datetime, timedelta

def incremental_update(urls: list, last_update: dict) -> dict:
    """
    增量更新网页内容
    
    Args:
        urls: 要监控的URL列表
        last_update: 上次更新的数据 {url: {'hash': 'xxx', 'content': '...'}}
    
    Returns:
        更新的内容
    """
    app = Firecrawl(api_key="fc-da5cc27f2e3743a991072cae744230a0")
    updates = {}
    
    for url in urls:
        try:
            result = app.scrape(url)
            content = result['markdown']
            current_hash = hashlib.md5(content.encode()).hexdigest()
            
            # 检查是否有变化
            if url in last_update:
                if last_update[url]['hash'] != current_hash:
                    updates[url] = {
                        'hash': current_hash,
                        'content': content,
                        'updated_at': datetime.now().isoformat(),
                        'is_new': False
                    }
            else:
                updates[url] = {
                    'hash': current_hash,
                    'content': content,
                    'updated_at': datetime.now().isoformat(),
                    'is_new': True
                }
        except Exception as e:
            print(f"Failed to scrape {url}: {e}")
    
    return updates
```

---

## 错误处理与重试

```python
from tenacity import retry, stop_after_attempt, wait_exponential
import firecrawl

class FirecrawlClient:
    """带重试机制的 Firecrawl 客户端"""
    
    def __init__(self, api_key: str):
        self.app = Firecrawl(api_key=api_key)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((firecrawl.errors.RateLimitError, ConnectionError))
    )
    def scrape(self, url: str, **kwargs):
        """带重试的抓取"""
        return self.app.scrape(url, **kwargs)
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def search(self, query: str, **kwargs):
        """带重试的搜索"""
        return self.app.search(query, **kwargs)
    
    def safe_scrape(self, url: str, fallback_content: str = None) -> dict:
        """安全抓取，失败时返回备用内容"""
        try:
            return self.scrape(url)
        except Exception as e:
            print(f"Failed to scrape {url}: {e}")
            return {
                'markdown': fallback_content or f"# 抓取失败\n\n无法获取 {url} 的内容。",
                'metadata': {'sourceURL': url, 'error': str(e)}
            }
```

---

## 数据处理与存储

### 存储到数据库

```python
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class WebContent(Base):
    __tablename__ = 'web_contents'
    
    id = Column(String, primary_key=True)
    url = Column(String, index=True)
    title = Column(String)
    content = Column(Text)
    source_type = Column(String)  # 'scrape', 'search', 'crawl'
    fetched_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def save_to_database(content_data: dict, db_session):
    """将抓取内容保存到数据库"""
    
    content = WebContent(
        id=hashlib.md5(content_data['url'].encode()).hexdigest(),
        url=content_data['url'],
        title=content_data.get('title', ''),
        content=content_data.get('markdown', ''),
        source_type=content_data.get('source_type', 'scrape')
    )
    
    db_session.merge(content)  # 使用merge实现upsert
    db_session.commit()
```

---

## 最佳实践

### 1. 尊重网站规则

```python
# 检查 robots.txt
def check_robots_txt(url: str) -> bool:
    """检查是否允许抓取"""
    from urllib.robotparser import RobotFileParser
    from urllib.parse import urlparse
    
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    
    rp = RobotFileParser()
    rp.set_url(robots_url)
    rp.read()
    
    return rp.can_fetch('*', url)
```

### 2. 控制抓取频率

```python
import time

def rate_limited_scrape(urls: list, delay: float = 1.0):
    """限速抓取"""
    app = Firecrawl(api_key="fc-da5cc27f2e3743a991072cae744230a0")
    
    for url in urls:
        try:
            result = app.scrape(url)
            yield result
            time.sleep(delay)  # 延迟避免触发限流
        except Exception as e:
            print(f"Error scraping {url}: {e}")
```

### 3. 内容去重

```python
def deduplicate_content(contents: list) -> list:
    """基于内容哈希去重"""
    seen_hashes = set()
    unique_contents = []
    
    for content in contents:
        content_hash = hashlib.md5(content['markdown'].encode()).hexdigest()
        if content_hash not in seen_hashes:
            seen_hashes.add(content_hash)
            unique_contents.append(content)
    
    return unique_contents
```

---

## 完整示例：职业信息自动收集器

```python
#!/usr/bin/env python3
"""
职业信息自动收集器 - 使用 Firecrawl
自动收集特定职业的详细信息并保存到数据库
"""

from firecrawl import Firecrawl
from dataclasses import dataclass
from typing import List, Optional
import json
from datetime import datetime

@dataclass
class CareerInfo:
    """职业信息数据结构"""
    occupation_name: str
    description: str
    salary_range: str
    education_requirements: str
    skills_required: List[str]
    career_path: str
    sources: List[dict]
    collected_at: str

class CareerInfoCollector:
    """职业信息收集器"""
    
    def __init__(self, api_key: str):
        self.app = Firecrawl(api_key=api_key)
    
    def collect(self, occupation_name: str) -> CareerInfo:
        """收集特定职业的完整信息"""
        
        # 1. 搜索职业概览
        search_results = self.app.search(
            f'{occupation_name} 工作内容 薪资待遇 职业前景',
            params={'limit': 5}
        )
        
        # 2. 整理信息
        sources = []
        full_content = []
        
        for result in search_results:
            sources.append({
                'url': result['metadata']['sourceURL'],
                'title': result['metadata']['title']
            })
            full_content.append(result['markdown'])
        
        # 3. 使用LLM提取结构化信息（可选）
        # extracted_info = self._extract_with_llm('\n\n'.join(full_content))
        
        return CareerInfo(
            occupation_name=occupation_name,
            description='\\n'.join(full_content)[:5000],
            salary_range='待提取',
            education_requirements='待提取',
            skills_required=[],
            career_path='待提取',
            sources=sources,
            collected_at=datetime.now().isoformat()
        )
    
    def batch_collect(self, occupations: List[str]) -> List[CareerInfo]:
        """批量收集多个职业的信息"""
        results = []
        for occupation in occupations:
            try:
                info = self.collect(occupation)
                results.append(info)
                print(f"✓ 已收集: {occupation}")
            except Exception as e:
                print(f"✗ 失败: {occupation} - {e}")
        return results

# 使用示例
if __name__ == "__main__":
    collector = CareerInfoCollector("fc-da5cc27f2e3743a991072cae744230a0")
    
    # 收集单个职业
    info = collector.collect("软件工程师")
    print(json.dumps(info.__dict__, ensure_ascii=False, indent=2))
    
    # 批量收集
    occupations = ["数据分析师", "产品经理", "UI设计师", "运营专员"]
    all_info = collector.batch_collect(occupations)
```

---

## API 密钥信息

```
API Key: fc-da5cc27f2e3743a991072cae744230a0
```

---

## 相关链接

- **官方文档**: https://docs.firecrawl.dev/introduction
- **Python SDK**: https://github.com/mendableai/firecrawl-py
- **API 参考**: https://docs.firecrawl.dev/api-reference

---

## 注意事项

1. **速率限制**: 免费账户有每日请求限制，大量抓取时请控制频率
2. **内容版权**: 抓取的内容仅供学习和研究使用，遵守相关版权法规
3. **robots.txt**: 尊重网站的 robots.txt 规则，不要抓取禁止访问的内容
4. **数据隐私**: 不要抓取包含个人隐私信息的内容

---

**最后更新**: 2026-02-24
