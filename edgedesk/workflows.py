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
for key in ('build-for-windows-sciter','build-rustdesk-linux-sciter','build-rustdesk-web','publish_unsigned'):
    original['jobs'].pop(key, None)
flatpak = original['jobs']['build-flatpak']
flatpak['needs'] = ['build-rustdesk-linux']
flatpak['strategy']['matrix']['job'] = [j for j in flatpak['strategy']['matrix']['job'] if not j.get('suffix')]
for step in flatpak['steps']:
    if step.get('id') == 'flatpak':
        commands = step['with']['run'].replace('pushd /workspace\n', '')
        step.clear()
        step.update({'name': 'Build Flatpak with SDK-compatible builder', 'shell': 'bash', 'run': '''docker run --rm --privileged --device /dev/fuse --volume "$PWD:/workspace" --workdir /workspace ubuntu:24.04 bash -euo pipefail <<'FLATPAK'
apt-get update -y
apt-get install -y git flatpak flatpak-builder appstream-compose
dpkg --compare-versions "$(dpkg-query -W -f='${Version}' flatpak-builder)" ge 1.4.0
''' + commands + '\nFLATPAK\n'})
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
checks = {'build-for-windows-flutter': {'name': 'Verify Windows executable starts', 'shell': 'pwsh', 'run': '$version = & ./rustdesk/rustdesk.exe --version\nif ($LASTEXITCODE -ne 0 -or "$version" -notmatch [regex]::Escape("${{ env.VERSION }}")) { throw "EdgeDesk executable failed to report its version: $version" }\n'}, 'build-for-macOS': {'name': 'Verify macOS application identity and executable', 'shell': 'bash', 'run': 'app=flutter/build/macos/Build/Products/Release/EdgeDesk.app\ntest "$(/usr/libexec/PlistBuddy -c \'Print CFBundleIdentifier\' "$app/Contents/Info.plist")" = com.edgealphix.desk\n"$app/Contents/MacOS/EdgeDesk" --version | grep -F "${{ env.VERSION }}"\n'}}
for name, check in checks.items():
    steps = original["jobs"][name]["steps"]
    index = next(i for i, step in enumerate(steps) if step.get("name") == "Build rustdesk")
    steps.insert(index + 1, check)
linux_build = next(step for step in original["jobs"]["build-rustdesk-linux"]["steps"] if step.get("name") == "Build rustdesk")
linux_build["with"]["run"] = linux_build["with"]["run"].replace("python3 ./build.py --flutter --skip-cargo", 'python3 ./build.py --flutter --skip-cargo\n          binary=$(find /workspace/flutter/build/linux -path "*/release/bundle/edgedesk" -type f -print -quit)\n          test -n "$binary"\n          "$binary" --version | grep -F "${{ env.VERSION }}"')
mac_steps = original["jobs"]["build-for-macOS"]["steps"]
mac_check = next(step for step in mac_steps if step.get("name") == "Verify macOS application identity and executable")
mac_steps.remove(mac_check)
index = next(i for i, step in enumerate(mac_steps) if step.get("name") == "Build rustdesk")
mac_steps.insert(index + 1, {'name': 'Sign development application consistently', 'shell': 'bash', 'run': 'codesign --force --deep --sign - --entitlements flutter/macos/Runner/Release.entitlements flutter/build/macos/Build/Products/Release/EdgeDesk.app\ncodesign --verify --deep --strict flutter/build/macos/Build/Products/Release/EdgeDesk.app\n'})
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
