#!/usr/bin/env python3
"""Capture a bounded Avinor research sample; never alter the route graph or viewer."""
import argparse
from collections import Counter
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

from rebuild import ROOT, write_json
from refresh_runner import locked, size_bytes

PROVIDER_URL = 'https://asrv.avinor.no/XmlFeed/v1.0'
TERMS_URL = 'https://partner.avinor.no/tjenester/flydata/'
TIMEZONES = {'OSL':'Europe/Oslo', 'BNN':'Europe/Oslo'}
MAX_RESPONSE = 8*1024*1024


def timestamp(value):
    result = dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.utcoffset() is None:
        raise ValueError('Source timestamp lacks a UTC offset')
    return result.astimezone(dt.timezone.utc)


def parse_feed(body, airport, fetched_at, known_airports):
    if b'<!DOCTYPE' in body.upper() or b'<!ENTITY' in body.upper():
        raise ValueError('XML declarations/entities are not accepted')
    root = ET.fromstring(body)
    if root.tag != 'airport' or root.get('name') != airport or root.find('flights') is None:
        raise ValueError('Unexpected airport feed identity or structure')
    records, issues, seen = [], [], set()
    for flight in root.findall('./flights/flight'):
        get = lambda key: (flight.findtext(key) or '').strip()
        unique = flight.get('uniqueID') or flight.get('uniqueId')
        identity = f'avinor:{airport}:D:{unique}'
        number, destination = get('flight_id') or get('flightId'), get('airport')
        try:
            if not unique or not number or get('arr_dep') != 'D':
                raise ValueError('Missing flight identity or unexpected direction')
            if not re.fullmatch(r'[A-Z0-9]{3}', destination) :
                raise ValueError('Invalid opposite airport')
            departure = timestamp(get('schedule_time'))
            if identity in seen:
                raise ValueError('Duplicate source flight identity')
            seen.add(identity)
            via = [s.strip() for s in get('via_airport').split(',') if s.strip()]
            for code in via:
                if not re.fullmatch(r'[A-Z0-9]{3}', code):
                    raise ValueError('Invalid intermediate airport')
            shares = {field:get(field) for field in ('codeshareAirlineDesignators','codeshareFlightNumbers','codeshareOperationalSuffixs')}
            carriers = shares['codeshareAirlineDesignators'].split(',') if shares['codeshareAirlineDesignators'] else []
            numbers = shares['codeshareFlightNumbers'].split(',') if shares['codeshareFlightNumbers'] else []
            suffixes = shares['codeshareOperationalSuffixs'].split(',') if shares['codeshareOperationalSuffixs'] else ['']*len(carriers)
            codeshares = []
            if len(carriers) == len(numbers) == len(suffixes):
                codeshares = [{'airline_iata':a.strip(), 'flight_number':n.strip(), 'suffix':s.strip()}
                              for a,n,s in zip(carriers,numbers,suffixes)]
            elif any(shares.values()):
                issues.append({'source_record_id':identity,'kind':'unresolved_codeshare_fields','fields':shares})
            status = flight.find('status')
            status_data = {'code': status.get('code'), 'time': status.get('time')} if status is not None else None
            if status_data and status_data.get('time'):
                timestamp(status_data['time'])
            circular=destination==airport
            if circular:
                issues.append({'source_record_id':identity,'kind':'circular_service_requires_leg_resolution'})
            record = {'source_record_id':identity, 'source':'avinor', 'source_airport':airport,
                      'origin_airport_id':airport, 'destination_airport_id':destination if destination in known_airports and not circular else None,
                      'destination_iata':destination, 'published_flight_number':number,
                      'operating_airline_iata':get('airline') or None, 'marketing_carrier':None,
                      'scheduled_departure_utc':departure.isoformat(), 'scheduled_arrival_utc':None,
                      'departure_timezone':TIMEZONES[airport],
                      'departure_local_date':departure.astimezone(ZoneInfo(TIMEZONES[airport])).date().isoformat(),
                      'via_airports':via, 'circular_service':circular, 'nonstop':None, 'codeshares':codeshares,
                      'status_as_reported':status_data, 'gate_as_reported':get('gate') or None,
                      'fetched_at':fetched_at.isoformat()}
            records.append(record)
            if destination not in known_airports:
                issues.append({'source_record_id':identity,'kind':'airport_missing_from_map','iata':destination})
        except (ValueError, TypeError) as error:
            issues.append({'source_record_id':identity,'kind':'invalid_record','reason':str(error)})
    records.sort(key=lambda r:(r['scheduled_departure_utc'],r['source_record_id']))
    return {'source':'avinor','airport':airport,'fetched_at':fetched_at.isoformat(),
            'attribution':{'text':'Flydata fra Avinor','url':'https://www.avinor.no/','terms_url':TERMS_URL},
            'records':records,'issues':issues}


