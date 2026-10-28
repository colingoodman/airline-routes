# Deploy the airplane viewer

## Where things live

- Public viewer: https://colingoodman.net/airplanes/
- Source: https://github.com/colingoodman/airline-routes (branch `main`).
- SSH: `ssh root@100.76.114.95` over the existing Tailscale connection.
- Server: Ubuntu 24.04, nginx 1.24; Cloudflare fronts the public domain.
- Viewer releases: `/var/www/airplanes/releases/<full-git-commit>`.
- Active viewer: `/var/www/airplanes/current`, a symlink to a release.
- Server copy of this guide: `/var/www/airplanes/README.md` (outside the public root).
- Existing homepage: `/var/www/website/dist`. Do not deploy the viewer into it.
- Active nginx site: `/etc/nginx/sites-available/website`, linked from `sites-enabled/website`.
- Viewer nginx snippet: `/etc/nginx/snippets/airplanes.conf` (source: `deploy/airplanes.nginx.conf`).
- nginx backups: `/etc/nginx/backups/website.*`, outside nginx's include directories.

The viewer is entirely static. There is no server-side Node/Python process, database, API key, dependency installation or build on the droplet. Keep the existing homepage, TLS/Certbot directives and its `/assets/` rules intact. This path uses the existing certificate and DNS.

## Subsequent deploys

On a machine with Node.js, Python 3, Git, OpenSSH, `tar`, and SSH access to the droplet:

```sh
git clone https://github.com/colingoodman/airline-routes.git
cd airline-routes
# Or, in an existing clean checkout:
git pull --ff-only origin main
./deploy/deploy.sh
```

Commit intended changes first. The script refuses tracked dirty files and exports **HEAD only**; untracked files, `.git`, caches, research scratch and credentials are excluded. It runs the frontend tests and data validator, creates deterministic precompressed assets without macOS metadata sidecars, checksums every deployed file, uploads a release, atomically switches `current`, and checks the origin. A failed origin check restores the previous pointer. Successful deploys refresh the server's README. Override the SSH destination with `AIRPLANES_HOST` if the server changes.

Data changes must first run `npm run build:data`; validation rejects a stale `web/map-data.json`. Ordinary deploys do not refresh or scrape Wikipedia. The complete `data.json` remains downloadable, while startup loads the compact projection.

The active commit is available at `/airplanes/DEPLOYED_REVISION`; its file checksums are in `/airplanes/SHA256SUMS`. Repeating the same revision checks its content instead of overwriting it. Releases are retained for rollback; prune only known inactive releases after successful verification. No nginx reload is needed for an ordinary static release.

## nginx setup or configuration changes

The existing HTTPS server includes this line after its `index` directive:

```nginx
include /etc/nginx/snippets/airplanes.conf;
```

`deploy/airplanes.nginx.conf` owns only `/airplanes` and `/airplanes/`:

- Canonical trailing-slash redirect preserves filter query parameters.
- Static alias points at `/var/www/airplanes/current/`.
- Missing assets return 404 rather than the homepage's SPA fallback.
- Standard MIME types are extended for `.mjs` and `.geojson`.
- Precompressed gzip files are served when supported; dynamic gzip is also enabled.
- `Cache-Control: no-cache` allows browser validation after deploys, including modules whose URLs did not change. Do not mark these filenames immutable.

The installed nginx has `http_gzip_static_module`. If replacing nginx, retain that module or remove `gzip_static` before validation.

When changing nginx, first back up the existing site and snippet under `/etc/nginx/backups/`. Copy the reviewed snippet into `/etc/nginx/snippets/airplanes.conf`, ensure the include appears **once inside the HTTPS server**, then:

```sh
sudo nginx -t
sudo systemctl reload nginx
```

Never reload after a failed syntax check. Restore the backup on failure. Changing the repository snippet alone does not modify nginx during a routine deploy; install it explicitly when needed.

## Verification

From the droplet, inspect the origin directly (HTTPS certificate verification stays enabled):

