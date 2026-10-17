#!/usr/bin/env python3
# ============================================================================
# Copyright (c) 2026 Supratim Sanyal of SANYALnet Labs.
# Proprietary rights reserved except as expressly licensed herein.
#
# DECnet-IV-Linux
# This file is governed by the SANYALnet Labs Non-Commercial License in the
# root LICENSE file. Non-Commercial use is permitted; Commercial Use and use
# for AI/ML model training are prohibited unless separately authorized.
#
# Attribution is required: "Based on original work by Supratim Sanyal of
# SANYALnet Labs." See LICENSE for full terms, warranty disclaimer, termination,
# patent, trademark, and governing-law provisions.
# ============================================================================

"""Offline mocked GitHub API regression for safe bounded Actions garbage collection."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "actions_gc.sh"
MOCK_GH = '''#!/usr/bin/env python3
import json, os, pathlib, sys
path=pathlib.Path(os.environ['MOCK_GH_STATE'])
state=json.loads(path.read_text())
args=sys.argv[1:]
assert args.pop(0) == 'api', args
method='GET'
if args[:2] == ['-X', args[1] if len(args) > 1 else '']:
    if args[1] in ('DELETE','POST','PATCH'):
        method=args[1]
        args=args[2:]
url=args.pop(0)
if not url.startswith('repos/tuklusan/DECnet-IV-Linux/') and url != 'rate_limit':
    sys.exit('unexpected API path: '+url)
if method=='DELETE':
    item=int(url.rsplit('/',1)[-1])
    field='caches' if '/caches/' in url else 'runs'
    assert item in state[field], (field,item,state)
    state[field].remove(item)
    state['deleted_'+field].append(item)
    if field == 'runs' and item == state.get('race_run'):
        path.write_text(json.dumps(state))
        print('gh: Not Found (HTTP 404)', file=sys.stderr)
        sys.exit(1)
elif method == 'GET' and '/actions/runs/' in url:
    item=int(url.rsplit('/',1)[-1])
    if item not in state['runs']:
        sys.exit(1)
    print(item)
elif method == 'POST':
    state['comments']+=1
elif method == 'PATCH':
    state['issue_open']=False
elif url == 'rate_limit':
    print('2000')
elif '/issues?' in url:
    print('1237' if state['issue_open'] else '')
elif '/actions/caches?' in url:
    print(len(state['caches']) if '--jq' in args and '.total_count' in args else '\\n'.join(map(str,state['caches'])))
elif '/actions/runs?' in url:
    assert 'created=%3C' in url, 'run deletion query requires encoded less-than date filter'
    print(len(state['runs']) if '--jq' in args and '.total_count' in args else '\\n'.join(map(str,state['runs'])))
else:
    sys.exit('unexpected API call: '+url)
path.write_text(json.dumps(state))
'''


def scenario(issue_open: bool, race_run: int | None = None) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = pathlib.Path(directory)
        cli = root / 'gh'
        cli.write_text(MOCK_GH)
        cli.chmod(0o755)
        state_path = root / 'state.json'
        state = dict(issue_open=issue_open, caches=[11, 12], runs=[21, 22],
                     deleted_caches=[], deleted_runs=[], comments=0, race_run=race_run)
        state_path.write_text(json.dumps(state))
        env = dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'],
                   GH_TOKEN='offline-test-token', GITHUB_REPOSITORY='tuklusan/DECnet-IV-Linux',
                   GITHUB_RUN_ID='99', MOCK_GH_STATE=str(state_path), DNIV_GC_MAX_DELETES='10')
        result = subprocess.run(['bash', str(SCRIPT)], env=env, capture_output=True, text=True)
        assert result.returncode == 0, (result.stdout, result.stderr)
        observed = json.loads(state_path.read_text())
        assert observed['caches'] == [] and observed['runs'] == [], observed
        assert observed['deleted_caches'] == [11, 12] and observed['deleted_runs'] == [21, 22]
        assert observed['comments'] == (1 if issue_open else 0)
        assert not observed['issue_open']
        env['GITHUB_REPOSITORY'] = 'wrong/repository'
        result = subprocess.run(['bash', str(SCRIPT)], env=env, capture_output=True, text=True)
        assert result.returncode == 2
        assert json.loads(state_path.read_text()) == observed


if __name__ == '__main__':
    subprocess.run(['bash', '-n', str(SCRIPT)], check=True)
    scenario(True)
    scenario(False)
    scenario(True, 21)
    print('Actions GC policy regression: PASS (mocked historical/routine, repository safety)')
