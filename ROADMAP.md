# Data refresh and flight schedule roadmap

Status: implementation in progress. Source access checked on 28 October 2026. Candidate tooling for milestone 1 and the bounded runner/systemd templates for milestone 2 are implemented and tested; recurring jobs and new integrations are not enabled. Live candidate validation remains a separate acceptance check. Milestone 3 has a tested Avinor capture tool and a first measured sample; see [SCHEDULE_RESEARCH.md](SCHEDULE_RESEARCH.md) for unresolved gates.

Keep the project at **$0 in additional spend**. First make the existing route dataset refreshable and auditable. Then investigate adding genuine flight numbers and dated schedules where free sources support them. Worldwide schedule coverage is an open research question, not a promised deliverable.

## Scope and constraints

- Use existing compute and storage. No paid API plans, trials that convert to billing, new hardware, or paid infrastructure. Set request, disk and runtime budgets before enabling a collector; stop when a budget is exhausted.
- Keep the viewer static. Collect data separately, validate a candidate release, and serve generated files through the existing deployment process.
- Preserve physical airport identities, reviewed overrides, airline/brand distinctions and source attribution. A changed code must not silently move a route to a different airport.
- Keep three distinct kinds of evidence: a source-listed route, a dated scheduled flight, and an observed flight. One must not silently become another.
- Provider permissions must cover the intended use: map display, retained records, downloadable JSON and the offline portable viewer. Keep restricted data out of those artifacts unless the provider explicitly permits it.

## Starting point

`scripts/rebuild.py` downloads OurAirports metadata and rebuilds `web/data.json` and its compact projection. It writes directly to the canonical files. `scripts/collect.py` reuses cached Wikipedia responses without an expiry, and labels source retrieval dates using the supplied snapshot date. Rerunning it with a newer date therefore does not prove that the evidence was fetched again.

The roster, hub selections, model classifications, aliases and discovery audit are reviewed inputs. Fetching airport pages does not update those decisions. Validation also includes fixed membership counts and example-route expectations, which need a review path when the real network changes.

Deployment exports committed HEAD into an immutable release directory identified by its Git commit. A refresh must produce a new reviewed data commit before deployment; it cannot replace files inside an existing release. See [DEPLOYMENT.md](DEPLOYMENT.md).

## Milestones

| Milestone | Deliverable | Completion condition |
| --- | --- | --- |
| 1. Reliable candidate builds | Isolated rebuild, honest freshness metadata, expiring cache and change report | A failed or partial collection cannot alter the released dataset |
| 2. Automatic refresh collection | Recurring collection on existing infrastructure, bounded resource use and release checks | Three consecutive weekly candidate runs complete with reviewed results; failure and rollback paths are exercised |
| 3. Free schedule investigation | Comparable source samples, coverage measurements and reuse decisions | At least one source is suitable for a bounded pilot, or the evidence establishes why none qualifies |
| 4. Schedule pilot | Optional, dated flight details for supported airports | Times, identities, codeshares, expiry and offline behavior pass validation within the free quota |
| 5. Observed route investigation | Small experiment using open aircraft traces | Airport matching accuracy and resource costs justify continuing, or the experiment is closed |

Milestones 1 and 2 take priority. Milestone 3 can run alongside them. Milestone 4 depends on the investigation result. Milestone 5 is optional and must not delay the refresh work.

## 1. Make refreshes reliable

### Isolate inputs and outputs

- Add explicit candidate output paths to the rebuild and projection workflow. Stage raw responses, normalized data, projection and validation results outside `web/` until promotion.
- Record an input manifest covering the collector version, roster, hub evidence, aliases, metadata corrections/additions, brand models and discovery audit. Some inputs currently load relative to the collector itself; make their provenance explicit.
- Preserve OurAirports' persistent row identifier alongside public airport codes. Compare against that identity when codes, names, closure status or coordinates change. Flag conflicts with reviewed overrides instead of overwriting them.
- Separate actual fetch/check timestamps from the snapshot's effective date. Record source revision/hash and whether evidence was fetched, revalidated or reused. Failed requests must never make old evidence appear newly fetched.

### Refresh sources politely

- Introduce cache expiry and a deliberate refresh mode. Use conditional requests where supported, descriptive identification, bounded retries and backoff. Respect provider rate limits and `Retry-After`; do not switch endpoints to evade a block.
- Deduplicate requests for shared airport pages. Resume interrupted work without refetching successful pages unnecessarily.
- Preserve the last successful release on failure. Retained evidence remains visibly dated and must not be promoted as a successful fresh snapshot.

### Compare before publishing

Produce a concise change report: airport identity/coordinate changes, route additions/removals, seasonal/future changes, source ages, missing carrier rows, unresolved destinations and coverage by origin.

