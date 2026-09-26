from datetime import datetime, timedelta, timezone
import sys
import types

import scripts.run_live_shadow as live_entrypoint
from scripts.run_live_shadow import _load_factory, run_cycle, run_forever


UTC = timezone.utc


class FakeRunner:
    def __init__(self):
        self.calls = []

    def discover_upcoming(self, dates, *, now):
        self.calls.append(("discover", tuple(dates), now))
        return type("Discovery", (), {"fixtures": ("fixture",), "scheduled_task_count": 2, "knowledge_entry_count": 1, "forecast_count": 3, "failed_dates": ()})()

    def run_once(self, *, now):
        self.calls.append(("cycle", now))
        return type("Cycle", (), {"forecast_count": 4})()


def test_run_cycle_uses_same_clock_for_discovery_and_collection():
    runner = FakeRunner()
    now = datetime(2026, 9, 26, 12, tzinfo=UTC)
    result = run_cycle(runner, ("20260926",), now=now)

    assert result["discovered_fixture_count"] == 1
    assert result["scheduled_task_count"] == 2
    assert result["knowledge_entry_count"] == 1
    assert result["first_observed_forecast_count"] == 3
    assert result["forecast_count"] == 7
    assert runner.calls[0] == ("discover", ("20260926",), now)
    assert runner.calls[1] == ("cycle", now)


def test_run_cycle_leaves_runtime_clock_to_runner_when_now_is_not_supplied():
    runner = FakeRunner()

    run_cycle(runner, ("20260926",))

    assert runner.calls[0] == ("discover", ("20260926",), None)
    assert runner.calls[1] == ("cycle", None)


def test_run_forever_once_is_restart_safe_and_does_not_sleep():
    runner = FakeRunner()
    emitted = []
    slept = []
    status = run_forever(
        runner,
        lambda: ("20260926",),
        interval_seconds=30,
        once=True,
        sleep=slept.append,
        clock=lambda: datetime(2026, 9, 26, 12, tzinfo=UTC),
        on_cycle=emitted.append,
    )

    assert status == 0
    assert len(emitted) == 1
    assert slept == []


def test_run_forever_once_returns_failure_when_fixture_discovery_fails():
    class FailedDiscoveryRunner(FakeRunner):
        def discover_upcoming(self, dates, *, now):
            self.calls.append(("discover", tuple(dates), now))
            return type(
                "Discovery",
                (),
                {
                    "fixtures": (),
                    "scheduled_task_count": 0,
                    "knowledge_entry_count": 0,
                    "forecast_count": 0,
                    "failed_dates": ("20261017",),
                },
            )()

    status = run_forever(
        FailedDiscoveryRunner(),
        lambda: ("20261017",),
        once=True,
        clock=lambda: datetime(2026, 9, 26, 12, tzinfo=UTC),
    )

    assert status == 1


def test_run_forever_retries_after_transient_cycle_failure():
    class FlakyRunner(FakeRunner):
        def __init__(self):
            super().__init__()
            self.cycle_attempts = 0

        def run_once(self, *, now):
            self.cycle_attempts += 1
            if self.cycle_attempts == 1:
                raise RuntimeError("temporary persistence outage")
            return super().run_once(now=now)

    class StopLoop(Exception):
        pass

    runner = FlakyRunner()
    errors = []
    sleeps = []

    def stop_after_recovery(interval):
        sleeps.append(interval)
        if len(sleeps) == 2:
            raise StopLoop

    try:
        run_forever(
            runner,
            lambda: ("20260926",),
            interval_seconds=7,
            sleep=stop_after_recovery,
            clock=lambda: datetime(2026, 9, 26, 12, tzinfo=UTC),
            on_error=errors.append,
        )
    except StopLoop:
        pass
    else:
        raise AssertionError("test loop should stop after two cycles")

    assert runner.cycle_attempts == 2
    assert len(errors) == 1 and "temporary persistence outage" in str(errors[0])
    assert sleeps == [7, 7]


def test_run_forever_discovery_cadence_does_not_skip_collection_cycles():
    class StopLoop(Exception):
        pass

    runner = FakeRunner()
    current = [datetime(2026, 9, 26, 12, tzinfo=UTC)]
    discovery_calls = []
    sleeps = []

    def dates_provider():
        discovery_calls.append(current[0])
        return ("20260926",)

    def advance(interval):
        sleeps.append(interval)
        current[0] += timedelta(seconds=interval)
        if len(sleeps) == 3:
            raise StopLoop

    try:
        run_forever(
            runner,
            dates_provider,
            interval_seconds=10,
            discovery_interval_seconds=20,
            sleep=advance,
            clock=lambda: current[0],
        )
    except StopLoop:
        pass
    else:
        raise AssertionError("test loop should stop after three collection cycles")

    assert len([call for call in runner.calls if call[0] == "cycle"]) == 3
    assert discovery_calls == [current[0] - timedelta(seconds=30), current[0] - timedelta(seconds=10)]
    assert [call[1] for call in runner.calls if call[0] == "discover"] == [
        ("20260926",),
        (),
        ("20260926",),
    ]


def test_main_defaults_to_builtin_live_runner_factory(monkeypatch):
    monkeypatch.delenv("CALIBRAXI_LIVE_RUNNER_FACTORY", raising=False)
    requested = []
    runner = FakeRunner()
    monkeypatch.setattr(live_entrypoint, "_load_factory", lambda value: requested.append(value) or runner)
    monkeypatch.setattr(live_entrypoint, "run_forever", lambda configured, *args, **kwargs: 0)

    assert live_entrypoint.main(["--once"]) == 0
    assert requested == ["calibraxi_data.live_factory:create_live_shadow_runner"]


def test_load_factory_resolves_nested_zero_argument_factory(monkeypatch):
    module = types.ModuleType("test_live_factory_module")
    runner = FakeRunner()
    module.make_runner = lambda: (lambda: runner)
    monkeypatch.setitem(sys.modules, module.__name__, module)

    assert _load_factory(f"{module.__name__}:make_runner") is runner


def test_load_factory_does_not_invoke_callable_runner(monkeypatch):
    module = types.ModuleType("test_live_callable_runner_module")

    class CallableRunner(FakeRunner):
        def __call__(self):
            raise AssertionError("configured runner must not be invoked")

    runner = CallableRunner()
    module.make_runner = lambda: runner
    monkeypatch.setitem(sys.modules, module.__name__, module)

    assert _load_factory(f"{module.__name__}:make_runner") is runner
