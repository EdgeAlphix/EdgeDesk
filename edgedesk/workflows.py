#!/usr/bin/env python3
"""Reuse released upstream platform builds without push/nightly build triggers."""
import re
from pathlib import Path
import yaml

class Loader(yaml.SafeLoader):
    pass
Loader.yaml_implicit_resolvers = {k: [(tag, rx) for tag, rx in values if tag != 'tag:yaml.org,2002:bool'] for k, values in Loader.yaml_implicit_resolvers.items()}
Loader.add_implicit_resolver('tag:yaml.org,2002:bool', re.compile(r'^(?:true|false|True|False)$'), list('tTfF'))
class Dumper(yaml.SafeDumper):
    pass
def string(dumper, value):
    return dumper.represent_scalar('tag:yaml.org,2002:str', value, style='|' if '\n' in value else None)
Dumper.add_representer(str, string)

mirror_step = {'name': 'Use official Ubuntu archive with bounded downloads', 'if': "runner.os == 'Linux'", 'shell': 'bash', 'run': 'sudo python3 - <<\'PYTHON\'\nfrom pathlib import Path\npaths = [Path(\'/etc/apt/apt-mirrors.txt\'), Path(\'/etc/apt/sources.list\')]\npaths += list(Path(\'/etc/apt/sources.list.d\').glob(\'*\'))\nfor path in paths:\n    if path.is_file():\n        data = path.read_text()\n        path.write_text(data.replace(\'http://azure.archive.ubuntu.com/ubuntu\', \'https://archive.ubuntu.com/ubuntu\'))\nPath(\'/etc/apt/apt.conf.d/99-edgedesk-downloads\').write_text(\'Acquire::http::Timeout "30";\\nAcquire::https::Timeout "30";\\nAcquire::Retries "3";\\n\')\nPYTHON\n'}
root = Path(__file__).resolve().parent.parent
wf = root / '.github/workflows'
original = yaml.load((wf/'flutter-build.yml').read_text(), Loader=Loader)
original['name'] = 'EdgeDesk platform builds'
original['permissions'] = {'contents': 'read'}
original['on']['workflow_call']['inputs'].update({'source-ref': {'required': True, 'type':'string'}, 'version':{'required':True,'type':'string'}})
original['env']['VERSION'] = '${{ inputs.version }}'
original['env']['VCPKG_CMAKE_VERSION'] = '4.3.0'
release_asset_checksums = {
    'windows-x64-release.zip': 'ede341b0015c745ecc67a5de504e424258f65fd976ac482a094b4c7bbab15fbea9e5a2f51b0869c306ec28c46ae83f578764c721bd179899736fad41ef36ad70',
    'usbmmidd_v2.zip': '2013089cce010f2f1be46259722813cf51150d2f9a66d46d6be522a656dc4d0ede331323b24725b40ce803df19ec5a5052472b887fb2ed45173a7958cd24320d',
    'apple-codesign-0.22.0-macos-universal.tar.gz': 'sha256:7031ee75ca2a55c558071701078517c05d959e012dd87833ac6b4a23c5ff52b9',
}
def release_download(match):
    url, name = match.groups()
    checksum = release_asset_checksums.get(name)
    return f'python edgedesk/vcpkg.py download {url} {name}' + (f' {checksum}' if checksum else '')

for job in original['jobs']['build-for-macOS']['strategy']['matrix']['job']:
    if job['os'] == 'macos-14':
        job['os'] = 'macos-15'
for key in ('build-for-windows-sciter','build-rustdesk-linux-sciter','build-rustdesk-web','publish_unsigned'):
    original['jobs'].pop(key, None)
