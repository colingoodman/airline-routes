# Free schedule investigation

Status: two distinct observation days are captured through 29 October 2026; daily observation is enabled on the droplet. Three departure records were cross-checked against the dated Avinor passenger board. Seven-day repeat observation and independent airline checks are pending. No schedule data has been added to the viewer or downloadable route dataset.

## Decision

Proceed with a bounded **Avinor departure-schedule investigation**. It requires no account, payment or new hardware. Its published reuse terms permit use with the visible linked attribution **Flydata fra Avinor**. Keep automatic publication disabled until the observation and identity checks below pass. Sources: [Avinor service documentation and terms](https://partner.avinor.no/tjenester/flydata/) and [current technical documentation](https://xwiki.avinor.no/spaces/AASRV/pages/171475934/XmlFeed-%2BApplication%2Bdocumentation).

The current technical documentation, updated in August 2026, describes up to 336 hours ahead and 36 hours back. An older linked version describes different limits. The implementation uses an explicitly requested 168-hour window and records the actual returned dates; the documented maximum is not evidence that every future service is present.

## Measured first sample

The fixed sample is Oslo (OSL) and Brønnøysund (BNN), with `TimeFrom=1`, `TimeTo=168`, `direction=D` and `codeshare=Y`. Two public requests returned HTTP 200. Raw XML and fetch metadata stay under ignored `work/schedule-research/`; they are not shipped as static current schedules.

| Measurement | Result |
| --- | --- |
| Departure records | 1,841 OSL + 45 BNN = 1,886 |
| Departure-local dates represented | 28 October–4 November 2026; partial first/last dates |
| Records with codeshares | 122 |
| Records with intermediate stops | 47 |
| Circular services requiring leg resolution | 11 |
| Records whose destination is absent from our current map | 37: RRS (12), SRP (16), OLA (9) |
| Invalid records after preserving circular services explicitly | 0 |
| Paired scheduled arrival time in a departure record | Unavailable |
| Distinct observation days | 1; repeat-observation gate pending |

The droplet's live verification capture at 15:11 UTC on 28 October returned
1,885 records, including 116 with codeshares, 47 with intermediate stops and
11 circular services. The 37 missing map references remain unresolved. Earlier
raw captures and their request ledger were migrated intact. This is still one
distinct observation day. Comparison with the earlier normalizer is withheld
until its raw evidence is replayed; the daily collector now uses a fixed commit.

The first parser rejected circular itineraries that leave OSL, call at SDN/SOG and return to OSL. It now preserves those source records and flags them for leg resolution. It does not turn a circular itinerary into a nonstop route or guess its first leg. Missing destinations remain unresolved map references; they are not discarded or assigned to another airport.

Source UTC timestamps are retained separately from the departure-local date, calculated using `Europe/Oslo` for these two reviewed Norwegian origins. Published flight numbers remain text, including zeros/suffixes. Codeshare numbers remain separate from the published primary number. The primary `airline` field is described as the operating airline in Avinor's field mapping. Gate/status values remain explicitly “as reported” at capture time. Estimated/status times never overwrite the scheduled timestamp.

A departure board provides a scheduled departure at its queried airport. An arrival board provides a scheduled arrival at its queried airport. A future full-leg timetable would need verified pairing or another permitted source; this sample does not invent the missing end time, duration, aircraft type, bookability or a recurring weekly pattern.

## Passenger-board spot check

The 29 October daily droplet capture at 04:01 UTC returned 1,817 OSL and 44 BNN
departures (1,861 total), with 11 circular services and 37 missing map endpoint
references. Its report records two observation days; the seven-day gate remains
pending. The OSL XML checksum and exact current-parser replay were checked
before using this existing capture in the [flight-matching investigation](FLIGHT_MATCHING_RESEARCH.md).
No additional schedule polling was added for aircraft tracking.

On 28 October, the [dated Oslo passenger board](https://www.avinor.no/en/airport/oslo/flight-times/) matched these source records after UTC-to-Oslo conversion:

| Flight | Destination | Source scheduled UTC | Passenger-board scheduled local time |
| --- | --- | --- | --- |
| RC435 | FAE | 11:25 | 12:25 |
| SK809 | LHR | 13:55 | 14:55 |
| DY1308 | LGW | 14:30 | 15:30 |

RC435's updated time was shown separately from its original scheduled time. The board also displayed WF148 at 16:40 local with both Sandane and Sogndal destinations, supporting the decision to preserve its multistop/circular source information for explicit leg resolution. This checks our interpretation against Avinor's passenger presentation; it is not an independent-provider completeness check.

## Reproduce and observe

```sh
.venv/bin/python scripts/schedule_research.py
# Re-normalize captured bytes after a parser change, without another API request:
.venv/bin/python scripts/schedule_research.py --replay work/schedule-research/captures/CAPTURE_DIRECTORY
```

The tool accepts only the two reviewed origins. It has an exclusive lock, a daily request-attempt ledger (24 by default), a three-minute minimum between requests for the same airport, an 8 MiB response limit and a 256 MiB storage budget. Failed requests consume the local budget. It never switches to a paid source or changes `web/`. Storage exhaustion stops new collection; raw evidence is not silently deleted. Replay verifies raw checksums, preserves original fetch times and does not count as a new observation day.

Each capture has raw XML, normalized records, issues, attribution, request URLs, normalizer hash and a comparison summary. Comparable captures report added/removed records and changed schedule/status fields. Disappearance is not classified as cancellation. A changed normalizer requires replaying prior raw evidence before comparison. Only complete captures of the same origins, horizon and schema count toward the observation gate. Seven days of future departures returned today are **one** observation day.

Daily droplet service definitions live in `deploy/refresh/airplanes-schedule-research.*`; the installer and verification steps are in the deployment guide. Use the same dedicated account/read-only collector checkout described in [DEPLOYMENT.md](DEPLOYMENT.md#candidate-refresh-runner-collection-only), with separate writable state at `/var/lib/airplanes-schedule-research`. Verify the units and run the service manually before enabling the timer. The enabled timer captures once daily at 03:45 UTC (09:15 India time), plus up to ten minutes of jitter: two requests/day, well below the local 24-attempt cap.

Before a viewer pilot:

1. Capture at least seven distinct days with this fixed sample. Compare the same future flights across captures; report additions, removals, changed times and cancellations rather than treating disappearance as proof of cancellation.
2. Spot-check dated flight numbers, endpoints and times against official airline/airport passenger information. Record mismatches and unresolved cases.
3. Resolve circular/multistop semantics and the RRS/SRP/OLA identity gaps using explicit evidence. Do not infer brand-group or marketing-carrier mappings from airline codes alone.
4. Decide whether the first viewer pilot shows departure-only schedules or obtains independently verified paired arrival times. Define its cadence, expiry and repository/release budget before publishing any schedule artifact.
5. Review attribution, offline capture dates, stale-record behavior and cancellation handling with the finished pilot. Keep its coverage separate from the worldwide source-listed route network.

## Other free sources

| Source | Decision | Evidence or remaining work |
| --- | --- | --- |
| [Swedavia](https://apideveloper.swedavia.se/faq) | Deferred, account required | Earlier same-day documentation listed 10,000 free requests/month with blocking at exhaustion. The latest fetch of that FAQ returned 502. Do not claim authenticated access or reuse rights have been tested. |
| [Finavia](https://apiportal.finavia.fi/) | Deferred, account required | Its [FAQ](https://apiportal.finavia.fi/faq) requires registration and a subscribed API key. Quotas, fields and retained/exported-data permissions need account-level verification. |
| [AirLabs](https://airlabs.co/#Pricing) | Optional limited comparison | Free personal-use pricing was checked earlier the same day: 1,000 queries/month. Its [schedule docs](https://airlabs.co/docs/schedules) describe a ten-hour horizon and 50 records/page for free keys. No key or account was created. |
| [US BTS](https://www.transtats.bts.gov/ontime/Index.aspx) | Historical enrichment only | Monthly flight-number and scheduled/actual-time records do not establish a future worldwide timetable. No bulk history was downloaded for this stage. |
| [airplanes.live](https://airplanes.live/api-docs/) | Not a dependency | Public test returned 403 requesting project details. No access request was sent. |
| [OpenSky](https://opensky-network.org/about/terms-of-use) | Not a dependency | Live operational REST use requires a written agreement; its API excludes airline timetable information. No agreement was requested. |
| [adsb.lol archives](https://www.adsb.lol/docs/open-data/historical) | Optional later work | Open tracks may support observed-route research. No bulk archive ingestion or live aircraft overlay is part of this schedule stage. |
