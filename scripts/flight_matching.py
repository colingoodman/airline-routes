#!/usr/bin/env python3
"""Offline OSL departure hypotheses; never assert a verified aircraft/flight link."""
import argparse
from collections import Counter, defaultdict
import datetime as dt
import hashlib
import json
from pathlib import Path
import re

import position_research as positions
import schedule_research as schedules
from rebuild import ROOT, write_json

POLICY = {'minutes_before_schedule':30, 'minutes_after_schedule':120,
          'episode_gap_seconds':1800, 'ground_radius_nm':3,
          'airborne_radius_nm':10, 'departure_transition_max_seconds':300,
          'max_schedule_age_hours':24}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def episodes(frames):
    """A hex is not a flight: split on callsign change, long gap or new ground visit."""
    result=[]; latest={}
    for frame in frames:
        for point in frame['positions']:
            now=positions.timestamp(point['observed_at'])
            prior=latest.get(point['aircraft_id'])
            if prior and now < positions.timestamp(prior['points'][-1]['observed_at']):
                raise ValueError('Position replay is out of order')
            split=(not prior or prior['callsign']!=point['callsign'] or
                   (now-positions.timestamp(prior['points'][-1]['observed_at'])).total_seconds()>POLICY['episode_gap_seconds'] or
                   (prior['points'][-1]['on_ground'] is False and point['on_ground'] is True))
            if split:
                prior={'episode_id':f"{point['aircraft_id']}:{point['observed_at']}:{len(result)}",
                       'aircraft_id':point['aircraft_id'],'callsign':point['callsign'],'points':[]}
                result.append(prior); latest[point['aircraft_id']]=prior
            prior['points'].append(point)
    return result


def departure_evidence(points):
    """Only fresh ground-to-air evidence near OSL; no destination inference."""
    ground=None
    for point in points:
        if point['stale']:continue
        distance=positions.distance_nm(positions.REGION['latitude'],positions.REGION['longitude'],point['latitude'],point['longitude'])
        now=positions.timestamp(point['observed_at'])
        if point['on_ground'] is True and distance<=POLICY['ground_radius_nm']:
            ground=now
        if (ground and point['on_ground'] is False and distance<=POLICY['airborne_radius_nm']
            and 0<(now-ground).total_seconds()<=POLICY['departure_transition_max_seconds']):
            return {'ground_observed_at':ground.isoformat(),'airborne_observed_at':now.isoformat()}
    return None


def match(frames, records, carriers):
    results=[]
    for episode in episodes(frames):
        points=episode.pop('points'); start=min(positions.timestamp(p['observed_at']) for p in points)
        end=max(positions.timestamp(p['observed_at']) for p in points)
        result={**episode,'first_observed_at':start.isoformat(),'last_observed_at':end.isoformat(),
                'fresh_reports_at_capture':sum(not p['stale'] for p in points),
                'stale_reports_at_capture':sum(p['stale'] for p in points),
                'departure_evidence':departure_evidence(points),'candidates':[],
                'state':'unknown','reason':None,'confirmed_flight':None,'actual_route':None}
        fresh=[positions.timestamp(p['observed_at']) for p in points if not p['stale']]
        if fresh:start,end=min(fresh),max(fresh)
        callsign=episode['callsign'] or ''
        parsed=re.fullmatch(r'([A-Z]{3})([0-9]{1,4})',callsign)
        if not callsign:result['reason']='missing_callsign'
        elif not fresh:result['reason']='only_stale_position_evidence'
        elif not parsed:result['reason']='non_numeric_or_unrecognized_callsign_format'
        elif parsed[1] not in carriers:result['reason']='unreviewed_carrier'
        else:
            mapping=carriers[parsed[1]]; number=mapping['iata']+parsed[2]
            result['hypothesized_published_number']=number
            for record in records:
                primary=record['published_flight_number']==number
                share=any(c['airline_iata']+c['flight_number']+c['suffix']==number for c in record['codeshares'])
                if not (primary or share):continue
                scheduled=positions.timestamp(record['scheduled_departure_utc']); rejected=[]
                if not primary:rejected.append('marketing_codeshare_only')
                if record['operating_airline_iata']!=mapping['iata']:rejected.append('operating_carrier_mismatch')
                if record['origin_airport_id']!='OSL':rejected.append('outside_osl_departure_scope')
                if end<scheduled-dt.timedelta(minutes=POLICY['minutes_before_schedule']) or start>scheduled+dt.timedelta(minutes=POLICY['minutes_after_schedule']):
                    rejected.append('outside_schedule_time_window')
                if (record.get('status_as_reported') or {}).get('code')=='C':rejected.append('cancelled_as_reported')
                fetched=positions.timestamp(record['fetched_at'])
                # Offline hindsight must not be mistaken for contemporaneous evidence.
                if fetched>start:rejected.append('schedule_captured_after_observation')
                elif start-fetched>dt.timedelta(hours=POLICY['max_schedule_age_hours']):rejected.append('schedule_capture_too_old')
                candidate={'source_record_id':record['source_record_id'],
                           'published_flight_number':record['published_flight_number'],
                           'scheduled_departure_utc':record['scheduled_departure_utc'],
                           'departure_local_date':record['departure_local_date'],
                           'planned_origin':'OSL','planned_destination_as_reported':record['destination_iata'],
                           'via_airports':record['via_airports'],'codeshares':record['codeshares'],
                           'schedule_fetched_at':record['fetched_at'],'carrier_sources':mapping['sources'],
                           'rejection_reasons':rejected,'evidence':'carrier mapping plus exact numeric suffix; hypothesis only',
                           'planned_pair':None,'route_resolution':'intermediate_circular_or_missing_airport'}
                if (not record['via_airports'] and not record.get('circular_service') and
                    record['destination_iata']!='OSL' and record['destination_airport_id']):
                    candidate['planned_pair']=['OSL',record['destination_iata']]
                    candidate['route_resolution']='planned_endpoints_only_actual_destination_unverified'
                result['candidates'].append(candidate)
            eligible=[c for c in result['candidates'] if not c['rejection_reasons']]
            if len(eligible)>1:result.update(state='ambiguous',reason='multiple_dated_flight_candidates')
            elif eligible:result.update(state='candidate',reason='independent_aircraft_to_flight_confirmation_required')
            else:result['reason']='no_eligible_schedule_candidate'
        results.append(result)
    # Aircraft substitution, duplicate callsigns or reuse must not become two asserted flights.
    associations=defaultdict(list)
    for result in results:
        for c in result['candidates']:
            if not c['rejection_reasons']:associations[c['source_record_id']].append(result)
    for group in associations.values():
        if len({r['aircraft_id'] for r in group})>1:
            for result in group:result.update(state='ambiguous',reason='multiple_aircraft_for_schedule_record')
    capture_start=min((positions.timestamp(f['captured_at']) for f in frames if f.get('captured_at')),default=None)
    capture_end=max((positions.timestamp(f['captured_at']) for f in frames if f.get('captured_at')),default=None)
    scheduled_in_window=[r for r in records if capture_start and capture_end and r['origin_airport_id']=='OSL'
                         and capture_start<=positions.timestamp(r['scheduled_departure_utc'])<=capture_end]
    covered={c['source_record_id'] for r in results for c in r['candidates'] if not c['rejection_reasons']}
    comparison={'scheduled_departures_in_capture_window':len(scheduled_in_window),
                'with_aircraft_hypothesis':sum(r['source_record_id'] in covered for r in scheduled_in_window),
                'without_aircraft_hypothesis':sum(r['source_record_id'] not in covered for r in scheduled_in_window),
                'interpretation':'Schedule-time window only; a hypothesis is not a confirmed departure. Missing hypotheses do not establish non-operation or feed incompleteness.'}
    return {'schema_version':1,'kind':'offline_research_hypotheses','policy':POLICY,'episodes':results,
            'schedule_window_comparison':comparison,
            'summary':{'aircraft':len({r['aircraft_id'] for r in results}),'episodes':len(results),
                       'states':dict(Counter(r['state'] for r in results)),
                       'reasons':dict(Counter(r['reason'] for r in results)),
                       'episodes_with_departure_evidence':sum(bool(r['departure_evidence']) for r in results),
                       'confirmed_matches':0,'precision':None,'match_coverage':None,
                       'validation_gate':'Pending independent review of 100 associations on two dates and 20 negative cases.'}}


