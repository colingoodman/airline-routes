#!/usr/bin/env python3
"""Bounded private OSL position capture and offline replay; never publish data."""
import argparse
from collections import Counter
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import signal
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, HTTPRedirectHandler, build_opener

from rebuild import ROOT, write_json
from refresh_runner import locked, size_bytes

URL = 'https://api.adsb.lol/v2/point/60.193901/11.1004/50'
REGION = {'airport':'OSL','latitude':60.193901,'longitude':11.1004,'radius_nm':50}
MAX_RESPONSE = 4*1024*1024
TIMEOUT = 15
MAX_DISK = 128*1024*1024
DAY_CAP = 180
MIN_INTERVAL = 20
MAX_SESSION_SECONDS = 1500
POLICY = {'stale_after_seconds':60,'future_tolerance_seconds':5,
          'trail_gap_seconds':120,'jump_speed_knots':1400,'jump_tolerance_nm':1}


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def timestamp(value):
    result=dt.datetime.fromisoformat(value)
    if result.utcoffset() is None:raise ValueError('Timestamp must include a UTC offset')
    return result.astimezone(dt.timezone.utc)


def number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def decode(body):
    if len(body)>MAX_RESPONSE:raise ValueError('Response exceeds 4 MiB')
    def invalid(value):raise ValueError('Non-finite JSON number: '+value)
    value=json.loads(body,parse_constant=invalid)
    if not isinstance(value,dict) or value.get('msg')!='No error' or not isinstance(value.get('ac'),list):
        raise ValueError('Unexpected position response')
    if type(value.get('total')) is not int or value['total']!=len(value['ac']) or len(value['ac'])>10000:
        raise ValueError('Invalid aircraft count')
    # This API wrapper uses milliseconds, unlike native readsb aircraft.json.
    if not number(value.get('now')) or not 946684800000<=value['now']<4102444800000:
        raise ValueError('Expected provider time in Unix milliseconds')
    return value


def distance_nm(lat1,lon1,lat2,lon2):
    a,b=map(math.radians,(lat1,lat2));x=math.sin((b-a)/2)**2+math.cos(a)*math.cos(b)*math.sin(math.radians(lon2-lon1)/2)**2
    return 3440.065*2*math.asin(min(1,math.sqrt(max(0,x))))


