# CalibraXI Engineering

**Status:** Living canonical engineering architecture

**Ownership:** This document owns acquisition, persistence, identity resolution, provider integration, assets, APIs, runtime, observability, deployment, migrations, and implementation concerns. `docs/CalibraXI.md` owns product/UX/IA and user behavior. `docs/CalibraXI-Analytics-Architecture.md` owns Forecast, PIT/evidence, Reliability, Signal, Recommendation, Curation, Combination, Power, Evaluation, and Track Record analytical semantics.

The source-acquisition architecture below is consolidated from the former product-document section without changing its substantive decisions. Future engineering decisions belong here and should be recorded in this document's Decision Log.

## 1. Source Acquisition / Scraper Platform — LOCKED WORKING ARCHITECTURE
CalibraXI'ın football data acquisition katmanı tek bir üçüncü taraf scraper library'ye veya tek provider'a bağlanmayacaktır.

**LOCKED WORKING DECISION:**

```text
CalibraXI Data Acquisition Platform
        != SoccerData
        != one website scraper
        != one provider API
```

SoccerData değerli bir **adapter / accelerator** olarak kullanılabilir; canonical ingestion authority değildir.

## 1.1 North-star

CalibraXI'ın ihtiyaç duyduğu competitions, seasons, fixtures, schedule revisions, scores/results, teams, squads, players, transfers, managers, venues, referees, lineups, availability/injuries/suspensions, minutes/starts/substitutions, team/player stats, shots/SOT, xG/xA, event streams, goals/cards/corners, historical seasons, odds/odds history, supported player props ve identity assets multi-source architecture ile alınacaktır.

Tek bir source'un coverage'ı veya availability'si ürünün tüm veri omurgısını belirleyemez.

## 1.2 Preferred technology direction

```text
Language: Python 3.12+
Crawler/orchestration: Scrapy
Direct HTTP/JSON: httpx and/or aiohttp
Dynamic/browser fallback: Playwright / scrapy-playwright
Deterministic parsing: Parsel / lxml
Existing scraper integration: SoccerData adapter layer
Queue/coordination: Redis
Canonical structured store: PostgreSQL
Raw evidence/assets: S3-compatible object storage; MinIO local/dev acceptable
Scheduling: simple workers/scheduler first; Prefect/Airflow-class orchestration later if needed
Observability: structured logs + metrics + per-source health
```

Technology component replacement ileride mümkündür; interface, lineage ve semantic boundaries korunur.

## 1.3 Acquisition preference order

Her source/capability için tercih sırası:

```text
1. permitted official/licensed machine-readable API
2. stable direct HTTP / XHR / JSON endpoint
3. deterministic HTML fetch + parser
4. browser/Playwright only when required
```

JavaScript kullanıyor diye her source Playwright ile scrape edilmez. Website'in kullandığı stable network response uygun şekilde tüketilebiliyorsa DOM scraping yerine direct response tercih edilir.

## 1.4 Scraped data is evidence, not truth

Canonical invariant:

```text
SCRAPED / FETCHED SOURCE DATA
!=
CANONICAL FOOTBALL TRUTH
```

Acquisition layer yalnızca şunu söyler:

> Source X, value Y'yi source/availability/knowledge/processing zaman bağlamında bildirdi.

Conceptual flow:

```text
SOURCE
  ↓
FETCH
  ↓
RAW SOURCE SNAPSHOT / OBSERVATION
  ↓
SOURCE-SPECIFIC PARSER
  ↓
NORMALIZED SOURCE OBSERVATION
  ↓
SCHEMA / INTEGRITY VALIDATION
  ↓
ENTITY RESOLUTION
  ↓
CONFLICT / AUTHORITY POLICY
  ↓
POINT-IN-TIME ELIGIBILITY
  ↓
CANONICAL DOMAIN FACT / VIEW
  ↓
FEATURE SNAPSHOT
  ↓
FORECAST / ANALYTICS
```

## 1.5 Raw Evidence Store

Material fetch'ler mümkün olan ölçüde reproducible provenance bırakır:
- source / endpoint identity;
- source object IDs;
- source observation time;
- source availability time if knowable;
- received/processing time;
- HTTP/result state;
- raw payload or object-store reference when permitted;
- content hash;
- parser/source-adapter version;
- schema version;
- extraction/integrity result;
- retry/correction relation.

