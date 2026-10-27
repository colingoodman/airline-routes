# Airline alliance route map

A local, buildless map and a single normalized dataset covering the active full members of Star Alliance, SkyTeam, and oneworld. The snapshot date is **27 October 2026**.

The delivered snapshot contains **60 airlines, 132 distinct hub airports (154 airline–hub relationships), 1,627 airports, and 11,131 listed service records**. All 154 hub tables were parsed; every linked destination in the selected current passenger rows was resolved, with **zero extraction issues**. Another 181 announced or suspended/ended entries are retained separately. These counts describe the sourced snapshot, not a certification of timetable completeness.

## Run

Requires Python 3. From this repository:

```sh
npm start
```

Or, without Node/npm:

```sh
python3 -m http.server 8080 --bind 127.0.0.1 --directory web
```

Open <http://127.0.0.1:8080>. Serve over HTTP; opening `index.html` as a `file://` URL prevents JSON loading in many browsers. No API keys, build step, online map tiles, or runtime package installation are required. Leaflet, the world outline, and the dataset are included locally.

Select alliances, search and select one or more airlines, and search airports by code, name, or municipality. Airline selections are a union within the selected alliances; airport selections show any service touching any selected airport. No explicit airline selection means all airlines in the selected alliances. Seasonal and charter toggles are independent. Click a hub for its airlines and coverage; click a route for source evidence. The service table is paginated, and its airport buttons apply an airport filter. Filters are encoded in the URL for bookmarks. Reset restores the complete map.

## Portable viewer

`node scripts/package.mjs /absolute/path/alliance-map.html` embeds the same JSON, world outline, styles, and map library into one HTML file. Open it directly in a browser; no server or network is needed. The download button exports the embedded normalized dataset. File-based previews do not update the URL when filters change.

## Single-file data

**`web/data.json` is the complete normalized data deliverable.** It contains:

| Collection | Primary key | References / meaning |
| --- | --- | --- |
| `alliances` | `id` | Name and map color |
| `airlines` | Stable brand `id` (normally IATA) | `alliance_id`, membership source, enumerated service brands |
| `airports` | IATA `id` | Coordinates, ICAO, municipality, country, metadata source |
| `hubs` | (`airline_id`, `airport_id`) | Hub role, hub evidence, route source and coverage |
| `routes` | Stable `id` | Airline, origin hub, destination, brand, service type, seasonality, source |
| `excluded_routes` | Stable `id` | Announced future and suspended/ended source entries |
| `airport_aliases` | `wikipedia_title` | Reviewed airport mapping and identity evidence source |
| `sources` | `id` | URLs, retrieval date, revision IDs and content hashes |
| `issues` | — | Unresolved source entries or extraction gaps, with their evidence |

Airline IDs are stable brand identifiers, generally based on IATA codes; Hawaiian retains `HA` as a brand key despite operational integration under Alaska's `AS` code. See its `identity_note`. Airport metadata is deduplicated. Every route references one member airline and two airports; no Cartesian product of airline destinations and hubs is used. A pair of hubs can have a record in each direction when both source tables list it. A mainline service and a regional-brand service can also share the same airports. These are separate service records; the map draws one connection per airline and unordered airport pair, retaining all records in its popup.

`listed` means present in the source's ordinary passenger destination row. `seasonal` means the source labels it seasonal. Neither asserts operation every day or on the snapshot date. `change_date`, when present, is parsed from the source note; a month-only date is represented as the first day of that month. Source notes are retained. Announced starts after the snapshot, undated announced starts, and ended/suspended entries are stored separately and omitted from the map.

## Research method and boundaries

1. Verify full, active membership against alliance directories and official membership announcements. The roster includes ITA Airways in Star Alliance and Hawaiian Airlines in oneworld. Aeroflot and S7 are recorded separately as suspended. Juneyao is a connecting partner and is not included as a full member.
2. Read each member's Wikipedia infobox for hubs and separately labeled secondary passenger hubs. Focus cities are retained in the research seed for inspection but are not promoted to hubs. Exclude explicit cargo hubs and hubs operated only by separately named partner airlines. Hubs are per member airline, not an inferred union of every subsidiary's bases.
3. Read each hub airport's **passenger airline/destination table**, matching the member airline and explicitly listed service brands. Exclude cargo and historical tables. United Express, American Eagle, Delta Connection, and other enumerated branded services are grouped under their member airline and retain their source brand. General codeshares and all alliance partners are not automatically included.
4. Normalize linked destinations to IATA airports using OurAirports' Wikipedia mappings, verified Wikipedia redirects, and explicit airport IATA identifiers. Never choose an airport solely because it shares a name or city. Preserve unresolved links as issues instead of inventing routes or coordinates.
5. Pin Wikipedia route and hub evidence to page revisions. Record retrieval dates and route HTML hashes. Validate identifiers, references, hub counts, route uniqueness, coordinate bounds, announced dates, and the user's Denver/Paris example routes.

