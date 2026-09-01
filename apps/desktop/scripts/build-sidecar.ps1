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
Set-Content `
  -LiteralPath (Join-Path $resourceRoot '.gitkeep') `
  -Value 'O sidecar PyInstaller e gerado neste diretorio durante desktop-build.' `
  -NoNewline

Push-Location $apiRoot
try {
  uv run --group build pyinstaller `
    --noconfirm `
    --clean `
    --onedir `
    --name delta-force-api `
    --paths src `
    --add-data "$apiRoot/alembic;alembic" `
    --add-data "$apiRoot/alembic.ini;." `
    --distpath $resourceRoot `
    --specpath "$apiRoot/build/pyinstaller" `
    --workpath "$apiRoot/build/pyinstaller" `
    src/crm_api/desktop_server.py
  if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
  }
} finally {
  Pop-Location
}