Raw retention source/legal policy'ye göre değişebilir; canonical lineage provenance reference'ını kaybetmez.

## 1.6 Source Adapter Contract

Source-specific behavior model/business code'a sızmaz.

Conceptual source modules:

```text
sources/
  sofascore/
  fbref/
  understat/
  whoscored/
  football_data/
  soccerdata/
  ...
```

Adapters capability bazlı çalışır. Provider'da capability yoksa explicit `UNSUPPORTED` veya eşdeğeri state döner; fake empty/zero data üretmez.

## 1.7 Source Capability Registry

Her capability için source policy tutulur:

```text
Capability
Primary Source
Secondary/Fallback Source
Competition/Season Coverage
Historical Depth
Current/Live Support
PIT Suitability
Known Delay/Cadence
Health
Usage/Rights State
```

Source existence, source priority, health ve usage suitability aynı kavram değildir.

## 1.8 SoccerData role

SoccerData **approved adapter accelerator**'dır.

```text
CalibraXI Source Acquisition Platform
  ├── Native adapters
  │   ├── direct HTTP / JSON
  │   ├── Scrapy
  │   └── Playwright fallback
  ├── SoccerData adapter wrapper
  └── future licensed/API adapters
```

Kurallar:
- exact dependency version pin edilir;
- kendi CalibraXI adapter interface'imiz arkasında çalışır;
- SoccerData DataFrame schema canonical domain contract olmaz;
- SoccerData cache CalibraXI provenance/evidence store olmaz;
- model code SoccerData'yı doğrudan import etmez;
- upstream breakage capability/source health olarak görünür;
- kritik capability gerekirse native CalibraXI adapter'a graduate edilir.

## 1.9 Entity Resolution is mandatory

Different sources aynı entity'yi farklı isim/ID ile gösterebilir.

```text
Arsenal
Arsenal FC
Arsenal Football Club
```

üç canonical team değildir.

Source identity → Canonical identity mapping Competition, Season, Fixture, Team, Player, Manager, Venue, Referee ve relevant market/source objects için uygulanır.

Source stable ID varsa korunur. String name normalization tek başına canonical identity kanıtı değildir.

## 1.10 Fixture identity

Fixture mapping existing stable Fixture architecture'ı korur.

Input hints:
- source fixture ID;
- competition/season/stage;
- canonical home/away teams;
- scheduled kickoff;
- venue;
- schedule revision.

Kickoff correction aynı maçı ikinci Fixture olarak yaratmamalı; iki distinct fixture sadece isim/tarih benziyor diye merge edilmemeli.

## 1.11 Player identity

Player resolution gerekirse source player ID, aliases/transliteration, birth date, nationality, historical/current club ve position evidence kullanır.

Transfer current association'ı değiştirir; historical fixture/squad/lineup context'i rewrite etmez.

## 1.12 Conflict and field-level authority

Source disagreement `latest write wins` ile çözülmez.

```text
Source A kickoff = 20:00
Source B kickoff = 21:00
```

iki ayrı observation olarak korunur.

Resolution capability/field-level policy, chronology, official revision semantics, integrity ve adjudication kullanabilir.

Bir provider tüm Fixture/Team/Player row'unun sahibi olmak zorunda değildir. Scheduling bir source'tan, xG başka source'tan, player detail başka source'tan gelebilir; provenance kaybolmaz.

## 1.13 No silent Frankenstein rows

Canonical read model compatible multi-source facts'i birleştirebilir; fakat field provenance'ı kaybolmuş arbitrary cross-source record yaratılmaz.

## 1.14 PIT chronology

Ingestion ilgili yerlerde şu zamanları ayırır:

```text
event valid time
source observation / availability time
CalibraXI knowledge time
processing time
```

Bugün scrape edilen bir value dün biliniyormuş gibi backtest'e sokulamaz.

Historical replay later lineup, later injury correction, closing odds, today's Power Rating veya corrected post-event values'i geçmişe sızdıramaz.

## 1.15 Job classes and adaptive cadence

Distinct jobs:

```text
BACKFILL
CURRENT SYNC
NEAR-KICKOFF REFRESH
LIVE/PERIODIC
POST-MATCH FINALIZATION
REPAIR / REPLAY
ASSET REFRESH
```