def normalize(body, captured_at, previous=None):
    data=decode(body);provider_time=data['now']/1000;capture_time=timestamp(captured_at).timestamp()
    if provider_time-capture_time>POLICY['future_tolerance_seconds']:
        raise ValueError('Provider clock is too far in the future')
    previous=previous or {};positions=[];rejected=[];seen=set()
    ids=Counter(a['hex'].lower() for a in data['ac'] if isinstance(a,dict) and isinstance(a.get('hex'),str))
    for index,a in enumerate(data['ac']):
        identity=a.get('hex') if isinstance(a,dict) else None
        try:
            if not isinstance(identity,str) or not re.fullmatch(r'~?[0-9a-fA-F]{6}',identity):raise ValueError('invalid_identity')
            identity=identity.lower()
            if identity in seen or ids[identity]>1:raise ValueError('duplicate_identity')
            seen.add(identity)
            if not all(number(a.get(k)) for k in ('lat','lon')):raise ValueError('missing_or_invalid_coordinates')
            lat,lon=a['lat'],a['lon']
            if not -90<=lat<=90 or not -180<=lon<=180:raise ValueError('invalid_coordinates')
            if distance_nm(REGION['latitude'],REGION['longitude'],lat,lon)>REGION['radius_nm']+0.1:
                raise ValueError('outside_region')
            if not number(a.get('seen_pos')) or a['seen_pos']<0:raise ValueError('missing_or_invalid_position_age')
            # Canonicalize to ISO microsecond precision before comparing timestamps.
            observed=round(provider_time-a['seen_pos'],6);age=capture_time-observed
            if age < -POLICY['future_tolerance_seconds']:raise ValueError('future_position')
            baro=a.get('alt_baro');ground=True if baro=='ground' else False if number(baro) else None
            p={'aircraft_id':identity,'source_type':a.get('type'),'callsign':a.get('flight').strip() or None if isinstance(a.get('flight'),str) else None,
               'registration_as_reported':a.get('r'),'latitude':lat,'longitude':lon,
               'observed_at':dt.datetime.fromtimestamp(observed,dt.timezone.utc).isoformat(),
               'position_age_seconds':round(age,6),'provider_position_age_seconds':a['seen_pos'],
               'on_ground':ground,'altitude_baro_ft':baro if number(baro) else None,
               'altitude_geometric_ft':a.get('alt_geom') if number(a.get('alt_geom')) else None,
               'ground_speed_knots':a.get('gs') if number(a.get('gs')) and a['gs']>=0 else None,
               'track_degrees':a.get('track') if number(a.get('track')) and 0<=a['track']<360 else None,
               'true_heading_degrees':a.get('true_heading') if number(a.get('true_heading')) and 0<=a['true_heading']<360 else None,
               'magnetic_heading_degrees':a.get('mag_heading') if number(a.get('mag_heading')) and 0<=a['mag_heading']<360 else None,
               'quality':{k:a.get(k) if number(a.get(k)) and 0<=a[k]<=upper else None for k,upper in (('nic',11),('nac_p',11),('sil',3),('rc',float('inf')))},
               'position_method_fields':{k:a.get(k) for k in ('mlat','tisb')},
               'stale':age>POLICY['stale_after_seconds'],'trail_event':'start','update_interval_seconds':None}
            prior=previous.get(identity)
            if prior:
                seconds=observed-timestamp(prior['observed_at']).timestamp()
                displacement=distance_nm(prior['latitude'],prior['longitude'],lat,lon)
                if seconds<0:raise ValueError('out_of_order_position')
                if seconds==0:
                    if displacement>0.001:raise ValueError('conflicting_position_timestamp')
                    p['trail_event']='repeated_position'
                elif seconds>POLICY['trail_gap_seconds']:p['trail_event']='gap'
                elif displacement>max(POLICY['jump_tolerance_nm'],POLICY['jump_speed_knots']*seconds/3600):
                    raise ValueError('implausible_jump')
                else:p['trail_event']='update'
                if seconds>0:p['update_interval_seconds']=round(seconds,6)
            positions.append(p)
        except (ValueError,OverflowError,OSError) as error:
            rejected.append({'index':index,'aircraft_id':identity,'reason':str(error)})
    return {'captured_at':captured_at,'provider_at':dt.datetime.fromtimestamp(provider_time,dt.timezone.utc).isoformat(),
            'provider_response_age_seconds':round(capture_time-provider_time,6),
            'reported_aircraft':len(data['ac']),'positions':positions,'rejected':rejected}


def percentile(values,percent):
    if not values:return None
    ordered=sorted(values);return round(ordered[max(0,math.ceil(len(ordered)*percent)-1)],6)


