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