Polling event-aware olur. Far-from-kickoff düşük cadence; lineup window ve live daha yüksek source-appropriate cadence kullanabilir.

Exact intervals source terms, rate limits, cost ve data criticality'ye göre belirlenir. Global brute-force 1-minute rescrape yoktur.

## 1.16 Incremental acquisition

Full football universe sürekli yeniden scrape edilmez.

Kullanılabilecek primitives:
- change validators/tokens;
- fixture windows;
- season state;
- content hashes;
- last successful observation;
- targeted refresh;
- immutable-ish historical cache.

## 1.17 Source politeness / rate control

Her adapter own concurrency, spacing, retry/backoff, circuit breaker ve session/cookie behavior'ını yönetir.

Uncontrolled concurrency kullanılmaz.

## 1.18 Source Health / schema drift

Per source/capability operational signals:
- last attempt/success;
- success rate;
- HTTP states;
- latency;
- records seen/changed;
- parse failure rate;
- schema validation failures;
- missing required fields;
- challenge/rate-limit state;
- asset failures.

Expected non-zero population'da parser 0 records döndürüyorsa sistem bunu doğrudan “0 fixtures” diye canonicalize etmez.

Possible states:

```text
HEALTHY
DEGRADED
SOURCE_FAILED
PARSER_SCHEMA_DRIFT
QUARANTINED
```

Exact enums Engineering'de dondurulur.

## 1.19 Circuit breaker and fallback

Repeated challenge, invalid schema, parse corruption veya anomaly source/capability circuit breaker'ı açabilir.

Fallback:
- secondary provenance'ı korur;
- reduced semantics varsa görünür;
- primary failure state'i saklanır;
- secondary data primary source identity'si gibi masquerade etmez.

## 1.20 Data quality gates

Applicable checks:
- required fields;
- types/ranges;
- impossible score/stat states;
- duplicate source identities;
- fixture-team consistency;
- competition/season consistency;
- timestamp plausibility;
- lineup context;
- odds/line integrity;
- asset validity.

Critical invariant:

```text
MISSING
!= 0
!= UNSUPPORTED
!= SOURCE_FAILED
```

## 1.21 Corrections

Source correction old observation'ı overwrite etmez. New observation/correction lineage oluşur.

Current canonical read corrected fact'i seçebilir; historical PIT view applicable old knowledge state'i reconstruct edebilir.

## 1.22 Asset Ingestion Pipeline

Identity assets ayrı governed pipeline kullanır:

```text
Source Asset URL / Payload
→ download/reference
→ MIME/content validation
→ dimensions/corruption validation
→ content hash
→ dedupe
→ original object storage
→ optimized derivatives
→ Canonical Asset Mapping
```

Classes:
- team crest;
- competition logo;
- player headshot;
- flags/source references;
- venue imagery where permitted.

Metadata:
- entity identity;
- asset type;
- source/reference;
- source asset ID;
- observed/downloaded times;
- content hash;
- MIME/dimensions;
- usage/license status;
- attribution;
- current/supersession relation.

## 1.23 Asset rights

Technical scrapeability commercial usage permission değildir.

Engineering source registry logo/player/competition/stadium assets için storage, redistribution, display ve attribution conditions'ı izler.

Unknown rights'ta commercial permission varsayılmaz.

Frontend arbitrary external URL hotlink'ine canonical dependency olarak güvenmez. Copy permitted değilse compliant reference veya neutral placeholder kullanılır.

Fake/generated club crest, player face veya competition logo yasaktır.

## 1.24 Storage roles

**PostgreSQL:** canonical/normalized structured identities, observations, lineage refs, relational read state.

**S3-compatible / MinIO:** raw JSON/HTML/source files/assets/debug payloads subject to policy.

**Redis:** queue/rate coordination/locks/dedup/hot cache. Redis canonical historical truth değildir.

## 1.25 Deterministic extraction

Production extraction deterministic ve versioned olur.

LLM extraction canonical parser olarak fixture IDs, player IDs, kickoff, scores, lineups, odds veya stats üretmez.

AI yalnız source discovery, schema-drift diagnosis, parser repair suggestions ve test generation gibi yardımcı rollerde kullanılabilir.

## 1.26 Tests

