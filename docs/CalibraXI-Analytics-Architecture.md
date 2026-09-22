# CalibraXI Analytics Architecture

**Status:** Living canonical analytical architecture

**Scope:** This document owns CalibraXI's domain constitution, point-in-time evidence, Feature Snapshots, Forecasts, calibration, Reliability, Signals, Recommendations, Curation, Combination governance, Power Ratings, and Outcome/Evaluation/Track Record analytical rules. Product behavior belongs in `docs/CalibraXI.md`. Source acquisition and implementation architecture belong in `docs/CalibraXI-Engineering.md` when that canonical document is created.

## 1. Authority And Core Invariants

This document extends the frozen analytical concepts registered in `docs/CalibraXI.md` section 11. The frozen source files are not present in this working tree; their preserved concepts remain binding where they own a concept. A later decision is recorded as an extension or supersession. It does not silently rewrite the historical rule.

The following invariants apply to every Recommendation and Curation artifact:

- Fixture identity is stable across schedule revisions; an artifact records the fixture revision it used.
- A pre-match artifact uses only evidence eligible at its point-in-time cutoff. PRE_MATCH and LIVE are separate Run Contexts.
- Evidence Manifest, Feature Snapshot, Prediction Run, Forecast, Signal Evaluation, candidate manifest, decision, publication, outcome, and evaluation are immutable. Corrections append a new artifact and link to what they supersede.
- One governed currentness decision applies to a Fixture x Run Context. A surface cannot independently choose a convenient "latest" Forecast.
- A Primary Distribution remains canonical for its coherence family. Recommendation policy cannot select a different model or distribution at runtime because its output looks more attractive.
- Calibration is governed at the parent/family level. Curation cannot recalibrate a child selection for presentation.
- Forecast Probability, Reliability, Signal, Recommendation, Curation, and user selection are distinct concepts.
- A Market Observation can create a new Signal Evaluation. It cannot mutate a historical Forecast.
- Same-match marginal probabilities must not be multiplied to manufacture a combination probability. Cross-match selections are not assumed independent merely because fixtures differ.
- Historical published or placed artifacts never silently rewrite.

## 2. Layer Boundaries And Vocabulary

### 2.1 Analytical Layers

```text
Evidence Manifest
  -> Feature Snapshot
  -> Prediction Run / Forecast
  -> Reliability Assessment
  -> Signal Evaluation (where an exact market contract is available)
  -> Candidate Population Manifest
  -> Recommendation or Curation Decision
  -> Publication Fact
  -> Outcome / Evaluation
  -> Track Record Projection
```

Each arrow is lineage, not mutation. A downstream decision stores references to upstream artifacts at the moment it was made.

### 2.2 Forecast

A **Forecast** is an immutable model output for an exact target under a Prediction Run. Its probability is not an instruction to act, a ranking, a price comparison, or a recommendation.

### 2.3 Reliability

**Reliability** describes the governed evidence, applicability, stability, and validation support for a Forecast or supported combination. It is not a probability multiplier and is not a substitute for a market price.

Reliability may be used as a hard eligibility gate or an explicitly validated policy input. A presentation band must reference the Reliability artifact and its version; a later Reliability value cannot be attached to an earlier decision.

### 2.4 Signal

A **Signal Evaluation** assesses an exact Betting Contract in a market context. It links the Forecast, applicable Reliability assessment, exact contract semantics, and one or more Market Observations or a declared fair-value basis.

`ELIGIBLE` means that a Signal passed the Signal Policy. It means neither "recommended" nor "published".

### 2.5 Recommendation

A **Recommendation** is a user-facing, governed selection decision. It may only exist through an immutable Recommendation Decision and, when shown as a public CalibraXI output, an immutable Publication Fact.

A Recommendation is never inferred from:

- a high probability;
- a high edge;
- a Reliability band;
- a top-ranked projection;
- an Explorer sort;
- a user simulation or manual Studio build;
- API availability, a cache entry, or a page render.

### 2.6 Curation

**Curation** selects and orders items for a product surface under a Curation Policy. Curation may rank Forecasts, Signals, or supported compositions. It does not create a Recommendation.

The label `TOP PROJECTION` denotes curation, not a recommendation. A single item can be both curated and recommended only when independent, linked Curation and Recommendation Decisions exist. The UI must expose their distinct labels and reasons.

