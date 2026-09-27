from datetime import timedelta

from calibraxi_data import (
    AcquisitionAttempt,
    AcquisitionResult,
    CapabilityState,
    Horizon,
    ObservationState,
    SourceResult,
)
from calibraxi_data.sofascore import SofascoreObservationParser

from test_live_runner import BASE, _evidence, _runner, _scoreboard


class PostKickoffCoordinator:
    def __init__(self, kickoff):
        self.kickoff = kickoff
        self.observation_base = BASE
        self.final = False
        self.failures = set()
        self.calls = []

    def acquire(self, capability, *, params=None, **kwargs):
        params = dict(params or {})
        self.calls.append((capability, params))
        source = "espn" if capability in {"fixtures", "lineups"} else "sofascore"
        if capability in {"xg", "xg_a"}:
            source = "understat"
        observed_at = self.observation_base + timedelta(seconds=len(self.calls))
        if capability in self.failures:
            result = SourceResult(CapabilityState.SOURCE_FAILED, source, capability, error=f"{capability} unavailable")
            attempt = AcquisitionAttempt(result, None, observed_at, observed_at)
            return AcquisitionResult(capability, CapabilityState.SOURCE_FAILED, source, None, None, (attempt,))

        if capability == "fixtures":
            payload = _scoreboard(
                self.kickoff,
                status="STATUS_FINAL" if self.final else "STATUS_SCHEDULED",
                home_score=2 if self.final else None,
                away_score=1 if self.final else None,
            )
        elif capability == "lineups":
            payload = {
                "rosters": [
                    {
                        "team": {"id": "espn-alpha"},
                        "roster": [{"athlete": {"id": "player-1", "displayName": "One"}, "starter": True}],
                    }
                ]
            }
        elif capability == "events":
            payload = {"incidents": [{"id": "incident-1", "incidentType": "goal", "time": 12}]}
        elif capability == "team_match_stats":
            payload = {"statistics": [{"period": "ALL", "groups": [{"statisticsItems": [{"name": "Possession", "home": "55%", "away": "45%"}]}]}]}
        elif capability == "player_stats":
            payload = {
                "home": {
                    "players": [
                        {"teamId": 44, "player": {"id": 7, "name": "One"}, "statistics": {"minutesPlayed": 90}}
                    ]
                }
            }
        elif capability == "shots":
            payload = {"shotmap": [{"id": 1, "xg": 0.2, "xgot": 0.3, "isHome": True}]}
        else:
            payload = {}

        evidence = _evidence(f"{source}-{capability}-{len(self.calls)}", observed_at, capability)
        result = SourceResult(CapabilityState.SUPPORTED, source, capability, payload=payload)
        attempt = AcquisitionAttempt(result, evidence, observed_at, observed_at)
        return AcquisitionResult(capability, CapabilityState.SUPPORTED, source, payload, evidence, (attempt,))


def _add_sofascore_id(runner, provider_id="sofa-100"):
    fixture = runner.fixture_store.list()[0]
    values = fixture.to_dict()
    values["provider_ids"] = {**values["provider_ids"], "sofascore": provider_id}
    runner.fixture_store.save(type(fixture).from_dict(values))
    return fixture.fixture_id


def test_run_once_collects_post_kickoff_enrichment_and_settles_when_one_capability_fails(tmp_path):
    kickoff = BASE + timedelta(hours=1)
    coordinator = PostKickoffCoordinator(kickoff)
    runner = _runner(tmp_path, coordinator, kickoff)
    runner.discover_upcoming((kickoff.strftime("%Y%m%d"),), now=BASE)
    fixture_id = _add_sofascore_id(runner)
    coordinator.failures.add("events")
    coordinator.final = True
    coordinator.calls.clear()
    coordinator.observation_base = kickoff + timedelta(minutes=5)

    cycle = runner.run_once(now=kickoff + timedelta(minutes=10))

    attempted = {capability for capability, _ in coordinator.calls}
    assert {"fixtures", "lineups", "events", "team_match_stats", "player_stats", "shots"} <= attempted
    assert cycle.settled_count == 4
    entries = [entry for entry in runner.ledger.list() if entry.fixture_id == fixture_id]
    assert any(entry.capability == "events" and entry.state is ObservationState.SOURCE_FAILED for entry in entries)
    assert all(
        entry.horizon is Horizon.EVENT
        for entry in entries
        if entry.capability in {"lineups", "events", "team_match_stats", "player_stats", "shots", "xg", "xg_a"}
    )
    assert any(entry.capability == "xg" and entry.state is ObservationState.UNSUPPORTED for entry in entries)
    assert any(entry.capability == "xg_a" and entry.state is ObservationState.UNSUPPORTED for entry in entries)
    assert any(entry.capability == "team_match_stats" and entry.state is ObservationState.SUCCESS for entry in entries)

    event_call = next(params for capability, params in coordinator.calls if capability == "events")
    lineup_call = next(params for capability, params in coordinator.calls if capability == "lineups")
    assert event_call["event_id"] == "sofa-100"
    assert lineup_call["event_id"] == "espn-100"


def test_post_kickoff_enrichment_is_bounded_until_the_next_poll_window(tmp_path):
    kickoff = BASE + timedelta(hours=1)
    coordinator = PostKickoffCoordinator(kickoff)
    runner = _runner(tmp_path, coordinator, kickoff)
    runner.discover_upcoming((kickoff.strftime("%Y%m%d"),), now=BASE)
    _add_sofascore_id(runner)
    coordinator.final = False

    coordinator.observation_base = kickoff + timedelta(minutes=5)
    runner.run_once(now=kickoff + timedelta(minutes=5))
    coordinator.calls.clear()
    coordinator.observation_base = kickoff + timedelta(minutes=9)
    runner.run_once(now=kickoff + timedelta(minutes=9))
    assert {capability for capability, _ in coordinator.calls} == set()

    coordinator.calls.clear()
    coordinator.observation_base = kickoff + timedelta(minutes=11)
    runner.run_once(now=kickoff + timedelta(minutes=11))
    assert {"lineups", "events", "team_match_stats", "player_stats", "shots"} <= {
        capability for capability, _ in coordinator.calls
    }
