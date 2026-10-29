import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import flight_matching as m

NOW=dt.datetime(2026,10,29,8,tzinfo=dt.timezone.utc)
CARRIERS={'SAS':{'iata':'SK','sources':['https://example.test/identity']}}


def point(**extra):
    return {'aircraft_id':'abcdef','callsign':'SAS123','observed_at':NOW.isoformat(),
            'latitude':60.193901,'longitude':11.1004,'on_ground':False,'stale':False,**extra}


def record(**extra):
    return {'source_record_id':'avinor:OSL:D:1','published_flight_number':'SK123',
            'operating_airline_iata':'SK','origin_airport_id':'OSL','destination_iata':'BGO',
            'destination_airport_id':'BGO','scheduled_departure_utc':NOW.isoformat(),
            'departure_local_date':'2026-10-29','via_airports':[],'circular_service':False,
            'codeshares':[],'status_as_reported':None,
            'fetched_at':(NOW-dt.timedelta(hours=2)).isoformat(),**extra}


def run(points=None,records=None):
    return m.match([{'positions':points if points is not None else [point()]}],
                   records if records is not None else [record()],CARRIERS)


class FlightMatchingTests(unittest.TestCase):
    def test_numeric_hypothesis_never_confirms_aircraft_or_actual_route(self):
        result=run(); episode=result['episodes'][0]
        self.assertEqual(episode['state'],'candidate')
        self.assertIsNone(episode['confirmed_flight']);self.assertIsNone(episode['actual_route'])
        self.assertEqual(episode['candidates'][0]['planned_pair'],['OSL','BGO'])
        self.assertIsNone(result['summary']['precision']);self.assertIsNone(result['summary']['match_coverage'])

    def test_twenty_ambiguous_or_negative_cases(self):
        cases=[
            ([point(callsign=None)],[record()],'unknown'),
            ([point(callsign='SAS12A')],[record()],'unknown'),
            ([point(callsign='ZZZ123')],[record()],'unknown'),
            ([point(callsign='LNABC')],[record()],'unknown'),
            ([point(callsign='sas123')],[record()],'unknown'),
            ([point(callsign='SAS0123')],[record()],'unknown'),
            ([point(callsign='SAS123')],[],'unknown'),
            ([point()],[record(published_flight_number='SK124')],'unknown'),
            ([point()],[record(operating_airline_iata='DY')],'unknown'),
            ([point()],[record(origin_airport_id='BNN')],'unknown'),
            ([point()],[record(scheduled_departure_utc=(NOW+dt.timedelta(minutes=31)).isoformat())],'unknown'),
            ([point()],[record(scheduled_departure_utc=(NOW-dt.timedelta(minutes=121)).isoformat())],'unknown'),
            ([point()],[record(scheduled_departure_utc=(NOW-dt.timedelta(days=1)).isoformat())],'unknown'),
            ([point()],[record(status_as_reported={'code':'C'})],'unknown'),
            ([point()],[record(fetched_at=(NOW+dt.timedelta(seconds=1)).isoformat())],'unknown'),
            ([point()],[record(fetched_at=(NOW-dt.timedelta(hours=25)).isoformat())],'unknown'),
            ([point()],[record(published_flight_number='DY123',operating_airline_iata='DY',codeshares=[{'airline_iata':'SK','flight_number':'123','suffix':''}])],'unknown'),
            ([point()],[record(),record(source_record_id='avinor:OSL:D:2')],'ambiguous'),
            ([point(),point(aircraft_id='123456')],[record()],'ambiguous'),
            ([point()],[record(published_flight_number='SK0123')],'unknown')]
        self.assertEqual(len(cases),20)
        for points,records,state in cases:
            with self.subTest(points=points,records=records):
                result=run(points,records)
                self.assertTrue(all(e['state']==state and e['confirmed_flight'] is None for e in result['episodes']))

    def test_rejections_preserve_all_dated_instances_and_reasons(self):
        result=run(records=[record(),record(source_record_id='other-day',scheduled_departure_utc=(NOW+dt.timedelta(days=1)).isoformat())])
        candidates=result['episodes'][0]['candidates'];self.assertEqual(len(candidates),2)
        self.assertIn('outside_schedule_time_window',candidates[1]['rejection_reasons'])

    def test_midnight_uses_utc_interval_not_equal_calendar_date(self):
        observed=NOW.replace(hour=0,minute=10);scheduled=observed-dt.timedelta(minutes=20)
        result=run([point(observed_at=observed.isoformat())],[record(scheduled_departure_utc=scheduled.isoformat(),fetched_at=(observed-dt.timedelta(hours=1)).isoformat())])
        self.assertEqual(result['episodes'][0]['state'],'candidate')

    def test_dst_fold_remains_two_distinct_instants(self):
        # Oslo 02:30 occurs at both UTC 00:30 and 01:30 on the autumn transition.
        early='2026-10-25T00:30:00+00:00';late='2026-10-25T01:30:00+00:00'
        result=run([point(observed_at=late)],[record(scheduled_departure_utc=early,fetched_at='2026-10-24T23:00:00+00:00'),record(source_record_id='second',scheduled_departure_utc=late,fetched_at='2026-10-24T23:00:00+00:00')])
        self.assertEqual(result['episodes'][0]['state'],'ambiguous')

    def test_multistop_circular_and_missing_airport_never_become_direct_pairs(self):
        for changes in ({'via_airports':['TRD']},{'circular_service':True},{'destination_airport_id':None},{'destination_iata':'OSL'}):
            with self.subTest(changes=changes):self.assertIsNone(run(records=[record(**changes)])['episodes'][0]['candidates'][0]['planned_pair'])

    def test_codeshares_are_metadata_not_duplicate_aircraft(self):
        result=run(records=[record(codeshares=[{'airline_iata':'LH','flight_number':'999','suffix':''}])])
        self.assertEqual(len(result['episodes']),1)
        self.assertEqual(len(result['episodes'][0]['candidates'][0]['codeshares']),1)

    def test_identity_does_not_persist_across_callsign_change_or_missing_callsign(self):
        points=[point(),point(callsign='SAS124',observed_at=(NOW+dt.timedelta(seconds=20)).isoformat()),point(callsign=None,observed_at=(NOW+dt.timedelta(seconds=40)).isoformat())]
        result=run(points);self.assertEqual(len(result['episodes']),3)
        self.assertEqual(result['episodes'][-1]['state'],'unknown')

    def test_same_callsign_after_long_gap_or_landing_is_a_new_episode(self):
        for second in (point(observed_at=(NOW+dt.timedelta(seconds=1801)).isoformat()),point(on_ground=True,observed_at=(NOW+dt.timedelta(seconds=20)).isoformat())):
            self.assertEqual(len(run([point(),second])['episodes']),2)

    def test_out_of_order_replay_fails(self):
        with self.assertRaises(ValueError):run([point(),point(observed_at=(NOW-dt.timedelta(seconds=1)).isoformat())])

    def test_fresh_ground_to_air_evidence_stays_a_hypothesis(self):
        result=run([point(on_ground=True),point(observed_at=(NOW+dt.timedelta(seconds=20)).isoformat())])
        self.assertIsNotNone(result['episodes'][0]['departure_evidence'])
        self.assertEqual(result['episodes'][0]['state'],'candidate')

    def test_stale_far_and_long_gap_points_do_not_corroborate_departure(self):
        for ground,air in ((point(on_ground=True,stale=True),point(observed_at=(NOW+dt.timedelta(seconds=20)).isoformat())),
                           (point(on_ground=True,latitude=60.5),point(observed_at=(NOW+dt.timedelta(seconds=20)).isoformat())),
                           (point(on_ground=True),point(observed_at=(NOW+dt.timedelta(seconds=301)).isoformat())),
                           (point(on_ground=True),point(latitude=60.5,observed_at=(NOW+dt.timedelta(seconds=20)).isoformat()))):
            self.assertIsNone(run([ground,air])['episodes'][0]['departure_evidence'])

    def test_stale_reports_cannot_create_or_extend_a_flight_candidate_window(self):
        self.assertEqual(run([point(stale=True)])['episodes'][0]['reason'],'only_stale_position_evidence')
        result=run([point(stale=True),point(observed_at=(NOW+dt.timedelta(minutes=10)).isoformat())],
                   [record(scheduled_departure_utc=(NOW-dt.timedelta(minutes=120)).isoformat())])
        self.assertEqual(len(result['episodes']),1)
        self.assertTrue(all(e['state']=='unknown' for e in result['episodes']))

    def test_pure_function_keeps_input_evidence_unchanged(self):
        points=[point()];records=[record()];before=copy.deepcopy((points,records))
        run(points,records);self.assertEqual((points,records),before)

    def fixture(self,root):
        session=root/'session';schedule=root/'schedules';session.mkdir();schedule.mkdir()
        body=json.dumps({'msg':'No error','total':1,'now':NOW.timestamp()*1000,'ac':[{'hex':'abcdef','type':'adsb_icao',
            'lat':60.2,'lon':11.1,'seen_pos':0,'flight':'SAS123','alt_baro':5000}]}).encode()
        (session/'000.json').write_bytes(body)
        manifest={'schema_version':1,'provider':'adsb.fi','url':m.positions.PROVIDERS['adsb.fi']['url'],
            'region':m.positions.REGION,'status':'captured','code_sha256':'test',
            'started_at':NOW.isoformat(),'finished_at':NOW.isoformat(),
            'attribution':m.positions.PROVIDERS['adsb.fi']['attribution'],
            'attempts':[{'index':0,'status':'captured','captured_at':NOW.isoformat(),
                         'http_status':200,'latency_seconds':.2,'bytes':len(body),
                         'sha256':hashlib.sha256(body).hexdigest()}]}
        (session/'manifest.json').write_text(json.dumps(manifest))
        xml=b'<airport name="OSL"><flights><flight uniqueID="1"><flight_id>SK123</flight_id><arr_dep>D</arr_dep><airline>SK</airline><airport>BGO</airport><schedule_time>2026-10-29T08:00:00Z</schedule_time></flight></flights></airport>'
        (schedule/'OSL.xml').write_bytes(xml)
        (schedule/'OSL.json').write_text(json.dumps({'raw_sha256':hashlib.sha256(xml).hexdigest(),
            'fetched_at':'2026-10-29T06:00:00Z','records':[{'incorrect_saved_normalization':True}]}))
        (schedule/'manifest.json').write_text(json.dumps({'status':'captured','requested_airports':['OSL']}))
        return session,schedule

    def test_analysis_reparses_raw_schedules_and_records_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            session,schedule=self.fixture(Path(directory));before={p:p.read_bytes() for p in Path(directory).rglob('*') if p.is_file()}
            result=m.analyze(session,schedule)
            self.assertEqual(result['summary']['states'],{'candidate':1})
            self.assertEqual(result,m.analyze(session,schedule))
            self.assertEqual(before,{p:p.read_bytes() for p in before})
            self.assertEqual(result['provenance']['schedule_raw_sha256'],m.digest(schedule/'OSL.xml'))

    def test_corrupt_position_or_schedule_raw_evidence_is_rejected(self):
        for relative in ('session/000.json','schedules/OSL.xml'):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);session,schedule=self.fixture(root)
                (root/relative).write_bytes(b'corrupted')
                with self.assertRaisesRegex(ValueError,'checksum'):m.analyze(session,schedule)

    def test_incomplete_captures_are_not_matching_evidence(self):
        for relative in ('session/manifest.json','schedules/manifest.json'):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);session,schedule=self.fixture(root);path=root/relative
                manifest=json.loads(path.read_text());manifest['status']='collecting';path.write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):m.analyze(session,schedule)

    def test_schedule_comparison_counts_hypotheses_without_claiming_operation(self):
        frames=[{'captured_at':NOW.isoformat(),'positions':[point()]}]
        result=m.match(frames,[record(),record(source_record_id='unseen',published_flight_number='SK456')],CARRIERS)
        comparison=result['schedule_window_comparison']
        self.assertEqual(comparison['scheduled_departures_in_capture_window'],2)
        self.assertEqual(comparison['with_aircraft_hypothesis'],1)
        self.assertEqual(comparison['without_aircraft_hypothesis'],1)
        self.assertEqual(result['summary']['confirmed_matches'],0)


if __name__=='__main__':unittest.main()
