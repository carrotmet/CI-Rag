# LazyLLM 静态工作流设计原则

> 基于 LazyLLM 框架的静态工作流（Static Pipeline）设计指南，整合长文档生成、Function Call、数据处理和 Pipeline 最佳实践。

---

## 参考文档

### 核心参考

| 文档 | 链接 | 核心内容 |
|------|------|----------|
| **基础使用** | [Learn/learn](https://docs.lazyllm.ai/zh-cn/latest/Learn/learn/) | LazyLLM 基础概念、快速入门、核心组件介绍 |
| **官方文档** | [GitHub/LazyLLM](https://github.com/LazyAGI/LazyLLM) | 源码仓库、Issue追踪、最新更新 |
| **最佳实践** | [Best Practice](https://docs.lazyllm.ai/zh-cn/latest/Best%20Practice/flow/) | 官方推荐的最佳实践模式和设计模式 |
| **使用案例** | [Cookbook](https://docs.lazyllm.ai/zh-cn/latest/Cookbook/) | 实际应用案例、场景化解决方案 |

### 专题参考

| 文档 | 链接 | 核心内容 |
|------|------|----------|
| **长文档生成** | [Cookbook/great_writer](https://docs.lazyllm.ai/zh-cn/latest/Cookbook/great_writer/) | 大型文档的分段生成、大纲规划、内容组装 |
| **Function Call** | [Best Practice/functionCall](https://docs.lazyllm.ai/zh-cn/latest/Best%20Practice/functionCall/?h=react#react) | ReAct 模式、工具调用、Agent 设计 |
| **数据处理** | [Best Practice/data_process](https://docs.lazyllm.ai/zh-cn/latest/Best%20Practice/data_process/) | 数据转换、批处理、流水线处理 |
| **Pipeline/Flow** | [Best Practice/flow](https://docs.lazyllm.ai/zh-cn/latest/Best%20Practice/flow/?h=) | 工作流编排、并行处理、条件分支 |
| **向量数据库/量化** | [latest/Tutorial](https://docs.lazyllm.ai/zh-cn/latest/Tutorial/12/) | 向量数据库、向量索引、缓存优化、量化 |

### API参考

| 文档 | 链接 | 核心内容 |
|------|------|----------|
| **API Reference** | [API/cli](https://docs.lazyllm.ai/zh-cn/latest/API%20Reference/cli/) | 完整API文档、类和方法参考 |
| **CLI工具** | [API/cli](https://docs.lazyllm.ai/zh-cn/latest/API%20Reference/cli/) | 命令行工具使用指南 |

### 示例代码

| 路径 | 说明 |
|------|------|
| `./scrpts/02baseRAG.py` | 基础RAG实现示例 |
| `./scrpts/03pipline.py` | Pipeline工作流示例 |

---

## 一、核心概念

### 1.1 什么是静态工作流

静态工作流（Static Pipeline）是指在**设计时就已经确定执行路径**的工作流，与动态工作流（Dynamic/Agentic Workflow）相对：

| 特性 | 静态工作流 | 动态工作流 |
|------|-----------|-----------|
| 执行路径 | 预定义，固定 | 运行时决定，灵活 |
| 适用场景 | 结构化任务、批处理 | 探索性任务、复杂决策 |
| 性能 | 高，无规划开销 | 较低，需要推理规划 |
| 可控性 | 高 | 较低 |
| 典型应用 | ETL、文档生成、数据处理 | ReAct Agent、自主决策 |

### 1.2 LazyLLM 核心组件

```python
from lazyllm import (
    # 工作流控制
    pipeline,          # 顺序执行管道
    parallel,          # 并行执行
    switch,            # 条件分支
    loop,              # 循环执行
    
    # 数据处理
    deduplicate,       # 去重
    join,              # 结果合并
    filter,            # 数据过滤
    transform,         # 数据转换
    
    # AI相关
    function_call,     # 函数调用
    llm,               # 大模型封装
    Tool,              # 工具定义
    Agent,             # 智能体
    
    # RAG相关
    Document,          # 文档处理
    Retriever,         # 检索器
    Reranker,          # 重排序
    
    # 部署相关
    deploy,            # 模型部署
    OnlineModule,      # 在线模型
)
```

### 1.3 基础概念速查

| 概念 | 说明 | 使用场景 |
|------|------|----------|
| `pipeline` | 顺序执行的流程容器 | 多步骤处理，如 ETL、文档生成 |
| `parallel` | 并行执行的流程容器 | 多任务同时处理，提高吞吐量 |
| `switch` | 条件分支选择器 | 根据条件选择不同处理路径 |
| `loop` | 循环控制器 | 需要迭代优化的场景 |
| `for_each` | 批量处理器 | 大数据量的分批处理 |
| `llm` | 大模型封装 | 统一调用各种LLM服务 |
| `Agent` | 智能体 | 需要推理和工具调用的复杂任务 |
| `Tool` | 工具定义 | 为Agent提供外部能力 |

---

## 二、快速入门

### 2.1 安装LazyLLM

```bash
# 基础安装
pip install lazyllm

# 包含所有依赖的完整安装
pip install "lazyllm[all]"

# 仅安装特定模块
pip install "lazyllm[llm]"      # 仅LLM相关
pip install "lazyllm[rag]"      # 仅RAG相关
pip install "lazyllm[deploy]"   # 仅部署相关
```

### 2.2 Hello World示例

```python
from lazyllm import pipeline, llm

# 最简单的pipeline
with pipeline() as p:
    p.greet = lambda name: f"Hello, {name}!"
    p.translate = lambda text: llm(f"Translate to Chinese: {text}")

# 执行
result = p("Alice")
print(result)  # 输出中文问候语
```

### 2.3 第一个RAG应用

```python
from lazyllm import Document, Retriever, llm, pipeline

# 1. 加载文档
docs = Document("./data", recursive=True)

# 2. 构建检索器
retriever = Retriever(docs, topk=3)

# 3. 构建RAG流程
with pipeline() as rag:
    rag.retrieve = retriever                # 检索相关文档
    rag.generate = lambda ctx: llm(f"基于以下信息回答问题：\n{ctx}")

# 4. 使用
answer = rag("什么是LazyLLM？")
```

### 2.4 CLI工具速查

LazyLLM 提供便捷的命令行工具：

```bash
# 查看版本
lazyllm --version

# 启动Web界面
lazyllm webui

# 运行脚本
lazyllm run script.py

# 部署模型
lazyllm deploy --model chatglm3

# 查看帮助
lazyllm --help
lazyllm deploy --help
```

---

## 三、设计原则

### 原则 1：单一职责原则 (SRP)

每个节点只做一件事，便于调试和复用。

```python
# ✅ 好的设计：拆分多个小节点
def extract_keywords(text):
    """提取关键词"""
    return llm(prompt="提取关键词：" + text)

def summarize_text(text):
    """生成摘要"""
    return llm(prompt="总结：" + text)

def classify_category(text):
    """分类"""
    return llm(prompt="分类：" + text)

# 组合成工作流
with pipeline() as p:
    p.keywords = extract_keywords
    p.summary = summarize_text
    p.category = classify_category

# ❌ 坏的设计：一个节点做太多事
def do_everything(text):
    return llm(prompt=f"提取关键词、总结、分类：{text}")
```

### 原则 2：数据流清晰原则

明确每个节点的输入输出类型，避免隐式转换。

```python
from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class Document:
    title: str
    content: str
    keywords: List[str] = None
    summary: str = None

# 明确类型注解
def process_document(doc: Document) -> Document:
    """处理文档，返回增强后的文档"""
    doc.keywords = extract_keywords(doc.content)
    doc.summary = summarize_text(doc.content)
    return doc
```

### 原则 3：错误处理原则

每个节点都应该有错误处理机制，避免级联失败。

```python
from lazyllm import wrapper

@wrapper(try_catch=True)  # 自动捕获异常
def robust_extract(text):
    """鲁棒的关键词提取"""
    try:
        return extract_keywords(text)
    except Exception as e:
        print(f"提取失败：{e}")
        return []  # 返回默认值

# 或者使用 switch 进行错误分支
with pipeline() as p:
    p.extract = extract_keywords
    p.check = lambda x: len(x) > 0  # 检查结果
    
with switch(p.check) as s:
    s.case(True, process_keywords)   # 成功分支
    s.case(False, handle_empty)      # 失败分支
```

### 原则 4：可观测性原则

添加日志和监控，便于追踪执行过程。

```python
from lazyllm import LOG

@wrapper(log=True)
def logged_process(data):
    """带日志的处理节点"""
    LOG.info(f"处理数据：{data[:50]}...")
    result = heavy_computation(data)
    LOG.info(f"处理完成，结果长度：{len(result)}")
    return result
```

---

## 三、模式库

### 模式 1：顺序处理模式 (Sequential Pipeline)

最常用的模式，数据按顺序流经各个节点。

```python
from lazyllm import pipeline

# 文档处理流水线
with pipeline() as doc_processor:
    doc_processor.load = load_document      # 加载文档
    doc_processor.clean = clean_text        # 清洗文本
    doc_processor.split = split_paragraphs  # 分段
    doc_processor.analyze = analyze_content # 内容分析
    doc_processor.save = save_results       # 保存结果

# 使用
result = doc_processor("path/to/document.pdf")
```

### 模式 2：并行处理模式 (Parallel Processing)

多个任务可以并行执行，提高吞吐量。

```python
from lazyllm import parallel

# 并行分析文档的不同方面
with parallel() as analyzer:
    analyzer.sentiment = analyze_sentiment    # 情感分析
    analyzer.topics = extract_topics          # 主题提取
    analyzer.entities = extract_entities      # 实体识别
    analyzer.keywords = extract_keywords      # 关键词提取

# 结果是一个字典，包含所有并行任务的结果
result = analyzer(document_text)
# result = {
#     "sentiment": "positive",
#     "topics": ["AI", "Technology"],
#     "entities": [{"name": "OpenAI", "type": "Company"}],
#     "keywords": ["machine learning", "NLP"]
# }
```

### 模式 3：Map-Reduce 模式

适用于大数据量的分批处理。

```python
from lazyllm import pipeline, parallel

def map_process(chunk):
    """处理单个分片"""
    return analyze(chunk)

def reduce_results(results):
    """合并所有分片结果"""
    return merge_summaries(results)

# Map-Reduce 工作流
with pipeline() as map_reduce:
    map_reduce.split = split_into_chunks    # 1. 拆分
    map_reduce.map = map_process.for_each() # 2. 并行处理每个分片
    map_reduce.reduce = reduce_results      # 3. 合并结果

# 使用：处理长文档
long_document = "..."  # 10万字文档
summary = map_reduce(long_document)
```

### 模式 4：条件分支模式 (Conditional Branching)

根据条件选择不同的处理路径。

```python
from lazyllm import pipeline, switch

def check_doc_type(doc):
    """检查文档类型"""
    return doc.metadata.type

# 条件分支工作流
with pipeline() as router:
    router.check = check_doc_type
    
with switch(router.check) as s:
    # 不同文档类型走不同处理路径
    s.case("pdf", pdf_processor)
    s.case("word", word_processor)
    s.case("txt", txt_processor)
    s.default(unknown_processor)
```

### 模式 5：循环迭代模式 (Loop Pattern)

需要多轮迭代直到满足条件。

```python
from lazyllm import loop, pipeline

# 迭代优化模式
with pipeline() as optimizer:
    optimizer.generate = generate_draft      # 生成初稿
    optimizer.evaluate = evaluate_quality    # 评估质量
    optimizer.revise = revise_content        # 根据反馈修改

# 循环直到质量达标
with loop(condition=lambda x: x.score < 0.9) as l:
    l.iter = optimizer
    
final_result = l(initial_prompt)
```

### 模式 6：ReAct Agent 模式

结合推理和行动，适用于复杂任务。

```python
from lazyllm import Agent, Tool

# 定义工具
search_tool = Tool(
    name="search",
    description="搜索信息",
    func=lambda query: web_search(query)
)

calculate_tool = Tool(
    name="calculate",
    description="计算数值",
    func=lambda expr: eval(expr)
)

# ReAct Agent
agent = Agent(
    llm=llm,
    tools=[search_tool, calculate_tool],
    max_iterations=10,
    react_prompt="""
    思考：分析当前任务
    行动：选择工具并执行
    观察：记录工具返回结果
    重复直到完成任务
    """
)

result = agent("查询北京明天天气，并计算温差")
```

### 模式 7：流式处理模式 (Streaming)

适用于需要实时输出的场景，如Chatbot。

```python
from lazyllm import pipeline, llm

# 流式输出
with pipeline() as streaming_chat:
    streaming_chat.prompt = lambda q: f"用户：{q}\n助手："
    streaming_chat.generate = llm.stream()  # 使用stream()方法

# 使用 - 输出会实时显示
for chunk in streaming_chat("讲个故事"):
    print(chunk, end="", flush=True)
```

### 模式 8：记忆增强模式 (Memory)

维护对话历史，实现多轮对话。

```python
from lazyllm import Memory, pipeline

# 创建记忆模块
memory = Memory(max_length=10)  # 保留最近10轮

with pipeline() as chat_with_memory:
    chat_with_memory.store = memory.store     # 存储当前输入
    chat_with_memory.context = memory.load    # 加载历史
    chat_with_memory.generate = lambda ctx: llm(ctx)
    chat_with_memory.update = memory.update   # 更新记忆

# 多轮对话
chat_with_memory("你好")           # 第1轮
chat_with_memory("刚才我说了什么")  # 能记住上下文
```

### 模式 9：多模型路由模式 (Model Router)

根据任务类型选择不同模型。

```python
from lazyllm import switch, llm

# 定义不同模型
gpt4 = llm(model="gpt-4", name="gpt4")
claude = llm(model="claude-3", name="claude")
local_model = llm(model="chatglm3", name="local")

# 根据复杂度选择模型
def select_model(query):
    if len(query) > 500:
        return "complex"
    elif "代码" in query:
        return "code"
    else:
        return "simple"

with switch(select_model) as router:
    router.case("complex", gpt4)       # 复杂任务用GPT-4
    router.case("code", claude)        # 代码任务用Claude
    router.case("simple", local_model) # 简单任务用本地模型

result = router("帮我写个Python函数")
```

### 模式 10：批处理优化模式 (Batch Processing)

高效处理大量数据。

```python
from lazyllm import pipeline, parallel

# 大批量数据处理
items = range(10000)  # 1万条数据

with pipeline() as batch_processor:
    # 分批处理，每批100条
    batch_processor.split = lambda items: [items[i:i+100] for i in range(0, len(items), 100)]
    
    # 并行处理每批
    batch_processor.process = parallel(
        process_function.for_each(),
        num_workers=4
    )
    
    # 合并结果
    batch_processor.merge = lambda results: sum(results, [])

results = batch_processor(items)
```

---

## 四、完整示例脚本

### 示例 1：长文档生成工作流

```python
#!/usr/bin/env python3
"""
长文档生成工作流示例
基于 LazyLLM 的大纲规划 + 分段生成 + 组装合并
"""

from lazyllm import pipeline, parallel, llm
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class Chapter:
    title: str
    outline: str
    content: str = ""

class DocumentGenerator:
    """长文档生成器"""
    
    def __init__(self, topic: str, total_words: int = 5000):
        self.topic = topic
        self.total_words = total_words
        self.chapters: List[Chapter] = []
        
        # 构建工作流
        self._build_workflow()
    
    def _build_workflow(self):
        """构建文档生成工作流"""
        
        # 1. 大纲生成阶段
        with pipeline() as outline_generator:
            outline_generator.analyze = self._analyze_topic
            outline_generator.plan_structure = self._plan_structure
            outline_generator.create_outline = self._create_outline
        
        # 2. 章节并行生成阶段
        with parallel() as chapter_writer:
            # 使用 for_each 并行处理每个章节
            chapter_writer.write = self._write_chapter.for_each()
        
        # 3. 后处理阶段
        with pipeline() as post_processor:
            post_processor.polish = self._polish_content
            post_processor.add_refs = self._add_references
            post_processor.format = self._format_document
        
        # 组合完整工作流
        with pipeline() as self.workflow:
            self.workflow.outline = outline_generator
            self.workflow.write_chapters = chapter_writer
            self.workflow.post_process = post_processor
    
    def _analyze_topic(self, topic: str) -> Dict:
        """分析主题，确定文档方向"""
        prompt = f"""
        分析主题"{topic}"，确定：
        1. 目标读者群体
        2. 核心要点
        3. 需要的章节数量（约{self.total_words // 1000}章）
        """
        analysis = llm(prompt)
        return {"topic": topic, "analysis": analysis}
    
    def _plan_structure(self, info: Dict) -> Dict:
        """规划文档结构"""
        prompt = f"""
        为"{info['topic']}"规划文档结构：
        - 总字数：{self.total_words}
        - 包含章节列表和每章字数分配
        - 每章需要涵盖的核心内容
        """
        structure = llm(prompt)
        info["structure"] = structure
        return info
    
    def _create_outline(self, info: Dict) -> List[Chapter]:
        """创建详细大纲"""
        prompt = f"""
        基于以下结构创建详细大纲：
        {info['structure']}
        
        为每个章节提供：
        1. 章节标题
        2. 详细大纲要点
        """
        outline_text = llm(prompt)
        
        # 解析大纲为 Chapter 对象
        chapters = self._parse_outline(outline_text)
        return chapters
    
    def _write_chapter(self, chapter: Chapter) -> Chapter:
        """撰写单个章节"""
        prompt = f"""
        撰写章节：{chapter.title}
        
        大纲：
        {chapter.outline}
        
        要求：
        - 内容详实，逻辑清晰
        - 包含具体例子和数据
        - 使用专业但易懂的语言
        """
        chapter.content = llm(prompt)
        return chapter
    
    def _polish_content(self, chapters: List[Chapter]) -> List[Chapter]:
        """润色内容，确保风格一致"""
        full_text = "\n\n".join([c.content for c in chapters])
        prompt = f"""
        润色以下文档，确保：
        1. 语言风格一致
        2. 逻辑连贯
        3. 无明显错误
        
        文档内容：
        {full_text[:3000]}...
        """
        # 润色处理...
        return chapters
    
    def _add_references(self, chapters: List[Chapter]) -> str:
        """添加参考文献"""
        full_text = "\n\n".join([
            f"# {c.title}\n\n{c.content}"
            for c in chapters
        ])
        references = "\n\n## 参考文献\n\n1. ...\n2. ..."
        return full_text + references
    
    def _format_document(self, text: str) -> str:
        """格式化文档"""
        # 添加标题页、目录等
        title_page = f"# {self.topic}\n\n"
        toc = self._generate_toc(text)
        return title_page + toc + "\n\n" + text
    
    def _parse_outline(self, outline_text: str) -> List[Chapter]:
        """解析大纲文本为 Chapter 对象"""
        # 实现大纲解析逻辑
        chapters = []
        # ...
        return chapters
    
    def _generate_toc(self, text: str) -> str:
        """生成目录"""
        return "## 目录\n\n..."
    
    def generate(self) -> str:
        """生成完整文档"""
        print(f"开始生成文档：{self.topic}")
        result = self.workflow(self.topic)
        print("文档生成完成！")
        return result


# 使用示例
if __name__ == "__main__":
    generator = DocumentGenerator(
        topic="人工智能在职业规划中的应用",
        total_words=5000
    )
    document = generator.generate()
    with open("output.md", "w", encoding="utf-8") as f:
        f.write(document)
```

### 示例 2：数据处理 ETL 工作流

```python
#!/usr/bin/env python3
"""
数据处理 ETL 工作流示例
数据提取 -> 转换 -> 加载
"""

from lazyllm import pipeline, parallel, deduplicate, join
from typing import Iterator, Dict, List
import json

class DataETLPipeline:
    """数据处理流水线"""
    
    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
        self._build_pipeline()
    
    def _build_pipeline(self):
        """构建 ETL 流水线"""
        
        # 提取阶段：并行从多个源提取
        with parallel() as extractor:
            extractor.source_a = self._extract_from_api_a
            extractor.source_b = self._extract_from_api_b
            extractor.source_c = self._extract_from_db
        
        # 转换阶段：数据清洗和增强
        with pipeline() as transformer:
            transformer.normalize = self._normalize_schema    # 统一 schema
            transformer.clean = self._clean_data              # 清洗数据
            transformer.enrich = self._enrich_data            # 数据增强
            transformer.validate = self._validate_data        # 验证数据
        
        # 批量处理：使用 for_each 处理大批量数据
        batch_processor = transformer.for_each(batch_size=self.batch_size)
        
        # 去重和合并
        with pipeline() as aggregator:
            aggregator.dedup = deduplicate(key=lambda x: x["id"])
            aggregator.join = join(separator="\n")
        
        # 加载阶段
        with pipeline() as loader:
            loader.format = self._format_output
            loader.save = self._save_to_storage
        
        # 组合完整流水线
        with pipeline() as self.etl:
            self.etl.extract = extractor
            self.etl.transform = batch_processor
            self.etl.aggregate = aggregator
            self.etl.load = loader
    
    def _extract_from_api_a(self, query: str) -> List[Dict]:
        """从 API A 提取数据"""
        # 模拟 API 调用
        return [{"id": 1, "name": "A1"}, {"id": 2, "name": "A2"}]
    
    def _extract_from_api_b(self, query: str) -> List[Dict]:
        """从 API B 提取数据"""
        return [{"id": 3, "name": "B1"}]
    
    def _extract_from_db(self, query: str) -> List[Dict]:
        """从数据库提取数据"""
        return [{"id": 4, "name": "C1"}]
    
    def _normalize_schema(self, data: Dict) -> Dict:
        """统一数据 schema"""
        return {
            "id": str(data.get("id", "")),
            "name": data.get("name", "").strip().lower(),
            "source": data.get("source", "unknown"),
            "timestamp": data.get("timestamp", ""),
        }
    
    def _clean_data(self, record: Dict) -> Dict:
        """清洗数据"""
        # 去除空值
        return {k: v for k, v in record.items() if v is not None and v != ""}
    
    def _enrich_data(self, record: Dict) -> Dict:
        """数据增强"""
        # 添加额外信息
        record["category"] = self._categorize(record["name"])
        return record
    
    def _categorize(self, name: str) -> str:
        """分类"""
        # 使用 LLM 或规则分类
        return "category_a"
    
    def _validate_data(self, record: Dict) -> Dict:
        """验证数据"""
        if not record.get("id"):
            raise ValueError("记录缺少 ID")
        return record
    
    def _format_output(self, data: List[Dict]) -> str:
        """格式化输出"""
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    def _save_to_storage(self, content: str) -> str:
        """保存到存储"""
        output_path = "output/data.json"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        return output_path
    
    def run(self, query: str) -> str:
        """运行 ETL 流程"""
        print(f"开始 ETL 流程，查询：{query}")
        result = self.etl(query)
        print(f"ETL 完成，结果保存至：{result}")
        return result


# 使用示例
if __name__ == "__main__":
    etl = DataETLPipeline(batch_size=50)
    result = etl.run("人工智能公司")
```

### 示例 3：Function Call Agent 工作流

```python
#!/usr/bin/env python3
"""
Function Call Agent 工作流示例
基于 ReAct 模式的工具调用 Agent
"""

from lazyllm import Agent, Tool, llm, pipeline
from typing import Any, Dict
import json

class ResearchAgent:
    """研究助手 Agent"""
    
    def __init__(self):
        self.tools = self._create_tools()
        self.agent = self._create_agent()
    
    def _create_tools(self) -> list:
        """创建工具集"""
        
        tools = [
            Tool(
                name="search",
                description="搜索互联网信息",
                parameters={
                    "query": "搜索关键词",
                    "limit": "返回结果数量（默认5）"
                },
                func=self._search_web
            ),
            Tool(
                name="calculator",
                description="执行数学计算",
                parameters={
                    "expression": "数学表达式，如 2+2"
                },
                func=self._calculate
            ),
            Tool(
                name="get_weather",
                description="获取城市天气",
                parameters={
                    "city": "城市名称",
                    "date": "日期（默认今天）"
                },
                func=self._get_weather
            ),
            Tool(
                name="summarize",
                description="总结长文本",
                parameters={
                    "text": "需要总结的文本",
                    "max_length": "最大长度"
                },
                func=self._summarize_text
            ),
        ]
        return tools
    
    def _search_web(self, query: str, limit: int = 5) -> str:
        """搜索网络"""
        # 实际实现：调用搜索引擎 API
        print(f"[Tool] 搜索：{query}")
        return f"搜索结果：关于 {query} 的信息..."
    
    def _calculate(self, expression: str) -> str:
        """计算"""
        try:
            result = eval(expression)
            return str(result)
        except:
            return "计算错误"
    
    def _get_weather(self, city: str, date: str = "today") -> str:
        """获取天气"""
        print(f"[Tool] 查询 {city} {date} 天气")
        return f"{city} {date} 天气：晴，25°C"
    
    def _summarize_text(self, text: str, max_length: int = 200) -> str:
        """总结文本"""
        prompt = f"总结以下内容（不超过{max_length}字）：\n\n{text[:1000]}"
        return llm(prompt)
    
    def _create_agent(self):
        """创建 ReAct Agent"""
        
        system_prompt = """
        你是一个研究助手，帮助用户收集和分析信息。
        
        使用以下格式思考：
        
        思考：分析用户需求，确定下一步行动
        行动：选择工具并执行（格式：工具名{"参数": "值"}）
        观察：记录工具返回的结果
        
        重复以上步骤直到完成任务，然后给出最终答案。
        
        可用工具：
        - search: 搜索互联网信息
        - calculator: 执行数学计算
        - get_weather: 获取城市天气
        - summarize: 总结长文本
        """
        
        return Agent(
            llm=llm,
            tools=self.tools,
            system_prompt=system_prompt,
            max_iterations=10,
            verbose=True
        )
    
    def research(self, topic: str) -> Dict[str, Any]:
        """研究主题"""
        print(f"\n开始研究：{topic}\n")
        
        # 使用工作流组织研究过程
        with pipeline() as research_flow:
            research_flow.search = self._search_phase
            research_flow.analyze = self._analysis_phase
            research_flow.summarize = self._summarization_phase
        
        result = research_flow(topic)
        return result
    
    def _search_phase(self, topic: str) -> Dict:
        """搜索阶段"""
        # 使用 Agent 进行多步搜索
        query = f"搜索 {topic} 的基本信息和最新进展"
        search_result = self.agent(query)
        return {"topic": topic, "search_result": search_result}
    
    def _analysis_phase(self, data: Dict) -> Dict:
        """分析阶段"""
        prompt = f"""
        分析以下关于"{data['topic']}"的信息：
        {data['search_result']}
        
        提取关键观点和数据。
        """
        analysis = llm(prompt)
        data["analysis"] = analysis
        return data
    
    def _summarization_phase(self, data: Dict) -> Dict:
        """总结阶段"""
        prompt = f"""
        基于以下分析，生成"{data['topic']}"的研究报告：
        
        分析内容：
        {data['analysis']}
        
        报告应包含：
        1. 核心发现
        2. 关键数据
        3. 结论和建议
        """
        report = llm(prompt)
        data["report"] = report
        return data


# 使用示例
if __name__ == "__main__":
    agent = ResearchAgent()
    result = agent.research("2024年人工智能发展趋势")
    
    print("\n=== 研究报告 ===\n")
    print(result["report"])
```

---

## 五、性能优化与调试

### 5.1 性能优化技巧

#### 并行度调优
```python
from lazyllm import parallel

# 控制并行度避免资源耗尽
with parallel(num_workers=4) as p:  # 限制4个并发
    p.task1 = task1
    p.task2 = task2

# 批量大小调优
processor = heavy_function.for_each(batch_size=50)  # 每批50条
```

#### 缓存策略
```python
from lazyllm import cache

@cache(ttl=3600)  # 缓存1小时
def expensive_operation(data):
    return llm(f"处理：{data}")

# 缓存命中直接返回，避免重复调用LLM
```

#### 异步执行
```python
from lazyllm import async_pipeline

# 异步pipeline提高吞吐量
with async_pipeline() as async_flow:
    async_flow.step1 = step1
    async_flow.step2 = step2

# 非阻塞执行
result = await async_flow(data)
```

### 5.2 调试技巧

#### 可视化工作流
```python
from lazyllm import visualize

# 生成工作流图
with pipeline() as flow:
    flow.a = step_a
    flow.b = step_b
    flow.c = step_c

visualize(flow, "workflow.png")  # 导出流程图
```

#### 分步调试
```python
from lazyllm import debug

# 开启调试模式
debug.enable()

# 单步执行
with pipeline(debug=True) as p:
    p.step1 = step1
    p.step2 = step2

# 查看中间结果
result = p.run_step("step1", data)  # 只运行第一步
```

#### 性能分析
```python
from lazyllm import profiler

# 性能分析
with profiler() as prof:
    with pipeline() as p:
        p.task1 = task1
        p.task2 = task2
    result = p(data)

# 查看耗时报告
prof.report()  # 显示每个节点的执行时间
```

### 5.3 日志记录

```python
from lazyllm import LOG, set_log_level

# 设置日志级别
set_log_level("DEBUG")  # DEBUG/INFO/WARNING/ERROR

# 在节点中使用
with pipeline() as p:
    p.process = lambda x: LOG.info(f"处理数据：{x}") or process(x)
```

---

## 六、最佳实践检查清单

### 设计阶段
- [ ] 明确定义每个节点的输入输出类型
- [ ] 确定工作流是静态还是动态
- [ ] 识别可以并行执行的节点
- [ ] 设计错误处理策略

### 实现阶段
- [ ] 使用类型注解
- [ ] 添加适当的日志记录
- [ ] 实现错误重试机制
- [ ] 使用 `for_each` 处理批量数据

### 测试阶段
- [ ] 单元测试每个节点
- [ ] 集成测试完整工作流
- [ ] 边界情况测试（空输入、大数据量）
- [ ] 性能测试

### 部署阶段
- [ ] 监控工作流执行时间
- [ ] 设置告警机制
- [ ] 记录执行日志
- [ ] 定期优化瓶颈节点

---

## 六、常见错误与解决方案

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| `TypeError` | 类型不匹配 | 添加类型检查和转换 |
| `KeyError` | 缺少字段 | 使用 `.get()` 提供默认值 |
| 内存溢出 | 数据量过大 | 使用流式处理或分批处理 |
| 超时 | 节点执行太慢 | 添加超时控制或异步处理 |
| 结果不一致 | 并行竞争条件 | 使用锁或顺序执行 |

---

## 七、参考资源

### 官方资源

| 资源 | 链接 | 说明 |
|------|------|------|
| **官方文档** | [docs.lazyllm.ai](https://docs.lazyllm.ai/) | 完整文档，包含所有API和教程 |
| **GitHub仓库** | [github.com/LazyAGI/LazyLLM](https://github.com/LazyAGI/LazyLLM) | 源码、Issue、Release |
| **学习指南** | [Learn/learn](https://docs.lazyllm.ai/zh-cn/latest/Learn/learn/) | 基础概念和快速入门 |
| **最佳实践** | [Best Practice](https://docs.lazyllm.ai/zh-cn/latest/Best%20Practice/) | 官方推荐的设计模式 |
| **使用案例** | [Cookbook](https://docs.lazyllm.ai/zh-cn/latest/Cookbook/) | 场景化解决方案 |
| **API文档** | [API Reference](https://docs.lazyllm.ai/zh-cn/latest/API%20Reference/) | 完整API参考 |

### 专题深入

| 主题 | 链接 |
|------|------|
| 长文档生成 | [great_writer](https://docs.lazyllm.ai/zh-cn/latest/Cookbook/great_writer/) |
| Function Call | [functionCall](https://docs.lazyllm.ai/zh-cn/latest/Best%20Practice/functionCall/) |
| 数据处理 | [data_process](https://docs.lazyllm.ai/zh-cn/latest/Best%20Practice/data_process/) |
| 流程编排 | [flow](https://docs.lazyllm.ai/zh-cn/latest/Best%20Practice/flow/) |

### 社区资源

- [Prompt Engineering Guide](https://www.promptingguide.ai/)
- [LangChain 工作流模式](https://python.langchain.com/docs/expression_language/)
- [Hugging Face 模型库](https://huggingface.co/models)

### 示例代码

- [./scrpts/02baseRAG.py](./scrpts/02baseRAG.py) - 基础RAG实现
- [./scrpts/03pipline.py](./scrpts/03pipline.py) - Pipeline示例

---

*最后更新：2026-02-08*  
*版本：v1.1*  
*基于 LazyLLM 最新文档整理*