### 2.7 Recommendation Target

A **Recommendation Target** is the exact object a Recommendation Decision can select:

- a Single Selection Candidate, containing one exact Betting Contract; or
- a Composition Candidate, containing a versioned immutable set of exact legs and declared combination support.

Raw statistics, team form statements, a Forecast without contract semantics, and a mutable Draft are not Recommendation Targets.

## 3. Identity, Time, And Immutable Artifacts

### 3.1 Candidate Population Manifest

A **Candidate Population Manifest** is an immutable, point-in-time enumeration of every candidate considered for one decision scope. It is created before selection and has at least:

- `candidate_population_id`;
- purpose: `SINGLE_SELECTION`, `DAILY_PICK`, `TOP_PROJECTION`, `STUDIO_CROSS_MATCH`, or `STUDIO_SAME_MATCH`;
- policy identity and immutable version;
- scope definition: product surface, Run Context, date window, fixture/competition/market eligibility, and decision objective;
- decision cutoff and generation time;
- candidate keys and upstream lineage references;
- inclusion, exclusion, and unknown/unsupported state for every candidate;
- input evidence watermark and currentness policy version.

The manifest is the denominator for coverage and non-recommend explanations. Re-running a policy after price, Forecast, or currentness changes creates a new manifest. It does not revise the earlier one.

### 3.2 Candidate Key

A candidate key is stable only for the exact analytical proposition it represents. For a Single Selection Candidate it includes, at minimum:

- Fixture and schedule revision;
- Run Context;
- exact Betting Contract and selection, including line, period, and settlement semantics;
- Forecast and Prediction Run;
- applicable Reliability Assessment;
- Signal Evaluation and Market Observation or fair-value basis, where required;
- candidate generation policy/version.

A Composition Candidate additionally includes ordered or set-semantic leg identities, the dependency/joint-probability support artifact, composition price basis, and settlement semantics. A changed line, quote, leg, Forecast lineage, or support method produces a different candidate identity.

### 3.3 Candidate Assessment

A **Candidate Assessment** records how a candidate fared under a particular policy run. It is immutable and has a disposition:

- `INELIGIBLE` - failed a hard gate;
- `ELIGIBLE_NOT_SELECTED` - passed hard gates but was not chosen;
- `SELECTED_NOT_PUBLISHED` - selected by a Recommendation or Curation Decision but not publicly released;
- `PUBLISHED` - selected and linked to a Publication Fact;
- `WITHHELD` - policy intentionally issued no selection for the slot or scope.

Candidate Assessment is not a Recommendation merely because it says `ELIGIBLE_NOT_SELECTED`. It provides the auditable basis for reason and non-recommend reason codes.

### 3.4 Recommendation Decision

A **Recommendation Decision** is the authoritative immutable result of a Recommendation Policy for one named decision slot. It has:

- `recommendation_decision_id`;
- decision type: `SINGLE_SELECTION`, `DAILY_PICK`, `STUDIO_CROSS_MATCH`, or `STUDIO_SAME_MATCH`;
- decision slot identity and objective/context;
- Candidate Population Manifest reference;
- Recommendation Policy identity, version, and release identity;
- chosen Recommendation Target or explicit `WITHHELD` result;
- selection rank/slot where relevant;
- positive reason codes, non-recommend census reference, and decision explanation version;
- all upstream analytical references, price basis, and applicable currentness evidence;
- decision time, valid-from, and decision cutoff;
- supersession links when a later decision replaces it;
- publication and withdrawal references when they occur.

A Decision is immutable even when its outcome is `WITHHELD`. A system that has no valid candidate must record that it withheld the slot instead of silently showing an attractive fallback.

### 3.5 Publication Fact

A **Publication Fact** records that a specific Recommendation Decision or Curation Decision was deliberately released through a declared product channel. It includes the published artifact identity, exact content/rendering version, timestamp, audience/surface, policy/version, and referenced decision.

Publication does not change the decision. It is proof that a decision became a public CalibraXI artifact.

### 3.6 Withdrawal Fact

A **Withdrawal Fact** removes an active public artifact from current recommendation availability. It contains the withdrawn artifact, time, governed reason code, actor/policy, and successor reference when one exists.

Withdrawal is not deletion. The original Decision and Publication Fact remain visible in historical lineage. A withdrawal cannot be used to remove a poor outcome from the Track Record population.

