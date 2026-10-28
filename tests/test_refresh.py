import copy
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).parents[1]/'scripts'))
import collect
import rebuild

ROOT = Path(__file__).parents[1]
NOW = dt.datetime(2026, 10, 28, 12, tzinfo=dt.timezone.utc)

class Response(io.BytesIO):
    def __init__(self, body, headers=None):
        super().__init__(body)
        self.headers = headers or {}

class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cache = Path(self.temp.name)
        self.path = self.cache/(hashlib.sha256(b'Airport_A').hexdigest()+'.json')
        self.page = {'parse': {'title': 'Airport A', 'revid': 123, 'text': {'*': '<table></table>'}}}
    def tearDown(self):
        self.temp.cleanup()
    def save(self, metadata=None):
        page = copy.deepcopy(self.page)
        if metadata is not None:
            page['_fetch'] = metadata
        self.path.write_text(json.dumps(page))
    def test_legacy_cache_is_unknown_not_retrieved_today(self):
        self.save()
        with patch.object(collect, 'urlopen') as request:
            page = collect.fetch('Airport_A', self.cache, offline=True, now=NOW)
        self.assertEqual(page['_fetch'], {'mode': 'legacy_cache'})
        request.assert_not_called()
    def test_fresh_cache_and_forced_conditional_revalidation(self):
        self.save({'fetched_at': NOW.isoformat(), 'checked_at': NOW.isoformat(), 'etag': 'v1'})
        with patch.object(collect, 'urlopen') as request:
            cached = collect.fetch('Airport_A', self.cache, now=NOW)
        self.assertEqual(cached['_fetch']['mode'], 'cache')
        request.assert_not_called()
        later = NOW+dt.timedelta(days=1)
        error = HTTPError('url', 304, 'Not modified', {}, None)
        with patch.object(collect, 'urlopen', side_effect=error) as request:
            page = collect.fetch('Airport_A', self.cache, refresh=True, delay=0, now=later)
        self.assertEqual(page['_fetch']['fetched_at'], NOW.isoformat())
        self.assertEqual(page['_fetch']['checked_at'], later.isoformat())
        self.assertEqual(page['_fetch']['mode'], 'revalidated')
        self.assertEqual(request.call_args.args[0].get_header('If-none-match'), 'v1')
    def test_expiry_fetches_new_bytes_and_records_real_time(self):
        self.save({'fetched_at': (NOW-dt.timedelta(days=8)).isoformat(), 'checked_at': (NOW-dt.timedelta(days=8)).isoformat()})
        with patch.object(collect, 'urlopen', return_value=Response(b'<html>"wgRevisionId":456</html>', {'ETag':'v2'})):
            page = collect.fetch('Airport_A', self.cache, delay=0, now=NOW)
        self.assertEqual(page['parse']['revid'], 456)
        self.assertEqual(page['_fetch']['fetched_at'], NOW.isoformat())
    def test_block_does_not_cycle_endpoints_or_overwrite_cache(self):
        self.save()
        before = self.path.read_bytes()
        error = HTTPError('url', 403, 'Forbidden', {}, None)
        with patch.object(collect, 'urlopen', side_effect=error) as request:
            with self.assertRaises(HTTPError):
                collect.fetch('Airport_A', self.cache, refresh=True, delay=0, now=NOW)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(before, self.path.read_bytes())
    def test_large_retry_after_and_invalid_response_leave_cache_intact(self):
        self.save()
        before = self.path.read_bytes()
        for error in [HTTPError('url',429,'Limit',{'Retry-After':'300'},None), ValueError('Malformed response')]:
            with patch.object(collect,'urlopen',side_effect=error):
                with self.assertRaises((RuntimeError,ValueError)):
                    collect.fetch('Airport_A',self.cache,refresh=True,delay=0,now=NOW)
        with patch.object(collect,'urlopen',return_value=Response(b'<html>unversioned content</html>')):
            with self.assertRaisesRegex(ValueError,'Cannot pin'):
                collect.fetch('Airport_A',self.cache,refresh=True,delay=0,now=NOW)
        self.assertEqual(before,self.path.read_bytes())
    def test_429_retries_same_endpoint_after_provider_delay(self):
        error=HTTPError('url',429,'Limit',{'Retry-After':'4'},None)
        with patch.object(collect,'urlopen',side_effect=[error,Response(b'<html>"wgRevisionId":456</html>')]) as request, patch.object(collect.time,'sleep') as sleep:
            collect.fetch('Airport_A',self.cache,delay=0,now=NOW)
        self.assertEqual(request.call_count,2)
        self.assertEqual(request.call_args_list[0].args[0].full_url,request.call_args_list[1].args[0].full_url)
        sleep.assert_any_call(4)
    def test_changed_upstream_identifier_cannot_be_hidden_by_override(self):
        with self.assertRaisesRegex(ValueError,'conflicts'):
            collect.apply_metadata_overrides([{'id':'1','iata_code':'NEW'}],{'OLD':{'ourairports_id':'1','iata_code':'REV','previous_iata':'OLD','verified_on':'2020-01-01'}},NOW.date())
    def test_colliding_codes_do_not_select_arbitrary_airport(self):
        rows=[{'id':'1','ident':'A','iata_code':'AAA'},{'id':'2','ident':'B','iata_code':'AAA'}]
        codes,_=collect.airport_indexes(rows,{})
        self.assertNotIn('AAA',codes)
        self.assertEqual(codes['oa:A']['id'],'1')

class CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline=json.loads((ROOT/'web/data.json').read_text())
    def test_retrieval_dates_and_source_order_are_not_network_changes(self):
        changed=copy.deepcopy(self.baseline)
        changed['as_of']='2027-01-01'
        changed['sources'].reverse()
        for source in changed['sources']:
            source['retrieved_on']='2027-01-01'
            source['fetch']={'checked_at':'2027-01-01T00:00:00+00:00'}
        self.assertFalse(rebuild.change_report(self.baseline,changed)['semantic_change'])
    def test_changed_evidence_and_route_removal_are_reviewable(self):
        changed=copy.deepcopy(self.baseline)
        removed=changed['routes'].pop()
        report=rebuild.change_report(self.baseline,changed)
        self.assertEqual(report['collections']['routes']['removed'],[removed['id']])
        self.assertEqual(report['publication'],'review_required')
        self.assertIn('routes changed: review required',report['hold_reasons'])
    def test_output_guard_keeps_canonical_files_intact(self):
        args=rebuild.parser().parse_args(['--candidate',str(ROOT/'web')])
        before=rebuild.digest(ROOT/'web/data.json')
        with self.assertRaisesRegex(ValueError,'outside'):
            rebuild.build(args)
        self.assertEqual(rebuild.digest(ROOT/'web/data.json'),before)
    def test_malformed_download_fails_without_touching_release(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            args=rebuild.parser().parse_args(['--work',str(base/'cache'),'--candidate',str(base/'candidate')])
            before=rebuild.digest(ROOT/'web/data.json')
            with patch.object(rebuild,'urlopen',return_value=Response(b'error HTML')):
                with self.assertRaisesRegex(ValueError,'Invalid or empty'):
                    rebuild.build(args)
            self.assertEqual(json.loads((args.candidate/'manifest.json').read_text())['status'],'failed')
            self.assertEqual(rebuild.digest(ROOT/'web/data.json'),before)

    def test_offline_fixture_runs_real_collector_projection_and_validator(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);inputs=base/'reviewed';work=base/'cache';inputs.mkdir();work.mkdir()
            roster={'airlines':[{'id':'UA','name':'United Airlines','wikipedia':'United_Airlines','alliance':'star','membership_source_url':'https://example.test/membership','hubs':[{'iata':'DEN','wikipedia':'Airport_DEN','kind':'hub','source_revision':12}]}]}
            audit={'summary':{'admitted_carriers':1,'admitted_origins':1,'directory_entries':1},'candidates':[{}],'carrier_admissions':[{'admitted':True}],'origin_admissions':[{'admitted':True}]}
            contents={'roster-hubs.json':roster,'airport-overrides.json':{},'airport-overrides-evidence.json':{},'airport-metadata-overrides.json':{},'airport-additions.json':[],'airline-models.json':{},'discovery-audit.json':audit}
            for name,data in contents.items():(inputs/name).write_text(json.dumps(data))
            header='id,ident,type,iata_code,icao_code,name,latitude_deg,longitude_deg,municipality,iso_country,wikipedia_link\n'
            rows='1,KDEN,large_airport,DEN,KDEN,Denver,39,-104,Denver,US,https://en.wikipedia.org/wiki/Airport_DEN\n2,KMCI,large_airport,MCI,KMCI,Kansas City,39,-94,Kansas City,US,https://en.wikipedia.org/wiki/Airport_MCI\n'
            (work/'ourairports.csv').write_text(header+rows)
            cache=work/'airports-cache';cache.mkdir()
            html='<h2>Airlines and destinations</h2><table><tr><th>Airline</th><th>Destinations</th></tr><tr><td><a href="/wiki/United_Airlines">United Airlines</a></td><td><a href="/wiki/Airport_MCI">Kansas City</a></td></tr></table>'
            (cache/(hashlib.sha256(b'Airport_DEN').hexdigest()+'.json')).write_text(json.dumps({'parse':{'title':'Airport DEN','revid':12,'text':{'*':html}}}))
            args=rebuild.parser().parse_args(['--work',str(work),'--candidate',str(base/'candidate'),'--inputs',str(inputs),'--offline','--structural'])
            before=rebuild.digest(ROOT/'web/data.json')
            try:result=rebuild.build(args)
            except subprocess.CalledProcessError:
                self.fail((base/'candidate/validation.log').read_text())
            self.assertEqual(result['status'],'validated')
            data=json.loads((base/'candidate/data.json').read_text())
            self.assertEqual(data['routes'][0]['destination_airport_id'],'MCI')
            self.assertIsNone(next(s for s in data['sources'] if s['id']=='airports')['retrieved_on'])
            self.assertEqual(data['airports'][0]['ourairports_id'],'1')
            self.assertEqual(rebuild.digest(ROOT/'web/data.json'),before)
            # A missing article must produce a failed candidate, never activate the partial graph.
            next(cache.iterdir()).unlink()
            args.candidate=base/'failed'
            with self.assertRaises(subprocess.CalledProcessError):rebuild.build(args)
            self.assertEqual(json.loads((args.candidate/'manifest.json').read_text())['status'],'failed')
            self.assertEqual(rebuild.digest(ROOT/'web/data.json'),before)

if __name__=='__main__':unittest.main()
