#!/usr/bin/env python3
"""Rebuild the source-evidenced alliance/hub route snapshot. See README for scope."""
import argparse, csv, datetime as dt, hashlib, json, re, time, unicodedata, os
from pathlib import Path
from urllib.parse import quote, unquote, urlencode
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup, NavigableString, Tag
from urllib.error import HTTPError

TODAY=dt.date(2026,10,27)
USER_AGENT='AllianceRouteMap/1.0 (personal educational research)'
BRANDS={
 'UA':['United Airlines','United Express'], 'AA':['American Airlines','American Eagle'],
 'DL':['Delta Air Lines','Delta Connection'], 'AC':['Air Canada','Air Canada Express','Air Canada Rouge'],
 'BA':['British Airways','BA Cityflyer','BA Euroflyer','British Airways CityFlyer','British Airways Euroflyer'],
 'IB':['Iberia','Iberia Express','Iberia Regional','Air Nostrum'],
 'FJ':['Fiji Airways','Fiji Link'], 'QF':['Qantas','QantasLink'], 'AY':['Finnair','Nordic Regional Airlines'],
 'LH':['Lufthansa','Lufthansa CityLine','Lufthansa City Airlines','Lufthansa Regional'],
 'AF':['Air France','Air France Hop','Air France HOP'], 'KL':['KLM','KLM Cityhopper'],
 'SQ':['Singapore Airlines'], 'AS':['Alaska Airlines','Alaska Horizon','Alaska SkyWest'],
 'NZ':['Air New Zealand','Air New Zealand Link'], 'SK':['Scandinavian Airlines','SAS','SAS Connect','SAS Link'],
 'NH':['All Nippon Airways','ANA Wings'], 'JL':['Japan Airlines','J-Air','Japan Air Commuter','Japan Transocean Air','Hokkaido Air System','Ryukyu Air Commuter'],
 'TP':['TAP Air Portugal','TAP Express'], 'A3':['Aegean Airlines','Olympic Air'],
 'AV':['Avianca','Avianca El Salvador','Avianca Costa Rica','Avianca Ecuador','Avianca Express'],
 'AI':['Air India'], 'SV':['Saudia'], 'MU':['China Eastern Airlines','Shanghai Airlines'],
 'CA':['Air China','Air China Inner Mongolia'], 'VN':['Vietnam Airlines','VASCO'],
 'AR':['Aerolíneas Argentinas','Aerolineas Argentinas'], 'AM':['Aeroméxico','Aeromexico','Aeroméxico Connect','Aeromexico Connect'],
 'MH':['Malaysia Airlines','MASwings','Firefly'], 'RO':['TAROM'], 'HA':['Hawaiian Airlines'],
}
def norm(s):
 s=unquote(s).replace('_',' ').split('#')[0]
 return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower())
def title(a):
 h=a.get('href','')
 return unquote(h.split('/wiki/',1)[1]).split('#')[0] if '/wiki/' in h else unquote(h[2:]).split('#')[0] if h.startswith('./') else None

def fetch(title_, cache, delay=0.8):
 title_=unquote(title_)
 p=cache/(hashlib.sha256(title_.encode()).hexdigest()+'.json')
 if p.exists(): return json.loads(p.read_text())
 if os.environ.get('ROUTE_CACHE_ONLY'): raise ValueError('Not cached yet')
 url='https://en.wikipedia.org/w/api.php?'+urlencode({'action':'parse','page':title_.replace('_',' '),'prop':'text|revid','format':'json'})
 urls=['https://en.wikipedia.org/wiki/'+quote(title_.replace(' ','_'),safe='')+'?useskin=vector',url+'&redirects=1','https://en.wikipedia.org/api/rest_v1/page/html/'+quote(title_.replace(' ','_'),safe='')]
 for n in range(6):
  try:
   time.sleep(delay)
   selected=urls[n%len(urls)]
   raw=urlopen(Request(selected,headers={'User-Agent':'Mozilla/5.0'}),timeout=70).read().decode()
   if raw.lstrip().startswith('{'):
    data=json.loads(raw)
   else:
    rev=re.search(r'(?:revision/|oldid=)([0-9]+)',raw)
    if not rev:
     rev=re.search(r'"wgRevisionId":([0-9]+)',raw)
    if not rev: raise ValueError('Cannot pin source revision')
    data={'parse':{'title':title_.replace('_',' '),'revid':int(rev[1]),'text':{'*':raw}}}
   if 'error' in data: raise ValueError(data['error'])
   p.write_text(json.dumps(data)); return data
  except Exception as e:
   print('retry',title_,n,str(e),flush=True)
   if n==5: raise
   time.sleep(1 if n<3 else 4)