## 4. Signal Eligibility Is Not Recommendation

Signal Policy and Recommendation Policy answer different questions:

| Question | Artifact | Result |
| --- | --- | --- |
| Does this exact contract meet governed Forecast, Reliability, price, and Signal criteria? | Signal Evaluation | eligible, ineligible, unsupported, or quarantined |
| Should this candidate occupy a user-facing recommendation slot in this scope? | Recommendation Decision | selected or withheld |
| Which items should appear in a discovery list and in what order? | Curation Decision | curated rank or no rank |
| Was the decision deliberately released? | Publication Fact | published or not published |

An eligible Signal can be excluded from a Recommendation because a slot is full, the objective is not met, the candidate duplicates exposure, concentration limits apply, the price is no longer acceptable, or the policy withholds all selections. This is expected behavior, not a Signal failure.

Conversely, Recommendation Policy cannot select a non-eligible Signal by relabeling it as a product pick. If a policy allows a non-market informational surface, it is Curation and must not use Recommendation language.

## 5. Policy, Objective, And Gating

### 5.1 Policy Identity And Versioning

Every Recommendation and Curation decision references a versioned policy. A policy version is immutable after it is used in production and identifies:

- policy family and version;
- effective window and release identity;
- allowed candidate types and scope;
- objective/context;
- hard gates and their configured parameters;
- selection and tie-breaking method;
- duplicate, diversity, and concentration constraints;
- price and Reliability requirements;
- publication and withdrawal rules;
- explanation/reason-code vocabulary version;
- evaluation and Track Record population rules.

Changing any decision-affecting rule creates a new version. A policy may be disabled prospectively; it does not rewrite decisions already made.

### 5.2 Objective And Context

Policy objective must be explicit before a candidate population is generated. Valid objectives include:

- `PUBLIC_SINGLE_SELECTION`: a bounded public selection for a declared fixture/date scope;
- `DAILY_PICK`: one daily public selection, or an explicit withhold;
- `TOP_PROJECTION`: discovery curation for a projection surface; never Recommendation by implication;
- `DAILY_STUDIO_CROSS_MATCH`: one or more governed cross-fixture compositions;
- `DAILY_STUDIO_SAME_MATCH`: one or more governed same-fixture compositions.

The objective defines the decision slot, scope, deadline, publication channel, and caps. It must not be reverse-engineered from later outcomes or redefined to make a historical population look better.

### 5.3 Hard Gates

A candidate must pass all applicable hard gates before it can be selected. Policy parameters may vary by target family, but gates must be versioned and testable.

Common hard gates are:

- valid Fixture, schedule revision, target, and exact contract identity;
- appropriate Run Context, normally PRE_MATCH for pre-match recommendations;
- PIT-valid Evidence Manifest, Feature Snapshot, Forecast, and Signal inputs;
- Forecast availability and governed currentness;
- Signal eligibility for market-linked Recommendation types;
- applicable Reliability requirement satisfied by a validated Reliability artifact;
- an exact, usable, current price where the objective is market-linked;
- compatible quote, line, source, and settlement semantics;
- sufficient time before kickoff under policy;
- no data-quality quarantine, unresolved identity conflict, source failure, or unsupported state;
- policy scope eligibility for competition, market family, jurisdiction, and product availability;
- for compositions, validated dependency, probability support, and settlement support.

Hard gates are not soft ranking inputs. Failing one records an ineligibility reason and bars selection.

### 5.4 Selection Gates

After hard eligibility, a policy may apply selection gates that govern the recommendation set rather than the individual candidate. These include slot limits, minimum objective fit, duplicate exposure controls, concentration caps, diversity requirements, and publication capacity.

Selection gates may lead to `ELIGIBLE_NOT_SELECTED` or `WITHHELD`. They cannot be bypassed by sorting the remaining candidates by probability or edge.

### 5.5 No Forced Output

No Recommendation Policy has an implicit "one per day" guarantee. A Daily Pick slot can be withheld. A Top 10 Curation surface can show fewer than ten items or an explicit empty/unsupported state. Daily Studio can publish zero compositions.

## 6. Price And Reliability Requirements

### 6.1 Price Requirements

Any market-linked Recommendation requires a governed **Price Reference** for the same exact Betting Contract. It must identify:

