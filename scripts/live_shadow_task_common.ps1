Set-StrictMode -Version Latest

function Resolve-LiveShadowRepositoryRoot {
    param([string]$RepositoryRoot)

    if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
        return (Resolve-Path (Join-Path $PSScriptRoot ".." )).Path
    }

    return (Resolve-Path -LiteralPath $RepositoryRoot).Path
}

function Resolve-LiveShadowPython {
    param([string]$PythonPath)

    $candidate = $PythonPath
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        $candidate = $env:CALIBRAXI_PYTHON
    }
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        $command = Get-Command python -ErrorAction SilentlyContinue
        if ($null -ne $command) {
            $candidate = $command.Source
        }
    }
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        throw "Python was not found. Pass -PythonPath or set CALIBRAXI_PYTHON."
    }

    $resolved = Resolve-Path -LiteralPath $candidate -ErrorAction SilentlyContinue
    if ($null -ne $resolved) {
        return $resolved.Path
    }
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        return (Get-Command $candidate).Source
    }
    throw "Python executable does not exist or is not on PATH: $candidate"
}

function Resolve-LiveShadowPowerShell {
    $pwsh = Get-Command pwsh -ErrorAction SilentlyContinue
    if ($null -ne $pwsh) {
        return $pwsh.Source
    }
    return (Get-Command powershell.exe -ErrorAction Stop).Source
}

function Resolve-LiveShadowLogDirectory {
    param(
        [string]$RepositoryRoot,
        [string]$LogDirectory,
        [switch]$Create
    )

    $directory = $LogDirectory
    if ([string]::IsNullOrWhiteSpace($directory)) {
        $directory = Join-Path $RepositoryRoot "temp\live-shadow\logs"
    }
    $directory = [Environment]::ExpandEnvironmentVariables($directory)
    if (-not [System.IO.Path]::IsPathRooted($directory)) {
        $directory = Join-Path $RepositoryRoot $directory
    }
    if ($Create) {
        New-Item -ItemType Directory -Force -Path $directory | Out-Null
    }
    return [System.IO.Path]::GetFullPath($directory)
}

function Resolve-LiveShadowStopFile {
    param([string]$RepositoryRoot)

    $base = $env:LOCALAPPDATA
    if ([string]::IsNullOrWhiteSpace($base)) {
        $base = $env:TEMP
    }
    if ([string]::IsNullOrWhiteSpace($base)) {
        $base = Join-Path $RepositoryRoot 'temp\live-shadow'
    }
    return Join-Path $base 'CalibraXI\live-shadow.stop'
}

function Request-LiveShadowStop {
    param([string]$RepositoryRoot)

    $path = Resolve-LiveShadowStopFile -RepositoryRoot $RepositoryRoot
    $directory = Split-Path -Parent $path
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    Set-Content -LiteralPath $path -Value ((Get-Date).ToUniversalTime().ToString('o')) -Encoding UTF8
    return $path
}

function Clear-LiveShadowStopRequest {
    param([string]$RepositoryRoot)

    $path = Resolve-LiveShadowStopFile -RepositoryRoot $RepositoryRoot
    Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
}

function ConvertTo-LiveShadowArgument {
    param([AllowEmptyString()][string]$Value)

    if ($null -eq $Value) {
        return '""'
    }
    return '"' + $Value.Replace('"', '\"') + '"'
}

function Get-LiveShadowTask {
    param([string]$TaskName)

    return Get-ScheduledTask -TaskName $TaskName -TaskPath '\' -ErrorAction SilentlyContinue
}

function Wait-LiveShadowTaskState {
    param(
        [string]$TaskName,
        [ValidateSet('Running', 'Ready', 'Disabled')][string]$State,
        [int]$TimeoutSeconds = 120
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $task = Get-LiveShadowTask -TaskName $TaskName
        if ($null -eq $task) {
            return $false
        }
        if ($task.State.ToString() -eq $State) {
            return $true
        }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)
    return $false
}

function Stop-LiveShadowTask {
    param(
        [string]$TaskName,
        [string]$RepositoryRoot,
        [int]$TimeoutSeconds = 120
    )

    $task = Get-LiveShadowTask -TaskName $TaskName
    if ($null -eq $task) {
        return $false
    }
    if ($task.State.ToString() -eq 'Running') {
        $repository = Resolve-LiveShadowRepositoryRoot -RepositoryRoot $RepositoryRoot
        Request-LiveShadowStop -RepositoryRoot $repository | Out-Null
        if (-not (Wait-LiveShadowTaskState -TaskName $TaskName -State Ready -TimeoutSeconds $TimeoutSeconds)) {
            # The worker may be blocked in a provider or persistence call. Use
            # Task Scheduler's hard stop only after the graceful window.
            Stop-ScheduledTask -TaskName $TaskName -TaskPath '\' -ErrorAction Stop
            if (-not (Wait-LiveShadowTaskState -TaskName $TaskName -State Ready -TimeoutSeconds $TimeoutSeconds)) {
                throw "Timed out waiting for scheduled task to stop: $TaskName"
            }
        }
    }
    return $true
}
