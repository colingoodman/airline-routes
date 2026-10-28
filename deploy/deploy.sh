#!/usr/bin/env bash
# Deploy committed static files; nginx is configured separately (DEPLOYMENT.md).
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root"
host=${AIRPLANES_HOST:-root@100.76.114.95}
revision=$(git rev-parse --verify HEAD)
git diff --quiet && git diff --cached --quiet || { echo 'Commit tracked changes before deploying.' >&2; exit 1; }
npm test
npm run validate
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
# Export only this commit. No caches, credentials, .git directory or research scratch.
git archive HEAD web | tar -xf - -C "$stage"
git show HEAD:DEPLOYMENT.md > "$stage/README.md"
printf '%s\n' "$revision" > "$stage/web/DEPLOYED_REVISION"
python3 - "$stage/web" <<'PY'
from pathlib import Path
import gzip, hashlib, sys
root=Path(sys.argv[1])
for p in sorted(root.rglob('*')):
    if p.is_file() and p.suffix in {'.html','.mjs','.js','.css','.json','.geojson','.svg'} and p.stat().st_size>1024:
        p.with_name(p.name+'.gz').write_bytes(gzip.compress(p.read_bytes(),compresslevel=6,mtime=0))
lines=[hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(root)) for p in sorted(root.rglob('*')) if p.is_file()]
(root/'SHA256SUMS').write_text('\n'.join(lines)+'\n')
PY
COPYFILE_DISABLE=1 tar --no-xattrs -czf "$stage/site.tar.gz" -C "$stage/web" .
remote_archive="/tmp/airplanes-${revision}-$$.tar.gz"
scp -q -o BatchMode=yes -o ConnectTimeout=15 "$stage/site.tar.gz" "$host:$remote_archive"
ssh -o BatchMode=yes -o ConnectTimeout=15 "$host" bash -s -- "$revision" "$remote_archive" < deploy/activate.sh
# Keep operating instructions outside the public document root and release switch.
scp -q -o BatchMode=yes -o ConnectTimeout=15 "$stage/README.md" "$host:/var/www/airplanes/README.md"
printf 'Deployed %s to https://colingoodman.net/airplanes/\n' "$revision"
