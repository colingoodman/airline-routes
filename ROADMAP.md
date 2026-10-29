# Live aircraft tracking research roadmap

Goal: show real aircraft moving on a map, with flight numbers and airport pairs supported by evidence. Build toward that goal at **$0 in additional spend**, starting with a regional pilot around Oslo. Worldwide coverage and consistently verified flight details remain unproven.

This is a research and testing plan, updated 29 October 2026. It does not enable live polling, change production data or authorize a public live launch. Each stage ends with measured results and a continue, narrow-scope or stop decision.

## What already exists

- A deployed static passenger-route atlas, physical airport identities and source links. Its airport-to-airport lines show source-listed services, not actual flight paths.
- Daily candidate collection and a bounded Avinor schedule study on the existing droplet. Both use committed code; Mac background jobs have been removed.
- A validated refresh candidate awaiting data review. Automatic collection does not publish it.
- Real flight numbers and dated departures for the OSL/BNN research sample. The latest verified capture on 28 October contained 1,885 records. Repeat observations and independent airline checks remain pending; this is not a claim about today's collection result.
- A freshness display and immutable frontend releases with rollback. There is no integrated live position feed, aircraft-to-flight matcher or moving-aircraft UI.

Operating details are in [DEPLOYMENT.md](DEPLOYMENT.md); measured schedule results and remaining schedule checks are in [SCHEDULE_RESEARCH.md](SCHEDULE_RESEARCH.md).

## Evidence we must keep separate

| Label | Evidence required | What it does not establish |
| --- | --- | --- |
| Observed position | Provider, aircraft identifier, position timestamp and coordinates | Flight number, destination or a complete flight path |
| Scheduled flight | A dated airport/airline record, explicit flight number and endpoints | That a particular aircraft is operating it |
| Matched flight | A supported association between an observed aircraft and that dated flight, with evidence and ambiguity checks | That its planned destination will be its actual landing airport |
| Observed trail | A sequence of received positions, with gaps marked | Positions during missing coverage or future movement |
| Observed airport pair | Sufficient departure and arrival evidence for the same flight instance | A recurring schedule or the route of tomorrow's flight |

A callsign prefix substitution is not verified flight-number matching. Proximity to an airport is not proof of departure or arrival. An unknown route must not hide an otherwise valid aircraft position. A static route line must never become a simulated live flight path.

## Sequence and dependencies

| Stage | Research question | Deliverable / decision gate |
| --- | --- | --- |
| 1. Free feed feasibility | Can we obtain suitable live positions with usable access and reuse terms? | Source comparison, one bounded sample and a justified request budget |
| 2. Position quality and coverage | How fresh, continuous and interpretable are the positions around Oslo? | Captured/replayable samples and a coverage report |
| 3. Aircraft-to-flight matching | Which aircraft can we reliably associate with dated Avinor flights? | Evidence-backed matches, measured errors and explicit unknowns |
| 4. Moving-map prototype | Can we display positions, trails and uncertainty clearly? | Local prototype replaying the same captured samples |
| 5. Droplet and failure testing | Can one shared collector serve the prototype within existing resources? | Bounded load/failure results and a deployment proposal |
| 6. Regional live pilot | Does the complete experience remain useful over repeated observations? | Seven-day pilot report and a decision about expansion |

Stage 1 starts first. Stage 2 and the existing schedule study then run alongside one another. Stage 4 can start with captured positions before stage 3 completes, showing aircraft with unknown flight details. Stage 5 requires a viable feed and replay prototype. A public pilot depends on access, accuracy, resource and failure gates passing. None of this waits for three weekly route-refresh cycles; that separate gate concerns unattended route-data publication.

## 1. Establish a usable free position source

