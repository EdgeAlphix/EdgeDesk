#!/usr/bin/env python3
"""Prepare exact corresponding source once per upstream published stable version."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.request

root = Path(__file__).resolve().parent.parent
repo = os.environ.get('GITHUB_REPOSITORY','EdgeAlphix/EdgeDesk')
def run(*args, cwd=root, capture=False):
    return subprocess.check_output(args,cwd=cwd,text=True).strip() if capture else subprocess.run(args,cwd=cwd,check=True)
def output(**values):
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:
            for k,v in values.items():
                f.write(f'{k}={v}\n')
    print(json.dumps(values))

release=json.loads(run('gh','api','repos/rustdesk/rustdesk/releases/latest',capture=True))
upstream=release['tag_name']
if release['draft'] or release['prerelease'] or not re.fullmatch(r'v?\d+\.\d+\.\d+(?:-\d+)?',upstream):
    raise RuntimeError('Only published stable version releases are accepted')
version=upstream.removeprefix('v')
tag=f'v{version}-edgedesk.7'
existing=subprocess.run(['gh','release','view',tag,'--repo',repo,'--json','isDraft'],capture_output=True,text=True)
if existing.returncode==0 and not json.loads(existing.stdout)['isDraft']:
    output(build='false',version=version,tag=tag)
    raise SystemExit(0)
remote=f'https://github.com/{repo}.git'
ref=run('git','ls-remote',remote,f'refs/tags/{tag}',capture=True)
if ref:
    output(build='true',version=version,tag=tag,source_ref=tag)
    raise SystemExit(0)
with tempfile.TemporaryDirectory(prefix='edgedesk-release-') as directory:
    dst=Path(directory)/'source'
    run('git','clone','--depth','1','--branch',upstream,'https://github.com/rustdesk/rustdesk.git',str(dst))
    run('git','submodule','update','--init','--recursive','--depth','1',cwd=dst)
    upstream_sha=run('git','rev-parse','HEAD',cwd=dst,capture=True)
    common_sha=run('git','rev-parse','HEAD',cwd=dst/'libs/hbb_common',capture=True)
    shutil.copytree(root/'edgedesk',dst/'edgedesk')
    run('python3','edgedesk/apply.py',cwd=dst)
    run('python3','edgedesk/finalize.py',cwd=dst)
    shutil.rmtree(dst/'.github/workflows')
    shutil.copytree(root/'.github/workflows',dst/'.github/workflows')
    shutil.copy(root/'README.md',dst/'README.md')
    run('python3','edgedesk/verify.py',cwd=dst)
    (dst/'edgedesk/patches').mkdir(exist_ok=True)
    # Include new files and binary artwork, excluding previous patch artifacts.
    run('git','add','-A',cwd=dst)
    run('git','add','-f','edgedesk/assets','flutter/assets','flutter/android/app/src/main/res',cwd=dst)
    run('git','reset','--','edgedesk/patches',cwd=dst)
    (dst/'edgedesk/patches/client.patch').write_text(run('git','diff','--cached','--binary',cwd=dst,capture=True)+'\n')
    (dst/'edgedesk/patches/hbb-common.patch').write_text(run('git','diff','--binary',cwd=dst/'libs/hbb_common',capture=True)+'\n')
    # Vendor the modified dependency so GitHub source archives contain the actual code.
    run('git','rm','--cached','libs/hbb_common',cwd=dst)
    (dst/'libs/hbb_common/.git').unlink()
    (dst/'.gitmodules').unlink()
    (dst/'edgedesk/upstream.json').write_text(json.dumps({'tag':upstream,'commit':upstream_sha,'hbb_common_commit':common_sha,'release_url':release['html_url']},indent=2)+'\n')
    shutil.rmtree(dst/'edgedesk/__pycache__',ignore_errors=True)
    run('git','config','user.name','EdgeDesk Release Bot',cwd=dst)
    run('git','config','user.email','release@edgealphix.com',cwd=dst)
    # Source-only commits inherit existing workflows from main and require no workflow privilege.
    parent = run('git','rev-parse','HEAD',capture=True)
    run('git','fetch',remote,parent,'--depth','1',cwd=dst)
    run('git','reset','--soft','FETCH_HEAD',cwd=dst)
    run('git','add','-A',cwd=dst)
    run('git','add','-f','edgedesk/assets','flutter/assets','flutter/android/app/src/main/res',cwd=dst)
    run('git','commit','-m',f'EdgeDesk {version}: apply managed client overlay',cwd=dst)
    run('git','tag',tag,cwd=dst)
    run('git','remote','set-url','origin',remote,cwd=dst)
    run('git','push','origin',f'HEAD:refs/heads/source/{tag}',f'refs/tags/{tag}',cwd=dst)
output(build='true',version=version,tag=tag,source_ref=tag)
