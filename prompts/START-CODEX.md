# START-CODEX.md

Read in order: `AGENTS.md`, `CONTEXT.md`, `docs/CalibraXI.md`, `docs/CalibraXI-Analytics-Architecture.md`, `docs/CalibraXI-Engineering.md`.

Do not start implementation unless explicitly requested.

First verify repository identity. The previously observed `oewinchester/power` remote is NOT confirmed as CalibraXI. Do not configure GitHub Issues, create issues, push or attach workflow to that remote until confirmed.

Preserve UTF-8; terminal mojibake is not permission to rewrite source text.

We are continuing an existing architecture handoff. Do not restart product discovery or discard prior decisions.

New locked data decision: CalibraXI owns the multi-source acquisition platform; SoccerData is adapter/accelerator only; preferred acquisition order is permitted official/licensed machine-readable source → direct HTTP/JSON → deterministic HTML/Scrapy → Playwright fallback; all data passes raw observation/provenance, validation, entity resolution, source/conflict policy, PIT chronology and canonicalization; models never directly depend on SoccerData/source clients; assets have provenance/licensing pipeline.

The Recommendation + Curation Architecture is now recorded in the canonical documents. Future work should preserve those boundaries and move to implementation planning when explicitly requested.