flatpak = original['jobs']['build-flatpak']
flatpak['needs'] = ['build-rustdesk-linux']
flatpak['strategy']['matrix']['job'] = [j for j in flatpak['strategy']['matrix']['job'] if not j.get('suffix')]
for step in flatpak['steps']:
    if step.get('id') == 'flatpak':
        commands = step['with']['run'].replace('pushd /workspace\n', '')
        step.clear()
        step.update({'name': 'Build Flatpak with SDK-compatible builder', 'shell': 'bash', 'run': '''docker run --rm --interactive --privileged --env DEBIAN_FRONTEND=noninteractive --device /dev/fuse --volume "$PWD:/workspace" --workdir /workspace ubuntu:24.04 bash -euo pipefail <<'FLATPAK'
apt-get update -y
apt-get install -y git flatpak flatpak-builder appstream-compose </dev/null
dpkg --compare-versions "$(dpkg-query -W -f='${Version}' flatpak-builder)" ge 1.4.0
''' + commands + '\nFLATPAK\ntest -s flatpak/rustdesk-${{ env.VERSION }}-${{ matrix.job.arch }}${{ matrix.job.suffix }}.flatpak\n'})
bridgejob = original['jobs']['generate-bridge']
bridgejob['uses'] = './.github/workflows/edgedesk-bridge.yml'
bridgejob['with'] = {'source-ref': '${{ inputs.source-ref }}'}
original['jobs']['build-RustDeskTempTopMostWindow']['uses'] = './.github/workflows/edgedesk-topmost.yml'
for jobname, job in original['jobs'].items():
    if 'steps' not in job:
        continue
    job['timeout-minutes'] = 180
    steps = [mirror_step]
    for step in job['steps']:
        use = step.get('uses','')
        if use.startswith('actions/checkout@'):
            step.setdefault('with',{})['ref'] = '${{ inputs.source-ref }}'
        if 'run' in step:
            step['run'] = re.sub(r'Invoke-WebRequest -Uri (https://github\.com/\S+/releases/download/\S+) -OutFile (\S+)', release_download, step['run'])
            step['run'] = step['run'].replace('RustDesk.app', 'EdgeDesk.app').replace('com.rustdesk.RustDesk', 'com.edgealphix.desk').replace('for name in rustdesk*??.rpm', 'for name in edgedesk*??.rpm')
            step['run'] = step['run'].replace('python preprocess.py --arp -d ../../rustdesk', 'Rename-Item ../../rustdesk/rustdesk.exe EdgeDesk.exe\npython preprocess.py --arp --app-name EdgeDesk --manufacturer "International Computing Group, LLC" -d ../../rustdesk')
        if use.startswith('softprops/action-gh-release@'):
            files = step['with'].get('files','').replace('rustdesk-*.rpm', 'edgedesk-*.rpm').replace('res/rustdesk-', 'res/edgedesk-').replace('./appimage/rustdesk-', './appimage/edgedesk-')
            # Publish only in the final all-platform job, after corresponding source is ready.
            step = {'name': 'Collect ' + step.get('name','package'), 'uses':'actions/upload-artifact@v4', 'with':{'name': f'package-{jobname}-{len(steps)}-${{{{ matrix.job.arch }}}}', 'path':files, 'if-no-files-found':'error'}, **({'if':step['if']} if 'if' in step else {})}
        steps.append(step)
    job['steps'] = steps
# The universal job has no arch matrix.
universal = original['jobs']['build-rustdesk-android-universal']
for step in universal['steps']:
    if step.get('uses','').startswith('actions/upload-artifact@'):
        values = step.get('with',{})
        if 'name' in values:
            values['name'] = values['name'].replace('${{ matrix.job.arch }}','universal')
windows_check = {"name": "Verify Windows executable starts", "shell": "pwsh", "run": '$process = Start-Process -FilePath (Resolve-Path ./rustdesk/rustdesk.exe) -ArgumentList "--version" -Wait -PassThru -RedirectStandardOutput version.txt -RedirectStandardError version-error.txt\n$version = Get-Content version.txt -Raw\nif ($process.ExitCode -ne 0 -or "$version" -notmatch [regex]::Escape("${{ env.VERSION }}")) { Get-Content version-error.txt; throw "EdgeDesk executable failed to report its version: $version" }\n'}
checks = {'build-for-windows-flutter': windows_check, 'build-for-macOS': {'name': 'Verify macOS application identity and executable', 'shell': 'bash', 'run': 'app=flutter/build/macos/Build/Products/Release/EdgeDesk.app\ntest "$(/usr/libexec/PlistBuddy -c \'Print CFBundleIdentifier\' "$app/Contents/Info.plist")" = com.edgealphix.desk\n"$app/Contents/MacOS/EdgeDesk" --version | grep -F "${{ env.VERSION }}"\n'}}
llvm = next(step for step in original['jobs']['build-for-windows-flutter']['steps'] if step.get('name') == 'Install LLVM and Clang')
llvm.pop('uses')
llvm.pop('with')
llvm['run'] = '''if ($env:RUNNER_ARCH -eq 'ARM64') {
  $target = 'woa64'
  $sha256 = '79d18b9498d7a6c36114f0277c83c91caf9258194c683a73e5886b68b4d304d1'
} else {
  $target = 'win64'
  $sha256 = '22e2f2c38be4c44db7a1e9da5e67de2a453c5b4be9cf91e139592a63877ac0a2'
}
$asset = "LLVM-$env:LLVM_VERSION-$target.exe"
$archive = Join-Path $env:RUNNER_TEMP $asset
$llvm = Join-Path $env:RUNNER_TEMP 'edgedesk-llvm'
python edgedesk/vcpkg.py download "https://github.com/llvm/llvm-project/releases/download/llvmorg-$env:LLVM_VERSION/$asset" $archive "sha256:$sha256"
if ($LASTEXITCODE -ne 0) { throw 'LLVM download failed' }
7z x $archive "-o$llvm" -y
if ($LASTEXITCODE -ne 0) { throw 'LLVM extraction failed' }
& "$llvm/bin/clang.exe" --version
if ($LASTEXITCODE -ne 0 -or -not (Test-Path "$llvm/bin/libclang.dll")) { throw 'LLVM installation failed' }
"$llvm/bin" >> $env:GITHUB_PATH
"LLVM_PATH=$llvm" >> $env:GITHUB_ENV
"LIBCLANG_PATH=$llvm/bin" >> $env:GITHUB_ENV
'''
for name, check in checks.items():
    steps = original["jobs"][name]["steps"]
    index = next(i for i, step in enumerate(steps) if step.get("name") == "Build rustdesk")
    steps.insert(index + 1, check)
