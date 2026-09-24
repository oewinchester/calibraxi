# Corrected Record-Level Qualification: EPL 2025/26 Additional Sources

**Benchmark scope:** EPL 2025/26, direct record-level surfaces, measured 2026-09-23 UTC / 2026-09-24 Europe/Istanbul. This is additive research evidence. It does not activate a source policy, select an authority, or change an existing adapter.

The checked-in first-stage fixture (`tests/fixtures/epl_2025_26_source_qualification.json`) recorded StatBunker and OpenFootball only from shallow/guessed routes. The measurements below extend that evidence using known season/data surfaces; the earlier rows remain historical evidence and should not be deleted.

## StatBunker

### Acquisition and season identity

- Acquisition mode: direct HTTPS HTML. No stable public JSON/XHR payload was retained in this pass; the useful surfaces are server-rendered HTML tables and match-detail pages.
- EPL 2025/26 competition identity: `comp_id=776`. The competition selector exposed EPL season IDs from `776` (25/26), `596` (24/25), `745` (23/24), back to `13` (93/94), plus `791` (26/27).
- Representative URLs:
  - `https://www.statbunker.com/competitions/LeagueTable?comp_id=776`
  - `https://www.statbunker.com/competitions/SeasonAppearances?comp_id=776`
  - `https://www.statbunker.com/competitions/TopGoalScorers?comp_id=776`
  - `https://www.statbunker.com/competitions/PlayerStandings?comp_id=776`
  - `https://www.statbunker.com/competitions/LastMatches?comp_id=776&limit=10&offset=0`
  - `https://www.statbunker.com/competitions/MatchDetails/Premier-League-25/26/West-Ham-United-VS-Leeds-United?comp_id=776&match_id=128552&date=24-May-2026`
  - `https://www.statbunker.com/competitions/getCompClubSquad?comp_id=776&club_id=4`
  - `https://www.statbunker.com/competitions/InjuriesAndSuspensions?comp_id=776`

The source labels pages as `Premier League 25/26`; the footer states “Stats are updated after the completion of each match.” No provider publication timestamp or revision ID was exposed. Pages include a dynamic server clock/CSRF token, so raw HTML hashes are not stable even when normalized records are stable.

### Measured season/table records

| Surface | HTTP / latency sample | Data rows | Stable IDs observed | Fields observed |
|---|---:|---:|---:|---|
| `LeagueTable` | 200; 0.77 s (one sample; other fetch 3.8 s) | 20 | 20 unique `club_id` values; e.g. Arsenal `5`, Liverpool `4`, Manchester City `14` | rank, club name, P/W/D/L, F/A, GD, points |
| `SeasonAppearances` | 200; 0.57-7.4 s | 697 | 697 player links, 679 unique `player_id` values; 18 IDs occur twice because players appear under two clubs after a transfer | player name, club, total, starts, sub starts, came on, off, goals |
| `SeasonAppearances&club_id=4` | 200; 0.57 s | 34 | 34 unique player IDs; `club_id=4` | same appearance fields, filtered to Liverpool |
| `TopGoalScorers` | 200; 3.3-4.0 s | 280 | 280 unique player IDs; 20 unique club IDs | goals, first/second half, first/last scorer, home/away |
| `PlayerStandings` | 200; 2.7-9.4 s | 679 | no player links/IDs in the table itself; club links expose 20 IDs | player name, club, position, total appearances, goals, assists, cards, starts/sub/CO/off, penalties, own goals |
| `PlayersShotsOnGoal` | 200; 2.0 s | 1 sentinel row (`No data found`) | none | header advertised goals/shots on/off target/goal-to-shots %, but no records were returned |
| `InjuriesAndSuspensions` | 200; 23.7 s | 0 records (headers only) | none | headers: name, club, from date, to date, type, description |
| `FantasyFootballPlayersStats` | 200; 23.2 s | 1 sentinel row (`No scorers found`) | none | no usable fantasy rows in this capture |

`SeasonAppearances` links are a useful identity surface: e.g. Djordje Petrovic is `/players/GetHistoryStats?player_id=26870`; the Liverpool filter uses `club_id=4`. Transfer splits are explicit rather than silently merged (for example, `player_id=58212` appears for Bournemouth and Manchester City). This makes player IDs and club IDs usable source-local keys, while the same player can have multiple club rows in a season.

### Match-level record

The `LastMatches` list is paginated by `offset`. With `limit=10`, offset `0` returned 10 unique match IDs `128552` through `128543` (all 24-May-2026); offset `10` returned a different 10 IDs `128542` through `128534` (19-May through 15-May-2026). Club filtering is also exposed through `club_id` links.

