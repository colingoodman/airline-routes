# Alphanumeric callsign investigation

Checked on 29 October 2026. **No permitted public API for a dated operational
callsign-to-commercial-flight-number mapping has been established for this
project.** Keep these aircraft visible as unknown flights in a future position
layer. Do not translate letters into numbers, strip suffixes or force the nearest
departure. This is an access/evidence gap; it is not a position-feed quota issue.

## What the sample actually contains

The first matcher's generic unsupported-format bucket contains more than airline
alphanumeric callsigns. The checked offline inventory separates their shapes and
compares registration-like values with the source's reported registration.

| Unsupported-format episodes | Evening | Morning |
| --- | --- | --- |
| Reviewed carrier prefix with alphanumeric suffix | 6 | 19 |
| Other company-shaped identifier, carrier unreviewed | 0 | 10 |
| Equals a registration as reported | 0 | 1 |
| Other format | 0 | 1 |
| Total | 6 | 31 |

The 19 morning reviewed-carrier cases comprise 10 NOZ, five SAS and four WIF
episodes; the evening has two of each. These are observed identifier episodes,
not proven passenger departures from OSL. Other company-shaped values may be
airlines, cargo, special operations or something else; shape alone does not
establish the operator. Registration equality is only as reported, not independent
registration verification.

Aggregate evidence is in
[the morning inventory](research/callsign-inventory-daytime.json) and
[the evening inventory](research/callsign-inventory-evening.json). Raw identifiers
and positions remain private. Reproduce without network requests:

```sh
.venv/bin/python scripts/callsign_inventory.py PRIVATE_COMPLETE_SESSION \
  --out research/NEW_INVENTORY.json
```

The tool verifies the raw capture before classification, reuses the existing
episode rules and records implementation/reference hashes. Repeated inventories
agree and preserve the original evidence. All **109 Python tests pass**, including
three new tests for mixed identifier types, read-only replay and corrupt/incomplete
evidence. The existing matcher and its refusal to guess remain unchanged.

## Why a generic decoder is unsafe

The [ACI callsign definition](https://aci-standards.atlassian.net/wiki/spaces/ACIDD/pages/17695395/Callsign)
distinguishes the operational flight-plan identifier from the commercial number.
They can differ to avoid radio confusion, and a callsign can be reused on more
than one flight leg in a day. Registration callsigns are also a normal case.
An evergreen `callsign → flight number` dictionary therefore cannot establish
a dated flight instance on its own.

[EUROCONTROL's published similarity rules](https://www.eurocontrol.int/sites/default/files/2022-06/eurocontrol-call-sign-similarity-rules.pdf)
describe allowable numeric and alphanumeric formats. They describe how identifiers
can be structured, not how to reverse them into ticket numbers. The inventory's
company-shaped category is deliberately broader than the recommended suffix
formats; it is a shape bucket rather than a standards-compliance verdict.

## Sources investigated

| Source | Result and decision |
| --- | --- |
| [SAS dated flight status](https://www.flysas.com/ie-en/flight-status) | Nine numeric candidates' dated schedules checked in the rendered UI. Expanded details expose scheduled, gate-departure and takeoff times, but no operational callsign or registration was available in those reviewed results. Useful corroboration; no alpha resolver established. |
| [Swedavia arrivals](https://www.swedavia.se/arlanda/ankomster/) | One dated Norwegian airport pair checked. The reviewed row exposes flight number, airport, time and status, not an aircraft/callsign link. No API subscription or new polling was configured. |
| [EUROCONTROL CSS](https://www.eurocontrol.int/service/call-sign-similarity-service) | Level 0 guidance is public. The schedule deconfliction tool belongs to level 1, requiring subscription and a service agreement. Public guidance is not an anonymously accessible mapping database; no access requested. |
| [EUROCONTROL NM B2B](https://www.eurocontrol.int/service/network-manager-business-business-b2b-web-services) | Operational stakeholder profiles, eligibility and usage agreements govern access. This project has no established access. No certificate, agreement or account was requested; not an approved zero-cost dependency. |
| [ADSBDB](https://github.com/mrjackwills/adsbdb) | Its response can contain ICAO/IATA callsign forms and route endpoints, but the README requires explicit permission to incorporate route data. The documented response does not establish the required operating date. Still excluded; no route query or ingestion. |
| [adsb.fi](https://github.com/adsbfi/opendata/blob/main/README.md) | Existing captures supply transmitted callsigns and reported aircraft registration. No dated commercial-flight mapping was present in the sampled aircraft records. Higher feeder access to snapshots does not itself establish this missing association. No additional feed requests were made. |

These findings do not prove no suitable free source exists anywhere. They mean
the sources checked here do not provide a tested, permitted mapping suitable for
automatic confirmation. A public website check also does not grant API or bulk
redistribution rights.

## Concrete next experiment

Use the 19 morning reviewed-carrier operational identifiers as the first private
review queue, prioritizing the ten NOZ cases. Seek an explicit mapping tying the
operational identifier to a commercial flight on that service date, ideally with
registration and flight-leg endpoints. Preserve source, capture time, date,
operator, direction and all conflicting candidates. Do not make a permanent
mapping from a single day's example.

If no permitted dated mapping becomes available, investigate observed endpoint
and departure/arrival behavior as **additional hypothesis evidence** after a new
capture budget is available. One 50-NM airborne-only window cannot establish the
full route. Test close departures, arrivals, overflights, delayed flights and
callsign reuse before considering any increase in confidence. Keep flight number
and actual destination unknown when the evidence is insufficient.

The [14-case external review](research/candidate-review.json) now has ten
corroborated dated flight/endpoint records and four unresolved official checks.
It still has zero independently confirmed aircraft links. The roadmap's precision
gate remains pending; schedule agreement must not be counted as match precision.
