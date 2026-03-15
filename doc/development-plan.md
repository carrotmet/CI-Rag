# CI-RAG-ROUTER 开发计划文档

## 项目概述

**项目名称**: CI-RAG-ROUTER (Confidence-Informed RAG Router)  
**项目目标**: 构建一个三层渐进式升级的查询路由系统，实现成本-精度-延迟的帕累托最优  
**核心原则**: "绝不前置LLM" - 将昂贵的LLM调用限制在真正需要的查询上

---

## 架构概览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CI-RAG-ROUTER 架构                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Query Input                                                           │
│       │                                                                 │
│       ▼                                                                 │
│   ┌─────────────┐     σ < 0.7      ┌─────────────┐     σ < 0.7         │
│   │  Level 0    │ ───────────────▶ │  Level 1    │ ───────────────▶    │
│   │  XGBoost    │                  │  Hybrid     │                     │
│   │  < 1ms      │     σ ≥ 0.7      │  Retrieval  │     σ ≥ 0.7         │
│   └─────────────┘ ───────────────▶ └─────────────┘ ───────────────▶    │
│          │              Hard Route        │             Hard Route      │
│          ▼                                ▼                             │
│   ┌─────────────┐                  ┌─────────────┐                     │
│   │   ABCD      │                  │   ABCD      │                     │
│   │   Zones     │                  │   Zones     │                     │
│   └─────────────┘                  └─────────────┘                     │
│                                                                         │
│   Level 0: 60% 查询    Level 1: 30% 查询    Level 2: 10% 查询          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 开发阶段

### 第一阶段: 基础架构搭建 (Week 1-2)

#### 1.1 项目结构初始化
- [ ] 创建核心包结构 `ci_architecture/`
- [ ] 配置管理模块 `config.py` (Pydantic模型)
- [ ] 主协调器 `orchestrator.py` - 流水线编排
- [ ] 监控指标模块 `metrics.py`

** deliverables **:
```
ci_architecture/
├── __init__.py
├── config.py
├── orchestrator.py
├── metrics.py
├── level0/
├── level1/
├── level2/
├── routing/
└── fallback/
```

#### 1.2 依赖管理与环境配置
- [ ] `requirements.txt` 定义核心依赖
- [ ] `pyproject.toml` 项目配置
- [ ] Docker 开发环境配置
- [ ] 环境变量模板 `.env.example`

**关键依赖**:
```
xgboost>=2.0.0
sentence-transformers>=2.2.0
faiss-cpu>=1.7.0
jieba>=0.42.1
litellm>=1.0.0
scikit-learn>=1.3.0
numpy>=1.24.0
pydantic>=2.0.0
```

---

### 第二阶段: Level 0 实现 (Week 2-3)

#### 2.1 冷启动策略设计

**核心原则**: XGBoost 模型未训练前不开放 XGBoost 进行 Level 0 决策

```
Level 0 架构: 启发式规则 + XGBoost 并行

┌─────────────────────────────────────────────┐
│              Level 0 Router                 │
│  ┌─────────────────────────────────────┐   │
│  │      Model State Detection          │   │
│  │  (检查模型文件是否存在且可加载)      │   │
│  └─────────────────────────────────────┘   │
│                    │                        │
│         ┌─────────┴─────────┐              │
│         ▼                   ▼              │
│    [模型不存在]         [模型存在]          │
│         │                   │              │
│         ▼                   ▼              │
│   Heuristic Only      XGBoost + Heuristic  │
│   (强制升级L1)        (并行运行)            │
│         │                   │              │
│         └─────────┬─────────┘              │
│                   ▼                        │
│              Decision Logic                │
│        (优先XGBoost，规则兜底)             │
└─────────────────────────────────────────────┘
```

#### 2.2 特征工程模块 `level0/features.py`
- [ ] 12维特征提取实现
  - [ ] 长度特征: `len_char`, `len_word`
  - [ ] 熵特征: `char_entropy`, `word_entropy`
  - [ ] 领域代理: `domain_switch_cnt` (~50领域词表)
  - [ ] 句法标记: `has_question`, `digit_ratio`
  - [ ] 历史上下文: `user_historical_freq`

**性能目标**: <0.5ms 特征提取

#### 2.3 启发式规则路由器 `level0/heuristic_router.py`
- [ ] 基于特征的硬编码规则实现
  - [ ] C判断: 领域切换≥2 或 词数>50 → C=1 (高复杂度)
  - [ ] I判断: 疑问句+数字比例>0.3 → I=1 (信息较充分)
