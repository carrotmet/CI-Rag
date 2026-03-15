# Windows SQLite CLI 操作指南

> 在 Windows PowerShell/CMD 环境下操作 SQLite 数据库的避坑指南

---

## 问题背景

Windows 命令行环境与 Linux/macOS 有显著差异，直接在 PowerShell 中执行 SQLite 命令或内联 Python 代码时，经常遇到以下问题：

1. **引号转义问题** - 单引号、双引号在 PowerShell 中有特殊含义
2. **Unicode 编码问题** - 中文输出显示为乱码或导致命令失败
3. **命令连接符问题** - `&&` 在 PowerShell 中不是有效的命令分隔符
4. **路径分隔符问题** - Windows 使用反斜杠 `\`，需要转义或改用正斜杠
5. **多行字符串问题** - Python 代码在命令行中难以维护缩进

---

## 推荐的解决方案

### 方案一：使用 Python 脚本文件（推荐）

不要直接在命令行中写 Python 代码，而是创建 `.py` 文件：

```python
#!/usr/bin/env python3
import sqlite3
import os

# 使用绝对路径或相对项目根目录的路径
db_path = os.path.join(os.path.dirname(__file__), 'data', 'career_guidance.db')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 你的查询代码
cursor.execute("SELECT * FROM user_profiles WHERE user_id = ?", ('user_id_here',))
rows = cursor.fetchall()

for row in rows:
    print(row)

conn.close()
```

执行：
```powershell
cd D:\github.com\carrotmet\zyplusv2
python check_db.py
```

### 方案二：使用 SQLite 命令行工具

如果只需要简单查询，使用官方 `sqlite3.exe` 工具：

```powershell
# 进入交互式 shell
sqlite3 data\career_guidance.db

# 或者在单行模式下执行
sqlite3 data\career_guidance.db ".tables"
sqlite3 data\career_guidance.db "SELECT * FROM user_profiles;"
sqlite3 data\career_guidance.db ".schema user_profiles"
```

### 方案三：在 WSL (Windows Subsystem for Linux) 中操作

如果有 WSL 环境，可以直接使用 Linux 命令：

```bash
cd /mnt/d/github.com/carrotmet/zyplusv2
sqlite3 data/career_guidance.db "SELECT * FROM user_profiles;"
```

---

## 从数据库错误诊断代码问题

### 典型案例：函数接口不匹配错误

**问题场景：**
- 用户生成报告时失败
- 数据库记录显示错误：`update_generation_task() got an unexpected keyword argument 'total_chapters'`
- 查看 `generation_tasks` 表发现 `error_message` 字段包含 Python 异常信息

**诊断过程：**

```powershell
# 1. 查看最近的失败任务
sqlite3 data\career_guidance.db "SELECT id, status, error_code, error_message FROM generation_tasks WHERE status='failed' ORDER BY created_at DESC LIMIT 3;"

# 输出：
# task_xxx|failed|GENERATION_ERROR|update_generation_task() got an unexpected keyword argument 'total_chapters'
```

**根因分析：**

这是典型的 **"调用方-被调用方接口不匹配"** 错误：

1. 调用方代码（`report_generation_service.py`）添加新参数：
   ```python
   update_generation_task(db, task_id, total_chapters=len(chapter_ids))  # 新增参数
   ```

2. 被调用函数（`crud_user_report.py`）签名未更新：
   ```python
   def update_generation_task(..., completed_chapters=None,  # 缺少 total_chapters 参数
                              error_code=None, ...)
   ```

**修复方案：**

```python
# 1. 更新函数签名，添加缺失的参数
def update_generation_task(
    db: Session,
    task_id: str,
    ...,
    completed_chapters: Optional[int] = None,
    total_chapters: Optional[int] = None,  # 新增参数
    error_code: Optional[str] = None,
    ...
)

# 2. 在函数体内添加参数处理逻辑
if total_chapters is not None:
    db_task.total_chapters = total_chapters
```

**预防措施：**

| 检查点 | 说明 |
|-------|------|
| 函数签名一致性 | 修改调用方时，必须同步检查被调用函数是否支持新参数 |
| 使用 IDE 重构功能 | 使用 PyCharm/VSCode 的 "Change Signature" 重构功能自动同步修改 |
| 代码审查清单 | 修改函数接口时，检查所有调用点是否同步更新 |
| 单元测试覆盖 | 确保修改后运行相关测试，捕获接口不匹配错误 |

**黄金法则：**
> **修改函数接口时，必须同时更新函数定义和所有调用点**。如果只改调用方不改定义，就会出现 `unexpected keyword argument` 错误；如果只改定义不改调用方，就会出现 `missing required argument` 错误。

---

## 常见问题速查

### 1. PowerShell 中的引号问题

**错误示例：**
```powershell
python -c "print('Hello')"  # 可能失败
```

**正确做法：**
```powershell
python -c 'print("Hello")'  # 外层单引号，内层双引号
# 或者
python -c "print(`"Hello`")"  # 使用反引号转义
```

### 2. Unicode/中文乱码问题

**问题表现：**
- 命令执行时报 `UnicodeEncodeError`
- 查询结果显示为 `����` 乱码

