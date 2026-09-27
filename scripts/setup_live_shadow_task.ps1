[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$TaskName = 'CalibraXI-LiveShadow',
    [string]$RepositoryRoot,
    [string]$PythonPath,
    [ValidateSet('AtLogOn', 'AtStartup')][string]$Trigger = 'AtLogOn',
    [string]$RunnerFactory,
    [double]$IntervalSeconds = 60,
    [double]$DiscoveryIntervalSeconds = 21600,
    [int]$Days = 10,
    [string]$LogDirectory,
    [switch]$Force
)

Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'live_shadow_task_common.ps1')

$repository = Resolve-LiveShadowRepositoryRoot -RepositoryRoot $RepositoryRoot
$python = Resolve-LiveShadowPython -PythonPath $PythonPath
$logs = Resolve-LiveShadowLogDirectory -RepositoryRoot $repository -LogDirectory $LogDirectory
$shell = Resolve-LiveShadowPowerShell
$wrapper = Join-Path $repository 'scripts\run_live_shadow_task.ps1'
$userId = if ([string]::IsNullOrWhiteSpace($env:USERDOMAIN)) { $env:USERNAME } else { "$env:USERDOMAIN\$env:USERNAME" }

$argumentParts = @(
    '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
    (ConvertTo-LiveShadowArgument $wrapper), '-RepositoryRoot', (ConvertTo-LiveShadowArgument $repository),
    '-PythonPath', (ConvertTo-LiveShadowArgument $python), '-IntervalSeconds', $IntervalSeconds.ToString([Globalization.CultureInfo]::InvariantCulture),
    '-DiscoveryIntervalSeconds', $DiscoveryIntervalSeconds.ToString([Globalization.CultureInfo]::InvariantCulture), '-Days', $Days.ToString([Globalization.CultureInfo]::InvariantCulture),
    '-LogDirectory', (ConvertTo-LiveShadowArgument $logs)
)
if (-not [string]::IsNullOrWhiteSpace($RunnerFactory)) {
    $argumentParts += @('-RunnerFactory', (ConvertTo-LiveShadowArgument $RunnerFactory))
}
$taskArguments = $argumentParts -join ' '

$existing = Get-LiveShadowTask -TaskName $TaskName
if ($null -ne $existing -and -not $Force) {
    throw "Scheduled task already exists: $TaskName. Re-run with -Force to replace its definition."
}

if ($PSCmdlet.ShouldProcess($TaskName, 'register CalibraXI live-shadow scheduled task')) {
    try {
        Resolve-LiveShadowLogDirectory -RepositoryRoot $repository -LogDirectory $logs -Create | Out-Null
        $action = New-ScheduledTaskAction -Execute $shell -Argument $taskArguments -WorkingDirectory $repository
        if ($Trigger -eq 'AtStartup') {
            $triggerDefinition = New-ScheduledTaskTrigger -AtStartup
        }
        else {
            $triggerDefinition = New-ScheduledTaskTrigger -AtLogOn -User $userId
        }
        $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
        $principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Limited
    }
    catch {
        throw "Could not prepare Windows Task Scheduler configuration. Confirm the Task Scheduler service is available and the current account may register tasks. Details: $($_.Exception.Message)"
    }
    if ($null -ne $existing) {
        Stop-LiveShadowTask -TaskName $TaskName -RepositoryRoot $repository | Out-Null
        Unregister-ScheduledTask -TaskName $TaskName -TaskPath '\' -Confirm:$false
    }
    Register-ScheduledTask -TaskName $TaskName -TaskPath '\' -Action $action -Trigger $triggerDefinition -Settings $settings -Principal $principal -Description 'CalibraXI prospective live-shadow collection worker.' | Out-Null
    [pscustomobject]@{
        task_name = $TaskName
        task_path = '\'
        trigger = $Trigger
        python = $python
        repository = $repository
        log_directory = $logs
        multiple_instances = 'IgnoreNew'
        restart_count = 3
        status = 'registered'
    } | ConvertTo-Json -Compress
}
