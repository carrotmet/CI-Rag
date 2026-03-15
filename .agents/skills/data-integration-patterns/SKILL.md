# 数据交接模式与陷阱 - 开发指南

> 本文档记录了职业规划导航平台在数据交接过程中的常见问题和最佳实践，用于指导新模块开发，避免数据格式不一致导致的错误。

---

## 1. 概述

在采用 Python/FastAPI + SQLite + Vanilla JS 技术栈的项目中，数据交接发生在以下关键环节：

```
┌─────────────┐     HTTP/JSON      ┌─────────────┐     ORM/SQL      ┌─────────────┐
│   Frontend  │ ←───────────────→ │   FastAPI   │ ←──────────────→ │   SQLite    │
│  (Vanilla   │   统一响应格式     │   Backend   │   模型转换       │   Database  │
│    JS)      │                   │   (Python)  │                  │             │
└─────────────┘                   └──────┬──────┘                  └─────────────┘
                                         │
                                         │ LLM API/JSON
                                         ↓
                                   ┌─────────────┐
                                   │  外部大模型  │
                                   │ (Kimi/GPT)  │
                                   └─────────────┘
```

---

## 2. 前后端 API 数据交接

### 2.1 问题：响应格式不统一

**现象**：
- 部分接口返回 `{code: 200, message: "...", data: {...}}`
- 部分接口直接返回 Pydantic 模型
- 前端无法正确判断请求是否成功

**示例 - 错误的返回方式**（直接返回模型）：
```python
@router.get("/center/init", response_model=ReportCenterInit)
async def get_report_center_init(...):
    return ReportCenterInit(...)  # ❌ 直接返回模型
```

**示例 - 正确的返回方式**（统一响应格式）：
```python
@router.get("/center/init")
async def get_report_center_init(...):
    result = ReportCenterInit(...)
    return {"code": 200, "message": "success", "data": result.model_dump()}  # ✅ 统一格式
```

### 2.2 问题：Pydantic 模型版本兼容性

**现象**：
- Pydantic v2 使用 `.model_dump()` 替代 v1 的 `.dict()`
- `from_attributes = True` 替代 `orm_mode = True`
- 混淆使用会导致序列化错误

**Pydantic v2 正确配置**：
```python
class UserReportResponse(BaseModel):
    id: str
    title: str
    # ...
    
    class Config:
        from_attributes = True  # ✅ Pydantic v2
```

### 2.3 问题：数据类型不一致

**现象**：
- 数据库使用 datetime 对象，前端期望 ISO 格式字符串
- Python 枚举类型直接返回会失败
- Optional 字段返回 None 时前端处理困难

**正确处理 datetime**：
```python
# ❌ 错误：直接返回 datetime 对象
return {"created_at": report.created_at}

# ✅ 正确：转换为 ISO 格式字符串
return {"created_at": report.created_at.isoformat() if report.created_at else None}
```

**正确处理枚举**：
```python
# ❌ 错误：直接返回枚举
return {"status": ReportStatus.COMPLETED}

# ✅ 正确：返回枚举值
return {"status": ReportStatus.COMPLETED.value}
```

### 2.4 问题：API 路径冲突

**现象**：
- 静态路由 `/center/init` 被动态路由 `/{report_id}` 拦截
- 404 错误但路径明明存在

**正确路由顺序**：
```python
# ✅ 静态路由必须在动态路由之前定义
@router.get("/center/init")  # 先定义
async def get_report_center_init(...):
    ...

@router.get("/{report_id}")  # 后定义
async def get_report(report_id: str, ...):
    ...
```

### 2.5 前端接收数据的陷阱

**现象**：
- 前端期望统一格式，但实际收到原始数据
- `response.code` 为 `undefined` 导致逻辑错误

**前端最佳实践**：
```javascript
// api-service.js 中的统一处理
async get(endpoint) {
    const response = await fetch(url);
    const result = await response.json();
    // 返回完整响应，包含 code, message, data
    return result;  // ✅ 返回 {code, message, data}
}

// 页面中使用
const response = await apiService.get('/user-reports/center/init');
if (response.code === 200) {  // 检查 code 字段
    centerData = response.data;  // 取 data 字段
}
```

---

## 3. 后端与数据库 ORM 数据交接

### 3.1 问题：JSON 字段序列化

**现象**：
- SQLAlchemy JSON 字段存储为字符串，读取时需要手动解析
- 写入时传入字符串而非对象，导致双层转义

**正确处理 JSON 字段**：
```python
# models.py - SQLAlchemy 模型
class UserProfile(Base):
    value_priorities = Column(JSON)  # 存储为 JSON

# crud.py - CRUD 操作
# ✅ 正确：直接传入 Python 对象，SQLAlchemy 自动处理
profile.value_priorities = ["成就感", "工作稳定"]

# ❌ 错误：手动 JSON 序列化
profile.value_priorities = json.dumps(["成就感", "工作稳定"])
```

