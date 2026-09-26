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
) -> int:
    """Run restart-safe cycles until interrupted or ``once`` is requested."""

    if interval_seconds < 0:
        raise ValueError("interval_seconds cannot be negative")
    if discovery_interval_seconds <= 0:
        raise ValueError("discovery_interval_seconds must be positive")
    current_time = clock or (lambda: datetime.now(UTC))
    next_discovery_at: datetime | None = None
    while True:
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
            sleep(interval_seconds)
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
        sleep(interval_seconds)


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
    )


if __name__ == "__main__":  # pragma: no cover - exercised through CLI smoke
    raise SystemExit(main())
