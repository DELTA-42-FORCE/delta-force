[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$issueRoot = Join-Path $repositoryRoot 'spikes\issue-43-windows'
$desktopRoot = Join-Path $issueRoot 'desktop'
$cargoCommand = Get-Command cargo.exe -ErrorAction SilentlyContinue
$cargoExecutable = if ($null -ne $cargoCommand) {
    $cargoCommand.Source
} else {
    Join-Path ([Environment]::GetFolderPath('UserProfile')) '.cargo\bin\cargo.exe'
}
$cargoBin = [System.IO.Path]::GetDirectoryName($cargoExecutable)
$lifecycleVerifier = Join-Path $PSScriptRoot 'verify_desktop_lifecycle.ps1'
$sourceHasher = Join-Path $PSScriptRoot 'hash_spike_sources.py'
$pythonExecutable = Join-Path $issueRoot 'api-poc\.venv\Scripts\python.exe'

function Assert-LastExitCode {
    param([Parameter(Mandatory)][string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

if (-not (Test-Path -LiteralPath $cargoExecutable -PathType Leaf)) {
    throw 'The isolated Rust toolchain is unavailable.'
}

& (Join-Path $PSScriptRoot 'build_api_poc.ps1')

& npm --prefix (Join-Path $repositoryRoot 'apps\web') run build
Assert-LastExitCode 'React build'

& npm --prefix $desktopRoot ci --ignore-scripts --no-audit --no-fund
Assert-LastExitCode 'isolated Tauri npm install'

$env:Path = "$cargoBin;$env:Path"
$env:CARGO_BUILD_JOBS = '1'
$env:CARGO_INCREMENTAL = '0'
$env:CARGO_PROFILE_DEV_DEBUG = '0'
$env:CARGO_PROFILE_DEV_CODEGEN_UNITS = '1'
$env:CARGO_PROFILE_TEST_DEBUG = '0'
$env:CARGO_PROFILE_TEST_CODEGEN_UNITS = '1'
$env:CARGO_PROFILE_RELEASE_CODEGEN_UNITS = '1'
Push-Location (Join-Path $desktopRoot 'src-tauri')
try {
    & $cargoExecutable fmt --all -- --check
    Assert-LastExitCode 'Rust formatting check'
    & $cargoExecutable test --locked -j 1
    Assert-LastExitCode 'Rust tests'
} finally {
    Pop-Location
}

& npm --prefix $desktopRoot run build
Assert-LastExitCode 'Tauri no-bundle build'

& $lifecycleVerifier

& $pythonExecutable $sourceHasher
Assert-LastExitCode 'spike source digest'