def date_in(text):
 text=re.sub(r'(\d)(?:st|nd|rd|th)\b',r'\1',text)
 for fmt,pat in [('%B %d, %Y',r'[A-Z][a-z]+ \d{1,2}, \d{4}'),('%d %B %Y',r'\d{1,2} [A-Z][a-z]+ \d{4}'),('%B %Y',r'[A-Z][a-z]+ \d{4}')]:
  m=re.search(pat,text)
  if m:
   try: return dt.datetime.strptime(m[0],fmt).date().isoformat()
   except ValueError: pass
 return None

def route_items(cell):
 """Keep the text after each destination link attached to it, including date notes."""
 for x in cell.select('sup.reference'): x.decompose()
 items=[]; current=None; seasonal=False; group='scheduled'; prefix=''
 for x in cell.descendants:
  if isinstance(x,Tag) and x.name in ('b','strong'):
   label=x.get_text(' ',strip=True).lower()
   if 'seasonal' in label: seasonal=True;group='charter' if 'charter' in label else 'scheduled'
   elif 'charter' in label: seasonal=False;group='charter'
   elif label.rstrip(':') in ('scheduled','regular'): seasonal=False;group='scheduled'
  if isinstance(x,Tag) and x.name=='a' and title(x):
   # Navigation links in annotations are not separate airports.
   if x.find_parent(['sup','small']) or (current and current['note'].count('(')>current['note'].count(')')):
    if current: current['note']+=' '+x.get_text(' ',strip=True)
    continue
   t=title(x)
   if ':' in t and not t.startswith('Airport'): continue
   current={'destination_title':t,'label':x.get_text(' ',strip=True),'note':'','seasonal':seasonal,'service_type':group,'struck':bool(x.find_parent(['s','del','strike']))}
   items.append(current)
  elif isinstance(x,NavigableString):
   if x.find_parent('a') or x.find_parent(['b','strong']): continue
   if current: current['note']+=str(x)
 return items

def passenger_table(table):
 # Walk active section ancestry, not just the nearest subheading. A history
 # section can contain a perfectly ordinary-looking destination table.
 context=[];level=7
 for heading in table.find_all_previous(['h2','h3','h4','h5','h6']):
  n=int(heading.name[1])
  if n<level:context.append(heading.get_text(' ',strip=True));level=n
  if n==2:break
 caption=table.find('caption')
 if caption:context.append(caption.get_text(' ',strip=True))
 return not re.search(r'cargo|former|histor|before \d{4}|discontinued', ' '.join(context), re.I)

def route_status(note, seasonal=False, struck=False):
 status='suspended_or_ended' if struck else 'seasonal' if seasonal else 'listed'
 change_date=date_in(note)
 if re.search(r'\b(begin|start|commenc|resum)',note,re.I):
  if not change_date or change_date>TODAY.isoformat():status='announced'
 if re.search(r'\b(suspended|ceased|terminated|discontinued)\b',note,re.I):
  status='suspended_or_ended'
 elif re.search(r'\b(end|ceas|terminat|suspend|discontinu)',note,re.I):
  if not change_date or change_date<=TODAY.isoformat():status='suspended_or_ended'
 return status,change_date