Existing partial coverage is the comparison baseline, not grounds to invent missing routes. A newly inaccessible source is a collection failure, not evidence that its services ended. Changes in airport identity, roster, alliance membership or hub selection require review. Initially, route additions and removals also require review.

Keep structural validation separate from reviewed snapshot expectations. Retain example and membership checks, but allow a documented, evidence-backed update when a real-world change invalidates an old expectation.

**Acceptance:** exercise unchanged inputs, expired caches, revalidation, rate limits, interrupted downloads, missing tables, malformed CSV and changed airport codes. Each failure leaves canonical files intact. Rebuilding fixed captured inputs produces the same semantic dataset. Run the existing Node/Python suites and dataset/projection validation on successful candidates.

## 2. Enable automatic collection and controlled releases

| Data | Initial cadence | Release policy |
| --- | --- | --- |
| OurAirports metadata | Daily check | Stage changes; review identity conflicts, code reassignment and material coordinate changes |
| Wikipedia airport route evidence | Weekly refresh | Stage a candidate and compare with the last release |
| Roster, alliances, hubs and brand classifications | Monthly review, plus significant announcements | Update reviewed inputs with evidence |
| Schedule records | Provider-specific, decided in milestone 3 | Refresh and expire independently of the route snapshot |

Use a single runner on existing infrastructure with a lock against overlapping runs, explicit timezone, timeouts, resumable caches and bounded artifact retention. Choose its location after measuring a full staged rebuild and confirming network access. A system timer on the existing server is a candidate; the static viewer must not depend on the collector being online.

Start with automatic collection and reviewed promotion. After three successful weekly cycles, define concrete change-size thresholds from the observed baseline and allow only agreed routine changes to publish automatically. Hold identity changes, new coverage gaps, unexpected carrier loss and unusually large diffs for review. Document those thresholds before enabling unattended publication.

For every release:

1. Validate data, source ages, references and the compact projection; run the affected tests.
2. Commit the accepted data changes and deploy that exact commit with the existing release script. Do not create releases solely because a check timestamp changed; keep successful no-change checks in runner state.
3. Verify origin and public assets, matching data/projection hashes, source links and the existing homepage. Exercise airport filters, comparison and the portable viewer after schema changes.
4. Retain the previous release and use the existing atomic switch/rollback process. Define bounded retention for inactive releases so regular refreshes cannot exhaust disk space.

Record last attempted check, last successful check and last published data separately. Expose the relevant data age and partial coverage in the viewer. Notify only on publication, actionable failures or required review; keep unchanged checks quiet.

**Acceptance:** demonstrate that overlapping jobs are prevented, failed collection/validation cannot deploy, a failed activation restores the previous release, and a no-change run creates no data commit. Scheduling and deployment changes are future implementation work, not part of this roadmap.

## 3. Investigate free flight numbers and schedules

### Source shortlist

