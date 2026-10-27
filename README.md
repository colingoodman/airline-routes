# Airline network route map

A local interactive map and one normalized JSON dataset of worldwide passenger airline networks. The snapshot date is **27 October 2026**.

The expanded snapshot contains **572 carriers/brand networks, 1,304 carrier–origin relationships at 699 distinct hub/base airports, 3,358 airports, and 32,648 listed service records**. It retains all 100 carriers from the previous version and adds 472. Another **650 future or suspended/ended entries** are separate from the displayed network.

The search audited **1,310 directory entries**: 955 in Wikipedia's worldwide passenger inventory, 197 regional entries, and 158 current low-cost entries. These overlap and are not 1,310 distinct airlines. After identity and operating-status review, 728 carrier proposals reached route admission; 572 had at least one usable origin. The complete candidate and origin decisions are embedded in `web/data.json`, including 156 rejected carrier proposals and 323 rejected origin proposals. Rejection means insufficient usable evidence for this map, not necessarily a defunct airline.

**Coverage remains partial:** 159 linked destination entries across 80 admitted origins could not be resolved safely. Their resolved services are displayed, their coverage is `parsed_with_unresolved`, and every gap remains in `issues` with its source. The map header shows the partial-origin count. The dataset is a sourced reference snapshot, not an exhaustive worldwide timetable.

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

The full-width map wraps east and west, repeating land, routes and pins across the date line. Filters sit underneath. Land, routes and airports have ordered panes; land cannot cover the network. “Fit routes” includes full curved paths and chooses a Pacific-centered extent when appropriate. Pins and routes open their source evidence. The service table is paginated; its airport buttons filter routes touching that airport.

Alliances/categories, airlines, airports and operating-model filters combine. Multiple selected airlines are a union; multiple airports show any service touching any selected airport. No explicit airline selection means all eligible carriers. Seasonal and charter controls are independent; charter services are off initially. A carrier represented only by charter entries is therefore hidden until charter services are enabled. Filters are bookmarked in the URL; Reset restores the defaults.

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

Every route references its carrier, service brand, two physical airports, and pinned airport-table evidence. There is no Cartesian product of an airline's destinations and hubs. Hub-to-hub routes may appear in both directions when both tables list them; mainline and regional brands can have separate records. The map draws one connection per carrier and unordered airport pair, retaining all source records in its popup.

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
.venv/bin/python scripts/rebuild.py --as-of 2026-10-27
```

The 27 Node tests cover filter composition, scoped brand models, reciprocal connections, airport aliases, full curved bounds and repeated-world geometry. The 21 Python tests cover source table ancestry, primary-brand matching, section labels, status/date handling, metadata safety, uncoded airports conservative business-model classification and directory identity boundaries. Dataset validation checks every key/reference, source pin, carrier-origin count, evidence flag, partial-coverage gap and admission-audit count, plus the Denver/Paris example routes. Browser checks exercise model filters and brand scoping on the rendered map. Projection tests compare every service field and filter result with the complete normalized dataset; geometry tests cover projection, simplification error, clipping, spatial hit testing and buffer reuse.

The rebuild also requires Node.js to regenerate the display projection. The rebuild uses the reviewed roster, aliases, metadata corrections/addition and classifications in `scripts/`; it downloads public OurAirports metadata and fetches airport articles using cached responses and bounded retries. A newer date does not automatically re-review those inputs. Use a fresh cache for a route refresh and review changed roster/classification/identity evidence. Network failures and newly unresolved entries are recorded explicitly. A rebuilt snapshot must pass validation before release.

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
