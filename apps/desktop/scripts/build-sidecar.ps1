$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$desktopRoot = Split-Path -Parent $PSScriptRoot
$repositoryRoot = Split-Path -Parent (Split-Path -Parent $desktopRoot)
$apiRoot = Join-Path $repositoryRoot 'apps/api'
$resourceRoot = Join-Path $desktopRoot 'src-tauri/resources/api-sidecar'

if (Test-Path -LiteralPath $resourceRoot) {
  Remove-Item -LiteralPath $resourceRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $resourceRoot -Force | Out-Null

Push-Location $apiRoot
try {
  uv run --group build pyinstaller `
    --noconfirm `
    --clean `
    --onedir `
    --name delta-force-api `
    --paths src `
    --add-data 'alembic;alembic' `
    --add-data 'alembic.ini;.' `
    --distpath $resourceRoot `
    --specpath "$apiRoot/build/pyinstaller" `
    --workpath "$apiRoot/build/pyinstaller" `
    src/crm_api/desktop_server.py
} finally {
  Pop-Location
}