- source/provider identity;
- observed quote identity and timestamp;
- contract, selection, line, period, and settlement semantics;
- decimal odds or declared price representation;
- availability, integrity, and freshness state;
- price-basis policy and any allowed source-selection method.

The published artifact stores the accepted Price Reference. A later best price, a line change, a quote from another source, or closing odds cannot silently replace it.

`Price missing`, `price stale`, `contract mismatch`, `line changed`, `unavailable`, and `source conflict` are distinct states. They never collapse into zero edge or a silent fallback.

Forecast-only Top Projection Curation may omit price. If it does, it must remain clearly labeled as a Forecast/Projection surface and cannot imply a market recommendation.

### 6.2 Reliability Requirements

A market-linked Recommendation requires an applicable validated Reliability assessment under the Recommendation Policy's family/parent requirements. A high probability or a favorable price cannot compensate for unsupported or inapplicable Reliability.

Reliability does not rank candidates by an invented universal score unless that scoring method is separately validated and versioned. For combinations, leg Reliability values must not be averaged or multiplied into a made-up composition Reliability. Publication requires a validated combination-level support/reliability method or the candidate remains unsupported.

## 7. Reasons And Non-Recommend Reasons

Reason codes are stable machine-readable policy outputs. Human explanations are rendered from those codes, source lineage, and an explanation version. They must not invent causal claims after the fact.

### 7.1 Positive Recommendation Reason Families

Examples include:

- `SIGNAL_ELIGIBLE`;
- `OBJECTIVE_FIT`;
- `RELIABILITY_REQUIREMENT_MET`;
- `PRICE_INTEGRITY_MET`;
- `CURRENT_AT_DECISION`;
- `DIVERSITY_CONSTRAINT_SATISFIED`;
- `COMBINATION_SUPPORT_VALIDATED`;
- `PUBLICATION_AUTHORIZED`.

These codes show why the policy permitted and selected a target. They do not mean that the outcome is likely to win or that the target is the highest-probability event.

### 7.2 Hard-Gate Non-Recommend Reason Families

Examples include:

- `FORECAST_UNAVAILABLE`;
- `PIT_INELIGIBLE`;
- `RUN_CONTEXT_INELIGIBLE`;
- `SIGNAL_NOT_ELIGIBLE`;
- `RELIABILITY_REQUIREMENT_NOT_MET`;
- `PRICE_MISSING`;
- `PRICE_STALE`;
- `PRICE_UNAVAILABLE`;
- `CONTRACT_OR_LINE_MISMATCH`;
- `CURRENTNESS_FAILED`;
- `KICKOFF_WINDOW_CLOSED`;
- `DATA_QUALITY_QUARANTINED`;
- `IDENTITY_OR_SOURCE_CONFLICT`;
- `UNSUPPORTED_MARKET_OR_SETTLEMENT`;
- `COMBINATION_SUPPORT_UNAVAILABLE`.

### 7.3 Selection Non-Recommend Reason Families

Examples include:

- `OBJECTIVE_THRESHOLD_NOT_MET`;
- `SLOT_LIMIT_REACHED`;
- `DUPLICATE_CONTRACT_EXPOSURE`;
- `FIXTURE_EXPOSURE_CAP`;
- `TEAM_EXPOSURE_CAP`;
- `COMPETITION_CONCENTRATION_CAP`;
- `MARKET_FAMILY_CONCENTRATION_CAP`;
- `COHERENCE_FAMILY_CONCENTRATION_CAP`;
- `DEPENDENCY_OR_CORRELATION_CAP`;
- `DIVERSITY_POLICY_EXCLUSION`;
- `PUBLICATION_HOLD`;
- `POLICY_WITHHELD_ALL`.

The population manifest records which code applies to each non-selected candidate. A public explanation can be concise, but internal lineage must retain the precise reason and policy version.

## 8. Single-Selection Recommendations And Daily Pick

### 8.1 Single Selection Recommendation

A **Single Selection Recommendation** selects exactly one Betting Contract/Selection candidate. It cannot contain multiple legs under a single-selection label. Its Decision must reference the exact Signal, Forecast, Reliability, price, and contract lineage.

The product may display multiple independently decided Single Selection Recommendations in a scope only when the policy states the maximum count and applies set-level exposure controls. Each selection still has its own Recommendation Decision identity and Publication Fact.

