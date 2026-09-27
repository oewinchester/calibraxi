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
    [pscustomobject]@{ task_name = $TaskName; status = 'not_registered' } | ConvertTo-Json -Compress
    exit 0
}

if ($PSCmdlet.ShouldProcess($TaskName, 'stop and unregister CalibraXI live-shadow scheduled task')) {
    $repository = Resolve-LiveShadowRepositoryRoot -RepositoryRoot $RepositoryRoot
    Stop-LiveShadowTask -TaskName $TaskName -RepositoryRoot $repository -TimeoutSeconds $TimeoutSeconds | Out-Null
    Unregister-ScheduledTask -TaskName $TaskName -TaskPath '\' -Confirm:$false
    Clear-LiveShadowStopRequest -RepositoryRoot $repository
    [pscustomobject]@{ task_name = $TaskName; status = 'removed' } | ConvertTo-Json -Compress
}