**Coverage describes extraction from public reference tables, not a certified worldwide timetable.** Wikipedia may omit service, retain obsolete rows, or mix seasonal and future changes. `parsed` means a matching source row was extracted with all its linked destinations mapped; it does not certify that the source itself is exhaustive. Every unresolved entry remains in `issues`, and every hub carries its coverage status and parsed counts. The data does not independently verify the operating carrier, actual nonstop operation, frequency, timetable validity, bookability, or precise flight path. Routes described with a `via` note preserve that note. Great-circle lines are geographic illustrations.

The map and data are a reproducible reference snapshot. For actual travel, verify the airline's timetable.

## Validation

```sh
npm test
npm run validate
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python tests/test_collect.py
```

Node tests cover combined filters, empty and multi-airport selections, seasonal/charter inclusion, reciprocal route merging, and date-line geometry. Python tests cover table parsing, date annotations, and normalization. Dataset validation checks every foreign key, unique key, coordinate, hub count, pinned route source, membership count, and the requested example routes. Browser QA checks the rendered HTTP app and its interactive controls. The portable HTML passes embedded-JSON and JavaScript syntax checks with no external script, stylesheet, dataset, or map dependency. Direct `file://` preview could not be exercised in the app browser, which only permits HTTP/HTTPS URLs.

## Rebuild

The checked-in dataset needs no network. Refreshing it requires public HTTP access and Python dependencies:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/rebuild.py --as-of 2026-10-27
npm run validate
```

The rebuild script downloads OurAirports metadata, copies the reviewed roster and airport aliases into ignored `work/`, and fetches Wikipedia hub-airport pages with a cache and bounded retries. To refresh a route snapshot, use a fresh cache directory or remove the ignored cached pages first. The member roster, hub classifications, service brands, and alias evidence are intentionally reviewed inputs; a newer date does not automatically update them. Recheck those inputs when refreshing. `scripts/airport-overrides-evidence.json` documents alias decisions. An unresolved new destination is an issue until its identity is reviewed. Some Wikipedia endpoints rate-limit automated access; the script tries article, API, and REST representations, and records failures explicitly.

## Sources and attribution

- [Star Alliance member directory](https://www.staralliance.com/en/members); [ITA joining announcement](https://www.airindia.com/content/air-india/in/en/newsroom/press-release/ita-airways-joins-star-alliance.html).
- [SkyTeam member directory](https://www.skyteam.com/en/about/our-members); [SkyTeam official anniversary infographic hosted by SAS](https://www.sasgroup.net/files/Public/290/4167223/skyteam-at-25--infographic.pdf).
- [oneworld member directory](https://www.oneworld.com/members); [Hawaiian joining announcement](https://www.oneworld.com/news/oneworld-welcomes-hawaiian-airlines).
- Wikipedia contributors: individual airline hub infoboxes and airport passenger tables, linked by revision in `data.json`. Text and source annotations are attributed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Facts have been extracted and normalized; source tables have not been reproduced as prose. Preserve attribution when reusing the dataset.
- [Wikidata](https://www.wikidata.org/wiki/Wikidata:Licensing): explicit airport IATA identifiers (P238), CC0; identity evidence appears in `airport_aliases` and `sources`.
- [OurAirports](https://ourairports.com/data/): airport identities and coordinates, public domain.
- [Natural Earth](https://www.naturalearthdata.com/about/terms-of-use/) via [geo-countries](https://github.com/datasets/geo-countries): public-domain world outlines, simplified locally for display. Boundaries are illustrative.
- [Leaflet 1.9.4](https://leafletjs.com/): BSD-2-Clause, license included in `web/vendor/leaflet-LICENSE`.

Code is MIT licensed; third-party data and assets retain their respective terms.