- [ ] 领域词表定义 (~50个领域)
- [ ] 规则版本管理 (便于迭代优化)

**冷启动行为**: 
- 所有查询 sigma 强制设为 0.5 (低于阈值 0.7)
- 100% 升级到 Level 1 收集训练数据

#### 2.4 XGBoost分类器 `level0/classifier.py`
- [ ] Model C (复杂度分类器) 训练管道
- [ ] Model I (信息充分性分类器) 训练管道
- [ ] 校准集成 `CalibratedClassifierCV`
- [ ] 模型序列化/加载
- [ ] 模型有效性检测 (防止加载空/损坏模型)

**性能目标**: <1ms 端到端推理

#### 2.5 统一路由器 `level0/router.py`
- [ ] 模型状态检测逻辑
  - [ ] 文件存在性检查
  - [ ] 模型可加载性验证
  - [ ] 模型非空性检查 (get_dump() 长度)
- [ ] 双模式路由逻辑
  - [ ] `COLD_START` 模式: 仅启发式，强制升级
  - [ ] `TRAINED` 模式: XGBoost + 启发式并行
- [ ] 保守联合置信度计算 `sigma_joint = min(sigma_c, sigma_i)`
- [ ] 逃逸决策逻辑
- [ ] ABCD硬路由映射

**渐进式启用策略**:

| 阶段 | 时间 | 模式 | 升级率 | 说明 |
|------|------|------|--------|------|
| **Week 1** | Day 1-7 | COLD_START | ~80% | 模型未训练，100%启发式 |
| **Week 2** | Day 8-14 | INITIAL | ~60% | 初始模型，保守阈值 α=0.6 |
| **Week 3** | Day 15-21 | CALIBRATION | ~40% | 校准优化，α=0.7 |
| **Month 2+** | Day 22+ | PRODUCTION | ~30% | 成熟模型，规则兜底 |

---

### 第三阶段: Level 1 实现 (Week 3-5)

#### 3.1 向量检索器 `level1/vector_retriever.py`
- [ ] sentence-transformers 集成
  - [ ] 模型: `paraphrase-multilingual-MiniLM-L12-v2`
  - [ ] 384维嵌入生成
- [ ] FAISS 索引管理
  - [ ] `IndexFlatIP` (<100K)
  - [ ] `IndexIVFFlat` (100K-10M)
  - [ ] 索引持久化/加载
- [ ] 检索指标计算: `sim_max`, `gap`, `entropy`

**性能目标**: 15-25ms 检索延迟

#### 3.2 关键词检索器 `level1/keyword_retriever.py`
- [ ] jieba 分词集成
  - [ ] 搜索引擎模式索引
  - [ ] 精确模式查询
  - [ ] 自定义词典支持
- [ ] 倒排索引实现
  - [ ] 位置信息存储
  - [ ] TF-IDF/BM25打分
- [ ] 布尔查询与短语查询

**性能目标**: 5-10ms 检索延迟

#### 3.3 结构化检索器 `level1/structured_retriever.py`
- [ ] 意图识别模块
  - [ ] 模式匹配 (正则规则)
  - [ ] 实体提取
  - [ ] Schema验证
- [ ] SQL查询生成器
- [ ] 知识图谱遍历器 (可选)
- [ ] 返回指标: schema匹配率, 行数, 空值率

**性能目标**: 10-30ms 查询延迟

#### 3.4 置信度融合 `level1/fusion.py`
- [ ] Isotonic Regression 校准
- [ ] 加权贝叶斯融合
  - [ ] Vector: 0.4, Structured: 0.5, Keyword: 0.1
- [ ] 冲突检测与惩罚

#### 3.5 C校准器 `level1/c_calibrator.py`
- [ ] 历史复杂度检索
- [ ] 有界调整 `delta ∈ [-0.2, +0.2]`
- [ ] 冲突触发降级

---

### 第四阶段: Level 2 实现 (Week 5-6)

#### 4.1 LLM客户端 `level2/llm_client.py`
- [ ] litellm 集成
  - [ ] 统一API封装
  - [ ] 自动降级链
  - [ ] 成本跟踪
- [ ] 异步支持 (双探针)

#### 4.2 提示构建器 `level2/prompt_builder.py`
- [ ] 上下文组装 (Level 0/1 结果 + 检索证据)
- [ ] 强制JSON输出指令
- [ ] 字段定义: C, I, confidence, missing_info, reasoning