| Source | Investigation | Current evidence and limits |
| --- | --- | --- |
| [Avinor](https://partner.avinor.no/tjenester/flydata/) | First pilot: Oslo and a smaller Norwegian airport | Public XML request returned HTTP 200 with flight IDs, scheduled times, gates and statuses. Covers Avinor airports. Free reuse requires attribution; cache on the server and respect its three-minute polling guidance. Verify the available time window and codeshare semantics. |
| [Swedavia](https://apideveloper.swedavia.se/faq) | Compare a major and smaller Swedish airport | Official free account provides 10,000 requests/month and stops access at quota exhaustion. Requires registration/key. Authenticated responses, time horizon, retention and export permissions remain untested. |
| [Finavia](https://apiportal.finavia.fi/) | Compare Helsinki and a smaller Finnish airport | Official portal offers a free Public Flights API with registration/key. Confirm the actual subscription quota, fields, date horizon and retention/export rights. |
| [AirLabs](https://airlabs.co/docs/schedules) | Optional comparison for airports outside the Nordic feeds | Rendered [pricing](https://airlabs.co/#Pricing) lists 1,000 monthly free requests for personal use. Schedule docs specify up to ten hours ahead and 50 records/page for free keys. Confirm field access and display/export rights. This quota cannot support daily refreshes of all our origins. |
| [US BTS](https://www.transtats.bts.gov/ontime/Index.aspx) | Assess historical flight-number and frequency enrichment | Free monthly US domestic reporting-carrier records include flight numbers and scheduled/actual times. Historical coverage must stay separate from future schedules. |

OurAirports remains the airport reference: [nightly public-domain downloads](https://ourairports.com/data/) and [field definitions](https://ourairports.com/help/data-dictionary.html). Its `scheduled_service` flag indicates whether scheduled airline service exists; it supplies no flight timetable.

### Investigation method

- Use a fixed sample of major/small airports, mainline/regional operators, domestic/international services and codeshares. Include airports already in the map so matching quality can be measured.
- For each provider, record authentication, permanent free quota, pagination, time horizon, timestamp semantics, update behavior, available fields, attribution and display/retention/export permissions. Recheck access terms before integration.
- Compare samples with dated official airline/airport information. Measure missing flight numbers/times, unresolved airport identities, duplicate codeshares and stale or conflicting records. Do not claim worldwide completeness from a small sample.
- Observe samples across at least seven days where quotas permit. Calculate the request budget including pagination, retries and rechecks before proposing a cadence; reserve at least 20% of the free allowance.
- Fail closed at the free quota. Keep keys outside browser files, Git, downloaded datasets and portable HTML. Do not sign up for billing or accept account terms automatically as part of the investigation.

Produce one source comparison with a go/no-go decision per provider and a bounded pilot proposal. Use only sources whose access and reuse permissions fit the proposed delivery. If no source qualifies, finish the investigation with that finding and continue shipping refreshed route data.

## 4. Add a bounded schedule pilot

Start with Avinor if milestone 3 confirms suitability. Keep schedules in a separate generated artifact, with its own source coverage, fetch time and expiry. Load it when an airport or route is inspected so global startup stays small. The map remains usable if schedule collection fails.

Publish bounded static snapshots through the same committed, immutable release process. Choose the cadence after measuring the source horizon and repository/release growth; polling a provider does not itself trigger a deploy. A continuously updating departure board would need a separate publication design and is outside this pilot.

The proposed data contract must include:

- Source-specific record ID, physical origin/destination airport references and departure-local service date.
- Published flight number as text, with marketing and operating carrier/number stored separately when explicitly supplied. Preserve leading zeros and suffixes; unknown values remain unknown.
- Scheduled departure/arrival timestamps with verified timezones or offsets, separate from estimated/actual times. Use a maintained free timezone source or provider offsets; OurAirports does not provide this mapping.
- Source, fetched time, valid-until time and any explicit operating days/effective dates. A near-term departure board must not become a presumed recurring weekly timetable.

Handle overnight arrivals, daylight-saving changes, cancellations and codeshares explicitly. A source's term “direct” does not itself establish nonstop operation. Missing schedule data means unavailable, not no service. Never infer a marketed flight number solely by replacing the prefix of an ADS-B callsign.

Show exact date, timezone, source and freshness beside flight details. Expired records leave the upcoming schedule view; a failed request must not make cached records appear current. Keep provider attribution visible.

Only include schedule records in downloadable JSON or portable HTML when retention and redistribution rights permit it. Otherwise keep those exports route-only and explain the coverage. A frozen offline schedule must show its capture date and must not be labeled live.

**Acceptance:** confirm sampled identities and times against official information; test midnight/DST cases, leading zeros, duplicate codeshares, cancellations, expired records, quota exhaustion and collection outages. Document coverage and measured resource use. Broader rollout requires a separate decision based on the pilot.

## 5. Investigate observed routes separately

[adsb.lol's API](https://www.adsb.lol/docs/open-data/api/) returned HTTP 200 without a key during research. It also offers [free daily track archives](https://www.adsb.lol/docs/open-data/historical) under ODbL. Test a small, capped historical sample before considering regular ingestion. Record attribution and derivative-database obligations separately from the existing sources.

Investigate whether sufficiently complete tracks can establish an airport pair, observed departure/arrival times and a callsign. Require evidence near both airports; do not treat first/last received coordinates as automatic takeoff/landing positions. Record uncertainty and reject ambiguous legs. Compare results against the schedule pilot and manually verified flights.

The possible output is “observed operating during this period,” with a last-observed date. It does not establish a future schedule, bookability, marketing carrier or absence of seasonal service. No live aircraft overlay is included in this roadmap.

Do not make the refresh pipeline depend on these sources without resolving their current limitations:

- [airplanes.live](https://airplanes.live/api-docs/): the public test returned HTTP 403 requesting project details by email. Access and permission to retain/export data are unconfirmed. [globe.airplanes.live](https://globe.airplanes.live/) is its viewer, not a separate schedule source.
- [OpenSky](https://opensky-network.org/about/terms-of-use): current terms require a written agreement for operational REST API integration, including live nonprofit services. Its [API documentation](https://openskynetwork.github.io/opensky-api/) excludes commercial schedule data.
- [adsbdb](https://github.com/mrjackwills/adsbdb): route mappings are available, but its README restricts copying, publishing or incorporating that route data into other databases without explicit permission.

**Acceptance:** publish measured matching quality, coverage gaps, download size, processing time and storage needs for the sample. Proceed only if the results are useful within existing resource budgets; otherwise close this workstream without delaying refreshes or schedules.

## First implementation slice

Implement milestone 1 first: isolated candidate output, honest source timestamps, explicit cache refresh, input manifest and a semantic change report. Deliver one locally validated candidate against the current release before installing any recurring job. In parallel, define the Avinor sample and quota/rights checklist for milestone 3. Leave production data and serving behavior unchanged until a candidate is accepted for release.
