---
name: git-workflow
description: Git 版本控制操作指南。包含常用 Git 命令、提交规范、分支管理和协作流程，适用于日常开发和版本管理。
---

# Git 工作流 Skill

## 概述

本 Skill 提供 Git 版本控制的标准操作流程，帮助开发者正确使用 Git 进行代码管理和团队协作。

## 常用操作

### 1. 查看状态

```powershell
# 查看工作区状态
git status

# 查看修改内容
git diff

# 查看已暂存的修改
git diff --staged
```

### 2. 添加和提交

```powershell
# 添加单个文件
git add <文件名>

# 添加所有修改
git add .

# 提交更改（简洁描述）
git commit -m "修复：报告模块路由404错误"

# 提交更改（详细描述）
git commit -m "修复：报告模块路由404错误" -m "- 调整路由顺序，静态路由先于动态路由定义
- 修复 /center/init 和 /generation/history 路由
- 确保 FastAPI 路由匹配正确"
```

### 3. 提交信息规范

**格式**：`<类型>: <简短描述>`

**类型说明**：
- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档更新
- `style`: 代码格式调整（不影响功能）
- `refactor`: 代码重构
- `test`: 添加测试
- `chore`: 构建/工具变动

**示例**：
```
feat: 添加用户报告生成模块

fix: 修复数据库连接超时问题
docs: 更新 API 接口文档
refactor: 优化查询性能
```

### 4. 分支操作

```powershell
# 查看分支列表
git branch

# 查看远程分支
git branch -r

# 创建新分支
git branch <分支名>

# 切换分支
git checkout <分支名>

# 创建并切换分支
git checkout -b <分支名>

# 合并分支（先切换到目标分支）
git checkout master
git merge <要合并的分支>

# 删除本地分支
git branch -d <分支名>

# 强制删除分支（未合并）
git branch -D <分支名>
```

### 5. 远程操作

```powershell
# 查看远程仓库
git remote -v

# 拉取最新代码
git pull

# 推送代码
git push

# 推送本地分支到远程
git push -u origin <分支名>

# 获取远程更新（不合并）
git fetch
```

### 6. 撤销操作

```powershell
# 撤销工作区修改（未暂存）
git checkout -- <文件名>

# 撤销暂存（保留修改）
git reset HEAD <文件名>

# 撤销最近一次提交（保留修改）
git reset --soft HEAD~1

# 撤销最近一次提交（丢弃修改）
git reset --hard HEAD~1

# 查看操作历史
git reflog
```

### 7. 查看历史

```powershell
# 简洁历史
git log --oneline

# 图形化历史
git log --oneline --graph --all

# 查看最近 N 条
git log --oneline -10

# 查看某文件的修改历史
git log -p <文件名>
```

### 8. 备份和恢复

```powershell
# 暂存当前修改（未提交）
git stash

# 查看暂存列表
git stash list

# 恢复最近一次暂存
git stash pop

# 创建备份分支
git branch backup-<日期>
```

## 工作流推荐

### 个人开发流程

```powershell
# 1. 检查状态
git status

# 2. 添加修改
git add .

# 3. 提交更改
git commit -m "fix: 修复xxx问题"

# 4. 推送代码
git push
```

### 修复线上问题流程

```powershell
# 1. 创建修复分支
git checkout -b hotfix/修复问题

# 2. 修复代码...

# 3. 提交修复
git add .
git commit -m "fix: 紧急修复xxx问题"

# 4. 推送分支
git push -u origin hotfix/修复问题

# 5. 合并到主分支（通过 PR 或手动）
git checkout master
git merge hotfix/修复问题
git push
```

## 注意事项

1. **提交前检查**：使用 `git status` 和 `git diff` 确认修改内容
2. **提交信息清晰**：描述清楚修改内容，方便后续追溯
3. **定期推送**：避免本地积累过多未推送的提交
4. **重要操作备份**：大改动前先创建备份分支
5. **敏感信息**：切勿提交密码、API Key 等敏感信息

## 常见问题

### 问题1：提交后发现有文件漏了
```powershell
# 添加遗漏文件
git add 遗漏的文件
git commit --amend --no-edit
```

### 问题2：提交信息写错了
```powershell
# 修改最近一次提交信息
git commit --amend -m "正确的提交信息"
```

### 问题3：误删文件
```powershell
# 从 Git 恢复删除的文件
git checkout HEAD -- <文件名>
```

### 问题4：忽略文件不生效
```powershell
# 清除缓存后重新添加
git rm -r --cached .
git add .
git commit -m "fix: 更新 .gitignore 配置"
```

## 相关文件

- `.gitignore` - Git 忽略文件配置
- `.git/config` - 本地仓库配置
- `~/.gitconfig` - 全局 Git 配置