def summarize(samples):
    records = [record for sample in samples for record in sample['records']]
    by_date = Counter(r['departure_local_date'] for r in records)
    return {'records':len(records), 'per_departure_local_date':dict(sorted(by_date.items())),
            'missing_destinations':sum(r['destination_airport_id'] is None and not r['circular_service'] for r in records),
            'circular_services':sum(r['circular_service'] for r in records),
            'codeshared_flights':sum(bool(r['codeshares']) for r in records),
            'via_flights':sum(bool(r['via_airports']) for r in records),
            'issues':dict(Counter(i['kind'] for sample in samples for i in sample['issues'])),
            'scheduled_arrival_available':False,
            'note':'Seven days of future departures in one response is not seven days of repeat observations.'}


def capture(args):
    work = args.work.resolve()
    if work == ROOT or work in ROOT.parents or work == ROOT/'web' or ROOT/'web' in work.parents:
        raise ValueError('Research output must be outside the published files')
    if set(args.airports)-TIMEZONES.keys():
        raise ValueError('This pilot is restricted to OSL and BNN')
    airports = list(dict.fromkeys(args.airports))
    if not 1 <= args.hours <= 336 or args.max_requests < len(airports) or args.max_disk_mib <= 0:
        raise ValueError('Invalid research budget or time window')
    lock = locked(work)
    if lock is None:
        raise RuntimeError('Schedule capture already running')
    try:
        now = dt.datetime.now(dt.timezone.utc)
        stamp = now.strftime('%Y%m%dT%H%M%S%fZ')
        ledger_file = work/'request-ledger.json'
        ledger = json.loads(ledger_file.read_text()) if ledger_file.exists() else {}
        known = {a['id'] for a in json.loads(args.data.read_text())['airports']}
        if set(airports)-known:
            raise ValueError('Pilot origin is absent from the route map')
        day = now.date().isoformat()
        if ledger.get('day') != day:
            ledger = {**ledger, 'day':day, 'requests':0}
        if ledger['requests']+len(airports) > args.max_requests:
            raise RuntimeError('Daily research request budget exhausted')
        for airport in airports:
            prior = ledger.get('last_attempts',{}).get(airport)
            if prior and (now-timestamp(prior)).total_seconds()<180:
                raise RuntimeError('Wait at least three minutes between requests for '+airport)
        if size_bytes(work)+MAX_RESPONSE*len(airports) > args.max_disk_mib*1024*1024:
            raise RuntimeError('Research disk budget exhausted')
        output = work/'captures'/stamp
        output.mkdir(parents=True)
        samples = []
        metadata = {'captured_at':now.isoformat(),'status':'collecting','requested_airports':airports,
                    'requested_hours_ahead':args.hours,'terms_url':TERMS_URL,'schema_version':1,
                    'map_sha256':hashlib.sha256(args.data.read_bytes()).hexdigest(),
                    'normalizer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        write_json(output/'manifest.json',metadata)
        try:
            for airport in airports:
                # Count attempts before IO, including failures and interrupted requests.
                ledger['requests']+=1
                ledger.setdefault('last_attempts',{})[airport]=dt.datetime.now(dt.timezone.utc).isoformat()
                write_json(ledger_file,ledger)
                url = PROVIDER_URL+'?'+urlencode({'airport':airport,'TimeFrom':1,'TimeTo':args.hours,'direction':'D','codeshare':'Y'})
                request = Request(url,headers={'User-Agent':'AllianceRouteMap/1.1 (https://github.com/colingoodman/airline-routes)','Accept':'application/xml'})
                with urlopen(request,timeout=45) as response:
                    body = response.read(MAX_RESPONSE+1)
                if len(body)>MAX_RESPONSE:
                    raise ValueError('Schedule response exceeds 8 MiB limit')
                fetched = dt.datetime.now(dt.timezone.utc)
                sample = parse_feed(body,airport,fetched,known)
                sample['request_url']=url
                sample['raw_sha256']=hashlib.sha256(body).hexdigest()
                (output/(airport+'.xml')).write_bytes(body)
                write_json(output/(airport+'.json'),sample)
                samples.append(sample)
            report = summarize(samples)
            # Only complete captures count toward the multi-day observation gate.
            days = set()
            for prior in (work/'captures').glob('*/manifest.json'):
                recorded = json.loads(prior.read_text())
                if (recorded.get('status')=='captured' and sorted(recorded.get('requested_airports',[]))==sorted(airports)
                    and recorded.get('requested_hours_ahead')==args.hours and recorded.get('schema_version')==1):
                    days.add(recorded['captured_at'][:10])
            days.add(day)
            report.update(observation_days=len(days),observation_gate='pending' if len(days)<7 else 'ready_for_review')
            write_json(output/'report.json',report)
            metadata.update(status='captured',summary=report)
            write_json(output/'manifest.json',metadata)
            return {'capture':str(output),**report}
        except Exception as error:
            metadata.update(status='failed',error=str(error))
            write_json(output/'manifest.json',metadata)
            raise
    finally:
        lock.close()


def replay(args):
    """Re-normalize immutable captured bytes without claiming another observation day."""
    source=args.replay.resolve()
    manifest=json.loads((source/'manifest.json').read_text())
    if manifest.get('status')!='captured':raise ValueError('Replay requires a complete original capture')
    known={a['id'] for a in json.loads(args.data.read_text())['airports']}
    samples=[]
    output=args.work/'replays'/(source.name+'-'+dt.datetime.now(dt.timezone.utc).strftime('%H%M%S%f'))
    if ROOT/'web' in output.resolve().parents:raise ValueError('Replay must remain outside web')
    for airport in manifest['requested_airports']:
        previous=json.loads((source/(airport+'.json')).read_text())
        body=(source/(airport+'.xml')).read_bytes()
        if hashlib.sha256(body).hexdigest()!=previous['raw_sha256']:raise ValueError('Raw capture checksum mismatch')
        sample=parse_feed(body,airport,timestamp(previous['fetched_at']),known)
        sample.update(raw_sha256=previous['raw_sha256'],request_url=previous['request_url'])
        write_json(output/(airport+'.json'),sample)
        samples.append(sample)
    report=summarize(samples)
    original=json.loads((source/'report.json').read_text())
    report.update(replay_of=str(source),observation_days=original['observation_days'],observation_gate=original['observation_gate'])
    write_json(output/'report.json',report)
    write_json(output/'manifest.json',{**manifest,'replay_of':str(source),
               'normalizer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    return {'replay':str(output),**report}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,default=ROOT/'work/schedule-research')
    p.add_argument('--replay',type=Path,help='Re-normalize an existing complete capture without API requests')
    p.add_argument('--data',type=Path,default=ROOT/'web/data.json')
    p.add_argument('--airports',nargs='+',default=['OSL','BNN'])
    p.add_argument('--hours',type=int,default=168)
    p.add_argument('--max-requests',type=int,default=24)
    p.add_argument('--max-disk-mib',type=int,default=256)
    return p


if __name__=='__main__':
    arguments=parser().parse_args()
    print(json.dumps(replay(arguments) if arguments.replay else capture(arguments),indent=2))