The match-detail URL above returned HTTP 200 and a stable numeric `match_id=128552` on repeated requests. The normalized record contained:

- West Ham United 3-0 Leeds United; match date 24 May 2026; kickoff 16:00.
- Venue `Queen Elizabeth Olympic Park`; attendance `62471`; referee `Anthony Taylor`.
- Three goal/event descriptions with minute, scorer/assist text, body-part, side, situation and distance text (67', 79', 90').
- Three booking descriptions with minute, player, card and reason (all yellow/foul in this sample).
- Two squad sections with 40 unique player IDs (20 linked players per side in the page), plus two substitution tables with 7 substitution rows (2 home, 5 away).
- No team-statistics table, player-match-statistics table, shots/shotmap, xG/xA/xGOT, odds or ratings was exposed on this match report. The match navigation contained overview and head-to-head only.

Repeated normalized extraction of the same match produced identical title, match ID, score, date, venue, referee, attendance, event strings, player IDs and substitution rows. Raw HTML SHA-256 changed because of dynamic tokens/clock. Two match-detail fetches were 1.29 s and 1.53 s in one repeat test. List requests were much slower (27.2 s and 30.3 s for offsets 0 and 10), and other list/detail requests timed out at a 20 s client limit.

### Chronology, repeatability and limitations

- Match kickoff/date is present in match-detail pages and `date=...` URL parameters. Provider-side source-available/publication timestamps, correction versions and per-field update chronology were not exposed. The footer's “updated after completion of each match” is a cadence statement, not point-in-time evidence.
- Numeric competition, club, player and match IDs are present on the measured surfaces. `PlayerStandings` is an exception: its rows are names only, so it must not be treated as an ID-complete player table.
- Pagination (`offset`) and club filtering work on the observed list surfaces; arbitrary `page=2` and `limit=100` on `SeasonAppearances` were ignored and returned the same 697-row population, so the endpoint-specific pagination contract must be captured rather than assumed.
- Dynamic anti-bot/Cloudflare token links appear in HTML; no bypass was attempted. Normalized match records were repeatable, but latency variance and timeouts make unattended bulk acquisition operationally medium difficulty.
- No odds or odds chronology were measured. Missing shots, injuries and fantasy rows are explicit empty/sentinel populations in this capture and must not be converted to zero.

An additional direct fetch on 2026-09-24 returned `LastMatches` offsets `0` and `10` with HTTP 200 in 5.82 and 5.94 seconds, respectively, with 10 numeric match IDs on each page and no overlap. A repeat fetch of `SeasonAppearances?comp_id=776` returned 697 rows and the same first record. These do not replace the earlier 27.2/30.3-second samples and client timeouts; latency remains variable. The new `PlayerStandings?comp_id=776` capture returned 679 rows, still without player links, and `SeasonAppearances?comp_id=776&club_id=4` returned 34 rows.

### Recommendation

**Classification: specialist production candidate (statistical tables and match-report/event specialist), pending rights/rate/health review.** StatBunker adds source-local numeric identities, season-level player/team tables, transfer-split rows, and match report events/lineups/referees/venue/attendance beyond the existing fixture/stat sources. It does not currently provide evidence for xG/shotmaps, player-match statistics, odds chronology or source-side PIT timestamps. No primary/fallback ordering is selected here.

## OpenFootball (`football.json`)

### Acquisition and repository identity

- Acquisition mode: direct HTTPS raw GitHub JSON; no API key. The repository README describes the datasets as “Free open public domain football (match fixtures & results) data” and states that schema, data and scripts are dedicated to the public domain.
- Season surfaces:
  - `https://raw.githubusercontent.com/openfootball/football.json/master/2025-26/en.1.json`
  - `https://raw.githubusercontent.com/openfootball/football.json/master/2025-26/en.1-full.json`
  - GitHub commit history: `https://api.github.com/repos/openfootball/football.json/commits?path=2025-26/en.1.json&per_page=100`
  - Full-file history: `https://api.github.com/repos/openfootball/football.json/commits?path=2025-26/en.1-full.json&per_page=100`

The earlier benchmark's 404 was for a guessed CSV route and does not apply to these working JSON surfaces.

### Coverage and fields

Both files contain 380 fixture records, 20 teams with 38 appearances each, 38 rounds with 10 matches each, and dates 2025-08-15 through 2026-05-24. There are no duplicate `(date, team1, team2)` keys within either file.

`en.1.json` records have `round`, `date`, `time`, `team1`, `team2`, and `score`. The final-score value is a `{ft, ht}` object for 353 rows and a bare `[0, 0]` for 27 rows; the latter is an ambiguous representation and should remain a source-specific missing/zero state until semantics are confirmed. All 380 records still have a final-score pair when compared with the full file by normalized date/home/away key.

`en.1-full.json` has 380 records with `{ht, ft}` score objects. Every record has `ground`, `attendance`, a two-sided `lineup`, and three referee records. Measured aggregate fields:

- 760 starting-XI arrays (11 starters per side in every match).
- Bench/substitution arrays on 758 of the 760 team records; two arrays are absent. Where present, substitution counts vary by match (0-6 per side in the observed file).
- 353 matches with goals arrays, totaling 1,045 goal records; 27 records have null/missing goal arrays while still carrying a 0-0 score.
- 366 matches with bookings arrays, totaling 1,481 booking records; 14 records have null bookings.
- 380 venue strings, 380 attendance values (10,762-74,257), and 1,140 referee records (3 per match).

The full file has no competition/team/player/match IDs, no odds, no xG/xA/xGOT, no shots, ratings, injuries, transfers or market values. Lineups, goals, bookings and referees are name/minute records only. Team naming differs between files (`Liverpool FC` vs `Liverpool`, `AFC Bournemouth` vs `Bournemouth`, and similar suffix changes), so cross-file/entity matching requires explicit normalization and cannot claim provider IDs.

### Repeatability and chronology

Two direct fetches of each raw file returned HTTP 200 with identical payload SHA-256 and ETag. Measured response times were approximately 0.33-0.34 s (`en.1.json`) and 0.45-0.46 s (`en.1-full.json`). Raw headers included `Cache-Control: max-age=300` and ETags. GitHub API history provides revision chronology:

- `en.1.json`: 22 commits from 2025-07-30T16:20:51Z through 2026-05-26T08:25:18Z; recent messages are dated auto-updates during the season.
- `en.1-full.json`: one captured commit, 2026-08-24T18:36:08Z.

Git commit time and file ETag are useful evidence/revision markers, but they are repository publication times rather than per-fixture provider collection timestamps. No correction semantics beyond Git history are defined in the JSON schema.

### Recommendation

**Classification: verification-reference.** OpenFootball adds a deterministic, fast, public-domain season schedule/result artifact and, in `en.1-full.json`, useful name-based report metadata (lineups, goals, bookings, officials, venues and attendance). It has no stable source IDs and no market/PIT quote chronology, so it should not replace ID-bearing canonical fixture/stat sources. It is well suited to immutable raw evidence and cross-source verification of schedule/results and basic match reports. No primary/fallback ordering is selected here.

## Global Sports Archive

The measured EPL season is competition `76035`, round `125229`, with 38 gameweeks, 380 unique numeric match IDs, and 20 numeric team IDs. Numeric player IDs were visible on player records. The full season count came from the round data; the season page itself rendered only one 10-match round, so that page is not evidence of 380 rows. The exact season/round request URL, response hashes, and latency were not retained. Repeated season/round extraction reproduced the same 380 IDs, with no duplicate fixture rows reported.

The representative match route was `https://globalsportsarchive.com/en/soccer/match/2025-08-15/liverpool-fc-vs-afc-bournemouth-fc/3739542` (HTTP 200, 1,725,401 bytes). Its `/player-stats` route returned HTTP 200 at 1,680,619 bytes and `/shot-chart` returned HTTP 200 at 1,578,090 bytes. These are large HTML responses; per-request latency and repeat hashes were not retained. The record exposes lineups, bench, events, formations, officials, venue, attendance, sidelined-player details, team/player statistics, shots, and xG. Do not infer a unique shot count from the un-deduplicated shot markers.

Match dates and kickoffs are present, but provider publication/source-available timestamps and revision history were not measured. GSA's incremental value is broad ID-bearing season coverage and integrated match/player detail, including formations, officials, attendance, and sidelined-player information. Several statistical fields overlap ESPN/Sofascore/Understat; this evidence does not make an exclusive xG claim. **Classification: strong production candidate**, pending rights, rate, chronology, and long-run health review. This is a qualification label only, not source authority or fallback activation.

## Transfermarkt

The Premier League `GB1`, season `2025` overview returned HTTP 200 and listed 20 clubs. All 20 squad pages returned HTTP 200: 798 club-player memberships represented 781 distinct numeric player IDs, with 17 IDs appearing for multiple clubs. The 2025/26 schedule had 380 unique numeric match-report IDs. The transfers page had 40 club lists, 788 row references, and 709 distinct transfer IDs. Transfer-fee completeness and fee semantics were not parsed.

The market-value page had 75 player rows. A sampled Erling Haaland page displayed `Last update: 22/07/2026`. A representative match page returned HTTP 200 and exposed 22 starters, 18 bench players, events, venue, attendance, and referee. The exact request URLs, latency, response sizes, and repeat-fetch comparisons were not retained for these page families. Historical market-value change rows were not extracted, so historical depth remains unknown.

Keep a transfer's effective date, a value's effective date, the provider's displayed update/publication time, and CalibraXI `observed_at` separate. The displayed Haaland date is only a page update label; it was not verified as a value-effective timestamp or CalibraXI knowledge time. Numeric club, player, match-report, and transfer IDs provide identity utility. Squad membership, transfer, and valuation surfaces add context not present in the existing core sources. **Classification: specialist production candidate**, pending exact route capture, repeatability, fee/history semantics, and rights/rate review.

## BetExplorer

The EPL 2025/26 results HTML returned HTTP 200 twice. Both 381,246-byte bodies had SHA-256 `d7f6e1f8b6dfb9eeaacf995dc703a62261a633a6f519a1ebae4b77283caee1b7` and contained 380 result rows, 380 numeric `data-test` IDs, and 380 slug IDs. The exact request URL and latency were not retained. The 1X2 cells were blank.

The page also contained an explicit 18+ confirmation overlay. No interaction or bypass was attempted, and no match-detail or odds request was made. Bookmakers, markets, opening/closing odds, movement, and per-observation timestamps therefore remain unmeasured; chronology must not be inferred. No incremental odds capability was verified beyond the existing sources. **Classification: operationally unsuitable for odds qualification in this pass** because the detail surface was not accessed past the overlay.

## 11v11

The correct 2025/26 season route is `https://www.11v11.com/competitions/premier-league/2026/matches/` (HTTP 200), with 380 unique numeric match IDs. The `/2025/` season route corresponds to 2024/25, not 2025/26. A representative linked match report returned HTTP 200 twice; normalized page text matched while raw hashes differed. Its exact detail URL and latency were not retained.

One report exposed lineups, goals, substitutions, cards, referee, venue, and attendance. Row counts, player/team IDs, provider update timestamps, and historical depth were not measured. Much of the report overlaps ESPN/Sofascore; venue/referee/attendance and match-event details can supplement a record, but one sample does not establish broader unique coverage. **Classification: research-only.**

## Mackolik

The archive season resolver `https://arsiv.mackolik.com/CompetitionHandler.aspx?op=seasons&group=17&year=2025/2026` returned HTTP 200 and identified the English Premier League season as `70266`. The exact standings route `https://arsiv.mackolik.com/Standings/Default.aspx?sId=70266` returned HTTP 200, 198,566 bytes, in 0.810451 seconds.

This is a successful page response, not record-level qualification: no normalized standings rows, match/player/team IDs, pagination behavior, or match-detail records were retained. Repeatability, chronology, historical depth, and any incremental capability beyond the core remain unknown. **Classification: research-only** with the exact limitation that EPL season identity is resolved but the season data records are not.

## Disposition

| Source | Qualification label | Measured incremental value |
|---|---|---|
| Global Sports Archive | Strong production candidate | Broad ID-bearing season and rich match coverage, including formations, officials, attendance, and sidelined-player details |
| StatBunker | Specialist production candidate | Season participation/contribution tables, numeric IDs, and match reports with events, substitutions, and officials |
| Transfermarkt | Specialist production candidate | Numeric squad/player/transfer identity, club memberships, transfers, and market-value surfaces |
| OpenFootball | Verification-reference | Deterministic public-domain fixtures/results and repository revision history for independent verification |
| BetExplorer | Operationally unsuitable for odds qualification in this pass | No bookmaker or odds data verified; explicit 18+ overlay stopped detail access |
| 11v11 | Research-only | One match-report sample with lineup/event and venue/official metadata; incremental breadth not established |
| Mackolik | Research-only | EPL season ID `70266` resolved; no record-level data verified |

## Scope boundary

This note intentionally leaves the existing ESPN, Sofascore, Understat and Football-Data.co.uk paths unchanged. It does not write adapters, alter capability policy, activate a fallback, or choose source authority. Historical first-stage and focused-discovery rows, including guessed-route failures, remain in the fixture; the corrected rows above are additive. Exact request URLs or timing are explicitly marked unretained where the captured record did not preserve them. Rights/terms and bulk-rate limits remain a separate source-registry review item, including for StatBunker and Transfermarkt HTML acquisition.
