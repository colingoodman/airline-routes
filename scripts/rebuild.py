#!/usr/bin/env python3
"""Build and validate a refresh candidate without modifying the published files."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ('roster-hubs.json', 'airport-overrides.json', 'airport-overrides-evidence.json',
          'airport-metadata-overrides.json', 'airport-additions.json', 'airline-models.json', 'discovery-audit.json')
AIRPORTS_URL = 'https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/airports.csv'
USER_AGENT = 'AllianceRouteMap/1.1 (https://github.com/colingoodman/airline-routes)'


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_url_map(data):
    return {s['id']: s['url'] for s in data['sources']}


def semantic_data(data):
    """Ignore polling dates, source numbering and ordering, but retain evidence identity."""
    value = json.loads(json.dumps(data))
    value.pop('as_of', None)
    sources = source_url_map(data)
    for source in value['sources']:
        for key in ('id', 'fetch', 'retrieved_on'):
            source.pop(key, None)
    def visit(item):
        if isinstance(item, dict):
            for key, child in item.items():
                if key.endswith('source_id') and isinstance(child, str):
                    item[key] = sources.get(child, child)
                elif key.endswith('source_ids') and isinstance(child, list):
                    item[key] = sorted(sources.get(s, s) for s in child)
                else:
                    visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
            item.sort(key=lambda row: json.dumps(row, sort_keys=True))
    visit(value)
    return value


def changes(before, after, key):
    a = {key(row): row for row in before}
    b = {key(row): row for row in after}
    return {'added': sorted(b.keys()-a.keys()), 'removed': sorted(a.keys()-b.keys()),
            'changed': sorted(k for k in a.keys() & b.keys() if a[k] != b[k])}


def change_report(before, after):
    old, new = semantic_data(before), semantic_data(after)
    report = {'semantic_change': old != new, 'collections': {}, 'hold_reasons': []}
    for name in ('airports', 'airlines', 'alliances', 'service_brand_models', 'routes', 'excluded_routes'):
        report['collections'][name] = changes(old[name], new[name], lambda row: row['id'])
    report['collections']['hubs'] = changes(old['hubs'], new['hubs'], lambda row: row['airline_id']+'|'+row['airport_id'])
    report['coverage'] = {'before': len(before['issues']), 'after': len(after['issues'])}
    old_issues = {json.dumps(i, sort_keys=True) for i in old['issues']}
    new_issues = {json.dumps(i, sort_keys=True) for i in new['issues']}
    if new_issues-old_issues:
        report['hold_reasons'].append('New or changed coverage gaps')
    for name in ('airports', 'airlines', 'alliances', 'service_brand_models', 'hubs', 'routes', 'excluded_routes'):
        diff = report['collections'][name]
        if any(diff.values()):
            report['hold_reasons'].append(name+' changed: review required')
    if old.get('discovery_audit') != new.get('discovery_audit'):
        report['hold_reasons'].append('Reviewed discovery audit changed')
    bad = [h for h in after['hubs'] if h['coverage'] not in ('parsed', 'parsed_with_unresolved')]
    if bad:
        report['hold_reasons'].append('Unavailable or unmatched origins')
    report['source_freshness'] = [{'url': s['url'], 'retrieved_on': s.get('retrieved_on'),
                                 'fetch': s.get('fetch')} for s in after['sources'] if s['kind'] in ('airport_metadata', 'airport_passenger_routes')]
    report['publication'] = 'review_required' if report['semantic_change'] else 'unchanged'
    return report


def build(args):
    work, candidate = args.work.resolve(), args.candidate.resolve()
    public = (ROOT/'web').resolve()
    if candidate == ROOT or candidate == public or public in candidate.parents:
        raise ValueError('Candidate output must be outside the published web directory')
    if candidate.exists():
        raise ValueError('Candidate directory already exists; use a new run directory')
    if work == candidate or candidate in work.parents:
        raise ValueError('Cache work directory must not be inside the candidate')
    if work == public or public in work.parents:
        raise ValueError('Cache work directory must be outside web')
    candidate.mkdir(parents=True)
    run = candidate/'inputs'
    run.mkdir()
    work.mkdir(parents=True, exist_ok=True)
    # Reviewed inputs are copied once, so collection cannot mix concurrent edits.
    for name in INPUTS:
        shutil.copyfile(args.inputs/name, run/name)
    manifest = {'started_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'as_of': args.as_of,
                'inputs': {name: digest(run/name) for name in INPUTS},
                'code': {name: digest(ROOT/'scripts'/name) for name in
                         ('collect.py', 'rebuild.py', 'build-runtime.mjs', 'validate.mjs')},
                'baseline_sha256': digest(args.baseline), 'offline': args.offline, 'validation': 'structural' if args.structural else 'reviewed_snapshot'}
    write_json(candidate/'manifest.json', manifest)
    shutil.copyfile(args.baseline,candidate/'baseline.json')
    try:
        metadata_path = work/'ourairports-fetch.json'
        airports_path = work/'ourairports.csv'
        if args.offline:
            if not airports_path.exists():
                raise ValueError('No cached OurAirports CSV available')
            metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {'fetched_at': None}
            metadata = {**metadata, 'mode': 'cache' if metadata.get('fetched_at') else 'legacy_cache'}
        else:
            with urlopen(Request(AIRPORTS_URL, headers={'User-Agent': USER_AGENT}), timeout=60) as response:
                body = response.read(32*1024*1024+1)
            if len(body)>32*1024*1024:
                raise ValueError('OurAirports download exceeds 32 MiB limit')
            import csv, io
            reader = csv.DictReader(io.StringIO(body.decode('utf-8-sig')))
            required = {'id', 'ident', 'type', 'iata_code', 'icao_code', 'latitude_deg', 'longitude_deg', 'iso_country', 'municipality', 'wikipedia_link'}
            if not required.issubset(reader.fieldnames or []) or not any(reader):
                raise ValueError('Invalid or empty OurAirports CSV')
            # The pair is verified on read: a crash between writes cannot relabel old bytes.
            temporary = work/'ourairports.csv.tmp'
            temporary.write_bytes(body)
            temporary.replace(airports_path)
            stamp = dt.datetime.now(dt.timezone.utc).isoformat()
            metadata = {'fetched_at': stamp, 'checked_at': stamp, 'mode': 'fetched',
                        'url': AIRPORTS_URL, 'sha256': digest(airports_path)}
            write_json(metadata_path, metadata)
        if metadata.get('sha256') and metadata['sha256'] != digest(airports_path):
            raise ValueError('OurAirports cache checksum mismatch')
        shutil.copyfile(airports_path, run/'ourairports.csv')
        write_json(run/'ourairports-fetch.json', metadata)
        # A shared cache permits resumable runs; raw responses never enter web/.
        (run/'airports-cache').symlink_to(work/'airports-cache', target_is_directory=True)
        (work/'airports-cache').mkdir(exist_ok=True)
        command = [sys.executable, str(ROOT/'scripts/collect.py'), '--work', str(run), '--inputs', str(run),
                   '--out', str(candidate/'data.json'), '--as-of', args.as_of,
                   '--cache-max-age', str(args.cache_max_age)]
        if args.refresh:
            command.append('--refresh')
        if args.offline:
            command.append('--offline')
        with (candidate/'collection.log').open('w') as log:
            subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT)
        subprocess.run(['node', str(ROOT/'scripts/build-runtime.mjs'), '--data', str(candidate/'data.json'),
                        '--out', str(candidate/'map-data.json')], check=True)
        data = json.loads((candidate/'data.json').read_text())
        report = change_report(json.loads((candidate/'baseline.json').read_text()), data)
        write_json(candidate/'changes.json', report)
        with (candidate/'validation.log').open('w') as log:
            validation=['node', str(ROOT/'scripts/validate.mjs'), '--data', str(candidate/'data.json'),
                        '--map', str(candidate/'map-data.json'), '--inputs', str(run)]
            if args.structural:validation.append('--structural')
            subprocess.run(validation, check=True, stdout=log, stderr=subprocess.STDOUT)
        manifest.update(status='validated', finished_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                        data_sha256=digest(candidate/'data.json'), map_sha256=digest(candidate/'map-data.json'),
                        semantic_change=report['semantic_change'], publication=report['publication'])
        write_json(candidate/'manifest.json', manifest)
        return manifest
    except BaseException as error:
        manifest.update(status='failed', error=str(error), finished_at=dt.datetime.now(dt.timezone.utc).isoformat())
        write_json(candidate/'manifest.json', manifest)
        raise


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, default=ROOT/'work/refresh-cache')
    p.add_argument('--candidate', type=Path, default=ROOT/'work/candidates'/dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    p.add_argument('--inputs', type=Path, default=ROOT/'scripts')
    p.add_argument('--baseline', type=Path, default=ROOT/'web/data.json')
    p.add_argument('--as-of', default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    p.add_argument('--structural', action='store_true', help='Skip reviewed snapshot assertions; candidate remains for manual review')
    p.add_argument('--offline', action='store_true')
    p.add_argument('--refresh', action='store_true')
    p.add_argument('--cache-max-age', type=int, default=604800)
    return p


if __name__ == '__main__':
    arguments = parser().parse_args()
    dt.date.fromisoformat(arguments.as_of)
    if arguments.cache_max_age < 0:
        raise SystemExit('Cache max age must be nonnegative')
    print(json.dumps(build(arguments), indent=2))
