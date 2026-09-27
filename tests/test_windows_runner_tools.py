from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def test_windows_runner_tooling_is_repository_managed_and_complete():
    expected = {
        "live_shadow_task_common.ps1",
        "run_live_shadow_task.ps1",
        "setup_live_shadow_task.ps1",
        "remove_live_shadow_task.ps1",
        "status_live_shadow_task.ps1",
        "restart_live_shadow_task.ps1",
    }
    assert expected <= {path.name for path in SCRIPTS.glob("*.ps1")}
    assert (ROOT / "docs" / "operations-live-shadow-windows.md").exists()


def test_task_definition_is_singleton_safe_and_does_not_embed_credentials():
    setup = (SCRIPTS / "setup_live_shadow_task.ps1").read_text(encoding="utf-8")
    wrapper = (SCRIPTS / "run_live_shadow_task.ps1").read_text(encoding="utf-8")

    assert "-MultipleInstances IgnoreNew" in setup
    assert "-RestartCount 3" in setup
    assert "run_live_shadow_task.ps1" in setup
    assert "Global\\CalibraXI.LiveShadow" in wrapper
    assert "run_live_shadow.py" in wrapper
    assert "--stop-file" in wrapper
    assert "Resolve-LiveShadowStopFile" in wrapper
    assert "& $python @pythonArguments" in wrapper
    assert "System.Diagnostics.ProcessStartInfo" not in wrapper
    assert wrapper.index("$mutex.WaitOne") < wrapper.index("Remove-Item -LiteralPath $stopFile")
    assert "CALIBRAXI_POSTGRES_DSN" not in setup
    assert "CALIBRAXI_MINIO_ENDPOINT_URL" not in setup
    assert "AWS_SECRET_ACCESS_KEY" not in setup


def test_lifecycle_scripts_stop_before_remove_and_wait_for_restart():
    remove = (SCRIPTS / "remove_live_shadow_task.ps1").read_text(encoding="utf-8")
    restart = (SCRIPTS / "restart_live_shadow_task.ps1").read_text(encoding="utf-8")

    assert "Stop-LiveShadowTask" in remove
    assert "Unregister-ScheduledTask" in remove
    assert "Stop-LiveShadowTask" in restart
    assert "Start-ScheduledTask" in restart
    assert "Wait-LiveShadowTaskState" in restart
    assert "RepositoryRoot" in remove
    assert "RepositoryRoot" in restart
