# CalibraXI — Local Codex Handoff v13

Fresh continuation package generated 2026-09-22.

## Before setup

Verify:

```powershell
git rev-parse --show-toplevel
git remote -v
git status
```

The previously seen `oewinchester/power` remote is **not confirmed** as CalibraXI. Do not bind GitHub Issues/wayfinder or push to it until explicitly confirmed.

## Read order after setup

1. `AGENTS.md`
2. `CONTEXT.md`
3. `docs/CalibraXI.md`
4. `docs/CalibraXI-Analytics-Architecture.md`
5. `docs/CalibraXI-Engineering.md`
6. `prompts/START-CODEX.md`

## Current source

`docs/CalibraXI.md` is the living document. `docs/CalibraXI-v13.md` is the immutable handoff snapshot.

## New locked decision

CalibraXI owns a multi-source data acquisition platform. SoccerData is an adapter/accelerator only. Preferred direction: Python + Scrapy + direct HTTP/JSON + Playwright fallback + Redis + PostgreSQL + S3/MinIO.

## Next architecture task

Recommendation + Curation. Do not start implementation unless explicitly requested.
