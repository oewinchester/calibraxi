[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$TaskName = 'CalibraXI-LiveShadow',
    [string]$RepositoryRoot,
    [int]$TimeoutSeconds = 120
)

Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'live_shadow_task_common.ps1')

$task = Get-LiveShadowTask -TaskName $TaskName
if ($null -eq $task) {
    throw "Scheduled task is not registered: $TaskName. Run setup_live_shadow_task.ps1 first."
}

if ($PSCmdlet.ShouldProcess($TaskName, 'restart CalibraXI live-shadow scheduled task')) {
    $repository = Resolve-LiveShadowRepositoryRoot -RepositoryRoot $RepositoryRoot
    Stop-LiveShadowTask -TaskName $TaskName -RepositoryRoot $repository -TimeoutSeconds $TimeoutSeconds | Out-Null
    Clear-LiveShadowStopRequest -RepositoryRoot $repository
    Start-ScheduledTask -TaskName $TaskName -TaskPath '\'
    if (-not (Wait-LiveShadowTaskState -TaskName $TaskName -State Running -TimeoutSeconds $TimeoutSeconds)) {
        throw "Timed out waiting for scheduled task to start: $TaskName"
    }
    [pscustomobject]@{ task_name = $TaskName; status = 'restarted'; state = 'Running' } | ConvertTo-Json -Compress
}
