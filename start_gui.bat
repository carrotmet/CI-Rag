@echo off
chcp 65001 >nul
echo ==========================================
echo CI-RAG-ROUTER GUI 启动器
echo ==========================================
echo.

:: 切换到脚本所在目录
cd /d "%~dp0"

:: 检查虚拟环境
if not exist ".venv\Scripts\python.exe" (
    echo [错误] 虚拟环境不存在，请先运行: uv venv --python 3.10
    pause
    exit /b 1
)

:: 检查 .env 文件并加载
if exist ".env" (
    echo [信息] 正在加载 .env 文件...
    for /f "tokens=1,2 delims==" %%a in (.env) do (
        if "%%a"=="CI_LLM_API_KEY" set "CI_LLM_API_KEY=%%b"
    )
)

if defined CI_LLM_API_KEY (
    echo [OK] API Key 已配置
) else (
    echo [警告] CI_LLM_API_KEY 未设置，Level 2 功能将不可用
)

echo.
echo [信息] 正在启动 GUI...
echo ==========================================
.venv\Scripts\python tools/ci_test_window.py

if errorlevel 1 (
    echo.
    echo [错误] GUI 启动失败
    pause
)
