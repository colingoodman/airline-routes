import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import position_research as p
import summarize_positions as s


class PositionSummaryTests(unittest.TestCase):
    def fixture(self,root):
        session=root/'session';session.mkdir();now=dt.datetime(2026,10,29,8,tzinfo=dt.timezone.utc)
        body=json.dumps({'msg':'No error','total':1,'now':now.timestamp()*1000,
            'ac':[{'hex':'abcdef','type':'adsb_icao','lat':60.2,'lon':11.1,
                   'seen_pos':0,'flight':'SAS123','alt_baro':5000}]}).encode()
        (session/'000.json').write_bytes(body)
        manifest={'schema_version':1,'provider':'adsb.fi','url':p.PROVIDERS['adsb.fi']['url'],
            'region':p.REGION,'status':'captured','code_sha256':'test',
            'started_at':now.isoformat(),'finished_at':now.isoformat(),
            'requested_samples':1,'requested_interval_seconds':20,
            'attempts':[{'index':0,'status':'captured','captured_at':now.isoformat(),
                         'requested_at':now.isoformat(),'http_status':200,'latency_seconds':.2,
                         'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}]}
        (session/'manifest.json').write_text(json.dumps(manifest))
        (session/'report.json').write_text(json.dumps(p.replay(session)))
        return session

    def test_aggregate_has_no_aircraft_rows_and_is_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            session=self.fixture(Path(directory));summary=s.summarize(session)
            self.assertEqual(summary,s.summarize(session))
            encoded=json.dumps(summary)
            self.assertNotIn('abcdef',encoded);self.assertNotIn('SAS123',encoded)
            self.assertEqual(summary['results']['unique_positioned_aircraft'],1)
            self.assertEqual(summary['consecutive_30_response_blocks'][0]['last_sample'],1)

    def test_semantic_change_requires_investigation(self):
        with tempfile.TemporaryDirectory() as directory:
            session=self.fixture(Path(directory));report=json.loads((session/'report.json').read_text())
            report['accepted_position_reports']=999
            (session/'report.json').write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError,'changed original metrics'):s.summarize(session)

    def test_original_analyzer_hash_can_differ_but_capture_provenance_is_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            session=self.fixture(Path(directory));report=json.loads((session/'report.json').read_text())
            report['analysis_code_sha256']='previous_analyzer';(session/'report.json').write_text(json.dumps(report))
            self.assertEqual(s.summarize(session)['results']['capture_code_sha256'],'test')


if __name__=='__main__':unittest.main()
