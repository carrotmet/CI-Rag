@echo off
chcp 65001 >nul
echo ========================================
echo CI-RAG-ROUTER GUI Launcher
echo ========================================
echo.

REM Check if venv exists
if not exist "..\.venv\Scripts\python.exe" (
    echo Error: .venv not found!
    echo Please run: uv venv
    pause
    exit /b 1
)

REM Set PATH to include MKL DLLs from conda if needed
set "CONDA_LIBRARY=C:\Users\%USERNAME%\anaconda3\Library\bin"
if exist "%CONDA_LIBRARY%" (
    set "PATH=%CONDA_LIBRARY%;%PATH%"
)

REM Use uv venv Python
echo Using Python: ..\.venv\Scripts\python.exe
echo.

..\.venv\Scripts\python.exe ci_test_window.py

if errorlevel 1 (
    echo.
    echo GUI exited with error
    pause
)
