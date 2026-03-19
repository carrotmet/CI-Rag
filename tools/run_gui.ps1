# CI-RAG-ROUTER GUI Launcher (PowerShell)
$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CI-RAG-ROUTER GUI Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if venv exists
$venvPython = "..\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Error ".venv not found! Please run: uv venv"
    exit 1
}

# Add conda Library/bin to PATH if exists (for MKL DLLs)
$condaLibrary = "D:\generic\anaconda\Library\bin"
if (Test-Path $condaLibrary) {
    $env:PATH = "$condaLibrary;$env:PATH"
    Write-Host "Added MKL libraries from: $condaLibrary" -ForegroundColor DarkGray
}

Write-Host "Using Python: $venvPython" -ForegroundColor Green
Write-Host ""

# Run GUI
try {
    & $venvPython ci_test_window.py
} catch {
    Write-Error "Failed to start GUI: $_"
    Read-Host "Press Enter to exit"
}
