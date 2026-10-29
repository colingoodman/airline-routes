import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import callsign_inventory as c
import test_position_summary as fixtures


class CallsignInventoryTests(unittest.TestCase):
    def test_mixed_operational_and_registration_shapes_are_not_all_airline_flights(self):
        carriers={'ABC':{}}
        for value,registrations,expected in [
            ('ABC12X',[],'reviewed_carrier_alphanumeric'),
            ('ABC3YZ',[],'reviewed_carrier_alphanumeric'),
            ('XYZ12X',[],'unreviewed_company_shaped'),
            ('LNABC',['LN-ABC'],'matches_reported_registration'),
            ('DOC',[],'other_format'),
            ('ABC123',[],'numeric_company_format'),
            (None,[],'missing_callsign')]:
            with self.subTest(value=value):self.assertEqual(c.classify(value,registrations,carriers),expected)

    def test_unsupported_inventory_is_repeatable_read_only_and_does_not_decode(self):
        with tempfile.TemporaryDirectory() as directory:
            session=fixtures.PositionSummaryTests().fixture(Path(directory))
            body=json.loads((session/'000.json').read_text());body['ac'][0]['flight']='NOZ1AB'
            encoded=json.dumps(body).encode();(session/'000.json').write_bytes(encoded)
            manifest=json.loads((session/'manifest.json').read_text());manifest['attempts'][0]['sha256']=hashlib.sha256(encoded).hexdigest()
            (session/'manifest.json').write_text(json.dumps(manifest))
            before={p:p.read_bytes() for p in session.iterdir()}
            result=c.inventory(session)
            self.assertEqual(result,c.inventory(session))
            self.assertEqual(result['categories'],{'reviewed_carrier_alphanumeric':1})
            self.assertEqual(result['decoded_flight_numbers'],0)
            self.assertEqual(before,{p:p.read_bytes() for p in before})
            self.assertNotIn('NOZ1AB',json.dumps(result))

    def test_corrupt_raw_and_incomplete_capture_fail_before_classification(self):
        for corrupt in (True,False):
            with tempfile.TemporaryDirectory() as directory:
                session=fixtures.PositionSummaryTests().fixture(Path(directory))
                if corrupt:(session/'000.json').write_bytes(b'bad evidence')
                else:
                    path=session/'manifest.json';manifest=json.loads(path.read_text());manifest['status']='collecting';path.write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):c.inventory(session)


if __name__=='__main__':unittest.main()
