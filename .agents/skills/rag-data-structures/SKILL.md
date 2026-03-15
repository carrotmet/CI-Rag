# RAG 前后端数据结构与参数交接规范

## Metadata
- **Version**: 1.0
- **Last Updated**: 2026-02-11
- **Scope**: 职业规划导航平台 - RAG对话模块
- **Related Modules**: TypeChat预处理器, DSPy RAG服务, 用户画像API

## Description
本文档定义了职业规划RAG对话系统中，前端TypeChat预处理与后端DSPy服务之间的完整数据结构和参数交接规范。作为开发经验固定下来，用于指导后续功能拓展和系统维护。

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              前端层 (Frontend)                                │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │ TypeChat Preprocessor                                                │ │
│  │ - 快速意图检测 (本地关键词)                                            │ │
│  │ - 深度意图分析 (LLM调用)                                               │ │
│  │ - 实体提取与结构化                                                     │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ↓ POST /api/user-profiles/{id}/chat
                              {message, context, preprocessed}
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API层 (FastAPI)                                  │
│  - 接收前端请求                                                              │
│  - 传递参数给DSPy服务                                                         │
│  - 处理画像更新逻辑                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ↓ process_message(..., preprocessed)
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DSPy服务层 (Backend)                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐   │
│  │ Intent       │ │ Info         │ │ Prompt       │ │ Response         │   │
│  │ Classifier   │ │ Extractor    │ │ Generator    │ │ Optimizer        │   │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ↓
                              结构化响应结果
```

---

## 一、前端 TypeChat 预处理输出

### 1.1 主接口: PreprocessedInput

前端通过 `typechatProcessor.ts` 处理用户输入后，生成以下结构：

```typescript
interface PreprocessedInput {
    // 基础文本信息
    rawText: string;              // 用户原始输入
    cleanedText: string;          // 清洗后的文本（trim）
    
    // 意图分析结果
    intent: Intent;
    
    // 提取的实体信息
    entities: ExtractedEntities;
    
    // 对话上下文信息
    contextSummary: string;       // 对话上下文摘要
    
    // 处理建议
    suggestedApproach: string;    // 建议的处理方式
}
```

### 1.2 Intent 结构

```typescript
interface Intent {
    type: 'interest_explore' |    // 兴趣探索
          'ability_assess' |      // 能力评估
          'value_clarify' |       // 价值观澄清
          'career_advice' |       // 职业建议
          'path_planning' |       // 路径规划
          'casve_guidance' |      // CASVE决策指导
          'general_chat' |        // 一般对话
          'emotional_support';    // 情感支持
    
    confidence: number;           // 置信度 0-1
    subType?: string;             // 子类型（可选）
    contextSignals: string[];     // 上下文信号数组
    emotionalState: 'anxious' |   // 焦虑
                    'confident' | // 自信
                    'curious' |   // 好奇
                    'frustrated' |// 沮丧
                    'neutral';    // 中性
}
```

### 1.3 ExtractedEntities 结构

```typescript
interface ExtractedEntities {
    // 兴趣列表
    interests: Array<{
        domain: string;           // 领域（如'音乐'）
        specific: string;         // 具体描述（如'古典音乐'）
        sentiment: 'positive' | 'negative' | 'neutral';
        constraints?: string[];   // 相关约束
    }>;
    
    // 能力列表
    abilities: Array<{
        skill: string;            // 技能名称
        level: 'beginner' | 'intermediate' | 'advanced';
        evidence: string;         // 证据/例子
    }>;
    
    // 价值观关键词列表
    values: string[];             // 如['成就感', '稳定', '创新']
    
