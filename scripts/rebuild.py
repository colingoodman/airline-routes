#!/usr/bin/env python3
"""Refresh route tables using the reviewed roster and airport alias evidence."""
import argparse,shutil,subprocess,sys
from pathlib import Path
from urllib.request import Request,urlopen
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--as-of',default='2026-10-27');p.add_argument('--work',type=Path,default=root/'work');args=p.parse_args();w=args.work.resolve();w.mkdir(parents=True,exist_ok=True)
for name in ['roster-hubs.json','airport-overrides.json','airport-overrides-evidence.json']:shutil.copyfile(root/'scripts'/name,w/name)
url='https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/airports.csv'
(w/'ourairports.csv').write_bytes(urlopen(Request(url,headers={'User-Agent':'AllianceRouteMap/1.0'}),timeout=90).read())
subprocess.run([sys.executable,str(root/'scripts/collect.py'),'--work',str(w),'--out',str(root/'web/data.json'),'--as-of',args.as_of],check=True)
