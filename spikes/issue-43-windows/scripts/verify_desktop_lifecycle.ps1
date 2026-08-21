[CmdletBinding()]
param(
    [string]$Executable
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$issueRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$releaseRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $issueRoot 'desktop\src-tauri\target\release')
).TrimEnd('\')
$expectedName = 'delta-force-windows-architecture-spike.exe'
$expectedWindowTitle = 'Delta Force CRM — Architecture Spike'
$expectedWindowClass = 'Tauri Window'
$expectedReactHeading = 'Delta Force CRM'
if ([string]::IsNullOrWhiteSpace($Executable)) {
    $Executable = Join-Path $releaseRoot $expectedName
}
$resolvedExecutable = [System.IO.Path]::GetFullPath($Executable)

if (
    [System.IO.Path]::GetDirectoryName($resolvedExecutable) -ne $releaseRoot -or
    [System.IO.Path]::GetFileName($resolvedExecutable) -ne $expectedName -or
    -not (Test-Path -LiteralPath $resolvedExecutable -PathType Leaf)
) {
    throw 'Refusing to test a process outside the exact generated spike path.'
}

if (-not ('SpikeNativeWindowControl' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public static class SpikeNativeWindowControl
{
    private delegate bool EnumWindowsProc(IntPtr window, IntPtr parameter);

    [DllImport("user32.dll")]
    private static extern bool EnumWindows(EnumWindowsProc callback, IntPtr parameter);

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr window, out uint processId);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetWindowText(IntPtr window, StringBuilder text, int count);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetClassName(IntPtr window, StringBuilder text, int count);

    [DllImport("user32.dll")]
    private static extern bool IsWindowVisible(IntPtr window);

    [DllImport("user32.dll")]
    private static extern bool IsWindowEnabled(IntPtr window);

    [DllImport("user32.dll")]
    private static extern bool PostMessage(IntPtr window, uint message, UIntPtr wParam, IntPtr lParam);

    public static long[] Find(uint expectedProcessId, string expectedTitle, string expectedClass)
    {
        var result = new List<long>();
        EnumWindows((window, _) => {
            GetWindowThreadProcessId(window, out uint processId);
            if (processId != expectedProcessId || !IsWindowVisible(window) || !IsWindowEnabled(window))
            {
                return true;
            }

            var title = new StringBuilder(512);
            var className = new StringBuilder(256);
            GetWindowText(window, title, title.Capacity);
            GetClassName(window, className, className.Capacity);
            if (title.ToString() == expectedTitle && className.ToString() == expectedClass)
            {
                result.Add(window.ToInt64());
            }
            return true;
        }, IntPtr.Zero);
        return result.ToArray();
    }

    public static bool RequestSystemClose(long handle)
    {
        const uint WM_SYSCOMMAND = 0x0112;
        const ulong SC_CLOSE = 0xF060;
        return PostMessage(new IntPtr(handle), WM_SYSCOMMAND, new UIntPtr(SC_CLOSE), IntPtr.Zero);
    }
}
'@
}

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

function Get-SidecarChildren {
    param([Parameter(Mandatory)][int]$ParentProcessId)

    @(
        Get-CimInstance Win32_Process |
            Where-Object {
                [int]$_.ParentProcessId -eq $ParentProcessId -and
                $_.Name -eq 'crm-api-poc.exe'
            }
    )
}

function Wait-ForSidecar {
    param(
        [Parameter(Mandatory)][int]$ParentProcessId,
        [int]$TimeoutSeconds = 15
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        $children = @(Get-SidecarChildren -ParentProcessId $ParentProcessId)
        if ($children.Count -eq 1) {
            return $children[0]
        }
        if ($children.Count -gt 1) {
            throw 'The shell created more than one sidecar process.'
        }
        Start-Sleep -Milliseconds 100
    } while ([DateTime]::UtcNow -lt $deadline)

    throw 'Timed out waiting for the sidecar process.'
}

function Wait-ForMainWindow {
    param(
        [Parameter(Mandatory)][System.Diagnostics.Process]$Process,
        [int]$TimeoutSeconds = 15
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        $Process.Refresh()
        if ($Process.HasExited) {
            throw 'The shell exited before creating its window.'
        }
        $handles = @(
            [SpikeNativeWindowControl]::Find(
                [uint32]$Process.Id,
                $expectedWindowTitle,
                $expectedWindowClass
            )
        )
        if ($handles.Count -eq 1) {
            return [int64]$handles[0]
        }
        if ($handles.Count -gt 1) {
            throw 'The shell created more than one matching native Tauri window.'
        }
        Start-Sleep -Milliseconds 100
    } while ([DateTime]::UtcNow -lt $deadline)

    throw 'Timed out waiting for the Tauri window.'
}

function Wait-ForReactMarker {
    param(
        [Parameter(Mandatory)][long]$WindowHandle,
        [int]$TimeoutSeconds = 15
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $nameCondition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::NameProperty,
        $expectedReactHeading
    )
    do {
        try {
            $window = [System.Windows.Automation.AutomationElement]::FromHandle(
                [IntPtr]::new($WindowHandle)
            )
            $markers = $window.FindAll(
                [System.Windows.Automation.TreeScope]::Descendants,
                $nameCondition
            )
            foreach ($marker in $markers) {
                if (
                    $marker.Current.ControlType -eq
                        [System.Windows.Automation.ControlType]::Text -and
                    -not $marker.Current.IsOffscreen
                ) {
                    return
                }
            }
        } catch [System.Windows.Automation.ElementNotAvailableException] {
            # WebView2 can recreate its accessibility tree while loading.
        }
        Start-Sleep -Milliseconds 100
    } while ([DateTime]::UtcNow -lt $deadline)

    throw 'The Tauri window did not expose the expected rendered React heading.'
}

function Wait-ForProcessExit {
    param(
        [Parameter(Mandatory)][System.Diagnostics.Process]$Process,
        [int]$TimeoutSeconds = 10
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        $Process.Refresh()
        if ($Process.HasExited) {
            return
        }
        Start-Sleep -Milliseconds 100
    } while ([DateTime]::UtcNow -lt $deadline)

    throw 'A generated spike process remained alive after shutdown.'
}

function Get-OnlyLoopbackListener {
    param([Parameter(Mandatory)][int]$ProcessId)

    $listeners = @(
        Get-NetTCPConnection -State Listen -ErrorAction Stop |
            Where-Object { [int]$_.OwningProcess -eq $ProcessId }
    )
    if (
        $listeners.Count -ne 1 -or
        $listeners[0].LocalAddress -ne '127.0.0.1' -or
        [int]$listeners[0].LocalPort -le 0
    ) {
        throw 'The sidecar listener is not exactly one ephemeral IPv4 loopback socket.'
    }
    $listeners[0]
}

function Stop-TrackedProcess {
    param([System.Diagnostics.Process]$Process)

    if ($null -eq $Process) {
        return
    }
    try {
        if (-not $Process.HasExited) {
            $Process.Kill()
        }
    } catch {
        # Cleanup is best effort and uses only process handles captured here.
    }
}

function Bind-ProcessIdentity {
    param(
        [Parameter(Mandatory)]
        [System.Diagnostics.Process]$Process
    )

    # Opening the handle now binds later waits and cleanup to this exact process,
    # even if Windows eventually reuses its numeric PID.
    [void]$Process.Handle
    $Process
}

$firstShell = $null
$secondShell = $null
$hardKillShell = $null
$trackedSidecars = [System.Collections.Generic.List[System.Diagnostics.Process]]::new()

try {
    $firstShell = Bind-ProcessIdentity -Process (
        Start-Process -FilePath $resolvedExecutable -PassThru -WindowStyle Normal
    )
    $firstSidecar = Wait-ForSidecar -ParentProcessId $firstShell.Id
    $firstSidecarProcess = Bind-ProcessIdentity -Process (
        Get-Process -Id $firstSidecar.ProcessId -ErrorAction Stop
    )
    $trackedSidecars.Add($firstSidecarProcess)
    $firstWindowHandle = Wait-ForMainWindow -Process $firstShell
    Wait-ForReactMarker -WindowHandle $firstWindowHandle
    $firstListener = Get-OnlyLoopbackListener -ProcessId $firstSidecar.ProcessId

    $secondShell = Bind-ProcessIdentity -Process (
        Start-Process -FilePath $resolvedExecutable -PassThru -WindowStyle Normal
    )
    if (-not $secondShell.WaitForExit(5000)) {
        throw 'The second shell instance did not exit promptly.'
    }
    if ($secondShell.ExitCode -ne 0) {
        throw 'The second shell instance did not exit successfully.'
    }
    $remainingChildren = @(Get-SidecarChildren -ParentProcessId $firstShell.Id)
    if (
        $remainingChildren.Count -ne 1 -or
        [int]$remainingChildren[0].ProcessId -ne [int]$firstSidecar.ProcessId
    ) {
        throw 'The second shell instance changed the running sidecar set.'
    }

    if (-not [SpikeNativeWindowControl]::RequestSystemClose($firstWindowHandle)) {
        throw 'The native Tauri window did not accept a system close request.'
    }
    if (-not $firstShell.WaitForExit(10000)) {
        throw 'The shell did not exit after its graceful close request.'
    }
    Wait-ForProcessExit -Process $firstSidecarProcess

    $hardKillShell = Bind-ProcessIdentity -Process (
        Start-Process -FilePath $resolvedExecutable -PassThru -WindowStyle Normal
    )
    $hardKillSidecar = Wait-ForSidecar -ParentProcessId $hardKillShell.Id
    $hardKillSidecarProcess = Bind-ProcessIdentity -Process (
        Get-Process -Id $hardKillSidecar.ProcessId -ErrorAction Stop
    )
    $trackedSidecars.Add($hardKillSidecarProcess)
    Wait-ForMainWindow -Process $hardKillShell | Out-Null
    $hardKillListener = Get-OnlyLoopbackListener -ProcessId $hardKillSidecar.ProcessId

    $hardKillShell.Kill()
    $hardKillShell.WaitForExit(5000) | Out-Null
    Wait-ForProcessExit -Process $hardKillSidecarProcess

    [ordered]@{
        checks = [ordered]@{
            graceful_shutdown = 'passed'
            hard_kill_job_object = 'passed'
            loopback_only = 'passed'
            react_render = 'passed'
            single_instance = 'passed'
            tauri_window = 'passed'
        }
        process_tree = 'tauri-shell -> crm-api-poc'
        listeners = @(
            "127.0.0.1:$($firstListener.LocalPort)",
            "127.0.0.1:$($hardKillListener.LocalPort)"
        )
    } | ConvertTo-Json -Depth 4
} finally {
    Stop-TrackedProcess -Process $secondShell
    Stop-TrackedProcess -Process $firstShell
    Stop-TrackedProcess -Process $hardKillShell
    foreach ($sidecarProcess in $trackedSidecars) {
        Stop-TrackedProcess -Process $sidecarProcess
    }
}