    // 约束条件列表
    constraints: Array<{
        type: 'time' | 'resource' | 'skill' | 'other';
        description: string;      // 约束描述
    }>;
}
```

### 1.4 使用示例

```typescript
// 前端发送请求
const requestBody = {
    message: "我对编程很感兴趣，但没太多时间学习",
    context: {
        history: [...],
        quick_intent: "interest_explore"
    },
    preprocessed: {
        rawText: "我对编程很感兴趣，但没太多时间学习",
        cleanedText: "我对编程很感兴趣，但没太多时间学习",
        intent: {
            type: "interest_explore",
            confidence: 0.85,
            subType: "tech_interest",
            contextSignals: ["首次提及", "表达兴趣"],
            emotionalState: "curious"
        },
        entities: {
            interests: [{
                domain: "编程",
                specific: "软件开发",
                sentiment: "positive",
                constraints: ["没时间练习"]
            }],
            abilities: [],
            values: [],
            constraints: [{
                type: "time",
                description: "缺乏学习时间"
            }]
        },
        contextSummary: "用户首次表达对编程的兴趣，但担心时间不足",
        suggestedApproach: "探索兴趣具体方向，提供时间管理的职业建议"
    }
};
```

---

## 二、后端 DSPy 服务输出

### 2.1 主服务返回: ChatMessageResponse

`dspy_rag_service.py` 的 `process_message` 方法返回：

```python
{
    # AI回复内容
    'reply': str,                          # AI的自然语言回复（已过滤reasoning_content）
    
    # 意图识别结果
    'intent': str,                         # 主意图类型
    'sub_intents': List[str],              # 子意图列表
    'confidence': float,                   # 意图判断置信度（0-1）
    'reasoning': str,                      # 意图判断的详细理由
    'emotional_state': str,                # 用户情感状态
    
    # 信息提取结果
    'extracted_info': List[Dict],          # 提取的结构化信息（API格式）
    'profile_updates': Dict,               # 建议更新的画像字段
    
    # 对话管理
    'conversation_stage': str,             # 对话阶段
    'suggested_questions': List[str],      # 建议的追问列表
    
    # 扩展字段（预留）
    'context_analysis': Dict,              # 上下文分析结果
    'optimization_notes': str              # 优化备注
}
```

### 2.2 意图分类模块输出

`IntentClassifier.forward()` 返回：

```python
{
    'intent_type': str,           # 意图类型（8种之一）
    'confidence': float,          # 置信度 0-1
    'reasoning': str,             # 判断理由（LLM生成）
    'sub_intents': List[str],     # 子意图列表
    'emotional_state': str        # 情感状态（5种之一）
}
```

### 2.3 信息提取模块输出

`StructuredInfoExtractor.forward()` 返回：

```python
{
    'interests': [                # 兴趣列表
        {
            'domain': str,        # 领域
            'specific': str,      # 具体描述
            'sentiment': str,     # 态度
            'constraints': List[str]
        }
    ],
    'abilities': [                # 能力列表
        {
            'skill': str,         # 技能名称
            'level': str,         # 水平
            'evidence': str       # 证据
        }
    ],
    'values': List[str],          # 价值观关键词
    'constraints': [              # 约束条件
        {
            'type': str,          # 类型
            'description': str    # 描述
        }
    ],
    'career_hints': {             # 职业偏好线索
        'preferred_industries': List[str],
        'preferred_roles': List[str],
        'avoided_things': List[str]
    },
    'profile_updates': {          # 建议更新的画像字段
        'holland_code': str,
        'mbti_type': str,
        'career_path_preference': str,
        # ... 其他可更新字段
    },
    'confidence': float           # 提取置信度
}
```

### 2.4 extracted_info API格式

`_convert_to_api_format()` 转换后的格式：

```python
[
    {
        'field': str,             # 字段名
        'value': Any,             # 字段值
        'confidence': float       # 置信度
    }
]

