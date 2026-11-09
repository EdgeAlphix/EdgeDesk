#!/usr/bin/env python3
"""Bootstrap vcpkg and verify build assets fetched through the GitHub API."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote


def api(path, *args):
    curl = str(Path(os.environ['SystemRoot']) / 'System32/curl.exe') if sys.platform == 'win32' else 'curl'
    token = os.environ.get('EDGEDESK_DOWNLOAD_TOKEN')
    headers = f'header = "Authorization: Bearer {token}"\n'.encode() if token else b''
    return subprocess.check_output([
        curl, '--config', '-', '--fail', '--silent', '--show-error', '--location',
        '--retry', '2', '--max-time', '120', *args,
        f'https://api.github.com/{path}',
    ], input=headers)


def fetch(url, checksum, destination):
    match = re.fullmatch(r'https://github\.com/([\w.-]+/[\w.-]+)/releases/download/([^/?#]+)/([^/?#]+)', url)
    if not match:
        raise SystemExit('Asset is not a GitHub release download')
    repo, tag, name = match.groups()
    release = json.loads(api(f'repos/{repo}/releases/tags/{tag}'))
    asset = next(asset for asset in release['assets'] if asset['name'] == unquote(name))
    digest = checksum or asset.get('digest')
    if digest and ':' not in digest:
        digest = f'sha512:{digest}'
    if not digest or not re.fullmatch(r'(?:sha512:[0-9a-f]{128}|sha256:[0-9a-f]{64})', digest):
        raise ValueError(f'No valid checksum for {name}')
    algorithm, expected = digest.split(':', 1)
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + '.part')
    try:
        nonce = os.environ.get('GITHUB_RUN_ID', 'local')
        api(f"repos/{repo}/releases/assets/{asset['id']}?run={nonce}",
            '-H', 'Accept: application/octet-stream', '--output', str(partial))
        actual = hashlib.new(algorithm)
        with partial.open('rb') as downloaded:
            for block in iter(lambda: downloaded.read(1024 * 1024), b''):
                actual.update(block)
        if actual.hexdigest() != expected:
            raise ValueError(f'Checksum mismatch for {name}')
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)


def bootstrap():
    root = Path(os.environ['EDGEDESK_VCPKG_ROOT']).resolve()
    commit = os.environ['VCPKG_COMMIT_ID']
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Invalid vcpkg commit')
    root.mkdir(parents=True, exist_ok=True)
    for args in (('init', '-q'), ('fetch', '-q', 'https://github.com/microsoft/vcpkg.git', commit),
                 ('checkout', '-q', '--detach', '--force', 'FETCH_HEAD')):
        subprocess.run(['git', '-C', str(root), *args], check=True)
    metadata = dict(line.split('=', 1) for line in
                    (root / 'scripts/vcpkg-tool-metadata.txt').read_text().splitlines() if '=' in line)
    arm = os.environ['RUNNER_ARCH'] == 'ARM64'
    if sys.platform == 'win32':
        name, checksum, executable = ('vcpkg-arm64.exe' if arm else 'vcpkg.exe'), None, root / 'vcpkg.exe'
    elif sys.platform == 'darwin':
        name, checksum, executable = 'vcpkg-macos', 'VCPKG_MACOS_SHA', root / 'vcpkg'
    else:
        name = 'vcpkg-glibc-arm64' if arm else 'vcpkg-glibc'
        checksum = 'VCPKG_GLIBC_ARM64_SHA' if arm else 'VCPKG_GLIBC_SHA'
        executable = root / 'vcpkg'
    tag = metadata['VCPKG_TOOL_RELEASE_TAG']
    fetch(f'https://github.com/microsoft/vcpkg-tool/releases/download/{tag}/{name}',
          metadata[checksum] if checksum else '', executable)
    executable.chmod(0o755)
    subprocess.run([str(executable), 'version', '--disable-metrics'], check=True)
    script = Path(__file__).resolve().as_posix()
    python = Path(sys.executable).as_posix()
    with open(os.environ['GITHUB_ENV'], 'a') as env:
        env.write(f'VCPKG_ROOT={root.as_posix()}\nVCPKG_DISABLE_METRICS=1\n')
        env.write(f'X_VCPKG_ASSET_SOURCES=x-script,"{python}" "{script}" {{url}} {{sha512}} {{dst}}\n')


if __name__ == '__main__':
    if sys.argv[1:] == ['bootstrap']:
        bootstrap()
    elif sys.argv[1:2] == ['download']:
        _, url, destination, *checksum = sys.argv[1:]
        fetch(url, checksum[0] if checksum else '', destination)
    else:
        fetch(*sys.argv[1:])
