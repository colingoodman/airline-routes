# Live position feed research

## Stage 1: initial access decision

Checked on 29 October 2026 India time (probe timestamps below are UTC). The initial
experiment used bounded, private adsb.lol research around OSL. The higher-limit
comparison below now prioritizes adsb.fi for further testing. Public live deployment remains
conditional on the provider's production-contact guidance and a separate data
publication design; no provider was contacted and no account or paid service was
created. This work does not change the map or publish aircraft records.

| Source | Access evidence | Decision |
| --- | --- | --- |
| [adsb.lol public API](https://www.adsb.lol/docs/open-data/api/) | Anonymous HTTP 200 from the development machine and droplet, using the same documented geographic query | Selected for a small regional research sample |
| [airplanes.live](https://airplanes.live/api-docs/) | Earlier API probe returned 403 requesting project details; today's documentation fetch does not establish a new access grant | Deferred; no endpoint cycling or repeated blocked requests |
| [OpenSky](https://opensky-network.org/about/terms-of-use) | Current terms require a written agreement for operational REST integration; no agreement exists for this project | Deferred; no operational polling attempted |

The [adsb.lol OpenAPI description](https://api.adsb.lol/api/openapi.json) permits
free API use, documents queries within a radius up to 250 nautical miles, requests
contact for production purposes and warns that feeder-backed keys may be needed
in future. This is evidence of current research access, not a service guarantee.
The public API page and schema identify its data as ODbL. The separate
[privacy/license page](https://www.adsb.lol/docs/privacy-license) describes CC0
for data contributed by feeders; that does not establish a CC0 license for the
aggregated API. Keep raw/normalized aircraft data out of Git, downloads and
portable viewers in this experiment. A future public endpoint/export needs an
explicit attribution and reuse assessment; MIT code licensing alone is insufficient.

### Measured probe

The fixed center comes from our reviewed OSL airport record: latitude 60.193901,
longitude 11.1004; radius 50 nautical miles. Query:
`https://api.adsb.lol/v2/point/60.193901/11.1004/50`.

| Environment | Captured UTC, 28 October 2026 | HTTP | Bytes | Aircraft / coordinates / callsigns | Response time |
| --- | --- | --- | --- | --- | --- |
| Development machine | 19:40:02 | 200 | 7,567 | 11 / 11 / 11 | 0.434 s |
| Existing droplet | 19:40:33 | 200 | 7,988 | 12 / 12 / 12 | 0.481 s |

Each probe made exactly one attempt with no redirect or retry, a 15-second socket
timeout and a 4 MiB body cap. Responses differ because they were collected 31
seconds apart; these are not coverage or cross-provider accuracy comparisons.
Raw probe evidence is under ignored `work/position-research/access/` locally and
`/var/lib/airplanes-position-research/access/` on the droplet. Summary hashes are
in [research/position-access.json](research/position-access.json).

### Fields, timestamps and limits

The API wrapper's `now` is observed in **milliseconds** since the Unix epoch;
readsb's native JSON documentation describes seconds. Normalize this wrapper
explicitly rather than treating its number as seconds. For each aircraft,
`seen_pos` is position age relative to provider time; `seen` is message age and
must not substitute for position age. Derive position time from provider time
minus `seen_pos`, then measure its age against capture time. Preserve both times
and check clock skew. A newly fetched wrapper must not make an old position fresh.

The [readsb field documentation](https://github.com/wiedehopf/readsb/blob/dev/README-json.md)
identifies barometric and geometric altitude in feet, speed in knots, track over
ground separately from magnetic/true heading, and `alt_baro="ground"` as a ground
flag. Transmitted callsigns are not verified marketed flight numbers. Preserve
non-ICAO addresses prefixed with `~`, their source type and any missing quality
fields rather than assuming all positions are ADS-B or equally precise.

Probe responses advertise `X-RateLimit-Limit: 4, 4;w=1, 60;w=60, 500;w=86400`.
The short-window remaining/reset headers do not prove how much of the daily
allowance remains, nor whether limits are per IP, account or shared network.
The research ceiling is **180 attempts per UTC day**, including the droplet
access probe, and at most **60 attempts per session**, at least **20 seconds
apart**. That ceiling is below 80% of the advertised 500/day limit. Do not request
more to discover the limit. Stop on 403/429 or a stricter/insufficient advertised
allowance, preserve Retry-After, and make no automatic retry or fallback request.

### Always-on tracking limit

The observed free allowance does **not** support continuous 20-second polling:
that would require 4,320 requests/day. Even spending all 500 advertised requests
would average one query every 172.8 seconds; preserving the planned 20% reserve
means at most 400/day, or one every 216 seconds. The research tool stays at its
stricter 180/day ceiling. A bounded research session can proceed, but continuous
tracking at 10–30-second cadence is a no-go under the observed anonymous allowance.
A future pilot must narrow active operating hours, accept a slower cadence, or
establish a separately documented free access arrangement. Multiple IPs/accounts
or endpoint cycling are not solutions to this limit. No higher quota is assumed.

## Stage 2: bounded Oslo position sample

The initial deliverable is one approximately 20-minute droplet session; the
roadmap's three sessions at different times of day remain a broader follow-up
measurement. One evening sample cannot establish all-day, Norwegian or worldwide
coverage. The checked sampler is `scripts/position_research.py`.

### Capture and replay contract

These are the original adsb.lol experiment limits; the longer adsb.fi experiment
below has a separately bounded provider profile.

- Fixed OSL region; 1–60 samples, at least 20 seconds apart; 180 attempts/UTC day.
  The earlier access probe is seeded into the persistent attempt ledger once.
  A single lock prevents overlapping runs. Attempts are persisted before network IO.
  Admission also counts the preceding UTC day conservatively: the advertised
  86,400-second window does not establish a midnight reset, so crossing midnight
  cannot double-spend the provider allowance.
- A 15-second total request deadline and socket timeout, 4 MiB body limit,
  128 MiB research-state limit and a 25-minute session budget. There are no
  automatic retries, redirects, alternative providers or recurring timers.
- Respect stricter advertised limits and reserve 20% of the advertised daily
  allowance. On failures or an unrecognized allowance, stop the session and halt
  further attempts that UTC day. Preserve HTTP status and Retry-After for review.
- Record raw bytes, SHA-256, request/capture/provider times, permitted response
  headers, normalized positions, rejections and a session report. The manifest
  hashes the sampler and its supporting helper modules. Raw/normalized aircraft
  records remain outside Git and public releases.
- Reject missing/invalid position age, invalid/out-of-region coordinates,
  duplicate identifiers, out-of-order/conflicting position timestamps and
  implausible jumps. The region filter allows a 0.1-nautical-mile boundary tolerance.
  Optional callsigns, altitude and quality fields stay unknown
  without dropping an otherwise valid position. Keep ADS-B/MLAT source types.
- Position freshness uses capture time minus the underlying position timestamp.
  Positions older than 60 seconds stay in the research evidence as stale; they
  remain in the quality denominator. Allow at most five seconds of future clock
  skew, preserve signed ages and reject larger discrepancies.
- A gap over 120 seconds breaks a trail. Across shorter intervals, reject movement
  faster than 1,400 knots with a one-nautical-mile tolerance. Unchanged positions
  do not become new trail updates. These are conservative research thresholds,
  not certified aircraft performance or measurement-accuracy bounds.
- Offline replay verifies source checksums and preserves capture/position times.
  It makes no API request, changes no ledger and creates no new observation day.
  `--out` writes one corrected `positions.json` plus its report into a new private
  replay directory, retaining the original source and analyzer hashes.
  Reports count positions, not confirmed flights or observed takeoffs/landings.
  Freshness counts are per accepted airborne position report, including repeated
  samples of the same aircraft; they do not measure fleet completeness. Quantiles
  use nearest-rank percentiles.

Run manually in the droplet's isolated research environment:

```sh
PYTHONPATH=/opt/airplanes-refresh/repo/scripts python3 /path/to/position_research.py capture \
  --work /var/lib/airplanes-position-research --samples 60 --interval 20
PYTHONPATH=/opt/airplanes-refresh/repo/scripts python3 /path/to/position_research.py replay \
  /var/lib/airplanes-position-research/sessions/SESSION_DIRECTORY \
  --out /var/lib/airplanes-position-research/replays/NEW_REPLAY_DIRECTORY
```

The research state directory must be owned by the unprivileged `airplanes-refresh`
account (mode 0700). This is separate from the route/schedule collectors. The
one-off experiment runs through a transient systemd unit with a 64 MiB RAM cap,
64 MiB swap cap, 25% CPU quota and 1,500-second hard runtime limit, read-only
system files, a private temporary directory, writable research state and no
elevated capabilities.
The initial launch failed before network IO because the parent research directory
was root-owned; correcting only that directory's ownership resolved it.

### Measured results

The one-off session completed successfully at 20:07:38 UTC on 28 October
(01:37:38 India time on 29 October). It sampled 19:47:58–20:07:38 UTC,
20:47:58–21:07:38 Oslo time. Summary metrics and all 60 raw response hashes are in
[research/position-sample-summary.json](research/position-sample-summary.json).

| Measurement | Result |
| --- | --- |
| Successful sample responses | 60/60, all HTTP 200; no retries |
| Distinct positioned aircraft identifiers | 24 |
| Aircraft reports / accepted position reports | 759 / 752 |
| Accepted airborne / ground reports | 602 / 150 |
| Accepted airborne position age | Median 0.602 s; p95 1.048 s; maximum 3.548 s |
| Accepted airborne reports within 60 seconds | 602/602; this is a report-weighted regional sample |
| Request latency | Median 0.487 s; p95 0.954 s |
| Response bytes | 474,486 total; largest 9,819 |
| Actual request-start intervals | 20.000725–20.005841 s |
| Callsign missing | 4 accepted reports |
| Quality fields missing/invalid | NACp and SIL each absent in 5 accepted reports; NIC/RC present |
| Observed trail events | 24 starts, 718 updates, 9 repeated points, 1 gap over 120 s |
| Snapshot disappearances / reappearances | 16 / 5; not arrival, cancellation or receiver-outage counts |
| Droplet resources | 19 min 41.713 s wall time; 6.752 s CPU; 17.2 MiB reported peak RAM; no swap |
| Existing scheduled OSL departures in the window | 7; all aircraft associations unresolved |

All accepted sample positions reported `adsb_icao`; this does not establish the
quality or availability of MLAT and other position sources. Seven source-derived
timestamp regressions remain quarantined. Their magnitudes and interpretation are
in the metrics file; source age rounding/alignment may contribute, so these must
not be called seven receiver outages. The existing Avinor snapshot was collected
at 15:11 UTC and is contextual scheduled evidence, not proof of subsequent actual
operations. Aircraft matching, missed departures and end-to-end routes remain
unassessed rather than reported as zero.

### Replay audit and private artifacts

The initial capture used immutable sampler source hash
`85e18b35e3667b5ac1c300bbbb87b7388196fd4f67882db5d9ac569b79a2ae01`.
Review found that a fractional-second comparison could reject an identical
position after an ISO timestamp round trip. A regression reproduced that bug;
canonicalizing to microsecond precision fixed it. The final checked analyzer also
validates optional quality fields and conservatively checks cross-day budgets.
Replay records both source hashes and retains the original capture products.

The corrected replay restores one repeated ground report: accepted positions rise
from 751 to 752, with out-of-order rejections falling from 8 to 7. There were no
other sampling requests to make this correction. All 60 raw SHA-256 values passed;
two offline replays produced identical metrics and left the attempt ledger
unchanged. The normalized replay is one private `positions.json`, with original
observation/capture times and an explicit offline-replay label.

Droplet evidence remains under `/var/lib/airplanes-position-research`. A private
local copy and corrected replay are under ignored
`work/position-research/remote/airplanes-position-research/`. Only aggregate metrics,
code and documentation are committed. The transient capture unit stopped on
completion; no recurring position job was installed. Existing route/schedule
timers and nginx remain active, and the public viewer revision remains `7040cd0`.

### Decision

- **Stage 1: go for bounded private research.** Both environments can read the
  free regional feed, and request budgets are explicit. Production access and
  publication conditions remain unresolved.
- **Stage 2 initial sample: go for further regional testing.** A 20-second cadence
  and a 60-second stale cutoff are reasonable candidates for the next experiment,
  supported by this sample's freshness and small resource use. This is not proof
  of all-day continuity, positional accuracy or scheduled-flight completeness.
- **Continuous 10–30-second polling: no-go under the observed anonymous quota.**
  An on-demand pilot could stop upstream requests when idle and share a cache
  between viewers. At 20 seconds/query, a reserved 400/day allowance supports
  about 2 h 13 min of total active polling, not a full day. The research tool's
  stricter 180/day limit supports one hour, with conservative cross-day admission.
- Before broader coverage claims, collect the other two time-of-day windows and
  compare them. Stage 3 must resolve aircraft/flight identities and assess the
  seven scheduled departures; unknown associations remain unknown. Nothing in
  this sample authorizes or publishes a live aircraft map.

## Higher-limit free feeds and contribution benefits

Researched on 29 October 2026 India time. The 500/day finding above belongs to
adsb.lol's observed anonymous endpoint; it is **not a limit shared by all free
feeds**. Continuous regional tracking appears feasible under other documented
free plans. Sustained availability and coverage still need a longer test.

### Request budget for continuous operation

One shared regional query every 20 seconds is 4,320 requests/day, or **133,920 in
a 31-day month**. At 15 seconds it is 178,560/month; at 10 seconds it is
267,840/month. A 300,000/month plan with our 20% reserve allows 240,000 usable
requests, so 15–20-second polling fits; continuous 10-second polling does not
leave the planned reserve. These calculations cover one region and one shared
upstream collector. Each extra region, endpoint and retry consumes the same
budget. Viewer count must not multiply provider requests.

### Options without receiver hardware

| Provider | Documented free access | Continuous regional fit | Verification and remaining conditions |
| --- | --- | --- | --- |
| [adsb.fi](https://github.com/adsbfi/opendata/blob/main/README.md) | Anonymous public queries at 1 request/second; geographic radius up to 250 NM | 20-second polling fits the documented rate; no daily/monthly ceiling stated | Two bounded Oslo probes passed, one locally and one on the droplet. No rate/quota headers appeared. This is not proof of unlimited access or 24-hour availability. Personal, non-commercial use with visible attribution/link; do not infer permission for unrelated data redistribution or relicensing. |
| [FlyItalyADSB](https://flyitalyadsb.com/en/data/api/) | Free email-based key; 30/minute, 300,000/month, radius up to 500 **km**; also a 100/minute IP cap | One 15–20-second regional query fits with 20% reserve even in 31-day months | No key requested and no authenticated query tested. Current plan applies since 27 October 2026; older 100/minute claims are insufficient. Free regional access needs no receiver. |
| [adsb.win](https://adsb.win/privacy-license) | Documents 20 requests/second sustained, short bursts of 40 and 16 concurrent connections | Numerically ample; not ready for our public cache/export design | Non-commercial API use is free, but systematic downloading and feed redistribution require permission. Its own terms say partner data remains merged into the live API despite display-only restrictions. Keep deferred until provenance and intended reuse are clarified; no position query made. |

**adsb.fi measured access:** the documented v3 geographic endpoint for the same
OSL center/50 NM returned HTTP 200 from both environments at 20:18 UTC on
28 October. Each response contained eight positioned aircraft with callsigns,
used about 5.3 KB and completed in 0.19–0.21 seconds. Both raw hashes passed and
all eight positions normalized without rejection. The API uses the same wrapper
shape/millisecond time observed in our adsb.lol sample. The two calls were 16
seconds apart and are not a simultaneous cross-provider completeness comparison.
Evidence is summarized in [research/alternative-feed-access.json](research/alternative-feed-access.json);
raw aircraft records remain in ignored research storage. No continuous collector
was enabled. At the time of those probes the sampler was adsb.lol-specific; the longer
test below adds a separate provider profile with identity, budgets and replay checks.

For FlyItalyADSB, the [current API terms](https://flyitalyadsb.com/en/terms/)
allow a product's server to cache data for its users, require attribution and
CC BY-SA 4.0 compliance, and distinguish that from redistributing a live API/feed
for other people's products. All devices share the key's quota. Use a key on our
server, not in browser assets. Its native API uses **kilometres and Unix seconds**;
the compatible ADS-B Exchange format uses nautical miles/milliseconds. Neither
format supplies verified airport-to-airport routes. Its [FAQ](https://flyitalyadsb.com/en/faq/)
confirms server caching, a best-effort service and error responses rather than
automatic overage billing. Authenticated Oslo coverage remains untested.

### What contributing real receiver data unlocks

| Provider | Contributor benefit | Conditions / limits |
| --- | --- | --- |
| [FlyItalyADSB feeder benefit](https://flyitalyadsb.com/en/faq/) | Pro limits free for non-commercial use: **300/minute, 10 million/month, worldwide radius** | Activate the benefit in My API from the receiver's network after it is feeding. Active contributions required, with three days of grace after stopping. Data access is documented, not tested for this project. |
| [adsb.fi feeder snapshot](https://github.com/adsbfi/opendata/blob/main/README.md) | All-aircraft snapshot refreshed twice a minute; one request every 30 seconds | Hosting a contributing receiver unlocks access from its feeder IP. This broadens area rather than raising the regional public rate. Personal/non-commercial terms still apply. |
| [ADSBHub](https://www.adsbhub.org/howtogetdata.php) | Aggregated continuous SBS/30003 TCP stream from participating stations, port 5002 | Must contribute at least one live ADS-B station and authorize access IPs in the profile. Published terms allow publication and commercial use. This is a stream rather than a per-query allowance; bandwidth, completeness and tiny-droplet processing cost are unmeasured. No connection attempted without entitlement. |
| [adsb.lol feeder re-api](https://www.adsb.lol/docs/feeders-only/re-api/) | Direct readsb HTTP API for the network, ODbL | Feeder-IP access; the documentation permits using a VPN/proxy from the station for another location. No numeric high-rate entitlement is published there, so do not call it unlimited or assume it removes our observed anonymous cap. Project-key requests are another conditional route. |
| [ADSB IQ](https://adsbiq.com/api/docs) | Documents active-feeder REST access every 20 seconds and a 10-second WebSocket push tier | Geographic stream/deltas may be useful. Data budgets still apply. API docs and [terms](https://adsbiq.com/terms) disagree about non-feeder access and key use from other IPs; defer adoption until reconciled. No account, trial or live connection started. |

The [FlyItalyADSB feeder guide](https://flyitalyadsb.com/en/community/feeder/)
and provider setup pages require a working 1090 MHz receiver, antenna and decoder
such as readsb/dump1090, with an internet connection. A receiver can contribute
outside Norway and still unlock the documented network-wide benefit. An existing
station can often feed several networks; a separate receiver per provider is not
inherently required. Its actual RF reception, uptime and eligibility must be
verified, and feeding loops must be avoided.

The droplet is a virtual server and cannot hear ADS-B radio transmissions by
itself. Running feeder software there with no real incoming receiver data does
not earn a contribution benefit. Re-uploading another API's data or inventing
messages is not a substitute for owning/operating a permitted receiver source.
With the project's no-spending rule, a feeder path is an option only if suitable
hardware and ongoing power/connectivity are already available without additional
spend. No such receiver is confirmed in this project. We have not installed
feeder software, registered accounts, requested keys or contacted providers.

### Exclusions and weaker leads

- [adsb.lol raw BEAST/MLAT output](https://www.adsb.lol/docs/feeders-only/beast-mlat-out/)
  is explicitly marked permanently paused for resource costs. Do not recommend
  this stream as an available feeder entitlement. The separate HTTP re-api and
  [ad-hoc project-key request page](https://www.adsb.lol/request) remain leads,
  with the actual approved quotas unresolved.
- [AvioADSB](https://avioadsb.org/docs/api) grants active contributors 10,000
  requests/month, versus 100/day anonymously. A higher per-second rate is not
  sufficient: even its contributor monthly quota is far below 133,920 for one
  20-second query throughout a 31-day month.
- [OpenSky's documented active-feeder allowance](https://openskynetwork.github.io/opensky-api/rest.html)
  rises from 4,000 to 8,000 daily credits with at least 30% receiver uptime/month.
  A sufficiently small region costs one credit/query, so 4,320/day can fit that
  contributor allowance, but global queries cost four credits. Its
  [operational-use written-agreement requirement](https://opensky-network.org/about/terms-of-use)
  remains; feeding alone does not establish permission for our live service.
- [Flightradar24's API FAQ](https://fr24api.flightradar24.com/docs/faq) explicitly
  says receiver hosts do not receive free API access. A contributor web/app plan
  is not an API entitlement. [ADS-B Exchange's Developer Hub](https://www.adsbexchange.com/community/developer-hub/)
  advertises a paid community API, not a verified zero-cost route for this project.
- [FlightBank](https://flightbank.co.uk/feed-adsb-data.html) documents free access
  while a real receiver contributes, but the examined feeder page does not
  establish a sustained quota, intended public redistribution rights or Oslo
  coverage. Keep it as an unverified lead rather than a primary dependency.
- ADSB IQ's [MCP limits](https://adsbiq.com/api/other/mcp) are separate from its
  REST/WebSocket tiers; a 3-day trial is not permanent free access. Do not mix
  protocol-specific quotas or count unapproved publisher access as a feeder grant.

### Recommended next decision

1. **Continue measured regional work with adsb.fi.** The one-hour test below
   completed without request failures. Next assess busy daytime coverage and
   replay a UI with explicit position aging; retain one shared upstream query.
   Reconfirm personal/non-commercial display use before a public endpoint or export.
2. **Keep FlyItalyADSB as the best documented keyed regional alternative.** Its
   published monthly quota fits continuous 15–20-second polling and explicitly
   supports a cached product display. An email-based free key and an Oslo sample
   are still required; the name does not establish Italian-only coverage.
3. **If a real receiver is already available, investigate FlyItalyADSB's free
   contributor Pro benefit first**, then adsb.fi's global snapshots or ADSBHub's
   stream. Validate entitlement and IP restrictions before deployment. A global
   access grant does not prove worldwide reception or resource suitability.

The new research establishes promising request budgets and one alternative's
bounded accessibility. It does not prove a 24-hour service, create a live map,
resolve flight numbers/routes or change the existing 500/day adsb.lol sampler.

## adsb.fi longer regional test

This bounded experiment ran for approximately one hour on the existing droplet:
180 samples, at least 20 seconds apart, using the documented v3 public endpoint
within 50 nautical miles of OSL. This is a single private research run, not a
24-hour service or a public aircraft display.

The sampler now has explicit provider profiles. adsb.fi uses its own endpoint,
attribution, ledger and default state directory. Its documentation states a
1-request/second limit but no daily allowance, and our probes returned no quota
headers. Missing quota headers are therefore accepted only for this documented
profile. A **self-imposed 360-attempt cap**, conservatively including the previous
UTC day, bounds research use; it is not a claimed provider daily entitlement.
Any stricter observed headers are retained and honored. The original adsb.lol
profile keeps its 60-sample, 180-attempt, quota-header-dependent limits.

The adsb.fi session has a 65-minute hard runtime budget, a 4 MiB response limit,
15-second request deadline and 128 MiB state budget. The transient droplet unit
adds a 64 MiB RAM cap, 64 MiB swap cap and 25% CPU quota. Failed requests are
counted before IO, stop the run and halt same-day attempts without retries or
provider switching. The prior droplet access probe is seeded into the new ledger.
No recurring position timer or Mac background job is installed.

Run the checked provider profile manually in its isolated droplet environment:

```sh
PYTHONPATH=/opt/airplanes-refresh/repo/scripts python3 /path/to/position_research.py capture \
  --provider adsb.fi --work /var/lib/airplanes-position-research-adsbfi \
  --samples 180 --interval 20
```

Implementation checks include a simulated complete 180-response session with no
quota headers, correct source attribution in capture and replay, provider ledger
isolation, stricter-header persistence, legacy adsb.lol safeguards and request /
runtime ceilings. All **85 Python tests pass**. A further regression reproduced
an invalid quota header overwriting the last known policy; the fix validates new
headers before updating the ledger and preserves the same-day halt.

### Completed hour: measured results

The captured window is **20:35:38–21:35:19 UTC on 28 October 2026**
(**02:05:38–03:05:19 India time on 29 October**, 21:35:38–22:35:19 Oslo time).
The service completed in 59 minutes 42.997 seconds. Aggregate evidence, all 180
raw-response hashes and six consecutive 30-response blocks are recorded in
[research/adsbfi-regional-test.json](research/adsbfi-regional-test.json).

| Measurement | Result |
| --- | --- |
| Request results | 180/180 HTTP 200; no request failure, retry or provider switch |
| Actual request-start intervals | 20.000623–20.014253 s |
| Distinct aircraft identifiers | 15 |
| Returned / accepted position reports | 592 / 592; no validation rejection |
| Ground state | All 592 indicated airborne; ground/MLAT behavior not established by this sample |
| Position age at capture | Median 1.036 s; p95 18.305 s; maximum 61.237 s |
| Airborne reports within 60 seconds | 591/592 (99.8%); one stale report retained and marked |
| Reports within 15 / 30 seconds | 561/592 / 571/592 |
| Response latency | Median 0.375 s; p95 0.497 s |
| Provider-wrapper age | Median 0.557 s; p95 1.440 s; maximum 2.148 s |
| Downloaded response bytes | 399,094 total; largest response 4,032 |
| Missing fields | Callsign absent in 14 reports; NACp and SIL absent in 3 each |
| Trail events | 15 starts, 545 updates, 26 repeats, 6 gaps over 120 s |
| Longest positive per-aircraft observation gap | 526.345 s; not proof of an outage or a flight endpoint |
| CPU / peak RAM / swap | 23.140 s / 18.4 MiB reported / 0 bytes |
| Recorded request budget | 180 session attempts plus the earlier droplet probe = 181; below the local 360 cap |

Freshness is conditional on returned, accepted position reports and weights
repeated observations of an aircraft. It is not a coverage percentage or an
independent positional-accuracy assessment. Missing aircraft and positions do not
enter that denominator. The API remained reachable, but the six trail gaps and
18 disappearance / 6 reappearance events may reflect region boundary crossings
or reception gaps; they do not establish arrival, cancellation or outage counts.
No flight number, airport pair or scheduled departure was independently matched.

### Variation during the hour

These are successive 30-response blocks, each spanning about ten minutes; the
same aircraft can appear in several blocks. This avoids interpreting the overall
percentile as uniform freshness throughout the session.

| Responses | Distinct identifiers | Airborne reports | Position-age p95 | Within 60 s |
| --- | --- | --- | --- | --- |
| 1–30 | 4 | 68 | 21.233 s | 68/68 |
| 31–60 | 4 | 73 | 47.660 s | 73/73 |
| 61–90 | 6 | 59 | 30.333 s | 59/59 |
| 91–120 | 8 | 132 | 1.365 s | 132/132 |
| 121–150 | 7 | 151 | 2.428 s | 151/151 |
| 151–180 | 6 | 109 | 18.305 s | 108/109 |

HTTP success and a fresh wrapper do not make every aircraft position current.
One point was already over 60 seconds old when fetched, and other points can
cross the stale threshold between polls. A future UI must age positions using
observation timestamps independently of request success, expire or visibly mark
stale positions, and break trails across gaps. Interpolation must not imply a
new measurement. The 60-second research freshness target passed; this is not
instantaneous FlightRadar24-equivalent tracking.

### Provenance, replay and decision

The capture ran committed implementation `4889e9f`, with immutable source SHA-256
`4d4b3bf1b411a2dc1e3fff9da9b426a4898e7a49e3855fff057d57f74636bc73`.
Analysis used the checked `02d260f` version, which changes invalid-header recovery,
not position normalization. All 180 response checksums passed on the droplet and
locally. Two local replays produced identical metrics, preserved the request
ledger, and matched every original capture metric except the analyzer's code
hash. Supporting-module hashes also matched the committed helpers.

Raw and normalized aircraft records remain private under
`/var/lib/airplanes-position-research-adsbfi` and ignored local
`work/position-research/adsbfi-long/airplanes-position-research-adsbfi/`.
The corrected export is one `positions.json` with provider attribution and capture
provenance. Only aggregate results are committed. The transient unit stopped and
was removed on completion. The two existing daily collectors remain enabled;
nginx and the original public route files are unchanged.

**Decision: proceed as a candidate for further regional testing and a replay
prototype, with explicit position aging.** This one late-evening 50-NM window
supports sustained 20-second querying for approximately an hour within the
measured resource budget. It does not establish 24-hour availability, peak
traffic capacity, ground coverage, worldwide reception or verified routes.
Collect a busy daytime window before broad coverage claims; establish public
reuse conditions and aircraft-to-flight matching before a live route display.
No recurring tracking service or frontend deployment is part of this test.

## Daytime Oslo follow-up, 29 October 2026

The follow-up uses the same 50-NM OSL region, adsb.fi endpoint, 20-second
cadence and committed capture implementation (SHA-256
`617270278853575f064735b215fd1f65e24484c58858ff2cc8a0a429dd64e8db`).
Its one-off droplet unit has the same 64-MiB RAM, 64-MiB swap, 25%-CPU,
128-MiB research-state and 3,900-second runtime ceilings. The
[provider's documented rate and personal/noncommercial conditions](https://github.com/adsbfi/opendata/blob/main/README.md)
were rechecked before capture.

The experiment reserves **179 requests**, approximately 59 minutes. The first
180-request launch was refused by preflight before any feed request: the previous
UTC day's 181 attempts still count toward the conservative local 360-attempt
rolling-day safety budget. The revised run fits exactly; no ledger was reset and
no limit increased. This project budget is separate from the provider's published
one-request-per-second limit. No further adsb.fi sampling is available within
this local budget until older attempts age out of the conservative window.

Aggregate reports can now be reproduced with the checked offline helper:

```sh
.venv/bin/python scripts/summarize_positions.py PRIVATE_SESSION \
  --out research/NEW_AGGREGATE.json
```

The helper verifies raw-response checksums, replays normalization, requires
semantic agreement with the original capture report, checks the requested
cadence and exports consecutive 30-response blocks. It includes source/code
hashes but no aircraft rows. Three new checks and the 85 existing Python checks
pass independently of the subsequent flight-matching stage.

### Completed morning: results

The sampled window was **06:44:44–07:44:07 UTC on 29 October**
(**07:44:44–08:44:07 Oslo**, **12:14:44–13:14:07 India**). The transient unit
finished successfully in 59 minutes 25.506 seconds. Aggregate evidence and all
179 response hashes are in [research/adsbfi-daytime-test.json](research/adsbfi-daytime-test.json).

| Measurement | Result |
| --- | --- |
| Requests | 179/179 HTTP 200; no failed feed request or retry |
| Distinct positioned aircraft identifiers | 52 |
| Accepted / returned position reports | 2,125 / 2,125; no validation rejection |
| Airborne position age | Median 1.308 s; p95 4.945 s; maximum 61.527 s |
| Within 60 seconds | 2,121/2,125 (99.8%); four stale reports retained and marked |
| Ground state | All reports indicated airborne; zero ground reports |
| Source types as reported | 2,080 adsb_icao, 39 mlat, 6 mode_s |
| Missing data | Three reports without callsigns; NACp/SIL absent in 52 each |
| HTTP latency | Median 0.396 s; p95 0.490 s |
| Downloaded bytes | 1,423,762 total; largest response 11,545 |
| Trail events | 52 starts, 2,008 updates, 62 repeats, three gaps over 120 s |
| CPU / peak RAM / swap | 35.160 s / 25.7M as reported / zero bytes |

The six consecutive blocks have position-age p95 values of 4.907, 15.084,
18.477, 2.436, 3.830 and 1.576 seconds (the last block has 29 responses).
The overall research freshness target passes, with variation during the hour.
The morning yielded more identifiers/reports than the evening, but these are
different traffic periods, not an independent coverage or provider comparison.
MLAT/mode_s labels were observed; their positional accuracy was not independently
checked. Zero ground reports means this sample cannot validate ground coverage
or provide a measured ground-to-air departure transition.

Server and local replays agree with the original report. Repeating local summary
generation gives identical results, preserves the ledger and confirms supporting
module hashes. Private raw/replayed evidence remains under
`/var/lib/airplanes-position-research-adsbfi` and ignored local
`work/position-research/adsbfi-daytime/`. The collector exhausted its reserved local
budget and finished; it does not recur. This second regional window supports
continued replay and identity research, with aging/expiry still required. It
does not establish continuous daily availability, peak-traffic capacity or
verified flight routes.
