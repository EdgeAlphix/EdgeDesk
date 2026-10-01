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
bridgejob = original['jobs']['generate-bridge']
bridgejob['uses'] = './.github/workflows/edgedesk-bridge.yml'
bridgejob['with'] = {'source-ref': '${{ inputs.source-ref }}'}
original['jobs']['build-RustDeskTempTopMostWindow']['uses'] = './.github/workflows/edgedesk-topmost.yml'
for jobname, job in original['jobs'].items():
    if 'steps' not in job:
        continue
    job['timeout-minutes'] = 180
    steps = []
    for step in job['steps']:
        use = step.get('uses','')
        if use.startswith('actions/checkout@'):
            step.setdefault('with',{})['ref'] = '${{ inputs.source-ref }}'
        if 'run' in step:
            step['run'] = step['run'].replace('RustDesk.app', 'EdgeDesk.app').replace('com.rustdesk.RustDesk', 'com.edgealphix.desk')
        if use.startswith('softprops/action-gh-release@'):
            files = step['with'].get('files','')
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
    for step in job.get('steps',[]):
        if step.get('uses','').startswith('actions/checkout@'):
            step.setdefault('with',{})['ref'] = '${{ inputs.source-ref }}'
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
