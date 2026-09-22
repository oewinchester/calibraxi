# Domain documentation

CalibraXI uses a single project context. `AGENTS.md` and `CONTEXT.md` remain lightweight working and handoff files.

Canonical project knowledge is consolidated in:

- `docs/CalibraXI.md` for product vision, information architecture, UX, behavior, Studio, Track Record, My CalibraXI, and product decisions.
- `docs/CalibraXI-Analytics-Architecture.md` for analytical and domain governance, including PIT/evidence, Feature Snapshots, forecasts, calibration, reliability, signals, recommendations, curation, combination, Power Ratings, outcomes, evaluation, and Track Record analytics.
- `docs/CalibraXI-Engineering.md` for acquisition, persistence, identity resolution, provider integration, assets, APIs, auth/payment, runtime, observability, deployment, migrations, and implementation concerns.

Read the relevant canonical document before changing a concept it owns. Keep ordinary decisions in the relevant document's Decision Log. Use standalone ADRs only for exceptional, high-impact architectural decisions that benefit from an independent record. `docs/agents/` contains skill routing and wayfinding only; it must not duplicate project architecture.
