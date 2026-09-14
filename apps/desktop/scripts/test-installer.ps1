param(
  [string]$InstallerPath = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$productName = 'Delta Force CRM'
$bundleIdentifier = 'br.com.deltaforce.crm'
$applicationExecutable = 'delta-force-desktop.exe'
$sidecarExecutable = 'api-sidecar/delta-force-api/delta-force-api.exe'
$uninstallRegistryRoot = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall'
$desktopRoot = Split-Path -Parent $PSScriptRoot

function Get-ProductRegistration {
  @(
    Get-ItemProperty "$uninstallRegistryRoot\*" -ErrorAction SilentlyContinue |
      Select-Object PSChildName, DisplayName, DisplayVersion, InstallLocation, UninstallString |
      Where-Object { $_.DisplayName -eq $productName }
  )
}

function Get-SmokeSidecars([string]$InstallRoot) {
  @(
    Get-Process -Name 'delta-force-api' -ErrorAction SilentlyContinue |
      Where-Object {
        try {
          $_.Path.StartsWith($InstallRoot, [StringComparison]::OrdinalIgnoreCase)
        } catch {
          $false
        }
      }
  )
}

if ($env:OS -ne 'Windows_NT') {
  throw 'The installer smoke test must run on Windows.'
}

if ([string]::IsNullOrWhiteSpace($InstallerPath)) {
  $bundleRoot = Join-Path $desktopRoot 'src-tauri/target/release/bundle/nsis'
  $installers = @(Get-ChildItem -LiteralPath $bundleRoot -Filter '*-setup.exe' -File)
  if ($installers.Count -ne 1) {
    throw "Expected exactly one NSIS installer in $bundleRoot; found $($installers.Count)."
  }
  $InstallerPath = $installers[0].FullName
}

$InstallerPath = (Resolve-Path -LiteralPath $InstallerPath).Path
$dataRoot = Join-Path $env:LOCALAPPDATA $bundleIdentifier
$desktopShortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) "$productName.lnk"
$startMenuShortcut = Join-Path ([Environment]::GetFolderPath('Programs')) "$productName.lnk"
$temporaryBase = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [IO.Path]::GetTempPath() }
$temporaryBase = [IO.Path]::GetFullPath($temporaryBase)
$smokeRoot = Join-Path $temporaryBase ("delta-force-installer-smoke-" + [guid]::NewGuid().ToString('N'))
$installRoot = Join-Path $smokeRoot 'app'
$app = $null

if (@(Get-ProductRegistration).Count -ne 0) {
  throw "$productName is already registered for the current user; smoke test cancelled."
}
if ((Get-Process -Name 'delta-force-desktop', 'delta-force-api' -ErrorAction SilentlyContinue)) {
  throw 'Delta Force CRM processes are already running; smoke test cancelled.'
}
if (Test-Path -LiteralPath $dataRoot) {
  throw "The application data directory already exists at $dataRoot; smoke test cancelled."
}
if ((Test-Path -LiteralPath $desktopShortcut) -or (Test-Path -LiteralPath $startMenuShortcut)) {
  throw 'Delta Force CRM shortcuts already exist; smoke test cancelled.'
}

New-Item -ItemType Directory -Path $smokeRoot | Out-Null

