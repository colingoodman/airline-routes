#!/usr/bin/env python3
"""Replay a complete position session into aggregate-only research evidence."""
import argparse
import hashlib
import json
from pathlib import Path

import position_research as p
from rebuild import ROOT, write_json


def summarize(session):
    manifest_path=session/'manifest.json';manifest=json.loads(manifest_path.read_text())
    if manifest.get('status')!='captured':raise ValueError('Expected a complete position capture')
    result=p.replay(session);original=json.loads((session/'report.json').read_text())
    if {k:v for k,v in result.items() if k!='analysis_code_sha256'}!={k:v for k,v in original.items() if k!='analysis_code_sha256'}:
        raise ValueError('Replay changed original metrics; investigate before publishing an aggregate')
    frames=[];previous={};attempts=[]
    for attempt in manifest['attempts']:
        if attempt['status']!='captured':continue
        frame=p.normalize((session/f"{attempt['index']:03d}.json").read_bytes(),attempt['captured_at'],previous)
        frames.append(frame);attempts.append(attempt)
        for point in frame['positions']:previous[point['aircraft_id']]=point
    starts=[p.timestamp(a['requested_at']) for a in manifest['attempts']]
    intervals=[(b-a).total_seconds() for a,b in zip(starts,starts[1:])]
    if any(t<manifest['requested_interval_seconds']-.001 for t in intervals):
        raise ValueError('Observed request interval violates the requested cadence')
    blocks=[]
    for offset in range(0,len(frames),30):
        group=frames[offset:offset+30]
        block=p.report(group,{**manifest,'started_at':group[0]['captured_at'],
                             'finished_at':group[-1]['captured_at'],'attempts':attempts[offset:offset+30]})
        blocks.append({'first_sample':offset+1,'last_sample':offset+len(group),
                       **{key:block[key] for key in ('successful_responses','unique_positioned_aircraft',
                           'airborne_position_reports','ground_position_reports','airborne_position_age_seconds',
                           'airborne_fresh_within_60_seconds','rejection_reasons')}})
    return {'schema_version':1,'study':manifest['provider']+'-osl-regional-position-test',
            'provenance':{'session':session.name,'source_manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                          'summary_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                          'raw_response_sha256':[a['sha256'] for a in manifest['attempts'] if a.get('sha256')],
                          'raw_aircraft_data_committed':False},
            'results':result,'consecutive_30_response_blocks':blocks,
            'minimum_request_start_interval_seconds':min(intervals,default=None),
            'maximum_request_start_interval_seconds':max(intervals,default=None),
            'audit':{'raw_checksums_verified':True,'replay_matches_original_metrics':True},
            'limitations':['One fixed Oslo window; no full-day, peak-traffic or worldwide coverage claim.',
                           'Freshness is conditional on returned accepted reports, not aircraft completeness.',
                           'No flight or actual route confirmation in this aggregate.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('session',type=Path)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    output=args.out.resolve()
    if not output.is_relative_to(ROOT/'research') or output.exists():raise ValueError('Use a new aggregate file inside research/')
    result=summarize(args.session);write_json(output,result)
    print(json.dumps(result['results'],indent=2))


if __name__=='__main__':main()
