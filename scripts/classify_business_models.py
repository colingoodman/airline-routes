"""Conservative Wikipedia business-model classification; absence always remains unknown.

This module is deliberately independent of the route builder. Callers provide
already-fetched, pinned source text and a current list entry for the *same*
carrier. An ownership or service-brand relationship is not identity evidence.
"""
import re
from bs4 import BeautifulSoup

GEOGRAPHIC_SECTIONS={'Africa','Americas','Asia','Europe','Oceania'}
def section_ancestry(node):
    result=[];level=7
    for heading in node.find_all_previous(['h2','h3','h4','h5','h6']):
        n=int(heading.name[1])
        if n<level:result.append(heading.get_text(' ',strip=True));level=n
        if n==2:break
    return list(reversed(result))

def current_lowcost_entries(html,title_from_link):
    """Read only leaf bullets in current geographic sections, never captions/defunct tables."""
    soup=BeautifulSoup(html,'html.parser');result=[];seen=set()
    for li in soup.find_all('li'):
        context=section_ancestry(li)
        if not context or context[0] not in GEOGRAPHIC_SECTIONS or li.find('ul') or li.find_parent(['table','nav']):continue
        links=[a for a in li.find_all('a') if title_from_link(a) and ':' not in title_from_link(a) and not a.find_parent('sup') and 'new' not in a.get('class',[])]
        if not links:continue
        a=links[0];title=title_from_link(a)
        if title in seen:continue
        seen.add(title);result.append({'wikipedia':title,'name':a.get_text(' ',strip=True),'section':context,'quote':a.get_text(' ',strip=True)[:120]})
    return result

def introductory_paragraph(html):
    soup=BeautifulSoup(html,'html.parser');container=soup.select_one('.mw-parser-output') or soup.body or soup
    for p in container.find_all('p'):
        if p.find_parent(['table','figure','nav']):continue
        txt=p.get_text(' ',strip=True)
        if len(txt)>70:return txt
    return ''

def explicit_intro_flags(text):
    """Use the airline's first present-tense description, not later ownership/comparison prose."""
    text=re.sub(r'\s+',' ',text).replace('–','-').replace('‑','-').replace('–','-')
    first=re.split(r'(?<=[.!?])\s+(?=[A-Z])',text,maxsplit=1)[0]
    match=re.search(r'\bis\s+(?:an?\s+)?([^.;,]{1,220})',first,re.I)
    if not match:return []
    clause=match[1]
    # These clauses describe a relationship to another carrier, not this airline's model.
    if re.search(r'\b(?:not|former|formerly|previously|shareholder|subsidiary|parent|partner|customer|supplier|owns|stake)\b',clause,re.I):return []
    flags=[]
    patterns=[('low_cost',True,r'\b(?:ultra[\s-]*)?low[\s-]*cost\b.{0,35}?\b(?:airlines?|carriers?)\b'),('low_cost',True,r'\b(?:budget|discount)\s+(?:airlines?|carriers?)\b'),('low_cost',False,r'\b(?:full[\s-]*service\b.{0,35}?\b(?:airlines?|carriers?)|legacy\s+carriers?)\b'),('regional',True,r'\bregional\s+(?:airlines?|carriers?)\b')]
    for flag,value,pattern in patterns:
        found=re.search(pattern,clause,re.I)
        if found:flags.append({'flag':flag,'value':value,'quote':found[0][:120]})
    # Both descriptions in a single introductory clause are not a clean binary classification.
    return flags

def classify(intro,article_source_url,article_revision,list_entry=None,list_source_url=None,list_revision=None):
    evidence=[];values={'low_cost':set(),'regional':set()}
    if list_entry is not None:
        values['low_cost'].add(True);evidence.append({'flag':'low_cost','value':True,'source_url':list_source_url,'revision_id':list_revision,'method':'Current low-cost-airline inventory entry for the same carrier','quote':str(list_entry)[:120]})
    for found in explicit_intro_flags(intro):
        values[found['flag']].add(found['value']);evidence.append({**found,'source_url':article_source_url,'revision_id':article_revision,'method':'Explicit first present-tense introductory description'})
    result={flag:next(iter(v)) if len(v)==1 else None for flag,v in values.items()}
    conflicts=[flag for flag,v in values.items() if len(v)>1]
    note='Unknown classifications are not inferred from list absence, nationality, fares, ownership, or service-brand relationships.'
    if conflicts:note='Conflicting source descriptions for '+', '.join(conflicts)+'; retained as unknown.'
    return {**result,'classification_note':note,'evidence':evidence}