### 8.2 Daily Pick

**Daily Pick** is a Recommendation Decision subtype, not a visual badge applied to a forecast or Top Projection.

A Daily Pick policy must define:

- the calendar/time-zone and decision window;
- one named daily slot, or an explicit no-pick result;
- eligible candidate scope;
- selection and tie-breaking method;
- price and Reliability requirements;
- duplicate/concentration interaction with other public Recommendations;
- publication and withdrawal behavior.

There can be at most one active published Daily Pick for the same policy version, date scope, and slot. A later replacement is a new Decision with an explicit supersession and Withdrawal Fact for the prior active publication. Both remain in historical lineage.

Daily Pick Track Record begins only with genuine published Daily Pick artifacts. Historical top-ranked Forecasts, Signals, and old UI cards cannot become Daily Pick history.

## 9. Projection Curation: Today'S Top Projection And Top 10

### 9.1 Curation Decision

A **Curation Decision** is an immutable output of a versioned Curation Policy. It carries a Candidate Population Manifest, ordered eligible candidates, curation reasons, rank basis, scope, time, and optional Publication Fact.

It is separate from a Recommendation Decision even where both refer to the same Forecast or Signal.

### 9.2 Today'S Top Projection

**Today's Top Projection** is the highest ranked item from a declared Projection Curation Policy for its exact scope. It is not a Daily Pick, Recommendation, Best Bet, or implicit recommendation.

It may be Forecast-first and have no price. Where market context is shown, the UI must state whether it is informational context or a separate Signal. The curation surface must show its scope, curation label, rank reason/context, and as-of/currentness state.

### 9.3 Top 10

**Top 10 Projections** is a Curation Decision that returns up to ten items. It is not "the ten highest probabilities" and is not a Recommendations list.

Its Policy defines candidate scope, family mix, duplicate rules, diversity/concentration constraints, eligibility, rank method, tie-breaking, and currentness. Probability, Reliability evidence, projection family, and compatible price/edge context can be policy inputs, but the rank number is not a probability or recommendation score.

A Top 10 item can display an explicit linked Recommendation badge only if a separate, currently published Recommendation Decision exists. That badge must be traceable to its own reason and publication lineage.

### 9.4 No Hidden Recommendation Through Sorting

Explorer and list sorting remain user research controls. Sorting by probability, edge, odds, or Reliability cannot change artifact type, create a Recommendation, affect a Track Record population, or bypass Curation/Recommendation Policy.

Terms such as `best`, `pick`, `strongest`, or equivalent recommendation language require a Recommendation Decision when shown as a public user-facing selection. A neutral `Top Projection` label remains Curation only.

## 10. Daily Studio Curation And Recommendation

### 10.1 Scope

Daily Studio has two governed publication families:

- `DAILY_STUDIO_CROSS_MATCH`: a composition containing legs from different fixtures;
- `DAILY_STUDIO_SAME_MATCH`: a composition containing legs from one fixture.

Both are distinct from Manual Build, Saved Drafts, Templates, Strategy Candidates, and user Simulation Bets. Those user-owned objects never become CalibraXI Recommendations by being displayed in Studio.

### 10.2 Composition Candidate Population

A Studio Candidate Population Manifest records every composition considered, not merely the published composition. It includes the candidate construction policy, leg source population, exact leg identities, candidate generation cutoff, support class, dependency status, price basis, and all exclusions.

Candidate generation cannot use arbitrary high-probability, high-edge, high-Reliability, or low-odds sorting as a hidden builder. It must be policy-governed and reproducible from the manifest.

### 10.3 Cross-Match Requirements

Every Cross-Match candidate requires:

- exact leg contract, Forecast, Signal, Reliability, and price lineage;
- no direct duplicate contract or equivalent duplicate exposure under policy;
- declared shared/latent dependency assessment; fixtures being different does not prove independence;
- a supported combination probability method, or an explicit unsupported/research-only state;
- exact combined-price basis and settlement semantics;
- combination-level Reliability/support that has been validated for this use;
- diversity and concentration checks across fixture, team, competition, market/coherence family, and identified dependency groups.

Cross-Match publication is withheld when these prerequisites are not met.

### 10.4 Same-Match Requirements

Every Same-Match candidate requires:

