# 使用 uv 设置 CI-RAG-ROUTER 环境

`uv` 是一个快速的 Python 包管理器，可以创建干净的隔离环境，避免 Anaconda 的 DLL 冲突问题。

## 安装 uv

```powershell
# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 或手动下载
# https://github.com/astral-sh/uv/releases
```

## 创建项目环境

```bash
# 进入项目目录
cd D:\github.com\carrotmet\CI-Rag-Router

# 创建虚拟环境 (使用 Python 3.10 或 3.11)
uv venv --python 3.10

# 激活环境
.venv\Scripts\activate
```

## 安装依赖

### 方式 1: 基础功能 (Keyword + Structured)
```bash
# 安装轻量级依赖（不含 PyTorch）
uv pip install numpy scikit-learn pydantic pydantic-settings jieba
```

### 方式 2: 完整功能 (含 Vector 检索)
```bash
# 安装全部依赖（自动处理 PyTorch）
uv pip install -r requirements.txt
```

如果遇到 PyTorch 问题，手动安装 CPU 版本：
```bash
# 先卸载可能冲突的 torch
uv pip uninstall torch

# 安装 CPU-only 版本
uv pip install torch --index-url https://download.pytorch.org/whl/cpu

# 然后安装其他依赖
uv pip install sentence-transformers faiss-cpu
```

## 运行测试

```bash
# 确保在虚拟环境中
.venv\Scripts\activate

# 测试 Level 0
python examples/demo_level0.py

# 构建 Level 1 索引
python scripts/build_level1_index.py

# 测试 Level 1
python scripts/test_level1.py

# GUI 测试工具
python tools/ci_test_window.py
```

## 常用 uv 命令

```bash
# 查看已安装包
uv pip list

# 更新依赖
uv pip install --upgrade numpy

# 导出当前环境
uv pip freeze > requirements.lock

# 退出虚拟环境
deactivate

# 删除环境重新创建
rm -rf .venv
uv venv --python 3.10
```

## 为什么 uv 能解决 PyTorch 问题？

1. **完全隔离**: 与 Anaconda base 环境完全分离
2. **干净安装**: 没有历史包冲突或损坏的依赖
3. **快速解析**: 依赖解析更精确，避免版本冲突
4. **无 DLL 污染**: 不会加载 Anaconda 中可能损坏的 DLL

## 故障排除

### 如果仍有 DLL 错误
```bash
# 检查 torch 安装
python -c "import torch; print(torch.__version__)"

# 如果失败，可能是 VC++ 运行库问题
# 安装: https://aka.ms/vs/17/release/vc_redist.x64.exe
```

### 如果 sentence-transformers 下载慢
```bash
# 使用清华镜像
uv pip install sentence-transformers -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 如果 faiss-cpu 安装失败
```bash
# 使用 conda-forge 的 faiss (需要在 conda 环境中)
# 或跳过 vector 检索，只用 keyword + structured
```
