# AGENTS.md — CalibraXI

## Read first

Read `CONTEXT.md`, `docs/CalibraXI.md`, `docs/CalibraXI-Analytics-Architecture.md`, `docs/CalibraXI-Engineering.md`, then relevant frozen legacy architecture/ADRs.

## Repository identity warning

The previously detected remote `oewinchester/power` is NOT confirmed as CalibraXI. Do not configure GitHub Issues, create issues/PR workflow, attach wayfinder, push, or otherwise bind project workflow to that remote until the user explicitly confirms it.

## UTF-8

Markdown is UTF-8. If terminal renders `—` as mojibake like `â€”`, fix terminal encoding; do not rewrite source with corrupted characters.

## Authority

1. `docs/CalibraXI.md` current living product spec.
2. Frozen analytical/domain architecture for concepts it owns.
3. Repository implementation as evidence, not automatic authority.
4. Legacy UI/product behavior as migration evidence.

## Core invariants

- Stable Fixture + schedule revisions.
- PIT chronology.
- Immutable Evidence Manifest / Feature Snapshot / Prediction Run.
- PRE_MATCH != LIVE.
- append/supersede, not destructive mutation.
- one canonical Primary Distribution per Run × family.
- no runtime model shopping.
- parent/family-level calibration.
- Forecast Probability != Reliability != Signal != Recommendation.
- Market Observation does not mutate Forecast.
- Track Record uses immutable evaluations + explicit populations.
- same-match marginal multiplication prohibited.
- historical published/placed artifacts never silently rewrite.

## Source acquisition — LOCKED WORKING DIRECTION

Preferred stack: Python 3.12+, Scrapy, direct HTTP/XHR/JSON, Playwright fallback, Parsel/lxml, Redis, PostgreSQL, S3-compatible storage/MinIO.

SoccerData: YES as adapter/accelerator; NO as sole ingestion platform, canonical schema, truth authority or provenance store.

Mandatory flow:
`Source → Raw Observation → Parser → Normalized Observation → Validation → Entity Resolution → Source/Conflict Policy → PIT Eligibility → Canonical Data → Feature Snapshot`

Model/business code must not directly depend on source-specific scraper libraries. Missing != zero != unsupported != source failure. Source breakage degrades/quarantines a capability; it must not overwrite canonical facts with empty data. Assets use a governed provenance/licensing pipeline.

See `docs/CalibraXI-Engineering.md` for the canonical source-acquisition specification and Section 10.15 of `docs/CalibraXI.md` for the concise product boundary.

## Product locks

Brand CalibraXI. Domain calibraxi.com. Tagline **Football, Calibrated.** Light-first. Desktop nav: Matches | Projections | Stats | Markets | Studio | Track Record. Mobile: Home | Matches | Projections | Studio | My. `/my` is personal terminal. Virtual Betslip is simulation only. Public Track Record != personal performance.

## Working method

Preserve every substantive user note, integrate into the correct section, add Decision Log entries, retain supersession history, challenge weak mechanisms without discarding intent, and avoid unnecessary clarification.

## Next architecture task

Recommendation + Curation Architecture: immutable Recommendation Decision, candidate population, eligibility/gating, policy/version, reasons/non-recommend reasons, Daily Pick, Top Projection distinction, Top 10 curation, Studio daily curation, duplicate exposure/diversity/concentration, currentness/withdrawal, publication, Track Record, no retrospective backfill, no hidden recommendation via sorting.

Do not start production implementation until explicitly requested.

## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues for `oewinchester/calibraxi`; use `gh --repo oewinchester/calibraxi` for issue operations. See `docs/agents/issue-tracker.md`.

### Domain docs

The repository uses a single-context layout with lightweight wayfinding to the three canonical CalibraXI documents. See `docs/agents/domain.md`.