def report(frames,manifest):
    positions=[p for f in frames for p in f['positions']];airborne=[p for p in positions if p['on_ground'] is False]
    ages=[p['position_age_seconds'] for p in airborne];updates=[p['update_interval_seconds'] for p in positions if p['trail_event']=='update']
    all_ids=set();last_ids=set();disappearances=reappearances=0
    for frame in frames:
        ids={p['aircraft_id'] for p in frame['positions']}
        disappearances+=len(last_ids-ids);reappearances+=len((ids-last_ids)&all_ids)
        all_ids|=ids;last_ids=ids
    attempts=manifest['attempts'];latencies=[a['latency_seconds'] for a in attempts if a.get('status')=='captured']
    return {'schema_version':1,'provider':'adsb.lol','region':REGION,'policy':POLICY,
            'started_at':manifest['started_at'],'finished_at':manifest.get('finished_at'),
            'capture_code_sha256':manifest['code_sha256'],'analysis_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'attempts':len(attempts),'successful_responses':len(frames),'http_statuses':dict(Counter(str(a.get('http_status','no_response')) for a in attempts)),
            'sample_seconds':round((timestamp(frames[-1]['captured_at'])-timestamp(frames[0]['captured_at'])).total_seconds(),6) if len(frames)>1 else 0,
            'latency_seconds':{'median':percentile(latencies,0.5),'p95':percentile(latencies,0.95)},
            'response_bytes':{'total':sum(a.get('bytes',0) for a in attempts),'max':max((a.get('bytes',0) for a in attempts),default=0)},
            'unique_positioned_aircraft':len(all_ids),'aircraft_reports':sum(f['reported_aircraft'] for f in frames),
            'accepted_position_reports':len(positions),'rejection_reasons':dict(Counter(r['reason'] for f in frames for r in f['rejected'])),
            'airborne_position_reports':len(airborne),'ground_position_reports':sum(p['on_ground'] is True for p in positions),
            'unknown_ground_state_reports':sum(p['on_ground'] is None for p in positions),
            'airborne_position_age_seconds':{'median':percentile(ages,.5),'p95':percentile(ages,.95),'max':max(ages,default=None)},
            'airborne_fresh_within_60_seconds':{'numerator':sum(not p['stale'] for p in airborne),'denominator':len(airborne)},
            'missing_callsign_reports':sum(p['callsign'] is None for p in positions),
            'missing_quality_fields':{k:sum(p['quality'][k] is None for p in positions) for k in ('nic','nac_p','sil','rc')},
            'source_types':dict(Counter(str(p['source_type']) for p in positions)),
            'trail_events':dict(Counter(p['trail_event'] for p in positions)),
            'observed_update_interval_seconds':{'median':percentile(updates,.5),'p95':percentile(updates,.95)},
            'disappearances_between_snapshots':disappearances,'reappearances_between_snapshots':reappearances,
            'schedule_comparison':'Not assessed: a position/callsign alone does not establish a scheduled departure or dated flight identity.',
            'coverage_limit':'One fixed region and sampled period; no all-day availability, completeness or end-to-end flight-path claim.'}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args):return None


def fetch():
    def timeout(*_):raise TimeoutError('15-second total request deadline exceeded')
    old=signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,TIMEOUT)
    try:
        with build_opener(NoRedirect).open(Request(URL,headers={'User-Agent':'AllianceRouteMap-research/1.0 (https://github.com/colingoodman/airline-routes)','Accept':'application/json'}),timeout=TIMEOUT) as response:
            body=response.read(MAX_RESPONSE+1)
            if len(body)>MAX_RESPONSE:raise ValueError('Response exceeds 4 MiB')
            headers={k.lower():v for k,v in response.headers.items() if k.lower() in ('x-ratelimit-limit','x-ratelimit-remaining','x-ratelimit-reset','retry-after','date','content-type')}
            return body,headers,response.status
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)