Investigate **adsb.lol first**. Its [API page](https://www.adsb.lol/docs/open-data/api/) documents public access and ODbL data. Its [OpenAPI description](https://api.adsb.lol/api/openapi.json) documents geographic and aircraft queries, requests contact for production use and warns of possible future feeder-backed key requirements. These are research leads, not a guarantee of durable access. Source documentation was checked on 29 October 2026; sustained access from our droplet still needs testing.

Keep alternatives conditional:

- [airplanes.live](https://airplanes.live/api-docs/): our earlier test returned HTTP 403 requesting project details. Recheck the documented access path; do not bypass it. Its globe viewer is not a separate data source.
- [OpenSky](https://opensky-network.org/about/terms-of-use): operational REST integration requires a written agreement. Its [API documentation](https://openskynetwork.github.io/opensky-api/) excludes schedules and related commercial flight information. It is not an assumed free production dependency.
- Any additional source must meet the same access, field, quota and reuse checks. Do not replace an unavailable free feed with a paid plan, a trial or receiver hardware purchases.

For each candidate, record access requirements, free allowances, permitted polling, geographic limits, data fields, attribution, retention, browser display, server redistribution and offline-export conditions. Distinguish an open-source API implementation from permission to reuse its data. Keep live evidence separate from the route dataset while reuse obligations are unresolved. Do not contact providers, register accounts or accept new agreements as part of the initial read-only investigation.

Start with one geographically bounded response around Oslo. Inspect aircraft identifiers, callsigns, position age, altitude type/units, ground speed, track versus heading, on-ground flags and available quality indicators. Confirm how response time differs from the last position timestamp. Test access from the droplet as well as the development environment; a successful local request is insufficient.

**Gate:** a sample can be parsed and its intended research use is supported. Before repeated requests, document a defensible cadence and hard attempt budget. If limits or production conditions are unclear, keep the experiment bounded and mark public deployment blocked on that question. Do not silently treat the absence of a published quota as unlimited access.

## 2. Measure position quality and regional coverage

Use a fixed region centered on OSL, initially a 50-nautical-mile radius if the provider supports it. Observe BNN separately only after establishing the first query's budget. Do not claim Norwegian or worldwide coverage from this region.

After stage 1 permits sampling, target three 20-minute sessions at different times of day. Proposed ceilings are 60 request attempts per session and 180 per day, with polling no faster than once every 20 seconds. These are experiment limits, not provider entitlements: use any stricter provider limit, reserve 20% of a stated allowance, count retries and stop at exhaustion. Requests get a 15-second timeout and a 4 MiB response cap; oversized responses require narrowing the sample. No unattended job is installed before these limits are justified.

Retain a bounded sample of raw responses where permitted, plus normalized positions and capture timestamps. Cap research evidence at 128 MiB initially; stop rather than silently deleting samples needed for review. Replay must preserve observation times and must not count as new live evidence.

Measure:

- Successful responses, rate limits, response latency/bytes and last-position age, including median and 95th percentile.
- Aircraft with usable positions, missing callsigns, missing quality fields, invalid coordinates and duplicates.
- Per-aircraft update gaps, disappearance/reappearance, ground versus airborne coverage, and continuity within the region.
- Scheduled departures in the same time window: observed, not observed, ineligible for comparison or unresolved. Missing tracking does not mean a flight did not operate.

Exercise absent fields, delayed/out-of-order timestamps, duplicates, implausible jumps, provider outages and receiver gaps. Reject unusable points and retain the reason; avoid inventing precision when quality fields are absent. Any numeric jump/stale thresholds must be documented, replay-tested and reported in the results.

**Gate:** select an update cadence and stale-data policy supported by measured position age and gaps. Publish the results even if continuity is inadequate. A suggested initial freshness target is 95% of displayed airborne positions no older than 60 seconds; this is a target to test, not an existing guarantee.

## 3. Match aircraft to dated flights and routes

Continue the existing Avinor study without increasing its polling to match the position-feed cadence. Seven days of future departures in one response remain one observation day. Before comparing changed normalizers, replay the earlier raw schedule evidence as described in [SCHEDULE_RESEARCH.md](SCHEDULE_RESEARCH.md).

Research the association between transponder identifiers, transmitted callsigns, registrations when available, operating carriers and marketed flight numbers. Treat the aircraft identifier as an aircraft identity, not a permanent flight identity. Build dated flight instances and retain every candidate match, evidence source, time window and rejection reason.

Test ordinary departures, missing and alphanumeric callsigns, reused flight numbers, midnight and daylight-saving boundaries, codeshares, aircraft substitutions, diversions, intermediate stops and circular services. Resolve the existing RRS/SRP/OLA map identity gaps using explicit evidence before displaying affected endpoints. Handle general aviation, cargo and airlines absent from our passenger atlas as valid aircraft with unknown schedule details.

Use dated official airport/airline information and observed departure behavior as corroboration. A schedule at OSL can support a planned destination; label the actual destination unverified until sufficient arrival evidence exists. Do not invent paired arrival times or a complete airport-to-airport trail from an OSL-only observation window. End-to-end track verification needs a separately budgeted sample covering both endpoints.

Review at least 100 proposed associations across at least two service dates, plus 20 deliberately ambiguous or nonmatching cases. Report confirmed-match precision with its numerator/denominator, match coverage among eligible observed departures, ambiguous cases and false matches. Sample across operators and difficult cases; show results by case type and do not extrapolate regional results to all flights.

**Gate:** proposed initial target is at least 98% independently supported matches in that reviewed sample, with no forced confirmed matches in the deliberately ambiguous/negative cases. This small sample is not statistical proof of general accuracy. If identity matching falls short, continue only as a position-only pilot with unknown routes. Preserve unresolved flights rather than increasing apparent coverage through guesses.

## 4. Test the moving-map experience with captured data

Build a local, optional aircraft layer while preserving route exploration. Replay the same real samples for comparisons so improvements cannot be explained by different traffic.

Test aircraft orientation, selection, timestamp/age display and short observed trails. Keep course over ground distinct from the aircraft's nose heading. Smooth motion between received points only with a documented rendering delay; identify any extrapolation and stop it at a tested short limit. Never animate indefinitely during an outage. Break trails across gaps, invalid jumps and aircraft/flight-instance changes. Handle crossing the date line and repeated map worlds using our existing map behavior.

Aircraft details should separately show position source/time, transmitted callsign, matched published flight number, planned endpoints, observed trail and unresolved identity. The UI must distinguish unknown, ambiguous, stale and unavailable data. Codeshares should not create duplicate aircraft icons. Offline exports remain a dated replay or route-only atlas, never a live display.

**Gate:** replay ordinary traffic, missing updates, resumed tabs, reordered responses and source outages. Confirm that aircraft do not jump to a static route line, frozen data is visibly stale and closing the live layer stops browser polling. Check desktop and mobile interaction and rendering performance, including 100- and 500-aircraft replay loads; these stress loads are not claims about regional coverage.

## 5. Validate the existing droplet and failure behavior

The existing droplet has about 458 MiB RAM and 1 GiB swap. Its route collector has a 160 MiB RAM cap and used roughly 36 minutes for its first full run. Measure current spare resources before proposing another service; swap is not evidence that sustained ingestion will be comfortable.

Prototype one regional upstream collector with a shared latest-state cache and a bounded observed-trail buffer. Serve the same cached response to all viewers; browser count must not multiply upstream calls. Keep provider credentials server-side if needed. Avoid user-driven arbitrary geographic fan-out: the initial service covers one fixed region, and a broader region requires a new budget.

Keep the frontend static, with an optional separate same-origin live-data endpoint. Keep live state outside immutable releases, Git, route JSON and portable exports. Decide whether the small endpoint can be served as atomically replaced JSON or needs a process after measuring the response size and desired cadence. A fresh wrapper timestamp must not conceal old underlying positions.

Benchmark 1, 10 and 50 simulated viewers against cached/replayed data, not additional provider calls. Measure CPU, peak RAM, swap activity, disk growth, upstream attempts, cache age and HTTP latency. Compare homepage/viewer latency with collection disabled, then exercise overlap with a route refresh. Initial candidate targets are at most 64 MiB additional service RAM, 128 MiB retained live state and less than 20% increase in existing-site 95th-percentile response latency under the defined test load. These are proposed ceilings to validate, not demonstrated capacity.

Exercise HTTP 429/Retry-After, 403, malformed/oversized responses, connection timeouts, disk exhaustion, process termination and server restart. Verify capped retries, backoff, single-collector locking, atomic cache replacement and preserved timestamps. If source access fails, show tracking unavailable; do not cycle endpoints/accounts. Ensure exceptions never affect nginx, the static atlas, schedule evidence or the last validated route candidate.

**Gate:** propose service CPU/RAM/disk/runtime limits only after measurements. If the droplet cannot meet the targets, reduce the region, cadence, retained trails or supported viewers. If that still fails, stop the live pilot rather than resize or buy another service. Test stopping the live collector and rolling back the frontend without disturbing existing jobs.

## 6. Run and evaluate a regional pilot

A public pilot requires the earlier access, matching/display and resource gates to pass. A position-only pilot remains an explicit option if reliable route matching is not established. Keep geographic coverage and update delay visible.

Observe at least seven distinct days, including daytime/evening sessions and overlap with scheduled collection. Record actual sampled periods and downtime; intermittent sessions must not be reported as continuous uptime. Report position freshness, continuity, match precision/coverage, unknown aircraft, false matches, API attempts, outages and droplet load. Add independent spot checks across multiple operators and dates.

Expansion order is evidence-driven: another Avinor airport, a second region with suitable ground truth, then a separately measured coverage expansion. Each needs a revised request/resource budget and endpoint-matching assessment. Full-day persistence, global snapshots, complete flight histories, worldwide schedules and guaranteed availability are outside the initial pilot.

**Gate:** recommend regional expansion, continued limited observation, position-only operation or stopping. Worldwide tracking needs a fresh feasibility decision; success around Oslo does not establish global coverage.

## Outputs, checkpoints and existing work

Maintain one concise research report and a machine-readable metrics file, with sample manifests linking exact provider responses, observation windows, parser versions and test results. Keep raw captures private to the research state unless their redistribution is supported. Separate measured facts, proposed targets and unresolved questions. Check each implementation stage and commit it before proceeding.

Expected checkpoints, measured from the start of implementation rather than promised calendar dates:

- First 1–2 working days: source/access decision, bounded position sample and an initial coverage/freshness result. Report a blocker immediately if no source qualifies.
- Next 2–4 working days: replay prototype and first manually checked aircraft-to-flight associations. These can proceed alongside repeated schedule observations; access and data quality may extend the work.
- After at least seven distinct observation days: first combined regional-pilot assessment. Public live deployment remains dependent on the gates above and is a separate implementation step.

Keep the daily route candidate and Avinor research jobs running within their existing budgets. Review refresh candidates separately; retain the three-weekly-cycle gate before considering unattended route publication. Broad schedule-provider expansion and historical archive ingestion are deferred until the live position and identity experiments show which missing evidence would materially improve this pilot.

The first implementation slice has delivered stage-1 access research and one
checked stage-2 Oslo sample with capture/replay tooling; see
[LIVE_TRACKING_RESEARCH.md](LIVE_TRACKING_RESEARCH.md). adsb.lol's observed
500/day anonymous allowance rules out continuous 20-second polling on that feed;
[other free feeds and contributor benefits](LIVE_TRACKING_RESEARCH.md#higher-limit-free-feeds-and-contribution-benefits)
have higher documented limits, with adsb.fi access verified through checked
evening (180-response) and morning (179-response) regional tests. FlyItalyADSB
keyed access remains untested. The first
[aircraft-to-flight matching pass](FLIGHT_MATCHING_RESEARCH.md) produces 14 dated
flight-number/planned-route hypotheses across those two service dates, with no
independently confirmed aircraft/flight associations. Alphanumeric callsigns,
ground/departure corroboration, the independent precision gate, further time-of-day
and availability sampling, and a permitted sustainable public live-data path
remain unresolved. Existing collection and public route data are unchanged.