#### 4.3 响应解析器 `level2/response_parser.py`
- [ ] JSON提取 (直接解析 + 正则回退)
- [ ] 字段验证
- [ ] 范围检查 [0,1]

#### 4.4 双探针验证 `level2/dual_probe.py`
- [ ] 多探针执行
- [ ] Jaccard相似度计算
- [ ] 一致性阈值 0.8
- [ ] 置信度调整

---

### 第五阶段: 路由与回退 (Week 6-7)

#### 5.1 ABCD路由映射 `routing/abcd_mapper.py`
- [ ] 离散区分类
- [ ] 软路由混合 (边界混合)
- [ ] 置信度加权资源分配

#### 5.2 执行规划器 `routing/execution_planner.py`
- [ ] 区内策略选择
- [ ] Token预算分配
- [ ] 延迟约束管理

#### 5.3 回退策略 `fallback/`
- [ ] 保守默认 (Zone B强制)
- [ ] 查询拒绝 (含改进建议)
- [ ] 人工介入协议 (HITL)

---

### 第六阶段: 监控与优化 (Week 7-8)

#### 6.1 在线监控 `metrics.py`
- [ ] 逃逸率金字塔跟踪
- [ ] ECE (期望校准误差) 计算
- [ ] C修正率监控
- [ ] 延迟分布统计

#### 6.2 持续优化管道
- [ ] Level 0: 特征重要性监控, 阈值调优
- [ ] Level 1: 周期性等渗回归重校准
- [ ] Level 2: 提示A/B测试

---

## 测试策略

### 单元测试
```
tests/
├── test_level0/
│   ├── test_features.py
│   └── test_classifier.py
├── test_level1/
│   ├── test_vector_retriever.py
│   └── test_fusion.py
└── test_level2/
    └── test_prompt_builder.py
```

### 集成测试
- [ ] 端到端流水线测试
- [ ] 各层级逃逸逻辑验证
- [ ] 性能基准测试 (<1ms, ~50ms, ~100ms)

### 校准验证
- [ ] 置信度-准确度相关性测试
- [ ] ECE < 0.05 目标验证
- [ ] 混淆矩阵分析

---

## 部署规划

### 阶段一: 开发环境
- [ ] 本地Python环境
- [ ] SQLite原型数据库
- [ ] 小型FAISS索引 (<10K)

### 阶段二: 测试环境
- [ ] Docker Compose 编排
- [ ] 向量数据库 (FAISS服务化)
- [ ] 监控面板 (基础指标)

### 阶段三: 生产环境
- [ ] Kubernetes 部署
- [ ] 水平扩展支持
- [ ] 完整监控告警

---

## 里程碑

| 里程碑 | 时间 | 关键交付物 | 成功标准 |
|--------|------|------------|----------|
| M1 | Week 2 | Level 0 原型 | <1ms延迟, 60%硬路由 |
| M2 | Week 4 | Level 1 完整 | ~50ms延迟, 30%逃逸率 |
| M3 | Week 6 | Level 2 + 路由 | ~100ms延迟, ECE<0.05 |
| M4 | Week 8 | 生产就绪 | 完整监控, 文档 |

---

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| XGBoost特征不足 | Level 0准确率低 | 预留特征扩展接口, 监控修正率 |
| FAISS索引规模大 | 延迟超标 | 支持IVF/PQ索引, 分片策略 |
| LLM API不稳定 | Level 2失败 | litellm自动降级, 超时控制 |
| 校准漂移 | 置信度不准 | 定期重校准, ECE监控 |

---

## 附录

### A. 核心配置参数

```yaml
ALPHA: 0.7                    # 统一逃逸阈值
LEVEL0_MODEL_C: "models/xgb_c.json"
LEVEL0_MODEL_I: "models/xgb_i.json"
VECTOR_MODEL: "paraphrase-multilingual-MiniLM-L12-v2"
FAISS_INDEX_PATH: "indexes/corpus.faiss"
LLM_MODEL: "gpt-4"
FUSION_WEIGHTS: [0.4, 0.5, 0.1]
```

### B. 参考文档

- `RAG-CI-ROUTER.md` - 详细实现手册
- `.agents/skills/ci-rag-router/SKILL.md` - 关键概念速查

---

*文档版本: 1.0*  
*最后更新: 2026-03-15*
