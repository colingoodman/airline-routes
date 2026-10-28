import datetime as dt
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import position_research as p
from rebuild import write_json

NOW=dt.datetime(2026,10,28,20,tzinfo=dt.timezone.utc)
LIMIT='4, 4;w=1, 60;w=60, 500;w=86400'


def aircraft(**extra):
    return {'hex':'abcdef','type':'adsb_icao','lat':60.2,'lon':11.1,'seen_pos':.5,
            'alt_baro':10000,'gs':250,'track':25,'flight':'SAS123  ',**extra}


def body(items=None,now=NOW):
    items=[aircraft()] if items is None else items
    return json.dumps({'msg':'No error','now':now.timestamp()*1000,'total':len(items),'ac':items}).encode()


class PositionTests(unittest.TestCase):
    def test_wrapper_milliseconds_and_position_age_are_not_message_age(self):
        frame=p.normalize(body([aircraft(seen=0,seen_pos=90)]),NOW.isoformat())
        point=frame['positions'][0]
        self.assertEqual(point['position_age_seconds'],90)
        self.assertTrue(point['stale'])
        self.assertEqual(point['observed_at'],(NOW-dt.timedelta(seconds=90)).isoformat())
        with self.assertRaisesRegex(ValueError,'milliseconds'):
            wrong=json.loads(body());wrong['now']/=1000
            p.normalize(json.dumps(wrong).encode(),NOW.isoformat())
    def test_provider_and_capture_age_are_both_included(self):
        f=p.normalize(body(now=NOW-dt.timedelta(seconds=20)),NOW.isoformat())
        self.assertEqual(f['positions'][0]['position_age_seconds'],20.5)
        with self.assertRaisesRegex(ValueError,'future'):
            p.normalize(body(now=NOW+dt.timedelta(seconds=6)),NOW.isoformat())
    def test_ground_units_headings_non_icao_and_unknown_quality(self):
        f=p.normalize(body([aircraft(hex='~ABCDEF',alt_baro='ground',alt_geom=40,true_heading=80,mag_heading=70,nic=0)]),NOW.isoformat())
        point=f['positions'][0]
        self.assertEqual(point['aircraft_id'],'~abcdef')
        self.assertTrue(point['on_ground']);self.assertIsNone(point['altitude_baro_ft'])
        self.assertEqual(point['altitude_geometric_ft'],40)
        self.assertEqual(point['track_degrees'],25);self.assertEqual(point['true_heading_degrees'],80)
        self.assertEqual(point['quality']['nic'],0);self.assertIsNone(point['quality']['sil'])
    def test_invalid_optional_quality_is_unknown_without_dropping_coordinates(self):
        f=p.normalize(body([aircraft(nic='bad',nac_p=99,sil=-1,rc=-5)]),NOW.isoformat())
        self.assertEqual(len(f['positions']),1)
        self.assertEqual(f['positions'][0]['quality'],{'nic':None,'nac_p':None,'sil':None,'rc':None})
    def test_missing_invalid_and_duplicate_positions_are_quarantined(self):
        cases=[(aircraft(lat=None),'missing_or_invalid_coordinates'),(aircraft(lon=999),'invalid_coordinates'),
               (aircraft(lat=0,lon=0),'outside_region'),(aircraft(seen_pos=None),'missing_or_invalid_position_age'),
               (aircraft(seen_pos=-2),'missing_or_invalid_position_age'),(aircraft(hex='bad'),'invalid_identity')]
        for item,reason in cases:
            with self.subTest(reason=reason):
                f=p.normalize(body([item]),NOW.isoformat());self.assertFalse(f['positions']);self.assertEqual(f['rejected'][0]['reason'],reason)
        f=p.normalize(body([aircraft(),aircraft(hex='ABCDEF')]),NOW.isoformat())
        self.assertFalse(f['positions']);self.assertEqual(len(f['rejected']),2)
    def test_identical_position_survives_microsecond_timestamp_round_trip(self):
        data=json.loads(body([aircraft(seen_pos=.14)]));data['now']+=1
        raw=json.dumps(data).encode()
        first=p.normalize(raw,NOW.isoformat())['positions'][0]
        repeated=p.normalize(raw,NOW.isoformat(),{'abcdef':first})
        self.assertEqual(repeated['rejected'],[])
        self.assertEqual(repeated['positions'][0]['trail_event'],'repeated_position')
    def test_missing_callsign_and_altitude_do_not_remove_a_valid_position(self):
        f=p.normalize(body([aircraft(flight=None,alt_baro=None)]),NOW.isoformat())
        self.assertIsNone(f['positions'][0]['callsign']);self.assertIsNone(f['positions'][0]['on_ground'])
    def test_trail_repetition_reordering_jumps_and_gaps(self):
        prior=p.normalize(body(),NOW.isoformat())['positions'][0];previous={'abcdef':prior}
        self.assertEqual(p.normalize(body(),NOW.isoformat(),previous)['positions'][0]['trail_event'],'repeated_position')
        later=NOW+dt.timedelta(seconds=20)
        frame=p.normalize(body([aircraft(lat=60.21)],later),later.isoformat(),previous)
        self.assertEqual(frame['positions'][0]['trail_event'],'update')
        self.assertEqual(frame['positions'][0]['update_interval_seconds'],20)
        for item,clock,reason in [(aircraft(seen_pos=2),NOW,'out_of_order_position'),
                                 (aircraft(lat=60.3),NOW,'conflicting_position_timestamp'),
                                 (aircraft(lat=60.8),NOW+dt.timedelta(seconds=1),'implausible_jump')]:
            f=p.normalize(body([item],clock),clock.isoformat(),previous)
            self.assertEqual(f['rejected'][0]['reason'],reason)
        clock=NOW+dt.timedelta(seconds=121)
        f=p.normalize(body([aircraft(lat=60.8)],clock),clock.isoformat(),previous)
        self.assertEqual(f['positions'][0]['trail_event'],'gap')
    def test_bad_envelopes_nonfinite_numbers_and_oversize_fail(self):
        for raw in [b'[]',b'{"msg":"No error","total":0,"now":NaN,"ac":[]}',b'x'*(p.MAX_RESPONSE+1)]:
            with self.assertRaises(ValueError):p.decode(raw)
        wrong=json.loads(body());wrong['total']=0
        with self.assertRaisesRegex(ValueError,'count'):p.decode(json.dumps(wrong).encode())
    def test_rate_policy_reserves_twenty_percent_and_honors_slower_limits(self):
        self.assertEqual(p.rate_policy(LIMIT),(180,20))
        self.assertEqual(p.rate_policy('1;w=60, 100;w=86400'),(80,60))
        self.assertEqual(p.rate_policy('50;w=86400'),(40,20))
        for value in ['', '500', '0;w=86400']:
            with self.assertRaises(ValueError):p.rate_policy(value)
    def args(self,work,samples=1):return SimpleNamespace(work=work,samples=samples,interval=20)
    def test_capture_and_offline_replay_match_without_network_or_extra_attempts(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch.object(p,'utcnow',return_value=NOW),patch.object(p,'fetch',return_value=(body(),{'x-ratelimit-limit':LIMIT},200)):
                result=p.capture(self.args(root))
            ledger=(root/'request-ledger.json').read_bytes()
            with patch.object(p,'fetch',side_effect=AssertionError('Replay performed network IO')):
                replay=p.replay(Path(result['session']),root/'replays/current')
            exported=json.loads((root/'replays/current/positions.json').read_text())
            with self.assertRaisesRegex(ValueError,'source research replays'):p.replay(Path(result['session']),root/'elsewhere')
            self.assertEqual(exported['kind'],'offline_replay')
            self.assertEqual(exported['snapshots'][0]['captured_at'],NOW.isoformat())
            with self.assertRaisesRegex(ValueError,'new directory'):p.replay(Path(result['session']),root/'replays/current')
            self.assertEqual(replay,result['report']);self.assertEqual(ledger,(root/'request-ledger.json').read_bytes())
            point=json.loads((Path(result['session'])/'000.normalized.json').read_text())['positions'][0]
            self.assertEqual(point['observed_at'],(NOW-dt.timedelta(seconds=.5)).isoformat())
            (Path(result['session'])/'000.json').write_bytes(b'{}')
            with self.assertRaisesRegex(ValueError,'checksum'):p.replay(Path(result['session']))
    def test_daily_budget_seeded_probe_and_lock_stop_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            write_json(root/'access/droplet/manifest.json',{'url':p.URL,'started_at':NOW.isoformat()})
            write_json(root/'request-ledger.json',{'days':{NOW.date().isoformat():179}})
            with patch.object(p,'utcnow',return_value=NOW),patch.object(p,'fetch') as fetch:
                with self.assertRaisesRegex(ValueError,'budget'):p.capture(self.args(root))
                fetch.assert_not_called()
            lock=p.locked(root)
            try:
                with self.assertRaisesRegex(ValueError,'already running'):p.capture(self.args(root))
            finally:lock.close()
    def test_midnight_cannot_double_spend_a_rolling_provider_allowance(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            write_json(root/'request-ledger.json',{'days':{(NOW-dt.timedelta(days=1)).date().isoformat():79,NOW.date().isoformat():1},'rate_limit':'100;w=86400'})
            with patch.object(p,'utcnow',return_value=NOW),patch.object(p,'fetch') as fetch:
                with self.assertRaisesRegex(ValueError,'budget'):p.capture(self.args(root))
                fetch.assert_not_called()
    def test_corrupt_negative_ledger_cannot_expand_the_request_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            write_json(root/'request-ledger.json',{'days':{NOW.date().isoformat():-100}})
            with patch.object(p,'utcnow',return_value=NOW),patch.object(p,'fetch') as fetch:
                with self.assertRaisesRegex(ValueError,'Invalid persisted'):p.capture(self.args(root))
                fetch.assert_not_called()
    def test_failed_attempt_is_counted_and_halts_day_without_retry(self):
        for code in (403,429):
            with self.subTest(code=code),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);error=HTTPError(p.URL,code,'blocked',{'Retry-After':'120'},BytesIO())
                with patch.object(p,'utcnow',return_value=NOW),patch.object(p,'fetch',side_effect=error) as fetch:
                    with self.assertRaises(HTTPError):p.capture(self.args(root,samples=3))
                    self.assertEqual(fetch.call_count,1)
                    with self.assertRaisesRegex(ValueError,'halted'):p.capture(self.args(root))
                    self.assertEqual(fetch.call_count,1)
                ledger=json.loads((root/'request-ledger.json').read_text())
                self.assertEqual(ledger['days'][NOW.date().isoformat()],1)
                manifest=json.loads(next((root/'sessions').glob('*/manifest.json')).read_text())
                self.assertEqual(manifest['status'],'failed');self.assertEqual(manifest['attempts'][0]['retry_after'],'120')
                error.close()
    def test_allowance_change_after_valid_frame_still_replays_identically(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch.object(p,'utcnow',return_value=NOW),patch.object(p,'fetch',return_value=(body(),{},200)):
                with self.assertRaisesRegex(ValueError,'allowance'):p.capture(self.args(root))
            session=next((root/'sessions').iterdir())
            self.assertEqual(p.replay(session),json.loads((session/'report.json').read_text()))
    def test_replay_also_verifies_retained_invalid_source_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch.object(p,'utcnow',return_value=NOW),patch.object(p,'fetch',return_value=(b'{}',{'x-ratelimit-limit':LIMIT},200)):
                with self.assertRaises(ValueError):p.capture(self.args(root))
            session=next((root/'sessions').iterdir())
            self.assertEqual(p.replay(session)['successful_responses'],0)
            (session/'000.json').write_bytes(b'[]')
            with self.assertRaisesRegex(ValueError,'checksum'):p.replay(session)
    def test_preflight_disk_and_interval_guards_and_protected_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch.object(p,'size_bytes',return_value=p.MAX_DISK),patch.object(p,'fetch') as fetch:
                with self.assertRaisesRegex(ValueError,'disk reserve'):p.capture(self.args(root))
                fetch.assert_not_called()
            write_json(root/'request-ledger.json',{'days':{},'last_attempt_at':NOW.isoformat()})
            with patch.object(p,'utcnow',return_value=NOW),patch.object(p,'fetch') as fetch:
                with self.assertRaisesRegex(ValueError,'interval'):p.capture(self.args(root))
                fetch.assert_not_called()
        for path in (p.ROOT,p.ROOT/'web',p.ROOT/'web/subdir',p.ROOT.parent):
            with self.assertRaises(ValueError):p.safe_work(path)
    def test_attempt_is_persisted_before_interrupted_network_io(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            def interrupt(*_):
                ledger=json.loads((root/'request-ledger.json').read_text())
                self.assertEqual(ledger['days'][NOW.date().isoformat()],1)
                manifest=json.loads(next((root/'sessions').glob('*/manifest.json')).read_text())
                self.assertEqual(manifest['attempts'][0]['status'],'attempted')
                raise KeyboardInterrupt()
            with patch.object(p,'utcnow',return_value=NOW),patch.object(p,'fetch',side_effect=interrupt):
                with self.assertRaises(KeyboardInterrupt):p.capture(self.args(root))
            manifest=json.loads(next((root/'sessions').glob('*/manifest.json')).read_text())
            self.assertEqual(manifest['status'],'failed')
            lock=p.locked(root);self.assertIsNotNone(lock);lock.close()
    def test_session_limits_and_runtime_are_checked_before_fetch(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for samples,interval in [(0,20),(61,20),(1,19),(60,120)]:
                args=SimpleNamespace(work=root,samples=samples,interval=interval)
                with self.subTest(samples=samples,interval=interval),patch.object(p,'fetch') as fetch:
                    with self.assertRaises(ValueError):p.capture(args)
                    fetch.assert_not_called()
    def test_total_network_deadline_and_redirects_are_disabled(self):
        response=SimpleNamespace(read=lambda limit:b'{}',headers={'X-RateLimit-Limit':LIMIT},status=200)
        context=unittest.mock.MagicMock();context.__enter__.return_value=response
        opener=unittest.mock.MagicMock();opener.open.return_value=context
        with patch.object(p,'build_opener',return_value=opener),patch.object(p.signal,'setitimer') as timer:
            raw,headers,status=p.fetch()
        self.assertEqual((raw,status),(b'{}',200));self.assertEqual(headers['x-ratelimit-limit'],LIMIT)
        self.assertEqual(opener.open.call_args.kwargs['timeout'],15)
        timer.assert_any_call(p.signal.ITIMER_REAL,15);timer.assert_any_call(p.signal.ITIMER_REAL,0)
        self.assertIsNone(p.NoRedirect().redirect_request(None,None,None,None,None,None))
    def test_continuity_counts_snapshot_disappearance_without_inventing_arrivals(self):
        frames=[];previous={}
        for seconds,items in [(0,[aircraft(),aircraft(hex='abcdee')]),(20,[aircraft(hex='abcdee')]),(40,[aircraft(),aircraft(hex='abcdee')])]:
            clock=NOW+dt.timedelta(seconds=seconds)
            frame=p.normalize(body(items,clock),clock.isoformat(),previous);frames.append(frame)
            for point in frame['positions']:previous[point['aircraft_id']]=point
        manifest={'started_at':NOW.isoformat(),'finished_at':(NOW+dt.timedelta(seconds=40)).isoformat(),'code_sha256':'test','attempts':[]}
        r=p.report(frames,manifest)
        self.assertEqual(r['unique_positioned_aircraft'],2)
        self.assertEqual(r['disappearances_between_snapshots'],1)
        self.assertEqual(r['reappearances_between_snapshots'],1)
        self.assertEqual(r['observed_update_interval_seconds'],{'median':20,'p95':40})
        self.assertIn('Not assessed',r['schedule_comparison'])
    def test_fetch_rejects_oversized_body_and_restores_deadline(self):
        context=unittest.mock.MagicMock()
        context.__enter__.return_value.read.return_value=b'x'*(p.MAX_RESPONSE+1)
        opener=unittest.mock.MagicMock();opener.open.return_value=context
        with patch.object(p,'build_opener',return_value=opener),patch.object(p.signal,'setitimer') as timer:
            with self.assertRaisesRegex(ValueError,'4 MiB'):p.fetch()
            timer.assert_any_call(p.signal.ITIMER_REAL,0)
    def test_metrics_include_stale_positions_and_unknowns_in_correct_denominators(self):
        items=[aircraft(seen_pos=90),aircraft(hex='abcdee',flight='',alt_baro='ground'),aircraft(hex='abcded',alt_baro=None)]
        frame=p.normalize(body(items),NOW.isoformat())
        manifest={'started_at':NOW.isoformat(),'finished_at':NOW.isoformat(),'code_sha256':'test','attempts':[]}
        metrics=p.report([frame],manifest)
        self.assertEqual(metrics['airborne_fresh_within_60_seconds'],{'numerator':0,'denominator':1})
        self.assertEqual(metrics['ground_position_reports'],1);self.assertEqual(metrics['unknown_ground_state_reports'],1)
        self.assertEqual(metrics['missing_callsign_reports'],1)


if __name__=='__main__':unittest.main()