Important adapters:
- parser unit tests;
- captured/sanitized payload fixtures where permitted;
- schema tests;
- identity resolution tests;
- known edge cases;
- regression tests;
- fetch→parse→normalized observation contract tests
kullanır.

Missing/unsupported/source failure test semantics mandatory.

## 1.27 Model/source decoupling

Feature/model layer canonical internal read contracts kullanır.

Model code doğrudan:

```text
soccerdata.FBref(...)
source_x.get(...)
```

çağırmaz.

Source adapter değişirse Forecast/model interface'i değişmemelidir.

## 1.28 Legal / contractual source registry

Her source için kayıt:
- acquisition method;
- terms/usage considerations;
- rate behavior;
- storage rights;
- redistribution/display rights;
- asset rights;
- attribution;
- commercial-use risk;
- replacement/fallback plan.

## 1.29 Source outage behavior

Bir source kırıldığında:
- affected capability degrade/unavailable olabilir;
- governed fallback değerlendirilebilir;
- historical canonical data korunur;
- unaffected capabilities devam eder;
- evidence requirement karşılanmıyorsa downstream Forecast withheld/unsupported olabilir.

One broken scraper entire CalibraXI data platform'ını çökertmemelidir.

## 1.30 Initial implementation sequence

```text
A0 — Source Capability Registry + internal contracts
A1 — Raw Evidence Store + fetch metadata
A2 — Entity Resolution primitives
A3 — SoccerData adapter wrapper
A4 — first native direct HTTP/JSON adapter
A5 — Scrapy orchestration
A6 — Playwright fallback
A7 — Data Quality / Quarantine
A8 — Asset ingestion
A9 — Source Health / Observability
A10 — PIT integration with Feature Snapshot pipeline
```

Exact order repository audit sonrası refine edilebilir.

## 1.31 Final working decision

```text
CalibraXI data foundation
=
multi-source acquisition platform
+ deterministic adapters
+ immutable raw/source observations
+ entity resolution
+ point-in-time chronology
+ validation/quarantine
+ capability-specific source policy
+ asset provenance
+ source health
```

SoccerData: **YES as adapter/accelerator.**

SoccerData: **NO as sole ingestion platform or canonical truth owner.**

Scrapy: **YES as primary crawling/orchestration direction.**

Direct HTTP/JSON: **YES as preferred extraction where stable/permitted.**

Playwright: **YES as fallback/dynamic acquisition layer, not default.**

---
## 2. Engineering Scope Boundary

This document is the implementation authority for the CalibraXI data foundation and the surrounding runtime. It owns the physical persistence and service contracts that consume the governed acquisition outputs, including PostgreSQL canonical state, object storage, Redis coordination, API/read contracts, runtime jobs, observability, deployment, migrations, and operational controls. Those details must preserve the source, provenance, identity, PIT, and immutability boundaries defined in section 1.

It does not redefine product behavior or analytical semantics. Product and UX decisions remain in `docs/CalibraXI.md`; analytical authority remains in `docs/CalibraXI-Analytics-Architecture.md`.

## 3. Decision Log

### 3.1 2026-09-22 — Source Acquisition Consolidated

The detailed Source Acquisition / Scraper Platform specification was moved from `docs/CalibraXI.md` and consolidated here. The product document retains a concise product-level boundary and its historical decision entry. No source-acquisition decision was intentionally removed.

### 3.2 2026-09-24 - Implemented acquisition boundaries

The repository now implements the source-registry and policy boundaries described above. ESPN is the qualified fixture identity primary and Sofascore is an explicitly translated fixture fallback; provider-specific Sofascore statistics and Understat xG remain separate semantic contracts. Football-Data.co.uk is a historical snapshot source whose odds are not treated as point-in-time movement. Global Sports Archive, StatBunker, Transfermarkt, TheSportsDB and OpenFootball remain measured candidates or references until rights, operational stability, or coverage evidence supports activation.

Source manifests and append-only capability policies are versioned and persistable. Fixture mappings are proposed and explicitly adjudicated; ambiguous mappings remain unresolved. Raw evidence can be stored in S3/MinIO and replayed through the normal parser and PostgreSQL canonical persistence boundary. Native JSON adapters use bounded retries for transient HTTP/network failures, while health, quarantine, recovery leases, and per-source rate/concurrency controls remain operational signals and do not redefine authority.