# 示例
[
    {
        'field': 'practice_experiences',
        'value': {'domain': '编程', 'specific': 'Web开发'},
        'confidence': 0.85
    },
    {
        'field': 'value_priorities',
        'value': ['成就感', '创新'],
        'confidence': 0.75
    },
    {
        'field': 'ability_assessment',
        'value': {'逻辑思维': 7, '创造力': 6},
        'confidence': 0.6
    }
]
```

---

## 三、前后端参数对照表

### 3.1 意图类型对照

| 前端 TypeChat | 后端 DSPy | 说明 |
|--------------|----------|------|
| `interest_explore` | `interest_explore` | 兴趣探索 |
| `ability_assess` | `ability_assess` | 能力评估 |
| `value_clarify` | `value_clarify` | 价值观澄清 |
| `career_advice` | `career_advice` | 职业建议 |
| `path_planning` | `path_planning` | 路径规划 |
| `casve_guidance` | `casve_guidance` | CASVE决策指导 |
| `general_chat` | `general_chat` | 一般对话 |
| `emotional_support` | `emotional_support` | 情感支持 |

### 3.2 实体字段对照

| 前端实体 | 前端结构 | 后端提取字段 | 后端存储字段 |
|---------|---------|-------------|-------------|
| interests | `domain`, `specific`, `sentiment` | `interests` | `practice_experiences` |
| abilities | `skill`, `level`, `evidence` | `abilities` | `ability_assessment` |
| values | `string[]` | `values` | `value_priorities` |
| constraints | `type`, `description` | `constraints` | `constraints` |

### 3.3 情感状态对照

| 前端 | 后端 | 显示 |
|-----|------|------|
| `anxious` | `anxious` | 焦虑 |
| `confident` | `confident` | 自信 |
| `curious` | `curious` | 好奇 |
| `frustrated` | `frustrated` | 沮丧 |
| `neutral` | `neutral` | 中性 |

---

## 四、API 请求/响应规范

### 4.1 请求体: ChatMessageRequest

```python
{
    'message': str,                    # 用户原始消息（必填）
    'context': {                       # 上下文信息（可选）
        'history': [                   # 对话历史
            {
                'role': 'user' | 'assistant',
                'content': str,
                'timestamp': str
            }
        ],
        'quick_intent': str            # 快速意图检测结果
    },
    'preprocessed': {                  # TypeChat预处理结果（可选）
        'rawText': str,
        'cleanedText': str,
        'intent': Intent,
        'entities': ExtractedEntities,
        'contextSummary': str,
        'suggestedApproach': str
    }
}
```

### 4.2 响应体: ChatMessageResponse

```python
{
    'reply': str,                      # AI回复内容
    'extracted_info': [                # 提取的信息
        {
            'field': str,
            'value': Any,
            'confidence': float
        }
    ],
    'updated_fields': List[str],       # 实际更新的字段名列表
    'suggested_questions': List[str],  # 建议追问
    'current_casve_stage': str,        # 当前CASVE阶段
    'profile_updates': {               # 更新后的画像状态
        'holland_code': str,
        'mbti_type': str,
        'value_priorities': List[str],
        'ability_assessment': Dict,
        'career_path_preference': str,
        'current_casve_stage': str,
        'universal_skills': Dict,
        'completeness_score': int
    }
}
```

---

## 五、数据流时序图

```
用户输入
    ↓
前端TypeChat预处理
    ├── 快速意图检测（本地关键词）
    └── 深度预处理（LLM调用）→ PreprocessedInput
    ↓
构建请求体
    {
        message: "...",
        context: {history, quick_intent},
        preprocessed: {...}     ← 前端预处理结果
    }
    ↓
POST /api/user-profiles/{id}/chat
    ↓
后端API接收
    ├── 获取用户画像
    ├── 调用DSPy服务
    │   └── process_message(preprocessed=...)
    │       ├── IntentClassifier → intent_result
    │       ├── StructuredInfoExtractor → extracted_info
    │       ├── ContextualPromptGenerator → prompt_config
    │       ├── LLM调用 → raw_response
    │       └── QuestionGenerator → suggested_questions
    │   └── 返回结构化结果
    ├── 更新画像（如果提取到有效字段）
    ├── 保存对话记录
    └── 构建响应
    ↓
返回ChatMessageResponse
    ↓