```sh
curl -I --resolve colingoodman.net:443:127.0.0.1 'https://colingoodman.net/airplanes?airlines=UA'
curl -I --resolve colingoodman.net:443:127.0.0.1 https://colingoodman.net/airplanes/app.mjs
curl -I --resolve colingoodman.net:443:127.0.0.1 -H 'Accept-Encoding: gzip' https://colingoodman.net/airplanes/map-data.json
curl -I --resolve colingoodman.net:443:127.0.0.1 https://colingoodman.net/airplanes/missing-file.mjs
```

Expect a 308 redirect preserving `?airlines=UA`, JavaScript MIME for `.mjs`, gzip plus `Vary: Accept-Encoding` for JSON, and a real 404 for the missing asset. Check the public Cloudflare URL too, including the revision marker and the homepage. Public responses may use Brotli instead of gzip.

Browser smoke test: load the viewer, select an airport/airline, inspect a route source popup, and try comparison via:
https://colingoodman.net/airplanes/?focus=NRT&compare_a=UA&compare_b=NH

The project documentation link goes to GitHub and works under this subpath. All runtime imports, data fetches, styles and map assets are relative to `/airplanes/`.

## Rollback

List releases and the current pointer:

```sh
ssh root@100.76.114.95 'readlink /var/www/airplanes/current; ls /var/www/airplanes/releases'
```

Choose an existing full commit directory, then atomically repoint `current` (replace `PREVIOUS_COMMIT`):

```sh
ssh root@100.76.114.95 'cd /var/www/airplanes && test -d releases/PREVIOUS_COMMIT && ln -s releases/PREVIOUS_COMMIT .rollback && mv -Tf .rollback current'
```

Verify the origin/public revision marker and browser afterward. No nginx reload is required. For the first deployment there is no previous release; remove the viewer include and validate/reload nginx if the entire feature must be withdrawn. The homepage remains separate.

## Diagnostics

```sh
ssh root@100.76.114.95 'nginx -t; systemctl status nginx --no-pager; tail -50 /var/log/nginx/error.log'
```

If a module returns HTML, the viewer's nginx location/include is missing. If a module returns `application/octet-stream`, inspect the `.mjs` MIME extension. If a source deploy seems stale, compare `DEPLOYED_REVISION`, the current symlink, HTTP cache headers, and Cloudflare behavior before changing the data. Remote requests may work even when the local agent environment cannot resolve the public hostname; distinguish local DNS restrictions from a production outage.

## Candidate refresh runner (collection only)

`scripts/refresh_runner.py` runs collection with an exclusive lock, a runtime limit,
a disk budget and bounded candidate retention. It never copies data to `web/`,
commits, deploys, or changes the active release. Successful unchanged checks update
only its private `state.json`; collection failures preserve the last-successful
check and publication timestamps. `latest.log` and the candidate manifest identify
failures. Exit status 1 is an actionable collection failure; overlapping runs exit
successfully without starting another job.

```sh
.venv/bin/python scripts/refresh_runner.py --state work/refresh-runner
```

Default limits are 45 minutes, 2 GiB of runner state, three candidates and a
seven-day Wikipedia cache. Airport metadata is fetched on every online run. Budget
exhaustion stops the entire collector process group and requires checking the
logs/cache before retrying; it cannot publish partial results. Raw caches are
retained for resumption, so a cache at its disk limit needs operator maintenance.

`deploy/refresh/airplanes-refresh.service` and `.timer` are templates, not installed
jobs. The timer checks daily at 03:00 UTC (08:30 India time), with up to 30 minutes
of randomized delay, and catches up after downtime. Route pages are rechecked as
their weekly cache expires. Prepare a separate checkout of the accepted collector
commit at `/opt/airplanes-refresh/repo`, its Python environment and Node runtime,
a dedicated `airplanes-refresh` user, and writable state at
`/var/lib/airplanes-refresh`. The collector needs no access to the public web root,
SSH deploy keys or nginx configuration. Keep source code read-only to that user.

