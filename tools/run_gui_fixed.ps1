# CI-RAG-ROUTER GUI Launcher (Fixed for memory issues)
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
}

# Set memory optimization environment variables
$env:OMP_NUM_THREADS = "1"           # Limit OpenMP threads
$env:MKL_NUM_THREADS = "1"           # Limit MKL threads
$env:TOKENIZERS_PARALLELISM = "false" # Disable tokenizer parallelism

Write-Host "Using Python: $venvPython" -ForegroundColor Green
Write-Host "Memory optimization enabled (single thread)" -ForegroundColor Yellow
Write-Host ""

# Run GUI
try {
    & $venvPython ci_test_window.py
} catch {
    Write-Error "Failed to start GUI: $_"
    Read-Host "Press Enter to exit"
}