for job in original['jobs']['build-rustdesk-linux']['strategy']['matrix']['job']:
    job['distro'] = 'ubuntu20.04'
linux_steps = original['jobs']['build-rustdesk-linux']['steps']
index = next(i for i, step in enumerate(linux_steps) if step.get('name') == 'Setup vcpkg with Github Actions binary cache')
linux_steps.insert(index, {
    'name': 'Install CMake for vcpkg on Linux ARM64',
    'if': "matrix.job.arch == 'aarch64' && env.UPLOAD_ARTIFACT == 'true'",
    'shell': 'bash',
    'run': 'python3 -m pip install --user "cmake==${VCPKG_CMAKE_VERSION}"\nuser_base="$(python3 -m site --user-base)"\n"${user_base}/bin/cmake" --version\necho "${user_base}/bin" >> "$GITHUB_PATH"\n',
})
for job in original['jobs'].values():
    steps = job.get('steps', [])
    index = next((i for i, step in enumerate(steps) if step.get('name') == 'Setup vcpkg with Github Actions binary cache'), None)
    if index is not None:
        setup = steps[index]
        directory = setup.pop('with').get('vcpkgDirectory', '${{ github.workspace }}/vcpkg')
        setup.pop('uses')
        setup.update({'shell': 'bash', 'env': {'EDGEDESK_VCPKG_ROOT': directory},
                      'run': 'python edgedesk/vcpkg.py bootstrap\n'})
        steps.insert(index, {
            'name': 'Use dependency baseline from release source',
            'shell': 'bash',
            'run': "python - <<'BASELINE'\nimport json\nimport os\nimport re\nfrom pathlib import Path\nmanifest = json.loads(Path('vcpkg.json').read_text())\nbaseline = manifest['vcpkg-configuration']['default-registry']['baseline']\nif not re.fullmatch('[0-9a-f]{40}', baseline):\n    raise ValueError('Invalid vcpkg baseline')\nwith open(os.environ['GITHUB_ENV'], 'a') as output:\n    output.write(f'VCPKG_COMMIT_ID={baseline}\\n')\nBASELINE\n",
        })
linux_build = next(step for step in original["jobs"]["build-rustdesk-linux"]["steps"] if step.get("name") == "Build rustdesk")
linux_build["with"]["install"] = linux_build["with"]["install"].replace("libva-dev", "libva-dev libdrm-dev")
linux_build["with"]["run"] = linux_build["with"]["run"].replace("for name in rustdesk*??.rpm", "for name in edgedesk*??.rpm")
linux_build["with"]["run"] = linux_build["with"]["run"].replace("python3 ./build.py --flutter --skip-cargo", 'python3 ./build.py --flutter --skip-cargo\n          binary=$(find /workspace/flutter/build/linux -path "*/release/bundle/edgedesk" -type f -print -quit)\n          test -n "$binary"\n          "$binary" --version | grep -F "${{ env.VERSION }}"')
mac_steps = original["jobs"]["build-for-macOS"]["steps"]
notarize = next(step for step in mac_steps if step.get('name') == 'Install rcodesign tool')
notarize['run'] = re.sub(r'wget (https://github\.com/\S+/releases/download/\S+/(\S+))',
                        lambda match: release_download(match).replace('edgedesk/vcpkg.py', '"$GITHUB_WORKSPACE/edgedesk/vcpkg.py"'),
                        notarize['run'])
