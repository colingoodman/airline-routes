#!/usr/bin/env bash
# Read via SSH by install-refresh.sh. Does not touch nginx or the public release.
set -euo pipefail
revision=$1
stage=$2
[[ "$revision" =~ ^[0-9a-f]{40}$ ]] || exit 2
[[ "$stage" == /tmp/airplanes-refresh-install.* && -d "$stage" ]] || exit 2
trap 'rm -rf "$stage"' EXIT
base=/opt/airplanes-refresh
release="$base/releases/$revision"
swapfile=/var/lib/airplanes-refresh.swap
# The 458 MiB droplet needs disk-backed swap before package installation or collection.
if (( $(awk '/SwapTotal:/{print $2}' /proc/meminfo) < 1048576 )); then
    if [[ ! -e "$swapfile" ]]; then
        available=$(df --output=avail -k /var/lib | tail -1)
        (( available > 3145728 )) || { echo 'Insufficient existing disk for swap and bounded collection.' >&2; exit 1; }
        install -m 600 /dev/null "$swapfile"
        fallocate -l 1G "$swapfile"
        mkswap "$swapfile"
    fi
    [[ -f "$swapfile" && ! -L "$swapfile" ]] || exit 2
    chmod 600 "$swapfile"
    if ! awk -v path="$swapfile" '$1==path{found=1} END{exit !found}' /proc/swaps; then swapon "$swapfile"; fi
fi
if [[ -f "$swapfile" ]]; then
    python3 - "$swapfile" <<'PY'
from pathlib import Path
import shutil,sys
path=Path('/etc/fstab');swap=sys.argv[1];text=path.read_text()
if not any(line.split()[:1]==[swap] for line in text.splitlines()):
    backup=Path('/etc/fstab.airplanes-refresh.bak')
    if not backup.exists():shutil.copyfile(path,backup)
    with path.open('a') as out:
        out.write(('' if not text or text.endswith('\n') else '\n')+swap+' none swap sw 0 0\n')
PY
fi
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l
apt-get update -qq
apt-get install -y --no-install-recommends nodejs python3-venv
getent passwd airplanes-refresh >/dev/null || useradd --system --home-dir /var/lib/airplanes-refresh --shell /usr/sbin/nologin airplanes-refresh
install -d -m 755 "$base/releases"
if [[ ! -d "$release" ]]; then
    incoming="$base/releases/.incoming-$revision"
    [[ ! -e "$incoming" ]] || { echo 'Inspect the interrupted incoming release before retrying.' >&2; exit 1; }
    install -d -m 755 "$incoming"
    tar -xzf "$stage/collector.tar.gz" -C "$incoming"
    mv "$incoming" "$release"
fi
if [[ ! -f "$release/.runtime-ready" ]]; then
    python3 -m venv "$release/.venv"
    "$release/.venv/bin/python" -m pip install --disable-pip-version-check -r "$release/requirements.txt"
    node "$release/scripts/validate.mjs" > "$release/runtime-validation.log"
    touch "$release/.runtime-ready"
fi
chown -R root:root "$release"
chmod -R go-w "$release"
install -d -o airplanes-refresh -g airplanes-refresh -m 700 /var/lib/airplanes-refresh /var/lib/airplanes-schedule-research
if [[ -f "$stage/cache.tar.gz" && ! -e /var/lib/airplanes-refresh/cache ]]; then
    install -d -o airplanes-refresh -g airplanes-refresh -m 700 /var/lib/airplanes-refresh/cache
    tar -xzf "$stage/cache.tar.gz" -C /var/lib/airplanes-refresh/cache
    chown -R airplanes-refresh:airplanes-refresh /var/lib/airplanes-refresh/cache
fi
if [[ -f "$stage/schedules.tar.gz" && ! -e /var/lib/airplanes-schedule-research/request-ledger.json ]]; then
    tar -xzf "$stage/schedules.tar.gz" -C /var/lib/airplanes-schedule-research
    chown -R airplanes-refresh:airplanes-refresh /var/lib/airplanes-schedule-research
fi
# A dedicated read-only runtime pointer is independent of /var/www/airplanes/current.
systemctl stop airplanes-refresh.timer airplanes-schedule-research.timer 2>/dev/null || true
if [[ $(systemctl show airplanes-refresh.service --property=ActiveState --value 2>/dev/null) =~ ^(active|activating|deactivating)$ ]] || [[ $(systemctl show airplanes-schedule-research.service --property=ActiveState --value 2>/dev/null) =~ ^(active|activating|deactivating)$ ]]; then
    echo 'An existing collector is running; wait for it before changing the runtime pointer.' >&2
    exit 1
fi
ln -s "releases/$revision" "$base/.repo-$revision"
mv -Tf "$base/.repo-$revision" "$base/repo"
install -m 644 "$release"/deploy/refresh/*.service "$release"/deploy/refresh/*.timer /etc/systemd/system/
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/airplanes-refresh.service /etc/systemd/system/airplanes-refresh.timer /etc/systemd/system/airplanes-schedule-research.service /etc/systemd/system/airplanes-schedule-research.timer
printf '%s\n' "$revision" > "$base/COLLECTOR_REVISION"
echo 'Collector installed; timers remain disabled until the manual runs pass.'