Capability roles are explicit: ESPN owns fixture identity and normalized lineup fallback may use Sofascore only through a confirmed canonical fixture mapping; Sofascore player/team statistics, incidents, and shots retain provider-specific contracts. A fallback request carrying a provider fixture ID is rejected unless the source-specific ID is confirmed against the canonical fixture, and competition/season identity proposals use explicit cross-provider maps when provider IDs differ.

### 3.3 2026-09-25 - Bootstrap and Forecasting Foundation Implementation

The repository now contains the first end-to-end analytical foundation in `src/calibraxi_data/bootstrap.py` and `src/calibraxi_data/forecasting.py`.

- `EplBootstrapper` acquires Football-Data.co.uk historical CSV snapshots through the existing capability/evidence path, persists canonical fixture and team observations, stores coverage and reconciliation reports, and keeps invalid rows in quarantine. Football-Data remains a historical snapshot source; it does not become ESPN fixture identity authority.
- `ForecastingPostgresStore` owns the PostgreSQL analytical tables for fixtures, coverage, reconciliation, Feature Snapshots, training datasets, model artifacts, calibration artifacts, and Forecast Runs. Snapshot and run replay compares the complete immutable payload and requires explicit supersession for a current replacement.
- MinIO remains the raw evidence and metadata store. The earlier live smoke path returned 145 objects; each 2025/26 ESPN replay added 114 immutable fixture evidence manifests. PostgreSQL smoke counts include 12,704 fixtures, 62 Feature Snapshots, two training datasets, four model artifacts, two calibration artifacts, and two Forecast Runs.
- `FeatureSnapshotBuilder` enforces pre-match cutoff ordering and explicit missingness states. `build_training_dataset` and `TemporalBacktester` reject PIT-ineligible snapshots, duplicate identities, future training examples, and invalid chronology. Forecast models receive only provider-neutral canonical records.
- The rights boundary is explicit: production activation accepts only `approved` or `permitted` source/capability rights, while local research may opt into `review_required`. Deferred GSA, StatBunker, Transfermarkt, and other research-only adapters remain inactive.
- Historical Football-Data publication/availability chronology is unknown, and player, lineup, event, shot, team-match-stat, and Understat xG/xA populations remain unsupported or missing. These states are persisted and are release gates for production PIT forecasting rather than hidden fallbacks.

### 3.4 2026-09-25 - 2025/26 ESPN reconciliation measurement

- The governed date-scoped ESPN collector acquired all 114 Football-Data match dates for EPL 2025/26: 380 unique fixture observations, 20 team observations, and 114 raw evidence manifests in one run. The raw responses and metadata remain in MinIO, and the machine-readable coverage report is persisted in PostgreSQL (`calibraxi_coverage_reports`).
- An explicit 20-entry provider-team alias map was used. PostgreSQL now retains 380 confirmed ESPN-to-canonical fixture mappings, with zero unresolved or ambiguous rows. No team name or fuzzy match was promoted as identity.
- The raw reconciliation report retained 158 kickoff-only differences. The timezone audit reclassified 156 as Europe/London normalization artifacts and leaves two residual kickoff schedule-revision candidates (`+10` and `+15` minutes); scores, home/away teams, competition, season, and fixture identity reconciled without source-conflict or duplicate-fixture promotion.
- ESPN historical responses were retrieved during bootstrap, but their original publication/availability time is not known. The mapped observations therefore enrich canonical lineage and reconciliation while remaining ineligible for historical pre-match PIT training unless a qualifying availability timestamp is supplied.

### 3.5 - Real historical PIT and prospective chronology

