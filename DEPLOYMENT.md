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

Commit intended changes first. The script refuses tracked dirty files and exports **HEAD only**; untracked files, `.git`, caches, research scratch and credentials are excluded. It runs the frontend tests and data validator, creates deterministic precompressed assets, checksums every deployed file, uploads a release, atomically switches `current`, and checks the origin. A failed origin check restores the previous pointer. Successful deploys refresh the server's README. Override the SSH destination with `AIRPLANES_HOST` if the server changes.

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