### 3.2 问题：ORM 模型转字典

**现象**：
- 需要将 ORM 对象转换为字典返回，但关系字段导致循环引用
- 手动转换字段容易遗漏

**推荐方案**：
```python
# ✅ 方法1：使用 Pydantic 模型转换（推荐）
from pydantic import BaseModel

class UserProfileResponse(BaseModel):
    id: int
    user_id: str
    nickname: Optional[str]
    
    class Config:
        from_attributes = True  # 允许从 ORM 模型创建

# 使用
profile = db.query(UserProfile).first()
return UserProfileResponse.model_validate(profile).model_dump()

# ✅ 方法2：自定义转换函数
def profile_to_dict(profile):
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "nickname": profile.nickname,
        "created_at": profile.created_at.isoformat() if profile.created_at else None
    }
```

### 3.3 问题：数据库字段名与 Python 命名规范冲突

**现象**：
- 数据库使用 snake_case（如 `created_at`），Python 类属性也是 snake_case
- 前端期望 camelCase（如 `createdAt`）
- 命名不一致导致映射错误

**处理方案**：
```python
# schemas.py
class UserReportResponse(BaseModel):
    id: str
    title: str
    created_at: datetime  # Python 保持 snake_case
    
    class Config:
        from_attributes = True
        # 如果需要前端 camelCase，使用 alias
        # alias_generator = to_camel

# 前端处理（api-service.js）
_convertToCamelCase(obj) {
    // 转换 snake_case 为 camelCase
    const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}
```

### 3.4 问题：事务管理

**现象**：
- 多个数据库操作需要原子性，但未使用事务
- 部分操作成功，部分失败，数据不一致

**正确使用事务**：
```python
# ✅ 使用 SQLAlchemy 事务
def create_user_profile(db: Session, profile: UserProfileCreate):
    try:
        db_profile = UserProfile(**profile.model_dump())
        db.add(db_profile)
        db.commit()  # 提交事务
        db.refresh(db_profile)
        return db_profile
    except Exception as e:
        db.rollback()  # 回滚事务
        raise e
```

---

## 4. 后端与大模型 API 数据交接

### 4.1 问题：LLM 返回格式不稳定

**现象**：
- LLM 有时返回字符串，有时返回列表
- 响应解析失败导致整个流程崩溃

**健壮的处理方式**：
```python
# dspy_rag_service.py
def _call_llm_safe(self, prompt: str) -> str:
    try:
        llm_response = self.llm(prompt)
        
        # ✅ 处理多种返回类型
        if llm_response is None:
            return ''
        elif isinstance(llm_response, list) and len(llm_response) > 0:
            return str(llm_response[0])
        elif isinstance(llm_response, list):
            return ''
        else:
            return str(llm_response)
            
    except Exception as e:
        print(f"[LLM] Call failed: {e}")
        return ''
```

### 4.2 问题：提示词模板变量注入

**现象**：
- 用户输入直接拼接到提示词中，导致提示词注入攻击
- 特殊字符破坏 JSON 格式

**安全处理**：
```python
import json

def build_prompt(user_input: str, context: dict) -> str:
    # ✅ 使用 json.dumps 转义特殊字符
    safe_input = json.dumps(user_input, ensure_ascii=False)
    
    prompt = f"""
    用户输入: {safe_input}
    上下文: {json.dumps(context, ensure_ascii=False)}
    
    请分析用户意图...
    """
    return prompt
```

### 4.3 问题：大模型响应超时

**现象**：
- LLM 调用阻塞整个请求
- 超时后前端无法收到响应

**异步处理**：
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

async def process_with_llm(message: str) -> str:
    loop = asyncio.get_event_loop()
    # ✅ 在线程池中运行阻塞调用
    result = await loop.run_in_executor(
        executor,
        lambda: llm_client.chat(message)
    )
    return result
```

### 4.4 问题：Fallback 机制不完善

**现象**：
- LLM 服务不可用时整个功能不可用
- 没有降级方案

**完善的 Fallback**：
```python
def process_message(self, user_message: str, ...) -> Dict[str, Any]:
    try:
        if self.dspy_available:
            return self._dspy_process(user_message, ...)
        else:
            return self._fallback_process(user_message, ...)
    except Exception as e:
        print(f"[RAG] Error: {e}")
        # ✅ 始终返回有效响应
        return {
            "reply": "抱歉，服务暂时不可用，请稍后再试。",
            "extracted_info": [],
            "intent": "error",
            "suggested_questions": ["能再试一次吗？"],
            "confidence": 0.0
        }
