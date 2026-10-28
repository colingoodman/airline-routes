#!/usr/bin/env python3
"""Install opt-in, candidate-only macOS agents pinned to a clean Git commit."""
import argparse
import datetime as dt
import io
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tarfile

from rebuild import ROOT, digest, write_json

LABELS = {'refresh':'net.colingoodman.airplanes.refresh', 'schedules':'net.colingoodman.airplanes.schedules'}


def agent_config(kind, runtime, state, python, node):
    if kind == 'refresh':
        command = [str(python),str(runtime/'scripts/refresh_runner.py'),'--state',str(state/'refresh'),
                   '--daily-after-utc','03:00','--max-seconds','2700','--max-disk-mib','2048','--retain','3']
    else:
        command = [str(python),str(runtime/'scripts/schedule_research.py'),'--work',str(state/'schedules'),
                   '--daily-after-utc','03:45','--airports','OSL','BNN','--hours','168',
                   '--max-requests','24','--max-disk-mib','256']
    return {'Label':LABELS[kind], 'ProgramArguments':command, 'WorkingDirectory':str(runtime),
            'RunAtLoad':True, 'StartInterval':3600, 'ProcessType':'Background',
            'EnvironmentVariables':{'PATH':str(Path(node).parent)+':/usr/bin:/bin:/usr/sbin:/sbin',
                                    'PYTHONDONTWRITEBYTECODE':'1'},
            'StandardOutPath':str(state/(kind+'.log')), 'StandardErrorPath':str(state/(kind+'.error.log'))}


def install(args):
    if sys.platform != 'darwin':
        raise ValueError('These agents require macOS; Linux templates are in deploy/refresh')
    subprocess.run(['git','diff','--quiet','HEAD'],cwd=ROOT,check=True)
    revision = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    python = Path(sys.executable).absolute()
    node = shutil.which('node')
    if not node:
        raise ValueError('Node.js is required for candidate validation')
    state = args.state.resolve()
    if state == ROOT or state in ROOT.parents or state == ROOT/'web' or ROOT/'web' in state.parents:
        raise ValueError('Automation state must be outside published files')
    state.mkdir(parents=True,exist_ok=True)
    runtime = state/'runtimes'/revision
    if not runtime.exists():
        raw = subprocess.check_output(['git','archive',revision,'scripts','requirements.txt','web/data.json','web/map-data.json'],cwd=ROOT)
        staging = state/'runtimes'/('.incoming-'+revision)
        if staging.exists():
            raise ValueError('Interrupted runtime staging exists; inspect it before retrying')
        staging.mkdir(parents=True)
        try:
            with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
                archive.extractall(staging,filter='data')
            staging.rename(runtime)
        finally:
            if staging.exists():shutil.rmtree(staging)
    if 'refresh' in args.kinds:
        if not args.seed_candidate:
            raise ValueError('Refresh installation requires a fully validated seed candidate')
        candidate=args.seed_candidate.resolve()
        manifest=json.loads((candidate/'manifest.json').read_text())
        if manifest.get('status')!='validated' or manifest.get('validation')!='reviewed_snapshot' or manifest.get('offline'):
            raise ValueError('Seed must have completed online reviewed-snapshot validation')
        if manifest['baseline_sha256']!=digest(runtime/'web/data.json'):
            raise ValueError('Seed baseline does not match the pinned runtime')
        for name,sha in manifest['code'].items():
            if digest(runtime/'scripts'/name)!=sha:
                raise ValueError('Seed collector version differs from pinned runtime: '+name)
        for name in ('data','map'):
            filename='data.json' if name=='data' else 'map-data.json'
            if digest(candidate/filename)!=manifest[name+'_sha256']:
                raise ValueError('Seed artifact checksum mismatch')
        runner_state=state/'refresh'
        runner_state.mkdir(exist_ok=True)
        if not (runner_state/'state.json').exists():
            report=json.loads((candidate/'changes.json').read_text())
            write_json(runner_state/'state.json',{'last_attempted_at':manifest['started_at'],
                       'last_successful_at':manifest['finished_at'],'status':report['publication'],
                       'latest_candidate':str(candidate),'hold_reasons':report['hold_reasons']})
        cache=runner_state/'cache'
        if not cache.exists() and args.seed_cache:
            shutil.copytree(args.seed_cache,cache,symlinks=False)
    if 'schedules' in args.kinds and args.seed_schedules and not (state/'schedules').exists():
        shutil.copytree(args.seed_schedules,state/'schedules',symlinks=False)
    agents_dir=args.agents_dir or (Path.home()/'Library/LaunchAgents' if args.enable else state/'launchagents')
    agents_dir.mkdir(parents=True,exist_ok=True)
    domain='gui/'+str(os.getuid())
    for kind in args.kinds:
        config=agent_config(kind,runtime,state,python,node)
        target=agents_dir/(LABELS[kind]+'.plist')
        if target.exists():
            previous=plistlib.loads(target.read_bytes())
            program=previous.get('ProgramArguments',[])
            if previous.get('Label')!=LABELS[kind] or len(program)<2 or state/'runtimes' not in Path(program[1]).parents:
                raise ValueError('Refusing to replace an unmanaged launch agent: '+str(target))
            if args.enable:
                subprocess.run(['launchctl','bootout',domain,str(target)],check=False,capture_output=True)
        target.write_bytes(plistlib.dumps(config))
        target.chmod(0o600)
        subprocess.run(['plutil','-lint',str(target)],check=True)
        if args.enable:
            subprocess.run(['launchctl','bootstrap',domain,str(target)],check=True)
            subprocess.run(['launchctl','print',domain+'/'+LABELS[kind]],check=True,stdout=subprocess.DEVNULL)
    result={'revision':revision,'runtime':str(runtime),'state':str(state),'labels':[LABELS[k] for k in args.kinds],
            'enabled':args.enable,'installed_at':dt.datetime.now(dt.timezone.utc).isoformat()}
    write_json(state/'installation.json',result)
    return result


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state',type=Path,default=ROOT/'work/automatic-refresh')
    p.add_argument('--agents-dir',type=Path,help='Override plist destination; default stages locally unless --enable is supplied')
    p.add_argument('--kinds',nargs='+',choices=LABELS,default=list(LABELS))
    p.add_argument('--seed-candidate',type=Path)
    p.add_argument('--seed-cache',type=Path)
    p.add_argument('--seed-schedules',type=Path)
    p.add_argument('--enable',action='store_true',help='Bootstrap the generated agents after validation')
    return p


if __name__=='__main__':
    print(json.dumps(install(parser().parse_args()),indent=2))
