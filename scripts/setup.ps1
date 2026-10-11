# setup.ps1
# Setup routine for the OCR Engine development environment

Write-Host "Starting environment setup..." -ForegroundColor Cyan

# 1. Create Virtual Environment if it doesn't exist
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment (.venv)..." -ForegroundColor Yellow
    python -m venv .venv
} else {
    Write-Host "Virtual environment (.venv) already exists." -ForegroundColor Gray
}

# 2. Upgrade pip and install requirements
Write-Host "Installing dependencies from requirements.txt..." -ForegroundColor Yellow
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. Verification
Write-Host "Verifying installation..." -ForegroundColor Yellow
& .\.venv\Scripts\python.exe --version
& .\.venv\Scripts\pip list

Write-Host "Setup completed successfully!" -ForegroundColor Green
