if (-not (Test-Path ".\set_env.ps1")) {
    Write-Host "Error: set_env.ps1 not found. Please copy set_env.example.ps1 to set_env.ps1 and adjust the variables." -ForegroundColor Red
    exit 1
}
. .\set_env.ps1

# -m uvicorn startet den REST-API-Server mit Hot-Reloading für Entwicklungszwecke
python -m app.main_worker