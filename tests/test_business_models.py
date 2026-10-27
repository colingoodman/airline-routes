import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from classify_business_models import classify,explicit_intro_flags,current_lowcost_entries
class BusinessModelTests(unittest.TestCase):
 def test_missing_list_entry_is_unknown(self):
  self.assertIsNone(classify('Air X is the national flag carrier of Country.','source',1)['low_cost'])
 def test_ownership_does_not_classify_parent(self):
  self.assertEqual(explicit_intro_flags('Air X is the second-largest shareholder of the low-cost carrier Budget Y.'),[])
  self.assertEqual(explicit_intro_flags('Air X is a subsidiary of a low-cost carrier based in Country.'),[])
 def test_later_ownership_sentence_does_not_classify_parent(self):
  self.assertEqual(explicit_intro_flags('Air X is the flag carrier airline of Country. It is a shareholder of the low-cost airline Budget Y.'),[])
 def test_explicit_lowcost_and_regional_can_coexist(self):
  flags=explicit_intro_flags('Fly X is a low-cost regional airline based in Country.')
  self.assertEqual([(x['flag'],x['value']) for x in flags],[('low_cost',True),('regional',True)])
 def test_explicit_fullservice_is_false_but_conflict_is_unknown(self):
  self.assertIs(classify('Air X is a full-service airline based in Country.','source',1)['low_cost'],False)
  self.assertIsNone(classify('Air X is a full-service airline based in Country.','source',1,'Air X','list',2)['low_cost'])
 def test_current_inventory_excludes_defunct_and_captions(self):
  html='<h2>Africa</h2><figure><figcaption><a href="/wiki/Dead_Air">Dead Air</a> ceased operations</figcaption></figure><ul><li><a href="/wiki/Current_Air">Current Air</a></li></ul><h2>Defunct low-cost carriers</h2><h3>Africa</h3><ul><li><a href="/wiki/Old_Air">Old Air</a></li></ul>'
  rows=current_lowcost_entries(html,lambda a:a.get('href','').split('/wiki/')[-1] if '/wiki/' in a.get('href','') else None)
  self.assertEqual([x['wikipedia'] for x in rows],['Current_Air'])
if __name__=='__main__':unittest.main()
