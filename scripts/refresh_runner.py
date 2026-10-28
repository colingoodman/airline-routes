#!/usr/bin/env python3
"""Run bounded refresh collection. Never publish or commit data automatically."""
import argparse
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from rebuild import ROOT, write_json


def size_bytes(directory):
    # Do not follow candidate cache links or count shared files multiple times.
    total=0
    for path in directory.rglob('*'):
        try:
            if path.is_file() and not path.is_symlink():
                total+=path.stat().st_size
        except FileNotFoundError:
            # The collector atomically renames temporary files while this scan runs.
            continue
    return total


def locked(directory):
    directory.mkdir(parents=True, exist_ok=True)
    stream = (directory/'runner.lock').open('a')
    try:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        stream.close()
        return None
    return stream


def stop(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except ProcessLookupError:
        pass
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def execute(command, log_path, state_dir, seconds, max_bytes):
    started = time.monotonic()
    with log_path.open('w') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while True:
                if time.monotonic()-started > seconds:
                    raise RuntimeError('Refresh runtime budget exhausted')
                if size_bytes(state_dir) > max_bytes:
                    raise RuntimeError('Refresh disk budget exhausted')
                try:
                    code = process.wait(timeout=min(5, seconds))
                    if code:
                        raise RuntimeError('Candidate build failed; inspect '+str(log_path))
                    if size_bytes(state_dir) > max_bytes:
                        raise RuntimeError('Refresh disk budget exhausted')
                    return
                except subprocess.TimeoutExpired:
                    continue
        finally:
            if process.poll() is None:
                stop(process)


def prune_candidates(directory, retain, protected=None):
    if not directory.exists():
        return
    protected = Path(protected).resolve() if protected else None
    candidates = sorted((p for p in directory.iterdir() if p.is_dir() and not p.is_symlink()
                         and (p/'manifest.json').is_file()), key=lambda p:p.name, reverse=True)
    for old in candidates[retain:]:
        # Failed attempts must never evict the last validated collection.
        if old.resolve() != protected:
            shutil.rmtree(old)


def daily_due(previous_attempt, now, after):
    if not after:
        return True
    import re
    if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',after):
        raise ValueError('Daily UTC time must be HH:MM')
    hour,minute=map(int,after.split(':'))
    if (now.hour,now.minute)<(hour,minute):
        return False
    return not previous_attempt or dt.datetime.fromisoformat(previous_attempt).astimezone(dt.timezone.utc).date()!=now.date()


def run(args):
    state_dir = args.state.resolve()
    if state_dir == ROOT or state_dir in ROOT.parents or (ROOT/'web') == state_dir or (ROOT/'web') in state_dir.parents:
        raise ValueError('Runner state must be outside the published files and repository ancestors')
    lock = locked(state_dir)
    if lock is None:
        return {'status':'already_running'}
    try:
        now = dt.datetime.now(dt.timezone.utc)
        stamp = now.strftime('%Y%m%dT%H%M%S%fZ')
        state_file = state_dir/'state.json'
        previous = json.loads(state_file.read_text()) if state_file.exists() else {}
        if not daily_due(previous.get('last_attempted_at'),now,args.daily_after_utc):
            return {'status':'not_due'}
        state = {**previous, 'last_attempted_at':now.isoformat(), 'status':'collecting'}
        # Survive a service/cgroup kill: never lose the attempt or retry it repeatedly that day.
        write_json(state_file,state)
        candidates = state_dir/'candidates'
        prune_candidates(candidates, args.retain-1, previous.get('latest_candidate'))
        candidate = candidates/stamp
        budget = args.max_disk_mib*1024*1024
        try:
            if size_bytes(state_dir) >= budget:
                raise RuntimeError('Refresh disk budget exhausted before collection')
            command = [sys.executable, str(ROOT/'scripts/rebuild.py'), '--work', str(state_dir/'cache'),
                       '--candidate', str(candidate), '--cache-max-age', str(args.cache_max_age)]
            if args.offline:
                command.append('--offline')
            execute(command, state_dir/'latest.log', state_dir, args.max_seconds, budget)
            manifest = json.loads((candidate/'manifest.json').read_text())
            if manifest.get('status') != 'validated' or manifest.get('validation') != 'reviewed_snapshot':
                raise RuntimeError('Candidate lacks full reviewed validation')
            report = json.loads((candidate/'changes.json').read_text())
            state.update(status='review_required' if report['semantic_change'] else 'unchanged',
                         last_successful_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                         latest_candidate=str(candidate), semantic_change=report['semantic_change'],
                         hold_reasons=report['hold_reasons'])
            state.pop('error', None)
        except Exception as error:
            state.update(status='failed', error=str(error))
        # Unchanged checks update private runner state, never the data timestamp in web/.
        write_json(state_file, state)
        return state
    finally:
        lock.close()


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state', type=Path, default=ROOT/'work/refresh-runner')
    p.add_argument('--max-seconds', type=int, default=2700)
    p.add_argument('--max-disk-mib', type=int, default=2048)
    p.add_argument('--retain', type=int, default=3)
    p.add_argument('--cache-max-age', type=int, default=604800)
    p.add_argument('--daily-after-utc', help='Attempt at most once per UTC day after HH:MM, including failed runs')
    p.add_argument('--offline', action='store_true')
    return p


if __name__ == '__main__':
    args = parser().parse_args()
    if min(args.max_seconds, args.max_disk_mib, args.retain) <= 0 or args.cache_max_age < 0:
        raise SystemExit('Runtime, disk and retention budgets must be positive; cache age must be nonnegative')
    result = run(args)
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result['status'] == 'failed' else 0)
