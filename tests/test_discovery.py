import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from discover import inventory
class DiscoveryTests(unittest.TestCase):
 def test_regional_table_bullets_are_current_but_defunct_section_is_not(self):
  html='<h2>Africa</h2><table><tr><td><ul><li><a href="/wiki/Current_Air">Current Air</a></li></ul></td></tr></table><h2>Defunct regional airlines</h2><h3>Africa</h3><ul><li><a href="/wiki/Old_Air">Old Air</a></li></ul>'
  self.assertEqual([r['wikipedia'] for r in inventory(html,'regional')],['Current_Air'])
 def test_spaced_airline_identity_is_not_collapsed_and_redlink_query_is_removed(self):
  html='<h2>Africa</h2><ul><li><a href="/wiki/Airlink">Airlink</a></li><li><a href="/wiki/Air_Link">Air Link</a></li><li><a class="new" href="/wiki/New_Air?action=edit&amp;redlink=1">New Air</a></li></ul>'
  rows=inventory(html,'passenger');self.assertEqual([r['wikipedia'] for r in rows],['Airlink','Air_Link','New_Air']);self.assertTrue(rows[-1]['redlink'])
if __name__=='__main__':unittest.main()