- Football-Data kickoff parsing uses `Europe/London` explicitly. Raw `Date` and `Time` are retained beside normalized UTC. A DST nonexistent or ambiguous wall clock is quarantined. The existing 380-row ESPN reconciliation artifact has 156 timezone-normalization artifacts and two remaining schedule-revision candidates after reclassification.
- `src/calibraxi_data/historical_evaluation.py` loads the 33-season archive through the governed parser, builds deterministic `features-v2-real-pit-r2` snapshots and `real-pit-dataset-v4` manifests, records exact warm-up skips, evaluates coherent Frequency, Poisson, Elo, and Dixon-Coles challenger distributions, writes per-prediction/per-season/pooled/reliability/calibration/selection artifacts, and replays versioned `elo-replay-v1-r2` ratings before/after history without future state. The revisioned namespace preserves earlier immutable partial runs with non-deterministic wall-clock metadata.
- PostgreSQL now has immutable evaluation-artifact, power-rating-history, and prospective-observation tables. MinIO stores evaluation manifests alongside raw evidence. `FileProspectiveObservationStore` and `ProspectiveObservationCollector` retain future source observations with actual CalibraXI knowledge time so later capabilities can be evaluated as true PIT data.
- Football-Data historical odds remain snapshots with unknown quote chronology. They are excluded from strict PIT features and may be used only for benchmark or post-hoc market-efficiency analysis. ESPN detail, Understat xG/xA/shots, OpenFootball revisions, current lineups, and player statistics remain chronology-qualified enrichment work rather than historical backfill.

### 3.6 - Live shadow operations and true-PIT knowledge ledger

The prospective boundary is implemented by `live.py`, `live_runner.py`, `live_persistence.py`, and `scripts/run_live_shadow.py`. It is intentionally separate from the reconstructed historical evaluation tables and model-selection artifacts.

- Every source attempt becomes a ledger row with source/capability, canonical and provider IDs, source timestamps when exposed, actual `knowledge_at`, processing time, evidence ID, parser/schema versions, horizon/context, and an explicit success/missing/unsupported/failure state. Raw evidence remains in the existing evidence store; PostgreSQL stores the durable analytical projection.
- The scheduler creates immutable tasks for fixture discovery, `t-72h`, `t-24h`, `t-6h`, `t-1h`, and `t-15m` windows. Task outcomes are append-only and leases/replays are idempotent. Missing or unavailable work records `missed_observation`; the runner never creates a historical observation after a deadline and never silently substitutes a current/latest row for an earlier cutoff.
- Prospective Feature Snapshots carry a separate versioned schema (`features-v3-prospective`), observation/evidence IDs, per-feature eligibility bases, missingness, cutoff, and generation time. The builder rejects any ledger row with `knowledge_at` after the cutoff. Lineup identity/version and later corrections remain source observations with their first actual knowledge time.
- Shadow Forecasts are immutable PostgreSQL/MinIO-compatible artifacts with `publication_state=shadow`. Frequency, Poisson, Dixon-Coles, and Elo produce coherent score distributions and derived outcome/total/BTTS markets independently for champion/challenger measurement. No runtime model shopping or public Signal/Recommendation publication is attached to this worker.
- PostgreSQL forecast rows are staged un-attested and committed before a second transaction assigns store-controlled `persisted_at` and `prediction_cutoff_at`. The feature `cutoff_at` is never rewritten. Read services expose only attested rows; interruption before attestation leaves the staged row out of TRUE-PIT evaluation and lets an idempotent restart finish the seal. Legacy rows migrate with a null `prediction_cutoff_at` and remain ineligible for prospective evaluation.
- Final-result settlement and Track Record writes are append-only and preserve result evidence. Settlement, Track Record, reliability, and monitoring share the forecast eligibility predicate: `knowledge_at <= cutoff_at`; store-assigned `created_at` and `persisted_at` do not exceed `prediction_cutoff_at`; `persisted_at <= prediction_cutoff_at < kickoff_at`; and the forecast retains successful actual fixture-source lineage. Reports also require persistence and prediction cutoff no later than their `generated_at`. An ineligible late-persisted/replayed forecast receives no Settlement or Track Record entry. Current metrics exclude superseded corrections while retaining their lineage. The prospective population is `prospective_true_pit`; reconstructed historical evaluation remains `historical_reconstructed` and is never merged by a read service or aggregate query.
- A completed fixture projection is result-eligible only when it carries an explicit source `knowledge_at`; `updated_at` alone never proves when its final score became known. A result ledger observation with its own actual `knowledge_at` may qualify the same fixture under the normal as-of rule.
- Reliability and monitoring reports are immutable snapshots with explicit sample thresholds and uncertainty intervals. `insufficient_sample` is the default state for early live data. These reports measure behavior and drift only; model promotion still requires a later offline governance decision.
- `scripts/run_live_shadow.py` defaults to the built-in `calibraxi_data.live_factory:create_live_shadow_runner`. It requires `CALIBRAXI_POSTGRES_DSN` (or `DATABASE_URL`) and `CALIBRAXI_MINIO_ENDPOINT_URL`; storage authentication continues through the standard AWS credential chain. The runner refuses `review_required` source policies, and no environment flag can override that rights state. A custom `CALIBRAXI_LIVE_RUNNER_FACTORY` can replace this composition root without changing runner contracts, but must enforce the same source-policy boundary.
- The built-in runner reads the existing Football-Data archive as reconstructed training input and persists prospective analytical state in PostgreSQL. Raw provider responses and their evidence manifests use MinIO. `PostgresCanonicalStore` supplies only confirmed provider fixture mappings to the acquisition coordinator; an unresolved mapping never passes an ESPN ID into Sofascore.
- Continuous operation checks upcoming dates across a ten-day window every six hours and runs due observation, forecast, settlement, and monitoring work on the configured collection interval (one minute by default). Discovery failures retry after at most five minutes; database/model errors are surfaced and retried without completing claimed horizons.
- Understat xG/xA policies remain provider-specific and review-required. Until a permitted live adapter and provider fixture identity are configured, the built-in adapter persists `unsupported`; it does not import SoccerData, substitute Sofascore metrics, or backfill a value.
- Provider access failures are retained as evidence/state and do not fabricate fixtures, lineups, odds, outcomes, or chronology. The continuous runner is deployable as a process; external hosting credentials and service supervision remain deployment configuration.
- Forecast lineage schema `actual-fixture-source-v2` persists the actual successful fixture observations used by each shadow snapshot, including provider/canonical IDs, source timestamps, CalibraXI knowledge and processing times, evidence, parser/schema versions, horizon, and state. A prospective Track Record entry is admitted only when that fixture observation belongs to the snapshot and was known by the forecast cutoff. The `prospective-true-pit-v2` read population excludes legacy v1/smoke rows without deleting their audit history.
- Reliability and monitoring refreshes apply their `generated_at` cutoff to settlement time, entry persistence time, forecast creation, and source-health observations. Corrections supersede only as of their own recorded time; an earlier report retains the settlement revision that was then available.

