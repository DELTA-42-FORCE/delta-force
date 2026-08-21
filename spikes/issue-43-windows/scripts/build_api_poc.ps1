[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$issueRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$apiRoot = Join-Path $issueRoot 'api-poc'
$buildRoot = Join-Path $issueRoot 'build'
$distRoot = Join-Path $buildRoot 'pyinstaller-dist'
$workRoot = Join-Path $buildRoot 'pyinstaller-work'
$specRoot = Join-Path $buildRoot 'pyinstaller-spec'
$entrypoint = Join-Path $apiRoot 'src\spike_runtime\__main__.py'
$python = Join-Path $apiRoot '.venv\Scripts\python.exe'
$pyinstaller = Join-Path $apiRoot '.venv\Scripts\pyinstaller.exe'
$verifier = Join-Path $PSScriptRoot 'verify_packaged_sidecar.py'
$preparer = Join-Path $PSScriptRoot 'prepare_signed_sidecar.py'
$sourceHasher = Join-Path $PSScriptRoot 'hash_spike_sources.py'
$sourceOnedir = Join-Path $distRoot 'crm-api-poc'
$sidecarRoot = Join-Path $buildRoot 'sidecar'
$pyproject = Join-Path $apiRoot 'pyproject.toml'
$pythonCheckPaths = @(
    (Join-Path $apiRoot 'src'),
    (Join-Path $apiRoot 'tests'),
    $verifier,
    $preparer,
    $sourceHasher
)

function Assert-LastExitCode {
    param([Parameter(Mandatory)][string]$Step)

    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

Get-Command uv -ErrorAction Stop | Out-Null

& uv sync `
    --project $apiRoot `
    --python 3.12 `
    --locked `
    --all-groups
Assert-LastExitCode 'uv sync'

if (-not (Test-Path -LiteralPath $pyinstaller -PathType Leaf)) {
    throw 'PyInstaller was not installed in the isolated spike environment.'
}

& $python -m black --config $pyproject --check @pythonCheckPaths
Assert-LastExitCode 'Python Black check'

& $python -m flake8 --max-line-length 88 @pythonCheckPaths
Assert-LastExitCode 'Python Flake8 check'

& $python -m pytest -q -c $pyproject (Join-Path $apiRoot 'tests')
Assert-LastExitCode 'Python tests'

& $pyinstaller `
    --clean `
    --noconfirm `
    --onedir `
    --contents-directory api-runtime `
    --noupx `
    --console `
    --name crm-api-poc `
    --distpath $distRoot `
    --workpath $workRoot `
    --specpath $specRoot `
    $entrypoint
Assert-LastExitCode 'PyInstaller onedir build'

$executable = Join-Path $sourceOnedir 'crm-api-poc.exe'
$runtimeDirectory = Join-Path $sourceOnedir 'api-runtime'
if (
    -not (Test-Path -LiteralPath $executable -PathType Leaf) -or
    -not (Test-Path -LiteralPath $runtimeDirectory -PathType Container)
) {
    throw 'PyInstaller did not produce the required onedir layout.'
}

& $python $verifier --executable $executable
Assert-LastExitCode 'packaged sidecar verification'

$resolvedBuildRoot = [System.IO.Path]::GetFullPath($buildRoot).TrimEnd('\')
$resolvedSidecarRoot = [System.IO.Path]::GetFullPath($sidecarRoot)
if (
    [System.IO.Path]::GetDirectoryName($resolvedSidecarRoot) -ne $resolvedBuildRoot -or
    [System.IO.Path]::GetFileName($resolvedSidecarRoot) -ne 'sidecar'
) {
    throw 'Refusing to prepare a sidecar outside the exact generated build path.'
}
if (Test-Path -LiteralPath $resolvedSidecarRoot) {
    Remove-Item -LiteralPath $resolvedSidecarRoot -Recurse -Force
}

& $python $preparer `
    --source-onedir $sourceOnedir `
    --destination $resolvedSidecarRoot
Assert-LastExitCode 'synthetic sidecar manifest preparation'
