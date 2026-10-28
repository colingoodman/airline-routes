import contextlib
import datetime as dt
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_positions import NOW, body
import position_research as p
from rebuild import write_json


class Clock:
    def __init__(self):self.seconds=0
    def now(self):return NOW+dt.timedelta(seconds=self.seconds)
    def monotonic(self):return self.seconds
    def sleep(self,seconds):self.seconds+=seconds


class ProviderTests(unittest.TestCase):
    def args(self,root,samples=1,provider='adsb.fi'):
        return SimpleNamespace(work=root,samples=samples,interval=20,provider=provider)

    def test_full_hour_fi_capture_without_quota_headers_replays_with_correct_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);clock=Clock()
            write_json(root/'access/probe/manifest.json',{'url':p.PROVIDERS['adsb.fi']['url'],'started_at':(NOW-dt.timedelta(minutes=1)).isoformat()})
            write_json(root/'access/other/manifest.json',{'url':p.URL,'started_at':NOW.isoformat()})
            def fetch(url):
                self.assertEqual(url,p.PROVIDERS['adsb.fi']['url'])
                return body(now=clock.now()),{},200
            with patch.object(p,'utcnow',side_effect=clock.now),patch.object(p.time,'monotonic',side_effect=clock.monotonic),patch.object(p.time,'sleep',side_effect=clock.sleep),patch.object(p,'fetch',side_effect=fetch) as network,contextlib.redirect_stdout(io.StringIO()):
                result=p.capture(self.args(root,samples=180))
            manifest=json.loads((Path(result['session'])/'manifest.json').read_text())
            self.assertEqual(manifest['provider'],'adsb.fi')
            self.assertEqual(manifest['attribution']['text'],'adsb.fi')
            self.assertIsNone(manifest['attribution']['license'])
            self.assertEqual(manifest['max_session_seconds'],3900)
            self.assertEqual(network.call_count,180)
            self.assertEqual(result['report']['sample_seconds'],3580)
            self.assertEqual(result['report']['provider'],'adsb.fi')
            self.assertEqual(json.loads((root/'request-ledger.json').read_text())['days'][NOW.date().isoformat()],181)
            with patch.object(p,'fetch',side_effect=AssertionError('Offline replay attempted network IO')):
                self.assertEqual(p.replay(Path(result['session']),root/'replays/checked'),result['report'])
            exported=json.loads((root/'replays/checked/positions.json').read_text())
            self.assertEqual(exported['provider'],'adsb.fi')
            self.assertEqual(exported['attribution']['text'],'adsb.fi')

    def test_provider_ledgers_cannot_be_reused_across_feeds(self):
        for ledger,provider in [({'days':{}},'adsb.fi'),({'days':{},'provider':'adsb.fi'},'adsb.lol')]:
            with self.subTest(provider=provider),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);write_json(root/'request-ledger.json',ledger)
                with patch.object(p,'fetch') as fetch:
                    with self.assertRaisesRegex(ValueError,'another provider'):p.capture(self.args(root,provider=provider))
                    fetch.assert_not_called()

    def test_fi_documented_policy_is_separate_from_lol_and_honors_stricter_headers(self):
        self.assertEqual(p.provider_policy({},'adsb.fi'),(360,20))
        self.assertEqual(p.provider_policy({'rate_limit':'100;w=86400'},'adsb.fi'),(80,20))
        self.assertEqual(p.provider_policy({'rate_limit':'1;w=60'},'adsb.fi'),(360,60))
        with self.assertRaisesRegex(ValueError,'daily allowance'):p.provider_policy({'rate_limit':None},'adsb.lol')
        with self.assertRaisesRegex(ValueError,'unrecognized'):p.provider_policy({'rate_limit':'unknown'},'adsb.fi')

    def test_missing_header_does_not_erase_a_previously_observed_stricter_fi_rate(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);clock=Clock();responses=iter([{'x-ratelimit-limit':'1;w=60'},{}])
            def fetch(_):return body(now=clock.now()),next(responses),200
            with patch.object(p,'utcnow',side_effect=clock.now),patch.object(p.time,'monotonic',side_effect=clock.monotonic),patch.object(p.time,'sleep',side_effect=clock.sleep),patch.object(p,'fetch',side_effect=fetch),contextlib.redirect_stdout(io.StringIO()):
                result=p.capture(self.args(root,samples=2))
            self.assertEqual(result['report']['sample_seconds'],60)
            self.assertEqual(json.loads((root/'request-ledger.json').read_text())['rate_limit'],'1;w=60')

    def test_invalid_policy_response_preserves_the_last_known_allowance(self):
        for provider,headers in [('adsb.lol',{}),('adsb.fi',{'x-ratelimit-limit':'unknown'})]:
            with self.subTest(provider=provider),tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                known='500;w=86400'
                write_json(root/'request-ledger.json',{'days':{},'provider':provider,'url':p.PROVIDERS[provider]['url'],'rate_limit':known})
                with patch.object(p,'utcnow',return_value=NOW),patch.object(p,'fetch',return_value=(body(),headers,200)):
                    with self.assertRaises(ValueError):p.capture(self.args(root,provider=provider))
                saved=json.loads((root/'request-ledger.json').read_text())
                self.assertEqual(saved['rate_limit'],known)
                self.assertEqual(saved['halted_day'],NOW.date().isoformat())

    def test_extended_count_does_not_extend_lol_and_long_fi_runtime_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for args in [self.args(root,180,'adsb.lol'),self.args(root,181),SimpleNamespace(work=root,provider='adsb.fi',samples=180,interval=120)]:
                with patch.object(p,'fetch') as fetch:
                    with self.assertRaises(ValueError):p.capture(args)
                    fetch.assert_not_called()

    def test_replay_rejects_provider_url_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            write_json(root/'manifest.json',{'schema_version':1,'provider':'adsb.fi','url':p.URL,'region':p.REGION})
            with self.assertRaisesRegex(ValueError,'identity'):p.replay(root)


if __name__=='__main__':unittest.main()