#### 2026-09-26 forecast cutoff field split

The live-shadow audit found that using one timestamp for both source eligibility and forecast persistence obscured the time CalibraXI could first attest a run. `cutoff_at` remains the immutable Feature Snapshot input boundary. `prediction_cutoff_at` is assigned by the store at or after durable forecast persistence, while `persisted_at` retains the persistence attestation itself. Existing forecast rows receive no inferred prediction cutoff and are excluded from `prospective-true-pit-v2`, preserving the no-retrospective-promotion rule.

#### 2026-09-26 operational readiness audit

PostgreSQL ledger writes and MinIO payload/manifest round trips were verified against the local integration services with temporary smoke records, which were removed after readback. A second round trip exercised the PostgreSQL forecast attestation write after the `prediction_cutoff_at` migration and verified both UTC fields before deleting the test row. The 2026-09-26 database audit found nine upcoming scheduled EPL fixtures (2026/27), 121 observation tasks, 31 knowledge-ledger rows, nine prospective snapshots, 24 staged forecast rows, two smoke settlements, two smoke-labelled Track Record rows, 16 reliability reports, and six monitoring reports. The 31 ledger rows comprise seven successful ESPN first-observed schedule observations, 11 ESPN failures, 11 unsupported Sofascore fixture observations, and two explicitly labelled `phase-smoke` observations. MinIO's `live-shadow/raw` prefix contained 43 objects, including 39 evidence manifests; these retained observations are not a fresh run by the current worker.

All 24 existing forecast rows are `persistence_attested=false`; after the additive migration, their `prediction_cutoff_at` values remain null. The read service correctly returns zero eligible shadow forecasts, and the fixed `prospective-true-pit-v2` Track Record population has no settled entries. The two existing Track Record entries use separate smoke population IDs and are not merged into that population. Existing reliability reports are `insufficient_sample`; they are not evidence of measured prospective accuracy. A real `python scripts/run_live_shadow.py --once` attempt failed closed before collection because eight ESPN/Sofascore/Understat capabilities remain `review_required`. No fresh source acquisition, newly eligible live forecast, or live settlement is claimed until access review qualifies those policies. Replayed rows cannot be promoted retroactively.
