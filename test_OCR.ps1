# test_OCR.ps1
# Script to setup environment and run the OCR pipeline end-to-end test

# 1. Activate the virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Cyan
& .\.venv\Scripts\Activate.ps1

# 2. Set environment variables
Write-Host "Setting environment variables..." -ForegroundColor Cyan
& .\scripts\set_env.ps1

# 3. Run the end-to-end OCR pipeline test
Write-Host "Executing OCR Pipeline End-to-End Test..." -ForegroundColor Yellow
& .\.venv\Scripts\python.exe test\test_ocr_pipeline_end_to_end.py

Write-Host "Test execution finished." -ForegroundColor Cyan
