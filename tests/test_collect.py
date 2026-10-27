import importlib.util, unittest
from pathlib import Path
from bs4 import BeautifulSoup
spec=importlib.util.spec_from_file_location('collect',Path(__file__).parents[1]/'scripts/collect.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
class ParsingTests(unittest.TestCase):
 def test_seasonal_group_and_future_note_stay_on_correct_destination(self):
  cell=BeautifulSoup('<td><a href="/wiki/Airport_A">A</a>, <a href="/wiki/Airport_B">B</a> (begins November 1, 2026)<sup class="reference">[1]</sup><br><b>Seasonal:</b> <a href="./Airport_C">C</a></td>','html.parser').td
  rows=c.route_items(cell)
  self.assertEqual([r['destination_title'] for r in rows],['Airport_A','Airport_B','Airport_C'])
  self.assertEqual([r['seasonal'] for r in rows],[False,False,True]);self.assertIn('begins',rows[1]['note']);self.assertNotIn('begins',rows[0]['note']);self.assertNotIn('[1]',rows[1]['note'])
 def test_via_link_is_annotation_not_a_second_destination(self):
  cell=BeautifulSoup('<td><a href="/wiki/Airport_A">A</a> (via <a href="/wiki/Airport_B">B</a>), <a href="/wiki/Airport_C">C</a></td>','html.parser').td
  rows=c.route_items(cell);self.assertEqual([r['destination_title'] for r in rows],['Airport_A','Airport_C']);self.assertIn('B',rows[0]['note'])
 def test_suspended_until_future_is_excluded(self):
  self.assertEqual(c.route_status('(suspended until May 2, 2027)')[0],'suspended_or_ended')
  self.assertEqual(c.route_status('(ends May 2, 2027)')[0],'listed')
  self.assertEqual(c.route_status('(begins May 2, 2027)')[0],'announced')
  self.assertEqual(c.route_status('(resumes seasonally)')[0],'announced')
 def test_history_parent_excludes_table_even_with_neutral_subheading(self):
  s=BeautifulSoup('<h2>History</h2><h3>International era</h3><h4>International service before 1994</h4><table id="past"></table><h2>Airlines and destinations</h2><h3>Passenger</h3><table id="now"></table><h3>Cargo</h3><table id="cargo"></table>','html.parser')
  self.assertFalse(c.passenger_table(s.select_one('#past')));self.assertTrue(c.passenger_table(s.select_one('#now')));self.assertFalse(c.passenger_table(s.select_one('#cargo')))
 def test_dates_support_both_wikipedia_orders(self):
  self.assertEqual(c.date_in('begins November 1, 2026'),'2026-11-01');self.assertEqual(c.date_in('ends 27 October 2026'),'2026-10-27');self.assertEqual(c.date_in('resumes seasonally'),None)
 def test_code_migration_preserves_the_physical_airport_and_effective_date(self):
  import datetime
  rows=[{'id':'3180','iata_code':'HBE','latitude_deg':'30.93'},{'id':'3179','iata_code':'ALY','type':'closed','latitude_deg':'31.18'}]
  entries={'HBE':{'ourairports_id':'3180','iata_code':'ALY','effective_on':'2026-09-16','previous_iata':'HBE'}}
  before=c.apply_metadata_overrides(rows,entries,datetime.date(2026,9,15));self.assertEqual(before[0]['iata_code'],'HBE')
  after=c.apply_metadata_overrides(rows,entries,datetime.date(2026,10,27));self.assertEqual(after[0]['iata_code'],'ALY');self.assertEqual(after[0]['latitude_deg'],'30.93');self.assertEqual(after[0]['_former_iata_code'],'HBE');self.assertEqual(after[1],rows[1]);self.assertEqual(rows[0]['iata_code'],'HBE')
 def test_missing_airport_code_enrichment_does_not_invent_a_former_iata(self):
  import datetime
  rows=[{'id':'26518','iata_code':'','icao_code':'VEPU','latitude_deg':'25.75'}]
  entries={'VEPU':{'ourairports_id':'26518','iata_code':'PXN','verified_on':'2026-10-27'}}
  result=c.apply_metadata_overrides(rows,entries,datetime.date(2026,10,27))[0];self.assertEqual(result['iata_code'],'PXN');self.assertNotIn('_former_iata_code',result);self.assertEqual(result['latitude_deg'],'25.75');self.assertEqual(result['icao_code'],'VEPU')
 def test_unicode_redirect_comparison(self):
  self.assertEqual(c.norm('Montr%C3%A9al%E2%80%93Trudeau_International_Airport'),c.norm('Montreal-Trudeau International Airport'))
 def test_primary_brand_only_does_not_claim_incidental_operator_network(self):
  cell=BeautifulSoup('<td><span class="flagicon"><a href="/wiki/United_States">US</a></span><a href="/wiki/American_Eagle">American Eagle</a> operated by <a href="/wiki/Envoy_Air">Envoy</a></td>','html.parser').td
  self.assertTrue(c.airline_row_matches(cell,{c.norm('American Eagle')}));self.assertFalse(c.airline_row_matches(cell,{c.norm('Envoy Air')}))
 def test_charter_section_context_is_applied_to_each_destination(self):
  soup=BeautifulSoup('<h2>Airlines and destinations</h2><h3>Seasonal charter</h3><table><td><a href="/wiki/Airport_A">A</a></td></table>','html.parser')
  self.assertTrue(c.passenger_table(soup.table));self.assertIn('Seasonal charter',c.table_context(soup.table))
  row=c.route_items(soup.td,True,'charter')[0];self.assertTrue(row['seasonal']);self.assertEqual(row['service_type'],'charter')
  nested=BeautifulSoup('<td><b>Seasonal:</b><a href="/wiki/A">A</a><b>Charter:</b><a href="/wiki/B">B</a></td>','html.parser').td
  self.assertTrue(all(r['seasonal'] and r['service_type']=='charter' for r in c.route_items(nested,True,'charter')))
 def test_uncoded_airport_has_namespaced_identity(self):
  row={'id':'1','ident':'TEST1','type':'small_airport','iata_code':'','icao_code':'','wikipedia_link':'https://en.wikipedia.org/wiki/Airport_A'}
  self.assertEqual(c.airport_identifier(row),'oa:TEST1');codes,titles=c.airport_indexes([row],{});self.assertEqual(titles[c.norm('Airport A')],row)
  row['icao_code']='ABCD';self.assertEqual(c.airport_identifier(row),'icao:ABCD')
 def test_external_metadata_url_is_never_a_wikipedia_title(self):
  self.assertIsNone(c.wikipedia_title('https://example.com/wiki/Fake'));self.assertEqual(c.wikipedia_title('https://en.wikipedia.org/wiki/Airport_A'),'Airport_A')
 def test_closed_status_is_not_inferred_from_history(self):
  self.assertIsNone(c.airport_unavailable(BeautifulSoup('<p>Opened after the old airport closed in 2013.</p>','html.parser')))
  self.assertIsNotNone(c.airport_unavailable(BeautifulSoup('<table class="infobox"><tr><th>Closed</th><td>2013</td></tr></table>','html.parser')))
if __name__=='__main__':unittest.main()