Before installing/enabling the templates on the existing server, measure a full
candidate run there, confirm available disk/memory/network capacity, run
`systemd-analyze verify` on the units, and perform a manual service run. Enabling
collection is separate from enabling automatic publication. Review the first
three weekly cycles and define accepted change thresholds before implementing
unattended publication; no such publication path exists today.

For a candidate release, review `changes.json`, `manifest.json`, source dates and
validation logs. Check the candidate baseline still matches the current canonical
JSON and that all manifest input hashes match the intended reviewed files. Copy
only accepted candidate `data.json` and `map-data.json` into `web/`, rerun tests and
validation, commit both files, then deploy that commit through the normal script.
An offline or structural-only investigation is not evidence of a fresh accepted
release. No-change checks should not create commits. Record actual successful
publication time separately from collection time when a release is deployed.

### Existing-host choice and macOS agents

The existing droplet was inspected on 28 October 2026: 458 MiB RAM, about 241 MiB
available, no swap, and no Node.js installation. The old collector retained every
parsed HTML tree and exceeded 3 GiB in a representative run. Its parser cache now
retains at most two trees and explicitly frees evicted trees; a subsequent
measurement was about 245 MiB for the collector alone. The parent/comparison and
Node validation need additional memory. Do not install the Linux collector timer
on this droplet at its current size or buy additional capacity for this project.

Use the existing development Mac for collection instead. The opt-in installer
`scripts/install_refresh_agents.py` freezes scripts and baseline data from a clean
Git HEAD into ignored local state, then creates two launch agents. It uses the
existing Python virtual environment and Node runtime; no new account or paid
service is involved. Hourly scheduler wakeups check explicit UTC due times, but
each job attempts collection at most once per UTC day, including failed attempts.
Route pages retain their weekly cache. Neither agent can commit or deploy data.

```sh
# Generate locally staged plists and a pinned runtime without loading agents:
.venv/bin/python scripts/install_refresh_agents.py --seed-candidate work/candidates/ACCEPTED_ONLINE_CANDIDATE
# Enable the agents after checking the candidate and local resource use:
.venv/bin/python scripts/install_refresh_agents.py --seed-candidate work/candidates/ACCEPTED_ONLINE_CANDIDATE --seed-cache work/refresh-cache --seed-schedules work/schedule-research --enable
```

The seed must have passed full online validation against the pinned baseline and
collector hashes. Its collection result seeds runner state without claiming a
publication occurred. Existing captured schedule days can be copied into the
private observation state; copying/replaying a capture does not create another
observation day. Without `--enable`, plist files remain under local state and are
not written to LaunchAgents. A loaded job can catch up when the Mac is awake after
its due time. It does not promise collection while the Mac is off.

Default state is `work/automatic-refresh/`: `installation.json` records the pinned
revision and agent labels; refresh results are in `refresh/state.json`, captures
in `schedules/captures/`, and job output in the adjacent logs. A code update requires
rerunning the installer from an accepted clean commit; changing branches in the
working checkout does not change a running pinned collector. Keep the referenced
`.venv` and Node executable available. Retire old runtime directories only after
confirming no installed agent references them and no old job is running.

Inspect or stop the jobs as the same macOS user:

```sh
launchctl print gui/$(id -u)/net.colingoodman.airplanes.refresh
launchctl print gui/$(id -u)/net.colingoodman.airplanes.schedules
launchctl bootout gui/$(id -u) "$HOME/Library/LaunchAgents/net.colingoodman.airplanes.refresh.plist"
launchctl bootout gui/$(id -u) "$HOME/Library/LaunchAgents/net.colingoodman.airplanes.schedules.plist"
```

Bootout stops the current registration; remove the two matching plist files as
well if the jobs must remain disabled after the next login. Check meaningful
failures in the private state/logs. No external notification channel has been
configured. The public viewer and active server release stay independent of these
local collection jobs.
