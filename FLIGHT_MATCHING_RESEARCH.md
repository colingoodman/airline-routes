# Aircraft-to-flight matching investigation

The first implementation generates **offline hypotheses** linking observed aircraft
episodes to dated Avinor OSL departures. It does not assert confirmed flight
identities or actual destinations, and it does not alter the public map.

The follow-up [external candidate review](#external-review-of-the-14-candidates-29-october)
corroborates ten dated flight/endpoint records; four official checks remain
unresolved. The [alphanumeric callsign investigation](CALLSIGN_RESOLUTION_RESEARCH.md)
separates the morning's 31 unsupported-format episodes into 19 reviewed-carrier
operational identifiers and 12 other cases. Aircraft associations remain
unconfirmed; the current full suite passes 109 tests.

## First real-data results

Both completed adsb.fi captures were replayed against the existing Avinor
capture preceding their observations. The morning schedules were already
collected by the daily droplet job; no additional schedule requests were made.
Aggregate counts and exact provenance are in
[research/flight-matching-summary.json](research/flight-matching-summary.json).

| Measurement | 28 October evening | 29 October morning |
| --- | --- | --- |
| Aircraft identifiers / observation episodes | 15 / 22 | 52 / 57 |
| Episodes with one eligible flight-number hypothesis | 4 | 10 |
| Unknown episodes | 18 | 47 |
| Ambiguous episodes in these samples | 0 | 0 |
| Carrier distribution of hypotheses | 4 SK | 5 SK, 5 DY |
| OSL scheduled departures within capture window | 4 | 25 |
| Those scheduled records with an aircraft hypothesis | 1 | 8 |
| Ground-to-air departure corroborations | 0 | 0 |
| Independently confirmed aircraft/flight associations | 0 | 0 |

There are **14 initial flight-number/planned-route hypotheses across two service
dates**. Each has a single eligible primary schedule record and resolved planned
endpoint references; none establishes actual destination or a complete observed
route. Some hypotheses concern departures scheduled before the capture began,
so they are outside the narrower schedule-window comparison. The 8/25 morning
comparison is **not** confirmed-match coverage or a statement that the other
17 flights did not operate.

The morning's unknown reasons are 31 nonnumeric/unrecognized callsign-format
episodes, 11 with no eligible schedule candidate, two unreviewed operators and
three missing callsigns. That makes alphanumeric operational callsigns a concrete
next research priority. Both samples had zero ground reports, so the software's
departure-transition rule has only synthetic validation here. No hypothesis was
promoted using numeric agreement alone. Independent precision and real match
coverage remain unmeasured.

Both analyses repeat identically and leave all original source files unchanged.
All **106 Python tests pass**, including 18 matcher tests with the 20 deliberate
negative/ambiguous synthetic cases. The final audit added a regression ensuring
stale reports cannot create or extend a flight candidate's time window.

## Evidence and matching rules

### External review of the 14 candidates, 29 October

The [case review](research/candidate-review.json) records a disposition for all
14 candidates, with dated source URLs and explicit limits. **Ten have corroborated
dated flight numbers and planned endpoints from an airline or destination airport;
four remain unresolved at that source standard. No aircraft association is
confirmed.** These sources may share operational data with Avinor, so this is an
external presentation check rather than proof of independent data lineage.

All nine SAS candidates matched the airline's rendered dated status search,
including planned endpoints and scheduled departure after conversion to Oslo
time: SK1330, SK1488, SK382 and SK320 on 28 October; SK821, SK251, SK332,
SK4082 and SK4472 on 29 October. For example, the
[SK821 dated result](https://www.flysas.com/ie-en/flight-status?flightNumber=SK821&date=2026-10-29)
showed OSL–AMS at 07:45 local, with takeoff separately reported at 07:52. Expanded
details were checked for all nine. Gate departure, takeoff and scheduled time
remain separate fields. The page did not expose a registration or operational
callsign, so the aircraft link remains unresolved. SAS displayed some numbers
with a zero-padded numeric portion; these exact page-level aliases are recorded
in the review, without changing the matcher's conservative string rules.

The [dated Swedavia arrival record](https://www.swedavia.se/arlanda/ankomster/#/2026-10-29/DY804)
supported DY804 from Oslo to ARN on 29 October, scheduled arrival 08:40 local,
landed as reported at 08:20. This checks the dated airport pair, not its departure
time or aircraft. The board's default current-time filter initially hid this
earlier arrival; selecting 00:00 revealed it. An empty filtered board is not
evidence of non-operation.

Norwegian's [public status page](https://www.norwegian.com/uk/flight-status/)
presented an anti-bot challenge in both the direct request and normal browser.
No challenge was solved and no alternate restricted endpoint was used.
DY1718, DY524, DY182 and DY932 therefore remain unresolved under the official
dated airline/airport check. Copenhagen's dated DY932 page rendered a flight
title but no time record, which is insufficient. Search-indexed FR24/Cirium
records for DY1718/DY182 are recorded as secondary leads, not accepted official
checks or evidence of API reuse rights. No paid/trial access, account creation,
provider contact or extra position-feed polling was used.

`scripts/flight_matching.py` verifies every position-response checksum and replays
the source bytes. It separately verifies the captured Avinor XML checksum and
normalizes it with the current schedule parser. Saved normalized schedule rows
are not taken as authoritative. The output records both capture manifests,
parser/matcher hashes, carrier-reference hash and provider attribution.

Five reviewed ICAO/IATA carrier pairs are in
[research/callsign-carriers.json](research/callsign-carriers.json). Identity sources
checked on 29 October 2026 are [ICAO's operator list](https://www.icao.int/CORSIA/AeroplaneOperators)
and [SAS's own SK identifier](https://www.flysas.com/es-es/informacion-legal/condiciones-de-transporte),
[IATA's Widerøe record](https://www.iata.org/en/about/members/airline-list/wideroe/233/),
and Aena's [Norwegian Air Shuttle](https://www.aena.es/en/alicante-elche-miguel-hernandez/airlines/norwegian-air-shuttle.html),
[Norwegian Air Sweden](https://www.aena.es/en/tenerife-sur/airlines/norwegian-sweden.html)
and [British Airways](https://www.aena.es/en/ibiza/airlines/british-airways.html) entries.
These establish carrier codes, not a rule that a transmitted callsign's suffix
always equals a passenger flight number. Older references use NAX for Norwegian;
the reviewed current airport reference uses NOZ. NAX is not silently treated as
an equivalent in this experiment.

A reviewed three-letter prefix and an exact one-to-four-digit suffix generate
a flight-number hypothesis. Leading zeros are preserved. Alphanumeric suffixes,
unknown operators, missing callsigns and general aviation remain unresolved.
The code never substitutes an arbitrary suffix or selects the nearest schedule
just because an aircraft is close to Oslo.

All same-number schedule records, including rejected dates, are retained for
review. A candidate requires the reported operating carrier, an OSL departure and
a fresh-at-capture observation overlapping the interval from 30 minutes before to 120 minutes
after scheduled departure. This is a conservative research filter, not a measured
delay distribution; flights delayed beyond it can remain unknown. A schedule
captured after the first eligible fresh observation or over 24 hours before it is ineligible.
Cancellation as reported excludes a candidate. Estimated times do not rewrite
the original scheduled time. Stale-only episodes remain unknown, and stale points
cannot extend a candidate's time window. [Avinor's field mapping](https://xwiki.avinor.no/spaces/AASRV/pages/171475934/XmlFeed-%2BApplication%2Bdocumentation)
supports the departure direction, opposite airport, operating airline and status
interpretation. Status D may represent off-block or takeoff, so it does not alone
prove a measured runway departure.

An aircraft hex is not a flight identity. Episodes split when callsigns change,
after a gap over 30 minutes or when airborne observations return to ground.
Missing callsigns do not inherit an earlier flight label. Multiple eligible dated
flights or different aircraft proposing the same schedule record are ambiguous;
no aircraft substitution is guessed. Codeshares stay on the primary record and
do not produce duplicate aircraft. Marketing-only matches are rejected.

A fresh ground observation within 3 NM of OSL followed within five minutes by a
fresh airborne observation within 10 NM is retained as departure corroboration.
These proximity/time thresholds are experimental and do not prove runway use.
Stale reports, distant ground positions and longer gaps cannot provide this
corroboration. It never promotes a candidate to confirmed.

Known endpoints with no reported intermediate or circular itinerary may produce
a **planned endpoint pair**. This is not a nonstop guarantee, actual flown path,
confirmed destination or proof against diversion. Intermediate/circular services
and missing map endpoints keep their unresolved route state. The existing
RRS/SRP/OLA map gaps are not guessed around. Registration and aircraft ownership
are not used as permanent operator or flight identities.

## Reproduce privately

```sh
.venv/bin/python scripts/flight_matching.py \
  --session work/position-research/PRIVATE_STATE/sessions/SESSION \
  --schedules work/flight-matching/captures/SCHEDULE_CAPTURE \
  --out work/flight-matching/NEW_HYPOTHESES.json
```

No network requests occur during matching. Output must be a new private file in
ignored `work/`. Raw aircraft data and hypotheses remain private; aggregate
counts and source hashes are suitable for the committed research report.

The schedule-window comparison counts OSL departures whose **scheduled** UTC
time falls within the position-capture window, with and without an aircraft
hypothesis. It does not count operated flights or estimate feed completeness.
Delays, arrivals, overflights, unidentified callsigns and limited schedule scope
prevent a defensible coverage denominator at this stage. Confirmed precision
and match coverage remain unavailable.

## Validation and remaining gate

Focused checks cover midnight, Oslo's repeated autumn hour, reused numbers,
leading zeros, alphanumeric and missing callsigns, codeshares, cancellations,
aircraft substitutions/collisions, stale data, gaps, circular/multistop routes,
missing airports, raw checksum failures, incomplete captures and repeatable
read-only analysis. Twenty deliberately ambiguous or negative synthetic cases
exercise refusal to force an association. Synthetic cases validate software
behavior; they do not count toward independent live-match precision.

The roadmap's independent review of 100 proposed associations across two service
dates, plus 20 real ambiguous/nonmatching cases, remains pending. Numeric callsign
agreement and an OSL schedule are insufficient to complete that gate. The next
review needs dated official aircraft-to-flight corroboration, especially for
alphanumeric operational callsigns; arrival evidence is needed before claiming
actual endpoint pairs. No automatic confirmed state exists in this first pass.

## Route-database shortcut investigated and excluded

[ADSBDB's official repository](https://github.com/mrjackwills/adsbdb) advertises a
public callsign-to-route endpoint, including ICAO/IATA callsigns and endpoints.
Its README separately requires explicit permission before copying, publishing
or incorporating its flight-route data into another database. The software's MIT
license does not grant those route-data rights. Its documented response also
does not establish a dated flight instance. No route query, ingestion or provider
contact was made; this is not an approved free matching dependency.