def rate_policy(header):
    limits={}
    for count,window in re.findall(r'(\d+)\s*;\s*w=(\d+)',header or ''):
        count,window=int(count),int(window)
        if count<=0 or window<=0:raise ValueError('Invalid provider rate policy')
        limits[window]=min(count,limits.get(window,count))
    if 86400 not in limits:raise ValueError('Provider daily allowance is missing or unrecognized')
    return min(DAY_CAP,limits[86400]*4//5),max([MIN_INTERVAL]+[window/count for window,count in limits.items() if window!=86400])


def safe_work(path):
    work=path.resolve()
    if work==ROOT or work in ROOT.parents or work==ROOT/'web' or ROOT/'web' in work.parents:
        raise ValueError('Research state must be outside published files and repository ancestors')
    return work


def bounded_json(path,value,work):
    encoded=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    if size_bytes(work)+len(encoded)-(path.stat().st_size if path.exists() else 0)>MAX_DISK:
        raise ValueError('Research disk budget exhausted')
    write_json(path,value)


def seed_ledger(work,ledger):
    seeded=set(ledger.get('access_probes',[]))
    for path in (work/'access').rglob('*manifest.json'):
        d=json.loads(path.read_text());key=d.get('started_at')
        if d.get('url')!=URL or not key or key in seeded:continue
        day=timestamp(key).date().isoformat();ledger.setdefault('days',{})[day]=ledger.setdefault('days',{}).get(day,0)+1;seeded.add(key)
    ledger['access_probes']=sorted(seeded)


def budget_used(ledger,now):
    # The provider's 86400-second window is not documented as UTC-midnight reset.
    # Including the preceding UTC day conservatively bounds every rolling day.
    for day,count in ledger['days'].items():
        dt.date.fromisoformat(day)
        if type(count) is not int or count<0:raise ValueError('Invalid persisted request count')
    earliest=(now-dt.timedelta(days=1)).date().isoformat()
    return sum(count for day,count in ledger['days'].items() if day>=earliest)


def capture(args):
    if not 1<=args.samples<=60 or not number(args.interval) or not 20<=args.interval<=120:
        raise ValueError('Use 1–60 samples, 20–120 seconds apart')
    if (args.samples-1)*args.interval+TIMEOUT>MAX_SESSION_SECONDS:
        raise ValueError('Requested session exceeds the 25-minute runtime budget')
    work=safe_work(args.work);lock=locked(work)
    if lock is None:raise ValueError('Position research already running')
    session=None;manifest=None;frames=[];previous={};started_clock=time.monotonic();last_clock=None
    try:
        ledger_file=work/'request-ledger.json';ledger=json.loads(ledger_file.read_text()) if ledger_file.exists() else {'days':{}}
        seed_ledger(work,ledger)
        now=utcnow();day=now.date().isoformat()
        cap,interval=rate_policy(ledger.get('rate_limit','4, 4;w=1, 60;w=60, 500;w=86400'))
        if ledger.get('halted_day')==day:raise ValueError('Provider access halted for this UTC day; inspect earlier failure')
        if budget_used(ledger,now)+args.samples>cap:raise ValueError('Daily request budget exhausted before session')
        if ledger.get('last_attempt_at') and (now-timestamp(ledger['last_attempt_at'])).total_seconds()<max(args.interval,interval):
            raise ValueError('Minimum request interval has not elapsed')
        if size_bytes(work)+MAX_RESPONSE*3>MAX_DISK:raise ValueError('Research disk reserve exhausted before session')
        session=work/'sessions'/now.strftime('%Y%m%dT%H%M%S%fZ');session.mkdir(parents=True)
        manifest={'schema_version':1,'provider':'adsb.lol','url':URL,'region':REGION,'started_at':now.isoformat(),'status':'collecting',
                  'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'support_code_sha256':{name:hashlib.sha256(Path(sys.modules[name].__file__).read_bytes()).hexdigest() for name in ('rebuild','refresh_runner')},
                  'requested_samples':args.samples,
                  'requested_interval_seconds':args.interval,'attempts':[],'attribution':{'text':'adsb.lol','url':'https://www.adsb.lol/','license':'ODbL-1.0'}}
        bounded_json(session/'manifest.json',manifest,work)
        for index in range(args.samples):
            now=utcnow();day=now.date().isoformat();cap,min_interval=rate_policy(ledger.get('rate_limit','4, 4;w=1, 60;w=60, 500;w=86400'))
            if ledger.get('last_attempt_at'):
                remaining=max(args.interval,min_interval)-(now-timestamp(ledger['last_attempt_at'])).total_seconds()
                if last_clock is not None:remaining=max(remaining,max(args.interval,min_interval)-(time.monotonic()-last_clock))
                if time.monotonic()-started_clock+max(0,remaining)+TIMEOUT>MAX_SESSION_SECONDS:
                    raise ValueError('Session runtime budget exhausted')
                if remaining>0:time.sleep(remaining)
            now=utcnow();day=now.date().isoformat()
            if budget_used(ledger,now)>=cap:raise ValueError('Daily request budget exhausted')
            if size_bytes(work)+MAX_RESPONSE*3>MAX_DISK:raise ValueError('Research disk reserve exhausted')
            if time.monotonic()-started_clock+TIMEOUT>MAX_SESSION_SECONDS:raise ValueError('Session runtime budget exhausted')
            last_clock=time.monotonic()
            ledger['days'][day]=ledger['days'].get(day,0)+1;ledger['last_attempt_at']=now.isoformat()
            bounded_json(ledger_file,ledger,work)
            attempt={'index':index,'requested_at':now.isoformat(),'status':'attempted'};manifest['attempts'].append(attempt)
            bounded_json(session/'manifest.json',manifest,work);clock=time.monotonic()
            try:
                body,headers,status=fetch();fetched=utcnow().isoformat()
                attempt.update(captured_at=fetched,latency_seconds=round(time.monotonic()-clock,6),headers=headers,http_status=status,bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
                # Retain malformed source bytes too, without treating them as a valid frame.
                (session/f'{index:03d}.json').write_bytes(body)
                frame=normalize(body,fetched,previous)
                bounded_json(session/f'{index:03d}.normalized.json',frame,work)
                for p in frame['positions']:previous[p['aircraft_id']]=p
                frames.append(frame);attempt['status']='captured'
                # A changed or absent allowance ends this session rather than guessing.
                cap,min_interval=rate_policy(headers.get('x-ratelimit-limit'))
                ledger['rate_limit']=headers['x-ratelimit-limit'];bounded_json(ledger_file,ledger,work)
                if budget_used(ledger,now)>cap:raise ValueError('Observed provider allowance is below the research budget')
            except BaseException as error:
                attempt.update(status='captured' if attempt['status']=='captured' else 'failed',error=str(error),latency_seconds=round(time.monotonic()-clock,6))
                if isinstance(error,HTTPError):attempt.update(http_status=error.code,retry_after=error.headers.get('Retry-After'))
                ledger['halted_day']=day;bounded_json(ledger_file,ledger,work)
                raise
            finally:
                bounded_json(session/'manifest.json',manifest,work)
            print(json.dumps({'sample':index+1,'accepted_positions':len(frame['positions']),'rejected':len(frame['rejected'])}),flush=True)
        manifest['status']='captured'
    except BaseException as error:
        if manifest is not None:manifest.update(status='failed',error=str(error))
        raise
    finally:
        try:
            if manifest is not None:
                manifest['finished_at']=utcnow().isoformat();bounded_json(session/'manifest.json',manifest,work)
                bounded_json(session/'report.json',report(frames,manifest),work)
        finally:
            lock.close()
    return {'session':str(session),'report':report(frames,manifest)}


def replay(session,output=None):
    manifest=json.loads((session/'manifest.json').read_text());frames=[];previous={}
    if manifest.get('schema_version')!=1 or manifest.get('url')!=URL or manifest.get('region')!=REGION:
        raise ValueError('Unexpected capture identity')
    for index,attempt in enumerate(manifest['attempts']):
        if attempt['index']!=index:raise ValueError('Unexpected capture sequence')
        if not attempt.get('sha256'):
            if attempt['status']=='captured':raise ValueError('Captured response lacks a checksum')
            continue
        path=session/f'{index:03d}.json'
        if path.stat().st_size>MAX_RESPONSE:raise ValueError('Replay body exceeds budget')
        body=path.read_bytes()
        if hashlib.sha256(body).hexdigest()!=attempt['sha256']:raise ValueError('Replay checksum mismatch')
        if attempt['status']!='captured':continue
        frame=normalize(body,attempt['captured_at'],previous);frames.append(frame)
        for p in frame['positions']:previous[p['aircraft_id']]=p
    result=report(frames,manifest)
    if output is not None:
        output=safe_work(output);work=safe_work(session.resolve().parent.parent)
        if session.parent.name!='sessions' or not output.is_relative_to(work/'replays'):
            raise ValueError('Replay output must be inside the source research replays directory')
        if output.exists():raise ValueError('Replay output must be a new directory')
        if manifest.get('status') not in ('captured','failed'):raise ValueError('Wait for capture to finish before exporting replay')
        output.mkdir(parents=True)
        bounded_json(output/'positions.json',{'schema_version':1,'kind':'offline_replay',
                     'source_session':str(session.resolve()),'source_manifest_sha256':hashlib.sha256((session/'manifest.json').read_bytes()).hexdigest(),
                     'capture_code_sha256':manifest['code_sha256'],'analysis_code_sha256':result['analysis_code_sha256'],
                     'source_capture_status':manifest['status'],'region':REGION,'snapshots':frames},work)
        bounded_json(output/'report.json',result,work)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('capture');p.add_argument('--work',type=Path,default=ROOT/'work/position-research');p.add_argument('--samples',type=int,default=60);p.add_argument('--interval',type=float,default=20)
    p=sub.add_parser('replay');p.add_argument('session',type=Path);p.add_argument('--out',type=Path,help='New private directory for one normalized positions.json and report')
    args=parser.parse_args();result=capture(args) if args.command=='capture' else replay(args.session,args.out)
    print(json.dumps(result,indent=2,allow_nan=False))


if __name__=='__main__':main()