def analyze(session, schedule_directory, carriers_path=ROOT/'research/callsign-carriers.json'):
    manifest=json.loads((session/'manifest.json').read_text())
    if manifest.get('status')!='captured':raise ValueError('Matching requires a complete position capture')
    report=positions.replay(session)  # Verify identity, sequence, response sizes and checksums.
    frames=[]; previous={}
    for attempt in manifest['attempts']:
        if attempt['status']!='captured':continue
        frame=positions.normalize((session/f"{attempt['index']:03d}.json").read_bytes(),attempt['captured_at'],previous)
        frames.append(frame)
        for point in frame['positions']:previous[point['aircraft_id']]=point
    schedule_manifest=json.loads((schedule_directory/'manifest.json').read_text())
    if schedule_manifest.get('status')!='captured' or 'OSL' not in schedule_manifest['requested_airports']:
        raise ValueError('Expected a complete OSL schedule capture')
    metadata=json.loads((schedule_directory/'OSL.json').read_text()); raw=schedule_directory/'OSL.xml'
    if digest(raw)!=metadata['raw_sha256']:raise ValueError('Schedule raw checksum mismatch')
    known={a['id'] for a in json.loads((ROOT/'web/data.json').read_text())['airports']}
    sample=schedules.parse_feed(raw.read_bytes(),'OSL',schedules.timestamp(metadata['fetched_at']),known)
    if any(i['kind']=='invalid_record' for i in sample['issues']):raise ValueError('Invalid schedule records require review')
    result=match(frames,sample['records'],json.loads(carriers_path.read_text())['carriers'])
    result['provenance']={'position_manifest_sha256':digest(session/'manifest.json'),
                          'position_capture_code_sha256':manifest['code_sha256'],
                          'position_analysis_code_sha256':report['analysis_code_sha256'],
                          'schedule_manifest_sha256':digest(schedule_directory/'manifest.json'),
                          'schedule_raw_sha256':digest(raw),'schedule_parser_sha256':digest(Path(schedules.__file__)),
                          'matcher_sha256':digest(Path(__file__)),'carrier_mapping_sha256':digest(carriers_path),
                          'position_attribution':manifest['attribution'],'schedule_attribution':sample['attribution']}
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session',type=Path,required=True);parser.add_argument('--schedules',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    output=args.out.resolve()
    if not output.is_relative_to(ROOT/'work') or output.exists():raise ValueError('Use a new private file inside work/')
    result=analyze(args.session,args.schedules);write_json(output,result)
    print(json.dumps(result['summary'],indent=2))


if __name__=='__main__':main()
