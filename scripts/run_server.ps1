$ProjectRoot = (Get-Item $PSScriptRoot).Parent.FullName
Set-Location $ProjectRoot

if (-not (Test-Path ".\scripts\set_env.ps1")) {
    Write-Host "Error: .\scripts\set_env.ps1 not found. Please copy .\scripts\set_env.example.ps1 to .\scripts\set_env.ps1 and adjust the variables." -ForegroundColor Red
    exit 1
}
. .\scripts\set_env.ps1

python -m uvicorn app.main_restapi:app --host 0.0.0.0 --port 5000 --reload --log-level debug