# CONTEXT.md — CalibraXI Handoff v13

Date: 2026-09-22

Canonical living document: `docs/CalibraXI.md`
Snapshot: `docs/CalibraXI-v13.md`

CalibraXI is a Predictive Football Analytics product. Tagline: **Football, Calibrated.**

Desktop nav: `Matches | Projections | Stats | Markets | Studio | Track Record`
Mobile: `Home | Matches | Projections | Studio | My`

Major surfaces already specified: Home, Matches/Match Center, Projections/Explorer, Stats/Power Rankings, Competition/Team/Player, Markets, Studio, Track Record, My CalibraXI, Watchlist/Alerts, Simulations, Strategy Lab.

## Source acquisition

Critical locked direction: multi-source CalibraXI-owned acquisition platform.

Preferred stack: Python 3.12+, Scrapy, direct HTTP/JSON, Playwright fallback, Parsel/lxml, Redis, PostgreSQL, S3/MinIO.

SoccerData is approved as adapter/accelerator, not canonical authority.

All football/stat/player/fixture/asset data passes through raw observations, validation, entity resolution, source/conflict policy, PIT chronology and canonicalization before models consume it.

Important: Source data != canonical truth. SoccerData normalization != canonical entity resolution. Missing != zero != unsupported != failed. Parser schema drift must degrade/quarantine, not write false empty data. Assets need provenance + usage/license state.

## Repository warning

The previously detected `oewinchester/power` Git remote is not confirmed as CalibraXI. Verify repo root/remote and ask/confirm before configuring GitHub Issues or pushing.

## Next task

Recommendation + Curation Architecture.
