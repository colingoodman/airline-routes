#!/usr/bin/env python3
"""Inventory unsupported callsign shapes offline; never decode a flight number."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

import flight_matching as matching
import position_research as positions
from rebuild import ROOT, write_json


def classify(callsign, registrations, carriers):
    # Registration equality is only as reported, not independent identity proof.
    if not callsign:return 'missing_callsign'
    if any(isinstance(r,str) and re.sub(r'[- ]','',r.upper())==callsign for r in registrations):
        return 'matches_reported_registration'
    if re.fullmatch(r'[A-Z]{3}[0-9]{1,4}',callsign):return 'numeric_company_format'
    parsed=re.fullmatch(r'([A-Z]{3})([A-Z0-9]{1,4})',callsign)
    if parsed:
        return 'reviewed_carrier_alphanumeric' if parsed[1] in carriers else 'unreviewed_company_shaped'
    return 'other_format'


def inventory(session):
    manifest=json.loads((session/'manifest.json').read_text())
    if manifest.get('status')!='captured':raise ValueError('Expected a complete capture')
    positions.replay(session)  # Identity, sizes, sequence and raw checksums first.
    frames=[];previous={}
    for attempt in manifest['attempts']:
        if attempt['status']!='captured':continue
        frame=positions.normalize((session/f"{attempt['index']:03d}.json").read_bytes(),attempt['captured_at'],previous)
        frames.append(frame)
        for point in frame['positions']:previous[point['aircraft_id']]=point
    mapping_path=ROOT/'research/callsign-carriers.json';carriers=json.loads(mapping_path.read_text())['carriers']
    counts=Counter();prefixes=Counter();unsupported=0
    for episode in matching.episodes(frames):
        callsign=episode['callsign'] or ''
        # Same subset as the initial matcher's generic unsupported-format reason.
        if not callsign or re.fullmatch(r'[A-Z]{3}[0-9]{1,4}',callsign):continue
        unsupported+=1
        category=classify(callsign,[p['registration_as_reported'] for p in episode['points']],carriers)
        counts[category]+=1
        if category=='reviewed_carrier_alphanumeric':prefixes[callsign[:3]]+=1
    return {'schema_version':1,'session':session.name,'unsupported_format_episodes':unsupported,
            'categories':dict(sorted(counts.items())),
            'reviewed_carrier_alphanumeric_episodes_by_prefix':dict(sorted(prefixes.items())),
            'decoded_flight_numbers':0,'new_confirmed_associations':0,
            'provenance':{'position_manifest_sha256':matching.digest(session/'manifest.json'),
                          'carrier_mapping_sha256':matching.digest(mapping_path),
                          'inventory_code_sha256':matching.digest(Path(__file__)),
                          'position_normalizer_sha256':matching.digest(Path(positions.__file__)),
                          'episode_builder_sha256':matching.digest(Path(matching.__file__))},
            'limits':['Shape classification only; no new identity, registration or operating-carrier verification.',
                      'A reviewed carrier prefix does not decode its alphanumeric operational identifier.',
                      'No aircraft identifiers, callsign rows or positions are exported.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('session',type=Path)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();out=args.out.resolve()
    if not out.is_relative_to(ROOT/'research') or out.exists():raise ValueError('Use a new aggregate file inside research/')
    result=inventory(args.session);write_json(out,result);print(json.dumps(result,indent=2))


if __name__=='__main__':main()
