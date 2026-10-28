#!/usr/bin/env bash
# Install a committed, candidate-only collector on the existing droplet.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root"
host=${AIRPLANES_HOST:-root@100.76.114.95}
revision=$(git rev-parse --verify HEAD)
git diff --quiet HEAD || { echo 'Commit tracked changes before installing collection.' >&2; exit 1; }
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
git archive "$revision" scripts requirements.txt web/data.json web/map-data.json deploy/refresh | gzip > "$stage/collector.tar.gz"
git show "$revision":deploy/refresh/setup.sh > "$stage/setup.sh"
remote_stage=$(ssh -o BatchMode=yes -o ConnectTimeout=15 "$host" 'mktemp -d /tmp/airplanes-refresh-install.XXXXXX')
[[ "$remote_stage" == /tmp/airplanes-refresh-install.* ]] || exit 2
scp -q -o BatchMode=yes -o ConnectTimeout=15 "$stage/collector.tar.gz" "$host:$remote_stage/collector.tar.gz"
if [[ -n ${REFRESH_SEED_CACHE:-} ]]; then
    COPYFILE_DISABLE=1 tar --no-xattrs -czf "$stage/cache.tar.gz" -C "$REFRESH_SEED_CACHE" .
    scp -q -o BatchMode=yes -o ConnectTimeout=15 "$stage/cache.tar.gz" "$host:$remote_stage/cache.tar.gz"
fi
if [[ -n ${REFRESH_SEED_SCHEDULES:-} ]]; then
    COPYFILE_DISABLE=1 tar --no-xattrs -czf "$stage/schedules.tar.gz" -C "$REFRESH_SEED_SCHEDULES" .
    scp -q -o BatchMode=yes -o ConnectTimeout=15 "$stage/schedules.tar.gz" "$host:$remote_stage/schedules.tar.gz"
fi
ssh -o BatchMode=yes -o ConnectTimeout=15 "$host" bash -s -- "$revision" "$remote_stage" < "$stage/setup.sh"
