# CI-RAG-ROUTER GUI 启动脚本
# 使用 uv 环境运行

$ErrorActionPreference = "Stop"

# 切换到脚本所在目录
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# 检查虚拟环境
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "错误: 虚拟环境不存在，请先运行: uv venv --python 3.10" -ForegroundColor Red
    exit 1
}

# 检查 API Key
$apiKey = $env:CI_LLM_API_KEY
if (-not $apiKey) {
    # 尝试从 .env 文件读取
    if (Test-Path ".env") {
        $envContent = Get-Content ".env" -Raw
        if ($envContent -match 'CI_LLM_API_KEY=(.+)') {
            $env:CI_LLM_API_KEY = $matches[1].Trim()
            Write-Host "已从 .env 文件加载 API Key" -ForegroundColor Green
        }
    }
}

if ($env:CI_LLM_API_KEY) {
    Write-Host "API Key 已配置" -ForegroundColor Green
} else {
    Write-Host "警告: CI_LLM_API_KEY 未设置，Level 2 功能将不可用" -ForegroundColor Yellow
}

# 启动 GUI
Write-Host "启动 CI-RAG-ROUTER GUI..." -ForegroundColor Cyan
.venv\Scripts\python tools/ci_test_window_v4.py