前端渲染
    ├── 显示reply（支持Markdown）
    ├── 显示suggested_questions
    ├── 更新UI画像显示
    └── 显示extracted_info通知
```

---

## 六、关键设计决策

### 6.1 为什么前端要做预处理？

| 优势 | 说明 |
|-----|------|
| 降低延迟 | 快速意图检测无需等待后端 |
| 减轻后端压力 | 简单的意图识别在前端完成 |
| 更好的用户体验 | 本地关键词匹配响应更快 |
| 数据丰富 | 为后端提供额外的结构化信息 |

### 6.2 为什么后端预处理参数没有被使用？

当前实现中，`preprocessed` 参数虽然传递到 `_dspy_process()`，但**没有被实际使用**。原因：

1. **向后兼容**：保持与旧版API兼容
2. **独立判断**：后端DSPy独立进行意图分类，确保准确性
3. **未来扩展**：预留接口，后续可实现意图融合（`IntentMerger`）

### 6.3 extracted_info 和 profile_updates 的关系

```
extracted_info: 从本次对话中提取的原始信息
        ↓
_convert_to_api_format(): 转换为API格式
        ↓
后端API过滤: 检查字段是否在UserProfileUpdate schema中
        ↓
profile_updates: 实际用于更新画像的字段
        ↓
数据库更新
```

### 6.4 reasoning_content 的处理

```
LLM原始响应
    └── {'text': '...', 'reasoning_content': '...'}
        ↓
_parse_llm_response()
    ├── 提取 text 字段 → 返回给用户
    └── 丢弃 reasoning_content（内部推理，不展示）
        ↓
如果需要存储，可扩展：
    ├── 存入日志
    ├── 存入 reasoning_log 表
    └── 用于调试分析
```

---

## 七、扩展指南

### 7.1 添加新的意图类型

1. **前端**：`careerChat.ts` 的 `IntentType`
2. **前端**：`typechatProcessor.ts` 的快速检测关键词
3. **后端**：`intent_signature.py` 的 `IntentClassification`
4. **后端**：`IntentClassifier` 的输出处理

### 7.2 添加新的实体提取字段

1. **前端**：`ExtractedEntities` 接口
2. **后端**：`extract_signature.py` 的 `StructuredInfoExtraction`
3. **后端**：`StructuredInfoExtractor` 的解析逻辑
4. **后端**：`_convert_to_api_format()` 转换方法
5. **后端**：`schemas_user_profile.py` 的 `UserProfileUpdate`

### 7.3 启用前端预处理结果

如需使用前端 `preprocessed` 数据：

```python
# 在 _dspy_process() 中添加
if preprocessed:
    # 融合前端意图
    frontend_intent = preprocessed.get('intent', {})
    intent_result = self.modules['intent_merger'](
        user_message=user_message,
        frontend_intent=frontend_intent,
        backend_intent=intent_result
    )
    
    # 补充实体提取
    frontend_entities = preprocessed.get('entities', {})
    extracted_info['frontend_interests'] = frontend_entities.get('interests', [])
```

---

## 八、数据结构变更日志

| 版本 | 日期 | 变更内容 |
|-----|------|---------|
| 1.0 | 2026-02-11 | 初始版本，整合TypeChat和DSPy数据结构 |

---

## 九、相关文件索引

| 路径 | 说明 |
|-----|------|
| `frontend/src/types/careerChat.ts` | TypeScript类型定义 |
| `frontend/src/services/typechatProcessor.ts` | 前端预处理逻辑 |
| `backend/app/schemas_user_profile.py` | Pydantic Schema |
| `backend/app/rag_dspy/dspy_rag_service.py` | DSPy主服务 |
| `backend/app/rag_dspy/modules/intent_classifier.py` | 意图分类 |
| `backend/app/rag_dspy/modules/info_extractor.py` | 信息提取 |
| `backend/app/rag_dspy/signatures/*.py` | DSPy签名定义 |
| `backend/app/api_user_profile.py` | API路由处理 |
