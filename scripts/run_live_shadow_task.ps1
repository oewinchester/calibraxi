[CmdletBinding()]
param(
    [string]$RepositoryRoot,
    [string]$PythonPath,
    [double]$IntervalSeconds = 60,
    [double]$DiscoveryIntervalSeconds = 21600,
    [int]$Days = 10,
    [string[]]$Date,
    [string]$RunnerFactory,
    [string]$LogDirectory
)

Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot 'live_shadow_task_common.ps1')

$repository = Resolve-LiveShadowRepositoryRoot -RepositoryRoot $RepositoryRoot
$python = Resolve-LiveShadowPython -PythonPath $PythonPath
$logs = Resolve-LiveShadowLogDirectory -RepositoryRoot $repository -LogDirectory $LogDirectory -Create
$stopFile = Resolve-LiveShadowStopFile -RepositoryRoot $repository
$logPath = Join-Path $logs ("live-shadow-{0}.jsonl" -f (Get-Date).ToUniversalTime().ToString('yyyyMMdd'))
$mutex = New-Object -TypeName System.Threading.Mutex -ArgumentList $false, 'Global\CalibraXI.LiveShadow'
$mutexHeld = $false

function Write-LiveShadowLog {
    param(
        [ValidateSet('INFO', 'WARN', 'ERROR')][string]$Level,
        [string]$Event,
        [string]$Message,
        [hashtable]$Fields = @{}
    )

    $record = [ordered]@{
        timestamp = (Get-Date).ToUniversalTime().ToString('o')
        level = $Level
        event = $Event
        message = $Message
        process_id = $PID
    }
    foreach ($entry in $Fields.GetEnumerator()) {
        $record[$entry.Key] = $entry.Value
    }
    Add-Content -LiteralPath $logPath -Value (($record | ConvertTo-Json -Compress)) -Encoding UTF8
}

try {
    try {
        $mutexHeld = $mutex.WaitOne(0)
    }
    catch [System.Threading.AbandonedMutexException] {
        $mutexHeld = $true
    }
    if (-not $mutexHeld) {
        Write-LiveShadowLog -Level WARN -Event 'singleton_skip' -Message 'A live-shadow worker already holds the process mutex.'
        exit 0
    }
    # Only the owner may clear a prior stop request. A duplicate invocation
    # must never cancel an administrator's graceful shutdown request.
    Remove-Item -LiteralPath $stopFile -Force -ErrorAction SilentlyContinue

    $arguments = @(
        (Join-Path $repository 'scripts\run_live_shadow.py'),
        '--interval-seconds', $IntervalSeconds.ToString([Globalization.CultureInfo]::InvariantCulture),
        '--discovery-interval-seconds', $DiscoveryIntervalSeconds.ToString([Globalization.CultureInfo]::InvariantCulture),
        '--days', $Days.ToString([Globalization.CultureInfo]::InvariantCulture),
        '--stop-file', $stopFile
    )
    foreach ($value in ($Date | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })) {
        $arguments += @('--date', $value)
    }
    if (-not [string]::IsNullOrWhiteSpace($RunnerFactory)) {
        $arguments += @('--runner-factory', $RunnerFactory)
    }

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $python
    $startInfo.WorkingDirectory = $repository
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    # Windows PowerShell 5.1 runs on .NET Framework, whose
    # ProcessStartInfo has no ArgumentList property.  Keep the wrapper
    # compatible with both Windows PowerShell and PowerShell 7 by constructing
    # one quoted command line from the already controlled argument values.
    $startInfo.Arguments = ($arguments | ForEach-Object {
        ConvertTo-LiveShadowArgument -Value ([string]$_)
    }) -join ' '

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    $process.EnableRaisingEvents = $true
    $process.add_OutputDataReceived({
        param($sender, $event)
        if ($null -ne $event.Data) {
            Write-LiveShadowLog -Level INFO -Event 'worker_output' -Message $event.Data -Fields @{ stream = 'stdout' }
        }
    })
    $process.add_ErrorDataReceived({
        param($sender, $event)
        if ($null -ne $event.Data) {
            Write-LiveShadowLog -Level ERROR -Event 'worker_output' -Message $event.Data -Fields @{ stream = 'stderr' }
        }
    })

    Write-LiveShadowLog -Level INFO -Event 'worker_start' -Message 'Starting live-shadow worker.' -Fields @{ python = $python; repository = $repository }
    if (-not $process.Start()) {
        throw 'Python worker process did not start.'
    }
    $process.BeginOutputReadLine()
    $process.BeginErrorReadLine()
    $process.WaitForExit()
    Start-Sleep -Milliseconds 100
    $exitCode = $process.ExitCode
    Write-LiveShadowLog -Level INFO -Event 'worker_exit' -Message 'Live-shadow worker exited.' -Fields @{ exit_code = $exitCode }
    exit $exitCode
}
catch {
    try {
        Write-LiveShadowLog -Level ERROR -Event 'worker_wrapper_error' -Message $_.Exception.Message -Fields @{ exception_type = $_.Exception.GetType().FullName }
    }
    catch {
        Write-Error $_
    }
    exit 1
}
finally {
    if ($mutexHeld) {
        $mutex.ReleaseMutex()
    }
    $mutex.Dispose()
}
