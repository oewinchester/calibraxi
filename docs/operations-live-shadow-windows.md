# Windows live-shadow operations

The repository includes a user-scoped Windows Task Scheduler setup for the unattended prospective worker. It invokes the existing `scripts/run_live_shadow.py` entrypoint from the repository root and leaves database, MinIO, provider, and AWS credentials in the task user's normal environment. No secret is copied into the task definition or checked into the repository.

From PowerShell, register the task at user logon:

```powershell
.\scripts\setup_live_shadow_task.ps1
```

Use `-Trigger AtStartup` only when the account and environment are available before logon. Use `-PythonPath` or `CALIBRAXI_PYTHON` to select a virtual-environment interpreter. `CALIBRAXI_POSTGRES_DSN`, `CALIBRAXI_MINIO_ENDPOINT_URL`, `CALIBRAXI_MINIO_BUCKET`, provider configuration, and standard AWS credentials remain external environment configuration. Make required variables persistent in the task user's user/system environment; setup does not serialize shell-local variables or secrets.

The task is configured with `MultipleInstances=IgnoreNew` and restarts up to three times with a one-minute delay. The wrapper also takes the named `Global\CalibraXI.LiveShadow` mutex, so an accidental second invocation exits without starting another Python worker. Each wrapper start, output line, exit, and error is written as JSON Lines under `temp\live-shadow\logs` by default.

```powershell
.\scripts\status_live_shadow_task.ps1 -Json
.\scripts\restart_live_shadow_task.ps1
.\scripts\remove_live_shadow_task.ps1
```

`remove_live_shadow_task.ps1` stops the scheduled task before unregistering it. `restart_live_shadow_task.ps1` requires an existing registration and waits for the task to reach `Running`; the worker's durable lease remains the authority for coordinating persisted work after a process restart.

When a task was registered with `-RepositoryRoot`, pass the same value to the remove or restart command so graceful stop requests use the same per-user control path.