- all-leg semantic compatibility and no deterministic contradiction;
- joint derivation or a provider exact same-game quote with its declared analytical support class;
- no multiplication of individual marginal probabilities or prices to claim a joint probability or offered same-game price;
- exact fixture, line, selection, quote, dependency/joint method, and settlement lineage;
- validated combination-level Reliability/support and an appropriate price basis.

Same-Match legs are intentionally concentrated in one fixture. This does not satisfy diversity; it triggers stricter dependency and joint-support requirements.

### 10.5 Studio Curation And Recommendation Decisions

Daily Studio publication requires both:

1. a **Studio Curation Decision** that selects a composition from its manifested candidate population under set-level diversity and concentration policy; and
2. a **Recommendation Decision** for the selected Composition Candidate under the relevant Studio Recommendation Policy.

Each can withhold. A composition is not published as a Daily Studio recommendation unless both decisions pass and a Publication Fact is created. The UI may present a published composition without recommendation language only under a separately declared informational curation policy; it cannot enter Recommendation or Studio performance populations that require recommendation publication.

### 10.6 Duplicate Exposure, Concentration, And Diversity

Policy controls must distinguish exact duplicates from correlated exposure:

- exact contract duplicates are prohibited within a published set;
- equivalent or overlapping contracts are governed by contract/coherence-family exposure policy;
- fixture, team, competition, market-family, coherence-family, source, and identified dependency-group caps are explicit;
- cross-match diversity is not a claim of statistical independence;
- same-match composition is assessed under its joint-support method, not rewarded for having more legs;
- diversity is a constraint or declared objective, not a universal quality score;
- a policy can publish fewer items or none rather than violate a cap.

The policy records every concentration exclusion in Candidate Assessment. It cannot remove those candidates from the manifest after seeing results.

### 10.7 Open Combination Mathematics Boundary

This architecture freezes the governance boundary for Daily Studio. It does not invent unresolved mathematics. Before production Studio Recommendation publication, the analytics program must validate and version:

- same-family joint derivation;
- cross-family and cross-fixture dependence treatment;
- combination probability calibration;
- combination-level Reliability/support method;
- exact price/settlement comparability;
- evaluation population and effective-sample treatment for correlated legs.

Until a target family's required support is validated, the candidate is `COMBINATION_SUPPORT_UNAVAILABLE` and Daily Studio Recommendation publication is withheld. Manual Studio may continue to provide only the support state it can substantiate.

## 11. Currentness, Supersession, And Withdrawal

### 11.1 Currentness

Currentness is a governed evaluation, not a page timestamp. For an active Recommendation or Curation artifact, it verifies the relevant Fixture status, run context, Forecast/Signal validity, price availability/freshness, policy window, and quarantine state.

Currentness does not alter history. When it fails, the system creates an immutable currentness result and, if policy requires it, a Withdrawal Fact or successor Decision.

### 11.2 Supersession

A successor Decision is required when a material input changes: contract/line, candidate identity, Forecast lineage, Reliability artifact, accepted price reference, policy version, or selected composition. It links `supersedes_decision_id` and explains the supersession reason.

A screen cannot replace a published price, selection, or explanation in place. It either shows the historical artifact or a separately identified current successor.

### 11.3 Withdrawal

Withdrawal reasons distinguish, at minimum:

- `PRICE_NO_LONGER_USABLE`;
- `CURRENTNESS_EXPIRED`;
- `FIXTURE_STATUS_CHANGED`;
- `DATA_QUALITY_QUARANTINE`;
- `SOURCE_OR_IDENTITY_CORRECTION`;
- `POLICY_WINDOW_CLOSED`;
- `SUPERSEDED_BY_SUCCESSOR`.

Withdrawal prevents a stale artifact from being presented as active. It does not erase its Decision, Publication Fact, price at publication, or eventual evaluation.

## 12. Publication And Historical Evaluation

### 12.1 Publication Requirements

Publication is an explicit downstream action. A public Recommendation requires:

- a positive Recommendation Decision;
- all required hard and selection gates satisfied at publication;
- exact current Price Reference for market-linked targets;
- explicit currentness confirmation;
- publication policy authorization;
- rendered reason/explanation version and required lineage metadata.

Publication cannot be inferred from API visibility, cache state, UI ranking, a user opening a page, a Signal becoming eligible, or placement of a user simulation.

### 12.2 Recommendation Track Record Population