```

---

## 5. 前端内部组件数据传递

### 5.1 问题：localStorage 存储非字符串

**现象**：
- 直接存储对象到 localStorage
- 读取后无法正确解析

**正确处理**：
```javascript
// ❌ 错误：直接存储对象
localStorage.setItem('profile', profile);

// ✅ 正确：序列化为 JSON
localStorage.setItem('profile', JSON.stringify(profile));

// 读取时
const profile = JSON.parse(localStorage.getItem('profile') || '{}');
```

### 5.2 问题：全局状态管理混乱

**现象**：
- 多个页面直接修改全局变量
- 状态不同步导致 UI 显示错误

**推荐方案**：
```javascript
// state.js - 集中状态管理
const AppState = {
    _state: {
        profile: null,
        isLoading: false
    },
    
    get(key) {
        return this._state[key];
    },
    
    set(key, value) {
        this._state[key] = value;
        this._notify(key, value);
    },
    
    _notify(key, value) {
        // 触发事件通知所有监听者
        window.dispatchEvent(new CustomEvent(`state:${key}`, {detail: value}));
    }
};
```

### 5.3 问题：异步数据获取时序

**现象**：
- 页面初始化时数据尚未加载完成
- 尝试访问 `undefined` 的属性导致错误

**防御性编程**：
```javascript
// ❌ 错误：直接访问可能 undefined 的属性
const name = state.profile.nickname;

// ✅ 正确：使用可选链和默认值
const name = state.profile?.nickname || '匿名用户';

// ✅ 正确：渲染时进行空值检查
function renderProfile() {
    if (!state.profile) {
        return '<div>加载中...</div>';
    }
    return `<div>${state.profile.nickname}</div>`;
}
```

---

## 6. 新模块开发检查清单

在开发新模块时，请逐项检查以下内容：

### API 层
- [ ] 所有接口返回统一格式 `{code, message, data}`
- [ ] Pydantic 模型使用 v2 语法（`model_dump`, `from_attributes`）
- [ ] 静态路由定义在动态路由之前
- [ ] datetime 字段转换为 ISO 格式字符串
- [ ] 枚举类型返回 `.value`
- [ ] 异常情况下也返回有效的 JSON 响应

### ORM 层
- [ ] JSON 字段直接存储 Python 对象，不手动序列化
- [ ] 使用 Pydantic 模型进行 ORM 对象转字典
- [ ] 多表操作使用事务（`db.commit()` / `db.rollback()`）
- [ ] 关系字段正确处理，避免 N+1 查询

### 大模型集成
- [ ] LLM 返回结果有多类型处理逻辑
- [ ] 提示词注入防护（使用 `json.dumps` 转义）
- [ ] 异步调用避免阻塞
- [ ] 完善的 Fallback 机制

### 前端
- [ ] localStorage 存储前 JSON 序列化
- [ ] API 响应检查 `code === 200`
- [ ] 从 `data` 字段提取实际数据
- [ ] 防御性编程处理 `undefined` 和 `null`

---

## 7. 常见错误速查表

| 错误现象 | 可能原因 | 解决方案 |
|---------|---------|---------|
| 页面卡在"加载中" | 后端返回格式不一致，`response.code` 为 `undefined` | 统一后端返回格式为 `{code, message, data}` |
| 404 但路径正确 | 动态路由在静态路由之前定义 | 调整路由顺序，静态路由优先 |
| JSON 解析错误 | 返回 datetime 对象或枚举类型 | 使用 `.isoformat()` 和 `.value` 转换 |
| 数据库字段为空 | JSON 字段手动转字符串存储 | 直接存储 Python 对象，让 SQLAlchemy 处理 |
| LLM 响应解析失败 | 返回格式不稳定（字符串/列表） | 添加多类型处理逻辑 |
| 前端显示 `undefined` | 数据未加载完成就渲染 | 添加空值检查和加载状态 |
| 状态不同步 | 多个地方直接修改全局变量 | 使用集中式状态管理 |

---

## 8. 最佳实践总结

1. **后端 API 返回格式**：始终返回 `{code: 200, message: "...", data: {...}}`

2. **Pydantic v2**：使用 `model_dump()` 替代 `dict()`，`from_attributes` 替代 `orm_mode`

3. **序列化**：使用 `.model_dump()` 和 `.model_validate()` 进行模型转换

4. **错误处理**：所有接口在异常情况下也返回有效的 JSON，不抛出未捕获的异常

5. **前端防御**：使用可选链 `?.` 和默认值 `||` 处理可能为空的数据

6. **测试验证**：新接口开发后，使用浏览器开发者工具验证返回格式是否符合预期

---

**最后更新**：2026-02-11

**维护者**：AI Assistant
