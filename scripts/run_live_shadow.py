"""Production-like entry point for the prospective shadow worker.

The built-in factory composes the PostgreSQL/MinIO runner. Deployments may
override it with ``CALIBRAXI_LIVE_RUNNER_FACTORY`` or ``--runner-factory``.
Provider rights, storage credentials, and service endpoints remain explicit
deployment configuration. The same cycle function supports one-shot smoke
runs and continuously scheduled operation.
"""

from __future__ import annotations

import argparse
import importlib
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


UTC = timezone.utc
LOGGER = logging.getLogger("calibraxi.live_shadow")


def _date_window(now: datetime, count: int) -> tuple[str, ...]:
    start = now.astimezone(UTC).date()
    return tuple((start + timedelta(days=offset)).strftime("%Y%m%d") for offset in range(max(1, count)))


def run_cycle(runner: Any, dates: Iterable[str], *, now: datetime | None = None) -> Mapping[str, Any]:
    """Discover, collect, forecast, settle, and refresh measurements once."""

    current = now or datetime.now(UTC)
    discovery = runner.discover_upcoming(tuple(str(date) for date in dates), now=now)
    cycle = runner.run_once(now=now)
    first_observed_forecasts = int(getattr(discovery, "forecast_count", 0))
    cycle_forecasts = int(getattr(cycle, "forecast_count", 0))
    return {
        "observed_at": current.astimezone(UTC).isoformat(),
        "discovered_fixture_count": len(discovery.fixtures),
        "scheduled_task_count": discovery.scheduled_task_count,
        "knowledge_entry_count": discovery.knowledge_entry_count,
        "first_observed_forecast_count": first_observed_forecasts,
        "forecast_count": first_observed_forecasts + cycle_forecasts,
        "failed_dates": list(discovery.failed_dates),
        "discovery_states": dict(getattr(discovery, "states", {}) or {}),
        "cached_fallback_dates": list(getattr(discovery, "cached_fallback_dates", ()) or ()),
        "cached_fallback_fixture_count": int(getattr(discovery, "cached_fallback_fixture_count", 0) or 0),
        "cycle": cycle,
    }


def run_forever(
    runner: Any,
    dates_provider: Callable[[], Iterable[str]],
    *,
    interval_seconds: float = 60.0,
    discovery_interval_seconds: float = 6 * 60 * 60,
    once: bool = False,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], datetime] | None = None,
    on_cycle: Callable[[Mapping[str, Any]], None] | None = None,
    on_error: Callable[[Exception], None] | None = None,
    stop_file: str | os.PathLike[str] | None = None,
) -> int:
    """Run the worker with startup diagnostics and an optional durable lease."""

    lease_store = getattr(runner, "worker_lease_store", None)
    guard = None
    if lease_store is not None:
        # Import lazily so the CLI remains usable with lightweight injected
        # runners and so lease composition stays outside model code.
        from calibraxi_data.live_runner import WorkerLeaseGuard

        guard = WorkerLeaseGuard(
            lease_store,
            os.environ.get("CALIBRAXI_WORKER_LEASE_KEY", "live-shadow"),
            clock=clock,
        )
        if not guard.acquire():
            LOGGER.error("live shadow worker lease is already held", extra={"lease_key": guard.lease_key})
            return 2

    try:
        startup_preflight = getattr(runner, "preflight", None)
        if callable(startup_preflight):
            try:
                reports = startup_preflight()
                LOGGER.info("live shadow startup preflight: %s", reports)
            except Exception:
                # Diagnostics are read-only and must not prevent the worker
                # from retaining fallback resilience during a probe outage.
                LOGGER.exception("live shadow startup preflight failed")

        wrapped_on_cycle = on_cycle
        if guard is not None:
            def wrapped_on_cycle(result: Mapping[str, Any]) -> None:
                if on_cycle is not None:
                    on_cycle(result)
                if not guard.renew():
                    raise RuntimeError(f"worker lease lost: {guard.lease_key}")

        return _run_forever(
            runner,
            dates_provider,
            interval_seconds=interval_seconds,
            discovery_interval_seconds=discovery_interval_seconds,
            once=once,
            sleep=sleep,
            clock=clock,
            on_cycle=wrapped_on_cycle,
            on_error=on_error,
            stop_file=stop_file,
        )
    finally:
        if guard is not None:
            guard.release()


