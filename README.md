# Airline network route map

A local interactive map and one normalized JSON dataset of worldwide passenger airline networks. The snapshot date is **27 October 2026**.

See [ROADMAP.md](ROADMAP.md) for the proposed zero-cost automatic refresh pipeline and investigation of real flight numbers and dated schedules. Candidate collection and Avinor research captures run through isolated systemd jobs on the droplet; no Mac login/background jobs are used. Publication remains reviewed, and schedule display is not yet enabled; see [DEPLOYMENT.md](DEPLOYMENT.md#candidate-refresh-runner-collection-only) for operation and shutdown.

The expanded snapshot contains **572 carriers/brand networks, 1,304 carrier–origin relationships at 699 distinct hub/base airports, 3,358 airports, and 32,648 listed service records**. It retains all 100 carriers from the previous version and adds 472. Another **650 future or suspended/ended entries** are separate from the displayed network.

The search audited **1,310 directory entries**: 955 in Wikipedia's worldwide passenger inventory, 197 regional entries, and 158 current low-cost entries. These overlap and are not 1,310 distinct airlines. After identity and operating-status review, 728 carrier proposals reached route admission; 572 had at least one usable origin. The complete candidate and origin decisions are embedded in `web/data.json`, including 156 rejected carrier proposals and 323 rejected origin proposals. Rejection means insufficient usable evidence for this map, not necessarily a defunct airline.

**Coverage remains partial:** 159 linked destination entries across 80 admitted origins could not be resolved safely. Their resolved services are displayed, their coverage is `parsed_with_unresolved`, and every gap remains in `issues` with its source. The map header shows the partial-origin count. The dataset is a sourced reference snapshot, not an exhaustive worldwide timetable.

## Hosting

Live viewer: [colingoodman.net/airplanes/](https://colingoodman.net/airplanes/). See [DEPLOYMENT.md](DEPLOYMENT.md) for server paths, repeatable deploys, nginx configuration, verification and rollback.

## Run

Requires Python 3. From this repository:

```sh
npm start
```

Or:

```sh
python3 -m http.server 8080 --bind 127.0.0.1 --directory web
```

Open <http://127.0.0.1:8080>. No API keys, build step, online map tiles, or runtime package installation are needed. Leaflet, world outlines and data are included locally. Ordinary source files need an HTTP server; the portable viewer below opens directly.

The map initially loads the compact, generated `web/map-data.json` display projection. **`web/data.json` remains the complete normalized download**, including all audit and provenance records. `npm run build:data` regenerates the projection after data changes; validation rejects a stale projection. The portable viewer embeds both and creates the full download only when requested.

The full-width map wraps east and west, repeating land, routes and pins across the date line. Filters sit underneath. Land, routes and airports have ordered panes; land cannot cover the network. “Fit routes” includes full curved paths and chooses a Pacific-centered extent when appropriate. Pins and routes open source evidence. Results and Airport details shortcuts make the sections below the map accessible without scrolling through every filter.

## Explore and compare

Search by airport code, city or name above the map, or select a pin or result airport. **Inspection focuses the details and destination list without applying an airport filter.** “Explore this airport” applies a touching-airport filter and fits its routes. Details include matching airlines/alliances, countries, documented hub/base roles, and source coverage. A focused airport can have no matches under the current filters; remove its focus chip or clear filters to recover.

Airport filters have three explicit modes:

- **Touches any selected airport:** either recorded endpoint belongs to the selection.
- **Between selected airports:** both endpoints belong to the selection; requires two or more selected airports.
- **Listed from selected hubs/bases:** the recorded hub/base endpoint belongs to the selection. This describes the source record, not independently verified flight direction.

Multiple choices within a category use OR; different categories combine with AND. No explicit airline selection means all eligible carriers. Incompatible selections stay visible and clearable. Seasonal and charter controls are independent; seasonal services are included and charters excluded by default. Low-cost and regional filtering remains scoped to documented service brands.

Every active restriction appears in removable chips. **Clear filters** clears selections, focus, comparison and searches while retaining map position and display/sorting preferences. **Reset view** also restores display defaults and world extent. HTTP views serialize filter modes, geographic/distance filters, focused airport, comparison/category visibility, display preferences and sorting into shareable URLs; older airline/airport URLs continue to work. Search text and map position are transient. Portable file views work offline but do not rewrite their URL.

The **Destinations** tab groups matching evidence by connected airport (or all endpoints in the global overview); **Service evidence** shows individual source entries. Both are searchable and paginated. Destination sorting supports name, code, country, approximate distance from the focused airport, and airline count. Evidence sorts by airline, hub/base, destination or distance. Airline choices sort by name, number of matching endpoint airports, or matching hub/base endpoints. Counts reflect filtered source records, rather than a complete timetable. Hovering or keyboard-focusing result rows highlights their network on the map.

Color by **alliance** or **airline**. Airline colors are deterministic, but many carriers can have similar colors: select fewer carriers for readable comparisons. Non-aligned routes use a muted overview color. Selected networks receive stronger strokes. Route hover highlights endpoints and shows codes, airlines, approximate distance and service attributes next to the pointer; clicking exposes all matching carriers' source evidence. Destination pins grow with zoom and have an additional five-pixel click tolerance.

Airport-code labels have Off, Automatic and On modes. Automatic shows focused/selected airports at every zoom and adds other visible airports from zoom 4. On labels visible airports subject to collision avoidance. Selected labels have priority. Labels and routes repeat across the date line. Identifiers fall back to ICAO/local identifiers where IATA is absent.

Country/territory and region filters apply to **either endpoint, both endpoints, the hub/base endpoint, or the destination endpoint**. Country and region restrictions must match the same endpoint. `web/geography.mjs` contains a public-domain OurAirports country-to-region mapping derived from the original metadata snapshot, with its source SHA256. A transcontinental country uses the majority region among its source airports; territories retain their own classifications, and unmapped countries use Unknown. This is a country-level convention, not an airport-coordinate boundary calculation.

The distance controls provide minimum/maximum sliders and numeric inputs, with kilometres or miles. They use cached spherical great-circle distances (mean Earth radius 6,371.0088 km), rather than actual flown paths. Units change presentation without changing the selected physical range. Slider updates are debounced while dragging.

Choose **two different airlines** for comparison. Their unordered airport pairs are classified as shared, A only or B only; with an airport focused, comparison is limited to its connected destinations. Reciprocal records are deduplicated while every source entry remains available. Shared/A/B visibility toggles affect the map and results; summary counts precede those toggles. Comparison uses the two selected airlines instead of the ordinary airline selection, retaining other filters equally for both. Changing an ordinary airline selection exits comparison. Comparison colors override the display palette; airport pins are neutral. Differences reflect the dataset's uneven source coverage, not proof that an airline does not operate a route.

## Low-cost and regional filters

**Yes, low-cost status can be detected programmatically when Wikipedia explicitly documents it.** The dataset uses nullable `low_cost` and `regional` flags:

- `true`: the same carrier/brand appears in the current geographic low-cost/regional directory, or its first present-tense introductory description explicitly identifies that business model.
- `false`: an explicit full-service/legacy description supports a non-low-cost classification.
- `null`: missing, mixed or conflicting evidence. Absence from a list, flag-carrier status, fares, nationality, company ownership and codeshares do not establish a negative.

129 admitted carriers have a positive low-cost classification and 110 have a positive regional classification. Additional source-named service brands can qualify even when the parent is unknown: **Air Canada Rouge is low-cost; Air Canada Express is regional; those facts do not classify all Air Canada services.** Brand-level explicit classifications take precedence over carrier flags. The filters operate on individual service records, and all claim evidence is retained. The non-low-cost option is deliberately conservative and has few carriers; most unclassified network carriers remain unknown.

Model changes preserve explicit airline selections. An incompatible combination shows no services and keeps the selection available to clear. The regional checkbox can combine with the low-cost dropdown.

## Portable viewer

```sh
node scripts/package.mjs /absolute/path/alliance-map.html
```

This embeds the same data, outlines, styles and library in one HTML file. Open it directly without a server or network. Its download button exports the embedded JSON. File-based viewers do not update the URL as filters change.

## Normalized single-file data

**`web/data.json` contains the complete data deliverable**, including evidence and the discovery audit.

| Collection | Key | Meaning |
| --- | --- | --- |
| `alliances` | `id` | Three alliances, Non-aligned and Suspended members; color and category kind |
| `airlines` | Stable `id` | Membership type, enumerated brands, model flags and claim evidence |
| `service_brand_models` | Carrier-qualified `id` | Brand name, carrier reference, model flags and evidence |
| `airports` | `id` | Codes, coordinates, municipality, country and metadata source |
| `hubs` | (`airline_id`, `airport_id`) | Hub/base/focus-city role, source, coverage, counts and notes |
| `routes` | Stable `id` | Carrier, origin, destination, source brand, model reference, status and service type |
| `excluded_routes` | Stable `id` | Future and suspended/ended source entries |
| `airport_aliases` | `wikipedia_title` | Reviewed physical airport mapping with evidence |
| `sources` | `id` | URLs, retrieval dates, pinned revisions and route HTML hashes |
| `issues` | — | Every unresolved destination at admitted origins |
| `discovery_audit` | — | Inventory, carrier/origin admission decisions, rejected identities and evidence gaps |

Carrier IDs usually use IATA brand codes. Collisions use explicit `icao:` or `wiki:` namespaces and retain identity notes; distinct airlines are never merged solely because they share a code or similar spelling. Australian Air Link and South African Airlink are distinct. Hawaiian retains stable brand key `HA` despite operational integration under Alaska's code.

Airport IDs use IATA when available; otherwise `icao:` or `oa:` namespaces preserve documented uncoded facilities. `iata` and `icao` can be null. An airport's local identifier is not automatically treated as ICAO. Most metadata and coordinates come from OurAirports; one separately sourced Wikipedia airport addition (Sukilumba, ICAO VNFN) has its own provenance. Reviewed metadata corrections match physical row IDs and preserve their coordinates. Conflicting IATA assignments remain separate: Nong Khang and Saravan use ICAO namespaces without reassigning codes from another airport. Alexandria's former HBE queries normalize to current ALY at the same Borg El Arab location.

Every route references its carrier, service brand, two physical airports, and pinned airport-table evidence. There is no Cartesian product of an airline's destinations and hubs. Hub-to-hub routes may appear in both directions when both tables list them; mainline and regional brands can have separate records. The map draws one connection per carrier and unordered airport pair, retaining all source records in its popup. Comparison mode combines the two carriers into one connection per airport pair.

`listed` means present in an ordinary source passenger row; `seasonal` means explicitly labeled seasonal, including section-level labels. Neither guarantees operation on a particular day. `change_date` is parsed from the note, with month-only dates represented by the first day. Future/undated announced starts and suspended/ended entries are retained separately and omitted from the map. Future closure notes do not prematurely remove a currently listed service. Notes describing a `via` stop are preserved.

## Research method and limits

1. Preserve the 60 verified active full alliance members (26 Star Alliance, 18 SkyTeam, 16 oneworld). Explicit affiliates and Juneyao's connecting-partner status retain distinct membership types; they do not increase the full-member counts. Aeroflot and S7 use a separate suspended-members category. Alaska remains in oneworld. Other regional airline groupings and codeshares do not imply membership in these alliances.
2. Search worldwide passenger, current regional and current low-cost inventories. Review airline articles for operating dates, explicit hubs/bases/focus cities and company identity. Country directories and direct operating-airport statements can establish a small carrier's origin when explicit; headquarters cities and destination lists cannot. Exclude cargo-only, ceased, planned and ambiguous entries from the proposed passenger roster. Preserve candidate decisions.
3. Use source-designated hubs, secondary hubs, operating bases or focus cities, retaining roles and selection notes. Previously reviewed major-origin selections for large point-to-point networks remain intact. LATAM remains an explicitly documented brand group.
4. Parse each selected airport's passenger tables. Match the primary marketing-airline row or an enumerated brand exactly. A secondary “operated by Envoy” link in an American Eagle row does not assign that whole network to Envoy. Skip cargo/history tables and explicitly unavailable airports. Section-level seasonal/charter labels apply to their rows. A carrier with no resolved active service at any origin remains in the audit instead of producing an empty network.
5. Resolve linked airports using unique metadata mappings and pinned explicit identifiers plus coordinate checks. Do not select an airport merely because it shares a city or name. Preserve towns, redlinks, source-closed airports, conflicting identities and rate-limited pages as gaps. Do not silently substitute a newer airport for a closed predecessor with the same code.
6. Classify low-cost/regional flags with scoped evidence and unknown values. Pin route, hub and classification sources; validate all keys, references, coordinates, counts and example routes.

`parsed` describes complete extraction of the linked entries in a matching row, not an up-to-date or exhaustive timetable. Wikipedia can omit service, retain obsolete rows or mix future changes. This dataset does not independently verify actual operating carrier, nonstop operation, frequency, bookability or exact flight paths. Great-circle lines illustrate geography. For travel, check the airline's timetable.

## Validate and rebuild

```sh
npm test
npm run validate
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
.venv/bin/python scripts/rebuild.py --candidate work/candidates/my-refresh
```

Node tests cover filter composition, scoped brand models, reciprocal connections, airport aliases, full curved bounds and repeated-world geometry. Python tests cover source table ancestry, primary-brand matching, section labels, status/date handling, metadata safety, uncoded airports conservative business-model classification and directory identity boundaries. Refresh and schedule tests also cover isolation, source revalidation, failed requests, resource limits, identity conflicts, UTC/DST handling, quotas and offline replay. Dataset validation checks every key/reference, source pin, carrier-origin count, evidence flag, partial-coverage gap and admission-audit count, plus the Denver/Paris example routes. Browser checks exercise model filters and brand scoping on the rendered map. Projection tests compare every service field and filter result with the complete normalized dataset; geometry tests cover projection, simplification error, clipping, spatial hit testing and buffer reuse.

The rebuild requires Node.js to generate and validate the display projection. It writes an isolated candidate, **never the published `web/` files**. Each candidate contains `data.json`, `map-data.json`, a frozen baseline, reviewed input copies, `manifest.json`, `changes.json`, collection logs and validation results. Failures mark the manifest failed and leave the existing release intact. Candidate directories must be new and outside `web/`.

Reviewed inputs include the roster, hub evidence, aliases, metadata corrections/additions, business-model classifications and discovery audit. Their hashes and collector hashes are recorded in the manifest. A newer snapshot date does not re-review these inputs. Generated airports retain the persistent OurAirports row ID; synthetic reviewed additions do not claim an OurAirports ID.

Wikipedia responses expire after seven days by default. `--refresh` forces a conditional check; `--cache-max-age SECONDS` changes the expiry. Requests use a descriptive user agent, bounded retries and backoff, honor `Retry-After`, and stop on access denial. Fetch/check times are separate from the effective snapshot date. `--offline` uses captured responses and metadata, preserving their original dates; legacy cache entries have unknown retrieval dates. No filesystem timestamp is treated as a source retrieval date.

```sh
# Reuse captured inputs without making network requests:
.venv/bin/python scripts/rebuild.py --offline --candidate work/candidates/offline-check
# Validate a candidate independently:
node scripts/validate.mjs --data work/candidates/my-refresh/data.json --map work/candidates/my-refresh/map-data.json --inputs work/candidates/my-refresh/inputs
```

Review the semantic change report and all coverage/identity changes before promoting a candidate. The original snapshot checks remain on by default. `--structural` skips only fixed historical expectations for investigation/fixtures; it does not establish release acceptance. Unchanged polling dates do not count as a semantic data change. Commit accepted data and its regenerated projection before using the existing deployment process.

For recurring collection, see the bounded runner and systemd templates in [DEPLOYMENT.md](DEPLOYMENT.md#candidate-refresh-runner-collection-only). They collect candidates only; no automatic publication is enabled.

For the measured Avinor departure sample, bounded capture tool and remaining pilot gates, see [SCHEDULE_RESEARCH.md](SCHEDULE_RESEARCH.md).

For a new discovery inventory, without modifying the released roster or dataset:

```sh
.venv/bin/python scripts/discover.py --work work/discovery
# Also inspect airline articles, serially with caching and bounded retries:
.venv/bin/python scripts/discover.py --work work/discovery --articles
```

Discovery results require identity, operating-status, origin and route admission review. `scripts/discovery-audit.json` records this release's decisions; `scripts/airline-models.json` retains the reviewed model inputs. Raw research HTML is not distributed. Public Wikipedia endpoints sometimes rate-limit access; inaccessible evidence is disclosed rather than inferred.

## Performance audit

The 27 October 2026 audit found that the overview created 140,934 individual Leaflet route objects and 15,001 pin objects, including oversized offscreen world copies. Every pan rebuilt them. Search also rescanned routes and rebuilt indexes; startup loaded and serialized the complete 16 MB research dataset.

The viewer now batches routes into up to ten color/seasonality canvas strokes. It caches spherical geometry and model indexes, simplifies projected curves within 0.65 CSS pixels, clips spatial hit-test segments to the buffered viewport, retains pins during pans, and reuses the route buffer for small pans. Routes remain individually clickable through a spatial index; no routes are sampled or removed. Overscan is 20% rather than 100%. Search reuses eligibility results instead of scanning the network per keystroke. The source download and all data facts remain unchanged.

Three alternating runs in the same browser tab at **1280 × 720, pixel ratio 1**, on localhost without CPU/network throttling:

| Measurement | Before | After |
| --- | ---: | ---: |
| Median application-ready time | 2,523 ms | 450 ms |
| Median synchronous map construction | 2,275 ms | 270 ms |
| Initial map data, uncompressed | 15,994,246 bytes | 2,734,905 bytes |
| Route/pin canvas backing storage at first frame | 51.8 MB | 16.9 MB |

These are application instrumentation measurements, **not Lighthouse scores, field Core Web Vitals, INP, or total process-memory measurements**. Canvas byte estimates use width × height × four bytes and exclude JavaScript objects, the basemap and browser/GPU overhead. Raw measurements, samples, pixel ratios and limitations are in `benchmarks/performance-audit.json`. Large overview redraws can still take around 100 ms; small pans inside the buffer avoid that redraw. Serving `map-data.json` with gzip reduces its body to about 716 KB; the basic Python preview does not enable HTTP compression.

To reproduce data-operation benchmarks:

```sh
npm run benchmark
```

Open the normal viewer with `?audit=1` to record bounded timing samples in the root element's `data-performance` attribute. Profiling is off by default and makes no external requests. Browser comparisons must keep viewport, pixel ratio, filter state and network conditions equal. Use `npm run build:data` and rerun validation/tests after changing the complete dataset. The normalized source data is checked for exact equality throughout this optimization.

## Sources and attribution

- [Wikipedia passenger airline inventory](https://en.wikipedia.org/wiki/List_of_passenger_airlines), [regional airline inventory](https://en.wikipedia.org/wiki/List_of_regional_airlines), [low-cost airline inventory](https://en.wikipedia.org/wiki/List_of_low-cost_airlines), plus individual airline and airport pages pinned in the dataset. Extracted facts and short source notes are attributed to Wikipedia contributors under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Preserve attribution when reusing the data.
- [Star Alliance](https://www.staralliance.com/en/members), [SkyTeam](https://www.skyteam.com/en/about/our-members), [oneworld](https://www.oneworld.com/members); official membership announcements linked in the data.
- [OurAirports](https://ourairports.com/data/): public-domain airport metadata and coordinates. [Wikidata](https://www.wikidata.org/wiki/Wikidata:Licensing): CC0 identifier evidence where noted.
- [Natural Earth](https://www.naturalearthdata.com/about/terms-of-use/) via [geo-countries](https://github.com/datasets/geo-countries): simplified public-domain outlines; illustrative boundaries.
- [Leaflet 1.9.4](https://leafletjs.com/): BSD-2-Clause, included license in `web/vendor/leaflet-LICENSE`.

Code is MIT licensed; third-party data and assets retain their terms.


The October 28 exploration expansion was checked against the optimized `439d841` version in the same Chromium tab (three alternating loads each, 1280×720, DPR 1, local HTTP, no throttling). Median application-ready time was 445 ms before and 472 ms after; median synchronous update was 145 ms before and 171 ms after. Initial route drawing was 103 ms before and 109 ms after. This small-sample comparison includes the added controls and destination aggregation and is not a field performance claim. Compact data payload remains unchanged. Raw samples are in `benchmarks/explorer-browser.json`. Browser checks cover airport inspection versus exploration, filter modes, chip removal/reset, geographic/distance combinations, comparison visibility and URL reloads, pointer hover/source popups, keyboard result highlighting, map zoom/wrapping, 390px layout, and the portable viewer.