try {
  $installer = Start-Process `
    -FilePath $InstallerPath `
    -ArgumentList @('/S', "/D=$installRoot") `
    -Wait `
    -PassThru `
    -WindowStyle Hidden
  if ($installer.ExitCode -ne 0) {
    throw "NSIS installer exited with code $($installer.ExitCode)."
  }

  $registrations = @(Get-ProductRegistration)
  if ($registrations.Count -ne 1) {
    throw "Expected one uninstall registration; found $($registrations.Count)."
  }
  $registeredLocation = $registrations[0].InstallLocation.Trim().Trim('"')
  if ([IO.Path]::GetFullPath($registeredLocation) -ne [IO.Path]::GetFullPath($installRoot)) {
    throw "Installer registered an unexpected location: $registeredLocation."
  }

  foreach ($relativePath in @($applicationExecutable, 'uninstall.exe', $sidecarExecutable)) {
    if (-not (Test-Path -LiteralPath (Join-Path $installRoot $relativePath) -PathType Leaf)) {
      throw "Installed package is missing $relativePath."
    }
  }
  if (-not (Test-Path -LiteralPath $desktopShortcut -PathType Leaf)) {
    throw 'The desktop shortcut was not created.'
  }
  if (-not (Test-Path -LiteralPath $startMenuShortcut -PathType Leaf)) {
    throw 'The Start Menu shortcut was not created.'
  }

  $app = Start-Process `
    -FilePath (Join-Path $installRoot $applicationExecutable) `
    -PassThru `
    -WindowStyle Hidden
  $readyDeadline = [DateTime]::UtcNow.AddSeconds(30)
  do {
    Start-Sleep -Milliseconds 500
    $app.Refresh()
    $sidecars = @(Get-SmokeSidecars $installRoot)
    $databaseReady = Test-Path -LiteralPath (Join-Path $dataRoot 'crm.sqlite3') -PathType Leaf
  } while (
    (-not $app.HasExited) -and
    (-not $databaseReady -or $sidecars.Count -ne 1) -and
    [DateTime]::UtcNow -lt $readyDeadline
  )

  if ($app.HasExited) {
    throw "Installed application exited before readiness with code $($app.ExitCode)."
  }
  if (-not $databaseReady -or $sidecars.Count -ne 1) {
    throw 'Installed application did not create its database and one sidecar within 30 seconds.'
  }

  if (-not $app.CloseMainWindow() -or -not $app.WaitForExit(15000)) {
    throw 'Installed application did not close gracefully within 15 seconds.'
  }
  Start-Sleep -Seconds 2
  if (@(Get-SmokeSidecars $installRoot).Count -ne 0) {
    throw 'The packaged sidecar remained after the desktop window closed.'
  }

  $sentinel = Join-Path $dataRoot 'installer-smoke-preservation.txt'
  [IO.File]::WriteAllText($sentinel, 'synthetic installer preservation proof')
  $uninstallerPath = Join-Path $installRoot 'uninstall.exe'
  $uninstaller = Start-Process `
    -FilePath $uninstallerPath `
    -ArgumentList '/S' `
    -Wait `
    -PassThru `
    -WindowStyle Hidden
  if ($uninstaller.ExitCode -ne 0) {
    throw "NSIS uninstaller exited with code $($uninstaller.ExitCode)."
  }

  $uninstallDeadline = [DateTime]::UtcNow.AddSeconds(30)
  do {
    Start-Sleep -Milliseconds 500
    $registrationRemoved = @(Get-ProductRegistration).Count -eq 0
    $applicationRemoved = -not (Test-Path -LiteralPath (Join-Path $installRoot $applicationExecutable))
    $shortcutsRemoved =
      -not (Test-Path -LiteralPath $desktopShortcut) -and
      -not (Test-Path -LiteralPath $startMenuShortcut)
  } while (
    (-not $registrationRemoved -or -not $applicationRemoved -or -not $shortcutsRemoved) -and
    [DateTime]::UtcNow -lt $uninstallDeadline
  )

  if (-not $registrationRemoved -or -not $applicationRemoved -or -not $shortcutsRemoved) {
    throw 'Uninstall did not remove registration, application files and shortcuts.'
  }
  if (-not (Test-Path -LiteralPath $sentinel -PathType Leaf)) {
    throw 'Uninstall removed the synthetic application data sentinel.'
  }
  if (-not (Test-Path -LiteralPath (Join-Path $dataRoot 'crm.sqlite3') -PathType Leaf)) {
    throw 'Uninstall removed the synthetic CRM database.'
  }

  $reinstaller = Start-Process `
    -FilePath $InstallerPath `
    -ArgumentList @('/S', "/D=$installRoot") `
    -Wait `
    -PassThru `
    -WindowStyle Hidden
  if ($reinstaller.ExitCode -ne 0) {
    throw "NSIS reinstaller exited with code $($reinstaller.ExitCode)."
  }

  if (@(Get-ProductRegistration).Count -ne 1) {
    throw 'Reinstall did not restore exactly one uninstall registration.'
  }
  foreach ($relativePath in @($applicationExecutable, 'uninstall.exe', $sidecarExecutable)) {
    if (-not (Test-Path -LiteralPath (Join-Path $installRoot $relativePath) -PathType Leaf)) {
      throw "Reinstalled package is missing $relativePath."
    }
  }
  if (
    -not (Test-Path -LiteralPath $desktopShortcut -PathType Leaf) -or
    -not (Test-Path -LiteralPath $startMenuShortcut -PathType Leaf)
  ) {
    throw 'Reinstall did not restore the application shortcuts.'
  }
  if (-not (Test-Path -LiteralPath $sentinel -PathType Leaf)) {
    throw 'Reinstall did not preserve the synthetic application data sentinel.'
  }

  $app = Start-Process `
    -FilePath (Join-Path $installRoot $applicationExecutable) `
    -PassThru `
    -WindowStyle Hidden
  $reinstallReadyDeadline = [DateTime]::UtcNow.AddSeconds(30)
  do {
    Start-Sleep -Milliseconds 500
    $app.Refresh()
    $sidecars = @(Get-SmokeSidecars $installRoot)
  } while (
    (-not $app.HasExited) -and
    $sidecars.Count -ne 1 -and
    [DateTime]::UtcNow -lt $reinstallReadyDeadline
  )

  if ($app.HasExited) {
    throw "Reinstalled application exited before readiness with code $($app.ExitCode)."
  }
  if ($sidecars.Count -ne 1) {
    throw 'Reinstalled application did not start exactly one sidecar within 30 seconds.'
  }
  if (-not $app.CloseMainWindow() -or -not $app.WaitForExit(15000)) {
    throw 'Reinstalled application did not close gracefully within 15 seconds.'
  }
  Start-Sleep -Seconds 2
  if (@(Get-SmokeSidecars $installRoot).Count -ne 0) {
    throw 'The packaged sidecar remained after the reinstalled desktop window closed.'
  }

  $secondUninstaller = Start-Process `
    -FilePath (Join-Path $installRoot 'uninstall.exe') `
    -ArgumentList '/S' `
    -Wait `
    -PassThru `
    -WindowStyle Hidden
  if ($secondUninstaller.ExitCode -ne 0) {
    throw "NSIS uninstaller after reinstall exited with code $($secondUninstaller.ExitCode)."
  }

  $secondUninstallDeadline = [DateTime]::UtcNow.AddSeconds(30)
  do {
    Start-Sleep -Milliseconds 500
    $registrationRemoved = @(Get-ProductRegistration).Count -eq 0
    $applicationRemoved = -not (Test-Path -LiteralPath (Join-Path $installRoot $applicationExecutable))
    $shortcutsRemoved =
      -not (Test-Path -LiteralPath $desktopShortcut) -and
      -not (Test-Path -LiteralPath $startMenuShortcut)
  } while (
    (-not $registrationRemoved -or -not $applicationRemoved -or -not $shortcutsRemoved) -and
    [DateTime]::UtcNow -lt $secondUninstallDeadline
  )

  if (-not $registrationRemoved -or -not $applicationRemoved -or -not $shortcutsRemoved) {
    throw 'Uninstall after reinstall did not remove registration, application files and shortcuts.'
  }
  if (
    -not (Test-Path -LiteralPath $sentinel -PathType Leaf) -or
    -not (Test-Path -LiteralPath (Join-Path $dataRoot 'crm.sqlite3') -PathType Leaf)
  ) {
    throw 'Uninstall after reinstall removed the preserved synthetic application data.'
  }

  Write-Output 'Installer smoke test passed: install, startup, uninstall, reinstall and data preservation.'
} finally {
  if ($null -ne $app -and -not $app.HasExited) {
    Stop-Process -Id $app.Id -Force -ErrorAction SilentlyContinue
  }
  Get-SmokeSidecars $installRoot | Stop-Process -Force -ErrorAction SilentlyContinue

  $uninstallerPath = Join-Path $installRoot 'uninstall.exe'
  if (Test-Path -LiteralPath $uninstallerPath -PathType Leaf) {
    Start-Process -FilePath $uninstallerPath -ArgumentList '/S' -Wait -WindowStyle Hidden
  }

  Remove-Item -LiteralPath $desktopShortcut -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $startMenuShortcut -Force -ErrorAction SilentlyContinue

  $expectedDataRoot = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA $bundleIdentifier))
  $resolvedDataRoot = [IO.Path]::GetFullPath($dataRoot)
  if ($resolvedDataRoot -eq $expectedDataRoot -and (Test-Path -LiteralPath $resolvedDataRoot)) {
    Remove-Item -LiteralPath $resolvedDataRoot -Recurse -Force
  }

  $resolvedSmokeRoot = [IO.Path]::GetFullPath($smokeRoot)
  $temporaryPrefix = $temporaryBase.TrimEnd('\') + '\'
  if (
    $resolvedSmokeRoot.StartsWith($temporaryPrefix, [StringComparison]::OrdinalIgnoreCase) -and
    (Split-Path -Leaf $resolvedSmokeRoot) -like 'delta-force-installer-smoke-*' -and
    (Test-Path -LiteralPath $resolvedSmokeRoot)
  ) {
    Remove-Item -LiteralPath $resolvedSmokeRoot -Recurse -Force
  }
}
