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

## Stage 2: bounded Oslo position sample

Implementation and measured results will be recorded here after capture and
replay checks. The initial deliverable is one 20-minute session; the roadmap's
three sessions at different times of day remain a broader follow-up measurement.
One evening sample cannot establish all-day, Norwegian or worldwide coverage.
