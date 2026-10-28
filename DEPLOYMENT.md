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

The viewer is entirely static and needs no application server or database. Separate scheduled Python/Node collection runs outside its release directory, as described below. Keep the existing homepage, TLS/Certbot directives and its `/assets/` rules intact. This path uses the existing certificate and DNS.

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

Collection belongs on the existing droplet. The two Mac launch agents have been
unloaded and their plist files removed; this branch no longer includes a macOS
background-job installer. Captured evidence is retained for migration.

Both droplet timers are enabled. The installed collector is commit
`1193dec430f403e9004f77fc8708bdc5fa623231`. Its first full service run on
28 October 2026 passed reviewed-snapshot validation in 35 minutes 49 seconds;
service RAM peaked at 128.5 MiB, with no out-of-memory events. It produced a
review-required candidate with 32,652 route records and 3,361 airports. A live
OSL/BNN schedule capture also succeeded, and the daily schedule service passed
its same-day gate. The public viewer remains on revision
`15181c0765d5b52a71c7d50bb95c1395c0fc5fb5`.

The collector is independent of the public viewer:

- Versioned runtime: `/opt/airplanes-refresh/releases/<full-git-commit>`.
- Runtime pointer: `/opt/airplanes-refresh/repo`.
- Installed revision: `/opt/airplanes-refresh/COLLECTOR_REVISION`.
- Unprivileged account: `airplanes-refresh`, with no login shell or deployment key.
- Refresh candidates/cache: `/var/lib/airplanes-refresh`.
- Avinor observations: `/var/lib/airplanes-schedule-research`.

The droplet has 458 MiB RAM. The installer uses 1 GiB of swap on its existing disk
(`/var/lib/airplanes-refresh.swap`, mode 0600, persisted in `/etc/fstab`) and Ubuntu's
Node.js/Python virtualenv packages. It does not resize the droplet, buy services,
change nginx, or touch `/var/www/airplanes/current` or the existing homepage.

The route service has 128 MiB memory pressure throttling, a 160 MiB hard RAM limit,
768 MiB maximum swap, half a CPU, a 90-minute collection budget and 1 GiB of state.
It retains three candidates and stops the process group on budget exhaustion.
The smaller schedule service has a 96 MiB RAM limit, 256 MiB swap limit, quarter of
a CPU, a 150-second startup timeout and 128 MiB of captured evidence. Systemd
orders it after an overlapping route refresh. Both services use read-only runtime
files, private temporary directories, no elevated capabilities and private state.

### Install or update

On the development machine, commit and check the intended branch first:

```sh
# Optional seed directories avoid downloading source pages or losing observations.
REFRESH_SEED_CACHE="$PWD/work/automatic-refresh/refresh/cache" \
REFRESH_SEED_SCHEDULES="$PWD/work/automatic-refresh/schedules" \
./deploy/install-refresh.sh
```

The installer exports HEAD only, creates a versioned collector/virtualenv,
validates the bundled baseline, seeds state only when absent, checks the systemd
units and leaves the timers stopped. It refuses to change the runtime pointer
while a collector is active. Install a new accepted commit through the same
command; a working-branch change on the Mac cannot alter the deployed collector.
No jobs are installed on the Mac by this workflow.

From the droplet, check capacity and manually run the services before enabling:

```sh
swapon --show
systemctl start airplanes-refresh.service
systemctl start airplanes-schedule-research.service
systemctl show airplanes-refresh.service airplanes-schedule-research.service -p Result -p ExecMainStatus -p MemoryPeak
cat /var/lib/airplanes-refresh/state.json
journalctl -u airplanes-refresh.service -u airplanes-schedule-research.service -n 50 --no-pager
systemctl enable --now airplanes-refresh.timer airplanes-schedule-research.timer
systemctl list-timers 'airplanes-*'
```

Each job attempts collection at most once per UTC day, including failures. A
seeded same-day schedule capture may correctly make the schedule service return
`not_due`; its copied observation remains one observation day. The route timer
checks at 03:00 UTC (08:30 India time), plus up to 30 minutes of jitter. The schedule
timer checks at 03:45 UTC (09:15 India time), plus up to ten minutes of jitter.
Persistent timers catch up after downtime. Route evidence is rechecked when its
seven-day cache expires; airport metadata is checked on every online run.

A failed job leaves the last successful collection and published release intact.
Its last attempt is written before child launch, so a resource-limit kill cannot
silently lose the attempt or cause repeated same-day restarts. Inspect private
state and the journal for failures. No external notification channel is configured.
Budget exhaustion requires checking the logs/cache before retrying; raw evidence
is not silently deleted to make room.

### Review, publish, stop or roll back

The services never copy data into `web/`, commit, deploy or change the public
release. The new source-freshness display supports both legacy and fully dated
snapshots, but the public snapshot remains unchanged until an accepted data commit
is deployed.

Review `changes.json`, source dates, identity/coverage changes, the manifest and
validation logs. Confirm the candidate's frozen baseline and reviewed input
hashes still match the intended release. Copy only accepted `data.json` and
`map-data.json` into `web/`, run checks, commit both and use the normal viewer
release process. An offline/structural-only investigation is not a fresh accepted
release. Review three weekly cycles and agree change thresholds before adding any
unattended publication; no automatic publication path exists today.

To stop collection without affecting the website:

```sh
systemctl disable --now airplanes-refresh.timer airplanes-schedule-research.timer
systemctl stop airplanes-refresh.service airplanes-schedule-research.service
```

To roll back collector code, first stop timers and wait for active collection to
finish, repoint `/opt/airplanes-refresh/repo` to a retained version, then verify the
services and restart the timers. Keep its recorded revision and unit files aligned
with that version. Never repoint the public viewer for a collector-only rollback.
Do not delete raw observations, cache or swap as part of an ordinary code rollback.
