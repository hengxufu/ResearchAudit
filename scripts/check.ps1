param([switch]$Browser)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
Push-Location $workspace
try {
    & .\.venv\Scripts\python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed' }
    & npm run build --prefix frontend
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
    if ($Browser) {
        Push-Location (Join-Path $workspace 'frontend')
        try {
            & npm run test:e2e
            if ($LASTEXITCODE -ne 0) { throw 'Browser tests failed' }
        } finally { Pop-Location }
    }
} finally { Pop-Location }
