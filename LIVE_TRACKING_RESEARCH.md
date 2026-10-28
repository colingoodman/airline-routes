# Live position feed research

## Stage 1: access decision

Checked on 29 October 2026 India time (probe timestamps below are UTC). Proceed
with bounded, private adsb.lol research around OSL. Public live deployment remains
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