def apply_metadata_overrides(rows,corrections,as_of):
 result=[]
 for row in rows:
  r=dict(row)
  for old,entry in corrections.items():
   if str(row.get('id'))==str(entry['ourairports_id']) and entry.get('effective_on',entry.get('verified_on','9999-12-31'))<=as_of.isoformat():
    r.update({k:entry[k] for k in ['iata_code','icao_code','name','wikipedia_link'] if k in entry})
    previous=entry.get('previous_iata') or row.get('iata_code','')
    if previous and previous!=r['iata_code']:r['_former_iata_code']=previous
    r['_original_wikipedia_link']=row.get('wikipedia_link','');r['_metadata_override']=entry
  result.append(r)
 return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--work',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--as-of',default='2026-10-27');args=ap.parse_args()
 global TODAY
 TODAY=dt.date.fromisoformat(args.as_of)
 w=args.work;cache=w/'airports-cache';cache.mkdir(exist_ok=True)
 roster=json.loads((w/'roster-hubs.json').read_text()); airlines=roster['airlines']
 rows=list(csv.DictReader((w/'ourairports.csv').open()))
 corrections_path=Path(__file__).with_name('airport-metadata-overrides.json')
 corrections=json.loads(corrections_path.read_text()) if corrections_path.exists() else {}
 rows=apply_metadata_overrides(rows,corrections,TODAY)
 bycode={r['iata_code']:r for r in rows if r['iata_code'] and r['type']!='closed'}
 for r in rows:
  if r.get('_former_iata_code'):bycode[r['_former_iata_code']]=r
 bytitle={norm(r['wikipedia_link'].split('/wiki/')[-1]):r for r in rows if r['wikipedia_link'] and r['iata_code'] and r['type']!='closed'}
 for r in rows:
  if r.get('_original_wikipedia_link'):bytitle[norm(r['_original_wikipedia_link'].split('/wiki/')[-1])]=r
 overrides=json.loads((w/'airport-overrides.json').read_text()) if (w/'airport-overrides.json').exists() else {}
 for t,code in overrides.items():
  if code in bycode: bytitle[norm(t)]=bycode[code]
 sources=[];source_index={}
 def source(url,kind,**kw):
  if url in source_index: return source_index[url]
  id_='s'+str(len(sources)+1);sources.append({'id':id_,'url':url,'kind':kind,'retrieved_on':TODAY.isoformat(),**kw});source_index[url]=id_;return id_
 airports={}
 def airport(r):
  code=r['iata_code']
  if code not in airports:
   airports[code]={'id':code,'iata':code,'icao':r.get('icao_code') or r['ident'],'name':r['name'],'city':r['municipality'],'country':r['iso_country'],'latitude':float(r['latitude_deg']),'longitude':float(r['longitude_deg']),'wikipedia_url':r['wikipedia_link'],'source_id':'airports'}
  if r.get('_metadata_override'):
   ev=r['_metadata_override']
   if r.get('_former_iata_code'):airports[code]['former_iata_codes']=[r['_former_iata_code']]
   airports[code]['identifier_source_id']=source(ev['source_url'],'airport_metadata_correction',source_title=ev.get('source_title','Reviewed airport identifiers'),note=ev['note'],**({'effective_on':ev['effective_on']} if ev.get('effective_on') else {'verified_on':ev['verified_on']}))
   if ev.get('effective_on'):airports[code]['identifier_effective_on']=ev['effective_on']
   else:airports[code]['identifier_verified_on']=ev['verified_on']
   if ev.get('supporting_source_urls'):airports[code]['supporting_identifier_source_ids']=[source(u,'airport_identity') for u in ev['supporting_source_urls']]
  return code
 routes=[];hubs=[];issues=[];excluded=[];out_airlines=[]
 for a in airlines:
  airlineid=a['id']; brands=a.get('service_brands') or BRANDS.get(airlineid,[a['name']]); aliases={norm(x) for x in brands}|{norm(a['wikipedia']),norm(a['name'])}
  ms=source(a['membership_source_url'],'alliance_nonmembership' if a['alliance']=='nonaligned' else 'alliance_membership')
  classification_sources=[ms]+[source(u,'alliance_membership') for u in ['https://www.staralliance.com/en/members','https://www.skyteam.com/en/about/our-members','https://www.oneworld.com/members']] if a['alliance']=='nonaligned' else [ms]
  out_airlines.append({'id':airlineid,'name':a['name'],'alliance_id':a['alliance'],**({'identity_note':'HA is a stable Hawaiian brand identifier. The current airline infobox lists AS/ASA following operational integration with Alaska; alliance membership is retained as a separate brand.'} if airlineid=='HA' else {}),'wikipedia_url':'https://en.wikipedia.org/wiki/'+quote(a['wikipedia']),'membership_source_id':ms,'classification_source_ids':classification_sources,**({'hub_selection_note':a['hub_selection_note']} if a.get('hub_selection_note') else {}),'service_brands':brands,**({'classification_note':a['classification_note']} if a.get('classification_note') else {}),**({'entity_scope':a['entity_scope']} if a.get('entity_scope') else {})})
  for h in a['hubs']:
   r=bycode.get(h['iata'])
   if not r: issues.append({'kind':'unknown_hub_code','airline_id':airlineid,'hub':h});continue
   origin=airport(r);hs=source('https://en.wikipedia.org/w/index.php?oldid='+str(h['source_revision']) if h.get('source_revision') else h.get('source_url','https://en.wikipedia.org/wiki/'+quote(a['wikipedia'])),'airline_hubs')
   hub={'airline_id':airlineid,'airport_id':origin,'kind':h.get('kind','hub'),'source_id':hs,'coverage':'pending','route_count':0,**({'note':h['note']} if h.get('note') else {}),**({'seasonal':True} if h.get('seasonal') else {})};hubs.append(hub)
   try:
    fetch_title=r['wikipedia_link'].split('/wiki/')[-1] if r['wikipedia_link'] else h['wikipedia']
    page=fetch(fetch_title,cache)
    parsed=page['parse'];soup=BeautifulSoup(parsed['text']['*'],'html.parser')
    sid=source('https://en.wikipedia.org/w/index.php?oldid='+str(parsed['revid']),'airport_passenger_routes',page_title=parsed['title'],revision_id=parsed['revid'],sha256=hashlib.sha256(parsed['text']['*'].encode()).hexdigest())
    tables=[]
    for table in soup.find_all('table'):
     heads=[x.get_text(' ',strip=True).lower() for x in table.find_all('th')[:8]]
     if any('airline' in x for x in heads) and any('destination' in x for x in heads):
      if not passenger_table(table):continue
      tables.append(table)
    matched=0;unresolved=0;seen=set()
    for table in tables:
     for tr in table.find_all('tr'):
      cells=tr.find_all(['td','th'],recursive=False)
      if len(cells)<2: continue
      first=cells[0]
      for ref in first.select('sup.reference'):ref.decompose()
      brand=first.get_text(' ',strip=True); links=[title(x) for x in first.find_all('a') if title(x)]
      if not (norm(brand) in aliases or any(norm(t) in aliases for t in links)):continue
      matched+=1
      for item in route_items(cells[1]):
       dest=bytitle.get(norm(item['destination_title']))
       note=re.sub(r'\s+',' ',item['note']).strip(' ,;')
       status,change_date=route_status(note,item['seasonal'],item['struck'])
       if not dest:
        if norm(item['destination_title']) in {norm('Seasonal'),norm('Charter flight')}:continue
        unresolved+=1;issues.append({'kind':'unresolved_destination','airline_id':airlineid,'hub_airport_id':origin,'title':item['destination_title'],'label':item['label'],'note':note,'source_id':sid});continue
       destination=airport(dest)
       if origin==destination:continue
       key=(destination,norm(brand),status,item['service_type'])
       if key in seen:continue
       seen.add(key)
       record={'airline_id':airlineid,'hub_airport_id':origin,'destination_airport_id':destination,'service_brand':brand,'status':status,'service_type':item['service_type'],'source_id':sid}
       if note:record['note']=note
       if change_date:record['change_date']=change_date
       if re.search(r'\bvia\b|\bstopover\b',note,re.I):record['via_note']=note
       if status in ('announced','suspended_or_ended'):excluded.append(record)
       else:routes.append(record);hub['route_count']+=1
    hub['coverage']='parsed_with_unresolved' if unresolved else 'parsed' if matched else 'no_matching_airline_rows'
    hub['matched_airline_rows']=matched
    hub['unresolved_destination_count']=unresolved
    hub['destination_count']=len({x['destination_airport_id'] for x in routes if x['airline_id']==airlineid and x['hub_airport_id']==origin})
    hub['route_source_id']=sid
    if not matched:issues.append({'kind':'missing_airline_rows','airline_id':airlineid,'hub_airport_id':origin,'tables_found':len(tables),'source_id':sid})
    print(airlineid,origin,hub['route_count'],hub['coverage'],flush=True)
   except Exception as e:
    hub['coverage']='fetch_failed';issues.append({'kind':'fetch_failed','airline_id':airlineid,'hub_airport_id':origin,'error':str(e)});print('FAILED',airlineid,origin,str(e),flush=True)
 # IDs stable with respect to ordering. Sources carry pinned airport revisions.
 routes.sort(key=lambda x:(x['airline_id'],x['hub_airport_id'],x['destination_airport_id'],x['service_brand'],x['status']))
 for r in routes+excluded:r['id']='r'+hashlib.sha256('|'.join(str(r.get(k,'')) for k in ('airline_id','hub_airport_id','destination_airport_id','service_brand','status','service_type')).encode()).hexdigest()[:16]
 evidence_path=w/'airport-overrides-evidence.json'
 alias_evidence=json.loads(evidence_path.read_text()) if evidence_path.exists() else {}
 airport_aliases=[]
 for wiki,code in sorted(overrides.items()):
  if code not in airports:continue
  ev=alias_evidence.get(wiki,{})
  ev_url=ev.get('source_url') or ('https://en.wikipedia.org/w/index.php?oldid='+str(ev['revision']) if ev.get('revision') else 'https://en.wikipedia.org/wiki/'+quote(ev.get('canonical',wiki).replace(' ','_')))
  alias_sid=source(ev_url,'airport_identity')
  airport_aliases.append({'wikipedia_title':wiki,'airport_id':code,'method':ev.get('method','Reviewed airport identifier'),'source_id':alias_sid,**({'wikidata_id':ev['wikidata_id']} if ev.get('wikidata_id') else {})})
 sources.append({'id':'airports','url':'https://ourairports.com/data/','download_url':'https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/airports.csv','kind':'airport_metadata','license':'Public domain','retrieved_on':TODAY.isoformat(),'sha256':hashlib.sha256((w/'ourairports.csv').read_bytes()).hexdigest()})
 data={'schema_version':1,'as_of':TODAY.isoformat(),'scope':{'membership':'Active full members of Star Alliance, SkyTeam, and oneworld, plus a curated set of 40 major carriers outside those three global alliances. Non-aligned is a category, not a fourth alliance. Connecting partners and suspended members are not treated as active full members. Alaska remains in oneworld.','hubs':'Wikipedia airline infobox hubs and secondary passenger hubs; primary operating bases or focus cities are used for point-to-point carriers without hubs. Every relationship preserves its source-defined kind; no inferred all-to-all routes.','routes':'Passenger destination entries in each selected hub or base airport Wikipedia table, matched to the airline or explicitly enumerated service brands. Airport table entries are source-listed services, not independently verified nonstop flight schedules.','seasonality':'Seasonal services included and labeled; future and suspended/ended entries are separate. Undated listed entries reflect the retrieved page, not a guarantee of operation on as_of.','coverage':'Coverage status means the source table was parsed. It does not certify the source is exhaustive or up to date. See issues for every unresolved entry.','direction':'Records are hub-origin services. A route listed at both hubs appears in both directions; no reciprocal service is invented.'},'alliances':[{'id':'star','name':'Star Alliance','color':'#d89614','kind':'alliance'},{'id':'skyteam','name':'SkyTeam','color':'#2474d2','kind':'alliance'},{'id':'oneworld','name':'oneworld','color':'#bd4294','kind':'alliance'},{'id':'nonaligned','name':'Non-aligned','color':'#12856f','kind':'category','description':'Curated major carriers outside Star Alliance, SkyTeam, and oneworld.'}],'airlines':out_airlines,'airports':sorted(airports.values(),key=lambda x:x['id']),'hubs':hubs,'routes':routes,'excluded_routes':excluded,'sources':sources,'issues':issues,'airport_aliases':airport_aliases,'membership_notes':roster.get('notes',[]),'suspended_members':roster.get('suspended',[])}
 args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
 (w/'collection-summary.json').write_text(json.dumps({'airlines':len(airlines),'hubs':len(hubs),'routes':len(routes),'airports':len(airports),'issues':len(issues)},indent=2))
 print((w/'collection-summary.json').read_text(),flush=True)
if __name__=='__main__':main()
