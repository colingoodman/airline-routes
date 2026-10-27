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
 def test_unicode_redirect_comparison(self):
  self.assertEqual(c.norm('Montr%C3%A9al%E2%80%93Trudeau_International_Airport'),c.norm('Montreal-Trudeau International Airport'))
if __name__=='__main__':unittest.main()