mac_check = next(step for step in mac_steps if step.get("name") == "Verify macOS application identity and executable")
mac_steps.remove(mac_check)
index = next(i for i, step in enumerate(mac_steps) if step.get("name") == "Build rustdesk")
mac_steps.insert(index + 1, {'name': 'Sign development application consistently', 'shell': 'bash', 'env': {'EDGEDESK_MACOS_P12': '${{ secrets.EDGEDESK_MACOS_P12 }}', 'EDGEDESK_MACOS_P12_PASSWORD': '${{ secrets.EDGEDESK_MACOS_P12_PASSWORD }}'}, 'run': 'bash edgedesk/sign_macos.sh flutter/build/macos/Build/Products/Release/EdgeDesk.app\n'})
index = next(i for i, step in enumerate(mac_steps) if step.get("name") == "Codesign app and create signed dmg")
mac_steps.insert(index + 1, mac_check)
# Archive .app with symlinks preserved; .dmg remains available too.
mac = original['jobs']['build-for-macOS']['steps']
mac += [{'name':'Archive EdgeDesk application','shell':'bash','run':'ditto -c -k --sequesterRsrc --keepParent flutter/build/macos/Build/Products/Release/EdgeDesk.app EdgeDesk-${{ env.VERSION }}-${{ matrix.job.arch }}.app.zip'}, {'name':'Collect macOS app','uses':'actions/upload-artifact@v4','with':{'name':'package-macos-app-${{ matrix.job.arch }}','path':'EdgeDesk-*.app.zip','if-no-files-found':'error'}}]
ios = original['jobs']['build-rustdesk-ios']['steps']
for step in ios:
    if step.get('run','').find('flutter build ipa') >= 0:
        step['run'] = '''cd flutter
flutter build ios --release --no-codesign
mkdir -p build/ios/Payload
cp -R build/ios/iphoneos/Runner.app build/ios/Payload/EdgeDesk.app
cd build/ios
zip -qry ../../../EdgeDesk-${{ env.VERSION }}-ios-unsigned.ipa Payload'''
ios += [{'name':'Collect unsigned IPA','uses':'actions/upload-artifact@v4','with':{'name':'package-ios','path':'EdgeDesk-*-ios-unsigned.ipa','if-no-files-found':'error'}}]
# Avoid duplicate APK uploads; final package-* artifacts already collect the signed APK.
for name in ('build-rustdesk-android','build-rustdesk-android-universal'):
    original['jobs'][name]['steps'] = [s for s in original['jobs'][name]['steps'] if not (s.get('uses','').startswith('actions/upload-artifact@') and s.get('with',{}).get('name','').endswith('.apk'))]
for job in original['jobs'].values():
    for step in job.get('steps', []):
        dependencies = step.get('name') == 'Install vcpkg dependencies'
        if dependencies or 'edgedesk/vcpkg.py' in step.get('run', ''):
            env = step.setdefault('env', {})
            env['EDGEDESK_DOWNLOAD_TOKEN'] = '${{ github.token }}'
            if dependencies:
                env['VCPKG_KEEP_ENV_VARS'] = 'EDGEDESK_DOWNLOAD_TOKEN'
# Keep upstream patch files but disable all upstream scheduled / push build entry points.
bridge = yaml.load((wf/'bridge.yml').read_text(), Loader=Loader)
bridge['on']['workflow_call'] = {'inputs':{'source-ref':{'required':True,'type':'string'}}}
for job in bridge['jobs'].values():
    job['steps'].insert(0, mirror_step)
    for step in job.get('steps',[]):
        if step.get('uses','').startswith('actions/checkout@'):
            step.setdefault('with',{})['ref'] = '${{ inputs.source-ref }}'
        if step.get('name') == 'Install prerequisites':
            step['timeout-minutes'] = 10
        if step.get('name') == 'Run flutter rust bridge':
            step['run'] += '\ncd flutter && dart format --output=none --set-exit-if-changed lib/main.dart lib/common.dart lib/mobile/pages/settings_page.dart lib/desktop/pages/desktop_setting_page.dart || dart format lib/main.dart lib/common.dart lib/mobile/pages/settings_page.dart lib/desktop/pages/desktop_setting_page.dart\nflutter analyze --no-fatal-infos --no-fatal-warnings lib/main.dart lib/common.dart lib/mobile/pages/settings_page.dart lib/desktop/pages/desktop_setting_page.dart\n'
third = yaml.load((wf/'third-party-RustDeskTempTopMostWindow.yml').read_text(), Loader=Loader)
for job in third['jobs'].values():
    for step in job.get('steps', []):
        if step.get('uses', '').startswith('microsoft/setup-msbuild@'):
            step.setdefault('with', {})['msbuild-architecture'] = 'x64'
        if step.get('name') == 'Build the project':
            step['run'] = step['run'].replace('msbuild ${{ env.project_path }}', 'msbuild ${{ env.project_path }} /p:PreferredToolArchitecture=x64')
for value in third['on']['workflow_call']['inputs'].values():
    if value.get('required'):
        value.pop('default', None)
third = yaml.dump(third, Dumper=Dumper, sort_keys=False)
for path in wf.glob('*.yml'):
    path.unlink()
(wf/'edgedesk-build.yml').write_text(yaml.dump(original,Dumper=Dumper,sort_keys=False,width=120))
(wf/'edgedesk-bridge.yml').write_text(yaml.dump(bridge,Dumper=Dumper,sort_keys=False,width=120))
(wf/'edgedesk-topmost.yml').write_text(third)
print('Generated release-only reusable workflows')