**解决方案：**
```powershell
# 在 Python 脚本开头添加
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 或者在 PowerShell 中设置编码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

### 3. 命令分隔符问题

**错误示例：**
```powershell
cd path && python script.py  # && 在 PowerShell 中可能不工作
```

**正确做法：**
```powershell
cd path ; python script.py   # 使用分号
# 或者分两步执行
cd path
python script.py
```

### 4. 路径分隔符

**错误示例：**
```powershell
python -c "open('data\file.txt')"  # \ 被当作转义字符
```

**正确做法：**
```powershell
python -c "open('data/file.txt')"   # 使用正斜杠
python -c "open(r'data\file.txt')"  # 使用原始字符串 r''
python -c "open('data\\file.txt')"  # 双反斜杠转义
```

---

## 常用 Python 脚本模板

### 模板 1：快速查看表结构

```python
#!/usr/bin/env python3
import sqlite3
import os

db_path = 'data/career_guidance.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print(f'=== Database: {db_path} ===\n')

# 列出所有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

for (table_name,) in tables:
    print(f'\n--- Table: {table_name} ---')
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    for col in columns:
        print(f'  {col[1]} ({col[2]})')

conn.close()
```

### 模板 2：查询特定用户数据

```python
#!/usr/bin/env python3
import sqlite3
import sys

db_path = 'data/career_guidance.db'
user_id = sys.argv[1] if len(sys.argv) > 1 else 'test_user_123'

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute('SELECT * FROM user_profiles WHERE user_id = ?', (user_id,))
row = cursor.fetchone()

if row:
    columns = [d[0] for d in cursor.description]
    for col, val in zip(columns, row):
        print(f'{col}: {val}')
else:
    print(f'User {user_id} not found')

conn.close()
```

执行：
```powershell
python check_user.py user_Z03wP07SwhPaOVyb9SRf_g
```

### 模板 3：查看最近的更新日志

```python
#!/usr/bin/env python3
import sqlite3
from datetime import datetime

db_path = 'data/career_guidance.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute('''
    SELECT user_id, field_name, old_value, new_value, timestamp, update_type
    FROM user_profile_logs 
    ORDER BY timestamp DESC 
    LIMIT 20
''')

print(f'{"Time":<20} {"User":<30} {"Field":<20} {"Type":<15} Change')
print('-' * 100)

for row in cursor.fetchall():
    time_str = row[4][:19] if row[4] else ''
    user = row[0][:28] if row[0] else ''
    field = row[1][:18] if row[1] else ''
    type_ = row[5][:13] if row[5] else ''
    change = f'{row[2]} -> {row[3]}'
    print(f'{time_str:<20} {user:<30} {field:<20} {type_:<15} {change}')

conn.close()
```

---

## PowerShell 实用技巧

### 设置别名快速访问

在 PowerShell 配置文件中添加：

```powershell
# 打开配置文件
notepad $PROFILE

# 添加以下内容
function Check-DB {
    cd D:\github.com\carrotmet\zyplusv2
    python check_db.py
}

function SQLite-Query($query) {
    sqlite3 D:\github.com\carrotmet\zyplusv2\data\career_guidance.db $query
}

Set-Alias -Name cdb -Value Check-DB
Set-Alias -Name sq -Value SQLite-Query
```

使用：
```powershell
cdb                    # 运行 check_db.py
sq ".tables"           # 列出所有表
sq "SELECT * FROM user_profiles;"
```

### 查看数据库文件信息

```powershell
# 文件大小
(Get-Item data\career_guidance.db).Length / 1KB

# 最后修改时间
(Get-Item data\career_guidance.db).LastWriteTime

# 完整路径
Resolve-Path data\career_guidance.db
```

---

## 最佳实践总结

| 场景 | 推荐方案 | 避免使用 |
|------|---------|---------|
| 复杂查询 | Python 脚本文件 | 命令行内联 Python |
| 简单查询 | sqlite3.exe 命令行 | PowerShell 直接操作 |
| 中文数据处理 | Python 脚本 + UTF-8 编码 | 命令行直接输出 |
| 多表关联查询 | Python 脚本 | 单行 SQL |
| 批量更新 | Python 脚本 + 参数化查询 | 字符串拼接 SQL |

### 黄金法则

1. **永远优先使用 Python 脚本文件**，而不是命令行内联代码
2. **使用参数化查询** (`?` 占位符)，永远不要拼接 SQL 字符串
3. **使用上下文管理器** (`with` 语句) 确保连接关闭
4. **使用正斜杠 `/`** 作为路径分隔符，避免转义问题
5. **将常用查询保存为 `.py` 或 `.sql` 文件**，方便重复使用
6. **修改函数接口时必须同步更新所有调用点**，避免 `unexpected keyword argument` 错误
7. **数据库错误日志是诊断代码问题的重要线索**，不要忽略 `error_message` 字段的内容

---

## 相关工具

- [DB Browser for SQLite](https://sqlitebrowser.org/) - 图形化管理工具
- [SQLite Studio](https://sqlitestudio.pl/) - 跨平台 SQLite 管理工具
- [DBeaver](https://dbeaver.io/) - 通用数据库管理工具，支持 SQLite