The default public Recommendation Track Record population is every validly published Recommendation Decision with:

- exact decision and Publication Fact;
- exact Recommendation Target and contract/composition lineage;
- accepted publication-time price basis where relevant;
- authoritative settlement/evaluation path;
- declared inclusion, exclusion, pending, void, and `CANNOT_EVALUATE` status.

Publication is the commitment point. A subsequent withdrawal cannot selectively remove a published artifact from this population. A correction or integrity quarantine remains visible as a separately classified record and cannot be silently counted as a loss or erased.

Daily Pick is a labeled subset of the Recommendation population. Published Studio Compositions have a distinct Studio population and must retain their Studio Curation, Recommendation, and publication lineage.

### 12.3 Evaluation

Outcome authority is independent of decision and publication authority. Evaluation uses the exact original contract, settlement policy, and publication-time price basis. Later Forecasts, Reliability values, odds, provider displays, or user simulations do not change the historical result.

Track Record reports explicit population definitions, denominators, pending/exclusion states, and report versions. `CANNOT_EVALUATE` is not a loss. Correlated child markets and composition legs must not be represented as independent observations without an explicit effective-sample policy.

### 12.4 No Retrospective Recommendation Backfill

Historical Forecasts, Signals, Top Projection rankings, user bets, or reconstructed combinations cannot be relabeled as production Recommendations. Retrospective analysis belongs to a separately labeled research population and never merges into public Recommendation, Daily Pick, or Studio Track Record.

## 13. Operational Prohibitions

The following are prohibited:

- renaming an eligible Signal as a Recommendation;
- using a probability/edge/odds sort to create a Recommendation;
- publishing a Daily Pick because a dashboard needs one;
- using a mutable Studio Draft as a published composition;
- treating different fixtures as automatically independent;
- multiplying same-match marginal probabilities or odds;
- using a stale or mismatched quote as a current price;
- updating a published artifact in place after a line, price, or Forecast change;
- backfilling recommendation history from attractive historical outputs;
- excluding withdrawn, poor, or inconvenient published artifacts from Track Record without a visible governed integrity classification;
- treating user simulations, strategy candidates, or personal performance as public CalibraXI Track Record.

## 14. Remaining Analytical Work

Recommendation and Curation governance is now specified. The following target-family mathematics and operating policies remain open until separately validated and versioned:

- joint probability and calibration methods for supported Studio combinations;
- combination-level Reliability/support validation;
- policy-specific numerical thresholds, objective functions, and tie-breakers;
- price-source and accepted-price policy per supported market/provider;
- correlation/effective-sample treatment in combination evaluation;
- capability-release criteria for each Recommendation/Studio family.

These open items do not authorize ad hoc production behavior. Their absence produces an explicit unsupported or withheld outcome.

## 15. Decision Log

### 15.1 2026-09-22 - Recommendation + Curation Governance

- `Forecast`, `Reliability`, `Signal`, `Recommendation`, `Curation`, and user selection are independent layers with immutable lineage. Signal eligibility and any ranking do not grant Recommendation status.
- Candidate Population Manifests are mandatory point-in-time denominators for Recommendation and Curation decisions. Candidate dispositions and non-recommend reasons are preserved rather than reconstructed later.
- Recommendation Decisions, Curation Decisions, Publication Facts, Withdrawal Facts, currentness assessments, and supersession links are immutable append-only artifacts.
- Single Selection, Daily Pick, Daily Studio Cross-Match, and Daily Studio Same-Match use named decision slots and may explicitly withhold output. A Daily Pick is not forced and can never be reconstructed from historical rankings or Signals.
- Today's Top Projection and Top 10 are Curation outputs. User sorting by probability, edge, odds, or Reliability remains research ordering and cannot create a Recommendation or Track Record membership.
- Market-linked Recommendations require an exact current Price Reference and applicable validated Reliability. Historical publication-time contract/price lineage never rewrites.
- Daily Studio requires separate Studio Curation and Recommendation Decisions, with explicit duplicate exposure, concentration/diversity, dependency, price, support, publication, withdrawal, and evaluation rules. Target-family combination mathematics remains an explicit release gate rather than an inferred product behavior.
- Public Track Record populations begin only at genuine Publication Facts. Withdrawal preserves historical membership; retrospective Recommendation, Daily Pick, or Studio backfill is prohibited.
