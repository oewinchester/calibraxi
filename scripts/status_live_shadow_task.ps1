[CmdletBinding()]
param(
    [string]$TaskName = 'CalibraXI-LiveShadow',
    [switch]$Json
)

Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'live_shadow_task_common.ps1')

$task = Get-LiveShadowTask -TaskName $TaskName
if ($null -eq $task) {
    $status = [pscustomobject]@{ task_name = $TaskName; registered = $false; state = 'NotRegistered' }
}
else {
    $info = Get-ScheduledTaskInfo -TaskName $TaskName -TaskPath '\'
    $status = [pscustomobject]@{
        task_name = $TaskName
        task_path = '\'
        registered = $true
        state = $task.State.ToString()
        last_run_time = $info.LastRunTime.ToUniversalTime().ToString('o')
        last_task_result = $info.LastTaskResult
        next_run_time = if ($info.NextRunTime -and $info.NextRunTime -ne [datetime]::MinValue) { $info.NextRunTime.ToUniversalTime().ToString('o') } else { $null }
        action = ($task.Actions | ForEach-Object { $_.Execute + ' ' + $_.Arguments }) -join ' '
        multiple_instances = $task.Settings.MultipleInstances
    }
}

if ($Json) {
    $status | ConvertTo-Json -Compress
}
else {
    $status | Format-List
}
