#!/usr/bin/env bash
# Invoked remotely by deploy.sh; archive contains only trusted, committed files.
set -euo pipefail
revision=$1
archive=$2
[[ "$revision" =~ ^[0-9a-f]{40}$ ]] || exit 2
base=/var/www/airplanes
release="$base/releases/$revision"
incoming="$base/releases/.incoming-$revision-$$"
install -d -m 755 "$base/releases" "$incoming"
trap 'rm -rf "$incoming"; rm -f "$archive"' EXIT
tar -xzf "$archive" -C "$incoming"
(cd "$incoming" && sha256sum --quiet -c SHA256SUMS)
find "$incoming" -type d -exec chmod 755 {} +
find "$incoming" -type f -exec chmod 644 {} +
if [[ -d "$release" ]]; then
    # Repeated deployment of the same commit must not silently replace it.
    cmp "$incoming/SHA256SUMS" "$release/SHA256SUMS"
    (cd "$release" && sha256sum --quiet -c SHA256SUMS)
else
    mv "$incoming" "$release"
fi
[[ ! -e "$base/current" || -L "$base/current" ]] || { echo 'current must be a symlink' >&2; exit 1; }
previous=$(readlink "$base/current" || true)
ln -s "releases/$revision" "$base/.current-$$"
mv -Tf "$base/.current-$$" "$base/current"
if ! python3 - "$revision" <<'PY'
import json, subprocess, sys
revision=sys.argv[1]
def request(path,expected):
    output=subprocess.check_output(['curl','--fail','--silent','--show-error','--max-time','30','--resolve','colingoodman.net:443:127.0.0.1','--write-out','\n%{http_code} %{content_type}','https://colingoodman.net/airplanes/'+path])
    body,metadata=output.rsplit(b'\n',1)
    status,content_type=metadata.decode().split(' ',1)
    assert status=='200' and content_type.split(';')[0]==expected, (path,metadata)
    return body
assert request('DEPLOYED_REVISION','application/octet-stream').decode().strip()==revision
assert b'Airline network route map' in request('','text/html')
assert b'function' in request('app.mjs','application/javascript')
assert len(json.loads(request('map-data.json','application/json'))['routes'])>0
print('Origin release, HTML, module and data checks passed.')
PY
then
    if [[ -n "$previous" ]]; then
        ln -s "$previous" "$base/.rollback-$$"
        mv -Tf "$base/.rollback-$$" "$base/current"
        echo "Verification failed; restored $previous" >&2
    else
        rm "$base/current"
        echo 'Verification failed; removed the initial release pointer.' >&2
    fi
    exit 1
fi
printf 'Active release: %s\nPrevious release: %s\n' "$revision" "${previous:-none}"
