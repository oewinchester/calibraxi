# Live Shadow Operations Plan

> **For agentic workers:** Execute inline in this session. The phase contract in the user request is authoritative.

**Goal:** Make the existing true-PIT shadow collector deployable and verify contemporaneous persistence without treating replayed timestamps as live evidence.

**Architecture:** Add a built-in runner factory that composes only permitted ESPN/Sofascore adapters, append-only PostgreSQL operational stores, MinIO raw evidence, and the existing 33-season reconstructed archive. Keep provider-ID translation gates intact and separate schedule discovery cadence from the short collection/settlement cycle. Review-required providers stay inactive until their rights state is reviewed.

**Tech Stack:** Python 3.12+, existing CalibraXI adapters, PostgreSQL, MinIO, pytest.

**Spec:** User request “LIVE SHADOW FORECASTING — TRUE-PIT PROSPECTIVE COLLECTION — RELIABILITY OBSERVATORY — TRACK RECORD FOUNDATION”; `docs/CalibraXI-Analytics-Architecture.md`; `docs/CalibraXI-Engineering.md`.

## Global Constraints

- Keep the immutable feature-information cutoff separate from store-assigned `prediction_cutoff_at`; count no run unless `persisted_at <= prediction_cutoff_at < kickoff_at` and all run timestamps are within the evaluation's as-of boundary.
- Enforce approved/permitted source policies in the live runner and require governed provider IDs for detail requests; do not provide a runtime override for `review_required` sources.
- Missed horizons remain missed; no late fetch is assigned to an earlier horizon.
- Keep reconstructed history separate from prospective actual-knowledge data.
- Do not add Signals, Recommendations, betting, frontend publication, or monetization.

## Review Focus

- Missing database or object-store configuration must fail before collection rather than silently selecting a local store.
- A restart must rediscover only on its cadence while collection and settlement continue each cycle.
- Provider detail calls without an adjudicated provider ID must remain unavailable and must never reuse an ESPN ID.
- Understat remains explicitly unsupported when its adapter or provider fixture ID is unavailable.
- Fresh smoke evidence must show database/object persistence after actual retrieval time and before kickoff.

### Task 1: Built-in production-like runner factory

**Files:** create `src/calibraxi_data/live_factory.py`; modify `scripts/run_live_shadow.py`; test `tests/test_live_runner_entrypoint.py` and a focused factory test.

- [x] Add tests for default-factory resolution, missing explicit source opt-in, and provider-specific adapters.
- [x] Verify those tests fail because no built-in factory exists.
- [x] Compose the fixed model set, archive history, PostgreSQL stores, and MinIO evidence without bypassing capability policy.
- [x] Run focused entrypoint/factory tests.

### Task 2: Discovery cadence and horizon coverage

**Files:** modify `scripts/run_live_shadow.py`; test `tests/test_live_runner_entrypoint.py`.

- [x] Add a test proving discovery happens initially and at its configured interval while collection runs on every cycle.
- [x] Run it to verify current behavior fails.
- [x] Add a six-hour discovery cadence and a ten-day default discovery window; retain one-minute collection cycles and retry behavior.
- [x] Run focused runner tests.

### Task 3: Live persistence and release verification

**Files:** canonical analytics/engineering docs only where implementation behavior changes.

- [x] Exercise the PostgreSQL knowledge-ledger and MinIO payload/manifest APIs with temporary smoke rows; verify readback and remove the smoke rows.
- [ ] Run a fresh one-shot against real upcoming EPL fixtures with actual runtime timestamps. Blocked at the access boundary: the runner was executed and refused before collection because eight ESPN/Sofascore/Understat capabilities remain `review_required`; do not activate without that access review.
- [x] Verify stored forecasts against persisted time, separate feature/prediction cutoffs, kickoff, and actual-source lineage; legacy replay rows without a store-assigned prediction cutoff remain excluded.
- [x] Re-run focused tests, full pytest, `compileall`, and `git diff --check` after timestamp-semantics correction; 326 tests passed, and the real PostgreSQL forecast/MinIO evidence round trips passed with smoke records removed.
- [ ] Commit and push the verified work to the explicitly requested `origin/main`; verify remote SHA and clean status.
