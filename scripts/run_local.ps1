$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path ".venv")) {
    py -3 -m venv .venv
}
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Host "Created .env. Set HTTP_USER_AGENT to include a real operator contact before using public OSM services."
}
$env:PYTHONPATH = "backend"
uvicorn app.main:app --app-dir backend --env-file .env --host 127.0.0.1 --port 8000 --reload