def _run_forever(
    runner: Any,
    dates_provider: Callable[[], Iterable[str]],
    *,
    interval_seconds: float = 60.0,
    discovery_interval_seconds: float = 6 * 60 * 60,
    once: bool = False,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], datetime] | None = None,
    on_cycle: Callable[[Mapping[str, Any]], None] | None = None,
    on_error: Callable[[Exception], None] | None = None,
    stop_file: str | os.PathLike[str] | None = None,
) -> int:
    """Run restart-safe cycles until interrupted, stopped, or ``once`` is requested.

    ``stop_file`` is a small local-process control plane for unattended hosts
    such as Windows Task Scheduler.  The worker checks it between cycles and
    exits cleanly with status zero; it never changes persisted forecast state.
    """

    if interval_seconds < 0:
        raise ValueError("interval_seconds cannot be negative")
    if discovery_interval_seconds <= 0:
        raise ValueError("discovery_interval_seconds must be positive")
    current_time = clock or (lambda: datetime.now(UTC))
    stop_path = Path(stop_file) if stop_file else None
    next_discovery_at: datetime | None = None

    def stop_requested() -> bool:
        return stop_path is not None and stop_path.exists()

    def wait_until_next_cycle() -> bool:
        if stop_path is None:
            sleep(interval_seconds)
            return False
        remaining = interval_seconds
        while remaining > 0:
            if stop_requested():
                return True
            portion = min(1.0, remaining)
            sleep(portion)
            remaining -= portion
        return stop_requested()

    while True:
        if stop_requested():
            LOGGER.info("live shadow stop requested", extra={"stop_file": str(stop_path)})
            return 0
        current = current_time().astimezone(UTC)
        discovery_due = next_discovery_at is None or current >= next_discovery_at
        try:
            result = run_cycle(runner, dates_provider() if discovery_due else ())
        except Exception as exc:
            LOGGER.exception("live shadow cycle failed")
            if on_error is not None:
                on_error(exc)
            if once:
                return 1
            if discovery_due:
                next_discovery_at = current + timedelta(seconds=min(discovery_interval_seconds, 300))
            if wait_until_next_cycle():
                LOGGER.info("live shadow stop requested", extra={"stop_file": str(stop_path)})
                return 0
            continue
        if discovery_due:
            delay = min(discovery_interval_seconds, 300) if result["failed_dates"] else discovery_interval_seconds
            next_discovery_at = current + timedelta(seconds=delay)
        if on_cycle is not None:
            on_cycle(result)
        else:
            LOGGER.info("live shadow cycle: %s", result)
        if once:
            return 1 if result["failed_dates"] else 0
        if stop_requested():
            LOGGER.info("live shadow stop requested", extra={"stop_file": str(stop_path)})
            return 0
        if wait_until_next_cycle():
            LOGGER.info("live shadow stop requested", extra={"stop_file": str(stop_path)})
            return 0


def _load_factory(specification: str) -> Any:
    module_name, separator, function_name = specification.partition(":")
    if not separator or not module_name or not function_name:
        raise ValueError("runner factory must use package.module:function syntax")
    factory = getattr(importlib.import_module(module_name), function_name)
    if not callable(factory):
        return factory
    runner = factory()
    # Deployment factories may return either a configured runner or a second
    # zero-argument factory.  A runner is identified by the two methods the
    # loop invokes, so callable runner objects are not accidentally executed.
    if hasattr(runner, "discover_upcoming") and hasattr(runner, "run_once"):
        return runner
    if callable(runner):
        runner = runner()
    return runner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run CalibraXI prospective EPL shadow collection")
    parser.add_argument("--once", action="store_true", help="run one discovery/collection cycle")
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--discovery-interval-seconds", type=float, default=6 * 60 * 60, help="delay between full schedule discoveries")
    parser.add_argument("--days", type=int, default=10, help="number of UTC schedule dates to discover")
    parser.add_argument("--date", dest="dates", action="append", help="explicit YYYYMMDD schedule date; repeatable")
    parser.add_argument(
        "--runner-factory",
        default=os.environ.get("CALIBRAXI_LIVE_RUNNER_FACTORY", "calibraxi_data.live_factory:create_live_shadow_runner"),
        help="configured runner factory; defaults to the built-in PostgreSQL/MinIO runner",
    )
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--stop-file", help="exit cleanly between cycles when this local file exists")
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    runner = _load_factory(args.runner_factory)
    explicit_dates = tuple(args.dates or ())
    return run_forever(
        runner,
        lambda: explicit_dates or _date_window(datetime.now(UTC), args.days),
        interval_seconds=args.interval_seconds,
        discovery_interval_seconds=args.discovery_interval_seconds,
        once=args.once,
        stop_file=args.stop_file,
    )


if __name__ == "__main__":  # pragma: no cover - exercised through CLI smoke
    raise SystemExit(main())
