#!/usr/bin/env python3
"""Inventory worldwide Wikipedia carrier candidates for review, without inventing routes.

The reviewed roster, identity aliases and admission audit remain separate inputs.
This command intentionally never modifies the released dataset or roster.
"""
import argparse,json,re
from pathlib import Path
from bs4 import BeautifulSoup
from collect import fetch,title,table_context
from classify_business_models import current_lowcost_entries,introductory_paragraph,classify,section_ancestry

SOURCES={'passenger':'List_of_passenger_airlines','regional':'List_of_regional_airlines','lowcost':'List_of_low-cost_airlines'}
GEOGRAPHY=re.compile(r'Africa|Asia|America|Europe|Oceania|Pacific|Caribbean|Middle East|Australasia',re.I)
def inventory(html,kind):
 if kind=='lowcost':return current_lowcost_entries(html,title)
 soup=BeautifulSoup(html,'html.parser');rows=[];seen=set()
 for li in soup.find_all('li'):
  context=section_ancestry(li)
  if not context or not any(GEOGRAPHY.search(s) for s in context) or any(re.search(r'defunct|former|reference|see also',s,re.I) for s in context):continue
  if li.find('ul') or li.find_parent('nav') or kind!='regional' and li.find_parent('table'):continue
  links=[a for a in li.find_all('a') if title(a) and ':' not in title(a) and not a.find_parent('sup')]
  if not links:continue
  a=links[0];t=title(a).split('?',1)[0]
  if t in seen:continue
  seen.add(t);rows.append({'wikipedia':t,'name':a.get_text(' ',strip=True),'section':context,'redlink':'new' in a.get('class',[])})
 return rows

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--work',type=Path,default=Path('work/discovery'));ap.add_argument('--kinds',default='passenger,regional,lowcost');ap.add_argument('--articles',action='store_true',help='Also fetch each candidate article serially for hub and model evidence');args=ap.parse_args()
 args.work.mkdir(parents=True,exist_ok=True);cache=args.work/'cache';cache.mkdir(exist_ok=True);out={'sources':[],'candidates':[]}
 for kind in args.kinds.split(','):
  page=fetch(SOURCES[kind],cache)['parse'];url='https://en.wikipedia.org/w/index.php?oldid='+str(page['revid']);out['sources'].append({'kind':kind,'url':url,'revision_id':page['revid']})
  for row in inventory(page['text']['*'],kind):
   row.update(discovery_kind=kind,discovery_source_url=url,status='needs_review')
   if args.articles and not row.get('redlink'):
    try:
     article=fetch(row['wikipedia'],cache)['parse'];source='https://en.wikipedia.org/w/index.php?oldid='+str(article['revid']);soup=BeautifulSoup(article['text']['*'],'html.parser');intro=introductory_paragraph(article['text']['*'])
     row.update(article_source_url=source,operating_model=classify(intro,source,article['revid'],row['name'] if kind=='lowcost' else None,url,page['revid']))
     row['origin_fields']=[]
     for tr in soup.select('table.infobox tr'):
      th=tr.find('th');td=tr.find('td')
      if not th or not td:continue
      label=th.get_text(' ',strip=True)
      if re.search(r'^(?:secondary )?hubs?$|operating bases?|focus cities',label,re.I):row['origin_fields'].append({'field':label,'note':td.get_text(' ',strip=True),'airports':[{'wikipedia':title(a),'label':a.get_text(' ',strip=True)} for a in td.find_all('a') if title(a)]})
      if re.search('ceased|commenced',label,re.I):row.setdefault('operating_dates',{})[label]=td.get_text(' ',strip=True)
    except Exception as e:row.update(status='fetch_failed',error=str(e))
   out['candidates'].append(row)
   (args.work/'candidates.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
  print(kind,len([r for r in out['candidates'] if r['discovery_kind']==kind]),flush=True)
if __name__=='__main__':main()
