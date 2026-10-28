import datetime as dt
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import schedule_research as schedules
from rebuild import write_json

NOW=dt.datetime(2026,10,28,12,tzinfo=dt.timezone.utc)

def feed(time='2026-10-28T23:30:00Z',destination='BGO',extra='',unique='123',number='SK0042A'):
    return f'<airport name="OSL"><flights><flight uniqueID="{unique}"><airline>SK</airline><flight_id>{number}</flight_id><arr_dep>D</arr_dep><schedule_time>{time}</schedule_time><airport>{destination}</airport>{extra}</flight></flights></airport>'.encode()

class ScheduleTests(unittest.TestCase):
    def parse(self,body):return schedules.parse_feed(body,'OSL',NOW,{'OSL','BGO'})
    def test_numbers_and_local_date_preserve_source_meaning(self):
        row=self.parse(feed())['records'][0]
        self.assertEqual(row['published_flight_number'],'SK0042A')
        self.assertEqual(row['departure_local_date'],'2026-10-29')
        self.assertIsNone(row['scheduled_arrival_utc'])
        self.assertIsNone(row['nonstop'])
    def test_dst_fallback_preserves_two_distinct_utc_times(self):
        first=self.parse(feed(time='2026-10-25T00:30:00Z'))['records'][0]
        second=self.parse(feed(time='2026-10-25T01:30:00Z'))['records'][0]
        self.assertNotEqual(first['scheduled_departure_utc'],second['scheduled_departure_utc'])
        self.assertEqual(first['departure_local_date'],second['departure_local_date'])
    def test_codeshares_and_cancellation_remain_separate_from_primary(self):
        body=feed(extra='<codeshareAirlineDesignators>LH,UA</codeshareAirlineDesignators><codeshareFlightNumbers>0042,9999</codeshareFlightNumbers><status code="C"/>')
        row=self.parse(body)['records'][0]
        self.assertEqual(row['codeshares'][0]['flight_number'],'0042')
        self.assertEqual(row['status_as_reported']['code'],'C')
        self.assertEqual(row['published_flight_number'],'SK0042A')
    def test_misaligned_codeshare_fields_are_not_paired_by_guess(self):
        result=self.parse(feed(extra='<codeshareAirlineDesignators>LH,UA</codeshareAirlineDesignators><codeshareFlightNumbers>0042</codeshareFlightNumbers>'))
        self.assertEqual(result['records'][0]['codeshares'],[])
        self.assertEqual(result['issues'][0]['kind'],'unresolved_codeshare_fields')
    def test_circular_service_is_preserved_without_inventing_a_leg(self):
        result=self.parse(feed(destination='OSL',extra='<via_airport>SDN,SOG</via_airport>'))
        self.assertTrue(result['records'][0]['circular_service'])
        self.assertIsNone(result['records'][0]['destination_airport_id'])
        self.assertEqual(result['issues'][0]['kind'],'circular_service_requires_leg_resolution')

    def test_missing_airport_is_reported_without_inventing_map_identity(self):
        result=self.parse(feed(destination='ZZZ',extra='<via_airport>TRD</via_airport>'))
        self.assertIsNone(result['records'][0]['destination_airport_id'])
        self.assertEqual(result['records'][0]['via_airports'],['TRD'])
        self.assertEqual(result['issues'][0]['kind'],'airport_missing_from_map')
    def test_naive_timestamp_wrong_feed_and_entities_are_rejected(self):
        result=self.parse(feed(time='2026-10-28T23:30:00'))
        self.assertEqual(result['records'],[])
        self.assertEqual(result['issues'][0]['kind'],'invalid_record')
        for body in [b'<html/>',feed().replace(b'name="OSL"',b'name="BNN"'),b'<!DOCTYPE x><airport name="OSL"><flights/></airport>']:
            with self.assertRaises(ValueError):self.parse(body)
    def test_comparison_distinguishes_time_status_changes_and_disappearance(self):
        previous=self.parse(feed())
        current=self.parse(feed(time='2026-10-28T23:45:00Z',extra='<status code="C"/>'))
        comparison=schedules.compare_samples([previous],[current])
        self.assertEqual(comparison['changed'][0]['fields'],['scheduled_departure_utc','status_as_reported'])
        removed=schedules.compare_samples([previous],[])
        self.assertEqual(len(removed['removed']),1)
        self.assertIn('not automatically',removed['note'])

    def test_throttle_and_daily_quota_stop_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            args=schedules.parser().parse_args(['--work',str(root),'--airports','OSL'])
            now=dt.datetime.now(dt.timezone.utc)
            write_json(root/'request-ledger.json',{'day':now.date().isoformat(),'requests':24})
            with patch.object(schedules,'urlopen') as request:
                with self.assertRaisesRegex(RuntimeError,'budget exhausted'):schedules.capture(args)
            request.assert_not_called()
            write_json(root/'request-ledger.json',{'day':now.date().isoformat(),'requests':0,'last_attempts':{'OSL':now.isoformat()}})
            with patch.object(schedules,'urlopen') as request:
                with self.assertRaisesRegex(RuntimeError,'three minutes'):schedules.capture(args)
            request.assert_not_called()
    def test_capture_counts_requests_and_does_not_claim_seven_days_observed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            args=schedules.parser().parse_args(['--work',str(root),'--airports','OSL'])
            with patch.object(schedules,'urlopen',return_value=io.BytesIO(feed())):
                report=schedules.capture(args)
            self.assertEqual(report['observation_days'],1)
            self.assertEqual(report['observation_gate'],'pending')
            self.assertEqual(json.loads((root/'request-ledger.json').read_text())['requests'],1)
            manifest=json.loads((Path(report['capture'])/'manifest.json').read_text())
            self.assertEqual(manifest['status'],'captured')
            args.replay=Path(report['capture'])
            with patch.object(schedules,'urlopen') as request:
                replay=schedules.replay(args)
            request.assert_not_called()
            self.assertEqual(replay['observation_days'],1)
            self.assertEqual(json.loads((Path(replay['replay'])/'OSL.json').read_text())['fetched_at'],json.loads((args.replay/'OSL.json').read_text())['fetched_at'])

if __name__=='__main__':unittest.main()
