#!/usr/bin/env python3
"""Apply the EdgeDesk overlay to an unmodified, released RustDesk checkout."""
import argparse
import json
import re
from pathlib import Path

ID_SERVER = 'api.edgedesk.edgealphix.com:21116'
API_SERVER = 'https://api.edgedesk.edgealphix.com'
PUBLIC_KEY = 'YuYD7E0GMg76D1xz9wb2t0UT46g3qR2ugjAsDFTGuSw='
SOURCE = 'https://github.com/EdgeAlphix/EdgeDesk'


def replace(path, old, new):
    data = path.read_text()
    if old not in data:
        raise RuntimeError(f'Upstream changed: {path}: {old[:80]}')
    path.write_text(data.replace(old, new))


def body(path, signature, replacement):
    data = path.read_text()
    start = data.index(signature)
    opening = data.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (data[end] == '{') - (data[end] == '}')
        end += 1
    path.write_text(data[:opening + 1] + '\n' + replacement + '\n' + data[end - 1:])


def apply(root):
    cfg = root / 'libs/hbb_common/src/config.rs'
    replace(cfg, 'RwLock::new("RustDesk".to_owned())', 'RwLock::new("EdgeDesk".to_owned())')
    replace(cfg, 'RwLock::new("com.carriez".to_owned())', 'RwLock::new("com.edgealphix".to_owned())')
    replace(cfg, 'pub static ref OVERWRITE_SETTINGS: RwLock<HashMap<String, String>> = Default::default();', '''pub static ref OVERWRITE_SETTINGS: RwLock<HashMap<String, String>> = RwLock::new(HashMap::from([
        ("custom-rendezvous-server".into(), "api.edgedesk.edgealphix.com:21116".into()),
        ("api-server".into(), "https://api.edgedesk.edgealphix.com".into()),
        ("key".into(), "YuYD7E0GMg76D1xz9wb2t0UT46g3qR2ugjAsDFTGuSw=".into()),
        ("relay-server".into(), "".into()),
    ]));''')
    replace(cfg, 'pub static ref DEFAULT_LOCAL_SETTINGS: RwLock<HashMap<String, String>> = Default::default();', '''pub static ref DEFAULT_LOCAL_SETTINGS: RwLock<HashMap<String, String>> = RwLock::new(HashMap::from([
        ("enable-udp-punch".into(), "Y".into()),
        ("enable-ipv6-punch".into(), "Y".into()),
        ("language".into(), "en".into()),
    ]));''')
    replace(cfg, 'pub static ref BUILTIN_SETTINGS: RwLock<HashMap<String, String>> = Default::default();', '''pub static ref BUILTIN_SETTINGS: RwLock<HashMap<String, String>> = RwLock::new(HashMap::from([
        ("hide-server-settings".into(), "Y".into()),
        ("allow-deep-link-server-settings".into(), "N".into()),
        ("allow-websocket".into(), "N".into()),
    ]));''')
    replace(cfg, 'pub const RS_PUB_KEY: &str = "OeVuKk5nlHiXp+APNn0Y3pC1Iwpwn44JGqrQCsWqmBw=";', f'pub const RS_PUB_KEY: &str = "{PUBLIC_KEY}";')
    body(cfg, 'pub fn get_rendezvous_server() -> String', f'        "{ID_SERVER}".to_owned()')
    body(cfg, 'pub fn get_rendezvous_servers() -> Vec<String>', f'        vec!["{ID_SERVER}".to_owned()]')
    common = root / 'src/common.rs'
    body(common, 'pub fn load_custom_client()', '    // EdgeDesk configuration is compiled into the client.')
    body(common, 'pub fn read_custom_client(config: &str)', '    let _ = config;\n    // External vendor configuration cannot override EdgeDesk settings.')
    body(common, 'pub fn check_software_update()', '    // Releases are published with corresponding source on GitHub; no device telemetry.')
    body(common, 'pub async fn do_check_software_update()', '    Ok(())')
    body(common, 'pub fn get_custom_rendezvous_server(custom: String)', f'    let _ = custom;\n    "{ID_SERVER}".to_owned()')
    body(common, 'fn get_api_server_(api: String, custom: String)', f'    let _ = (api, custom);\n    "{API_SERVER}".to_owned()')
    body(common, 'pub async fn get_rendezvous_server(ms_timeout: u64)', f'    let _ = ms_timeout;\n    ("{ID_SERVER}".to_owned(), Vec::new(), true)')
    body(root / 'src/ui_interface.rs', 'pub fn get_license()', '    "RustDesk: GNU AGPL-3.0\\nEdgeDesk modifications: GNU AGPL-3.0\\nCorresponding source and patches: https://github.com/EdgeAlphix/EdgeDesk".to_owned()')
    body(root / 'libs/hbb_common/src/lib.rs', 'pub fn version_check_request(typ: String)', '    (VersionCheckRequest { typ, ..Default::default() }, "".to_owned())')
    client = root / 'src/client.rs'
    replace(client, 'let other_server = interface.get_lch().read().unwrap().other_server.clone();', '''let other_server = interface.get_lch().read().unwrap().other_server.clone();
        if other_server.is_some() {
            bail!("EdgeDesk only supports its managed ID server");
        }''')
    # Package identifiers must match Kotlin class lookup and Apple bundle metadata.
    for base in ('flutter/android', 'flutter/ios', 'flutter/macos'):
        for path in (root / base).rglob('*'):
            if path.is_file() and path.suffix in {'.kt', '.java', '.xml', '.gradle', '.plist', '.pbxproj', '.xcconfig', '.xib', '.swift', '.entitlements', '.json'}:
                data = path.read_text()
                data = data.replace('com.carriez.flutter_hbb', 'com.edgealphix.desk').replace('com.carriez.flutterHbb', 'com.edgealphix.desk').replace('com.carriez.rustdesk', 'com.edgealphix.desk')
                data = data.replace('RustDesk', 'EdgeDesk')
                path.write_text(data)
    # Keep native library names and JNI symbols stable; only package-class paths change.
    for path in (root / 'libs').rglob('*.rs'):
        if '.git' not in path.parts:
            data = path.read_text().replace('com/carriez/flutter_hbb', 'com/edgealphix/desk')
            path.write_text(data)
    for path in (root / 'src').rglob('*.rs'):
        data = path.read_text().replace('com/carriez/flutter_hbb', 'com/edgealphix/desk')
        path.write_text(data)
    for path in (root / 'flutter/lib').rglob('*.dart'):
        data = path.read_text()
        # Preserve upstream translation lookup keys, but rename their rendered values centrally.
        data = data.replace('rustdesk://', 'edgedesk://')
        path.write_text(data)
    dart = root / 'flutter/lib/common.dart'
    data = dart.read_text()
    match = re.search(r'String translate\([^\n]+', data)
    if not match:
        raise RuntimeError('Could not find translation entry point')
    # Exact translation entry point is patched separately after its signature is checked.
    mobile = root / 'flutter/lib/mobile/pages/settings_page.dart'
    replace(mobile, "tiles: [\n            SettingsTile(\n                onPressed: (context) async {\n                  await launchUrl(Uri.parse(url));", "tiles: [\n            SettingsTile(title: edgeDeskCompanyInfo(context), leading: const Icon(Icons.business)),\n            SettingsTile(title: const Text('Open Source Licenses'), leading: const Icon(Icons.code), onPressed: (context) => showLicensePage(context: context, applicationName: 'EdgeDesk')),\n            SettingsTile(title: const Text('Source and patches (AGPL-3.0)'), leading: const Icon(Icons.source), onPressed: (context) => launchUrlString('" + SOURCE + "')),\n            SettingsTile(\n                onPressed: (context) async {\n                  await launchUrl(Uri.parse(url));")
    replace(mobile, "Text('Version: $version'),", "Text('Version: $version'),\n        edgeDeskCompanyInfo(context),\n        const Text('RustDesk and EdgeDesk modifications: GNU AGPL-3.0'),\n        InkWell(onTap: () => launchUrlString('" + SOURCE + "'), child: const Text('Source and patches')),")
    desktop = root / 'flutter/lib/desktop/pages/desktop_setting_page.dart'
    replace(desktop, "child: _Card(title: translate('About RustDesk'), children: [", "child: _Card(title: translate('About RustDesk'), children: [\n          edgeDeskCompanyInfo(context).marginOnly(bottom: 16),\n          TextButton(onPressed: () => showLicensePage(context: context, applicationName: 'EdgeDesk'), child: const Text('Open Source Licenses')),\n          TextButton(onPressed: () => launchUrlString('" + SOURCE + "'), child: const Text('Source and patches (AGPL-3.0)')),")
    # Disable all runtime rustdesk.com destinations, including documentation links.
    for base in ('src', 'libs/hbb_common/src', 'flutter/lib', 'res'):
        for path in (root / base).rglob('*'):
            if path.is_file() and path.suffix in {'.rs', '.dart', '.tis', '.xml', '.plist', '.desktop', '.spec', '.txt', '.html'}:
                data = path.read_text()
                data = re.sub(r'(?:https?://)?(?:[\w-]+\.)*rustdesk\.com(?:/[^\s\"\'<>)]*)?', SOURCE, data)
                path.write_text(data)
    replace(root / 'build.py', 'RustDesk.app', 'EdgeDesk.app')
    replace(root / 'build.py', 'RustDesk Installer', 'EdgeDesk Installer')
    for path in (root / 'res').glob('*.desktop'):
        path.write_text(path.read_text().replace('Name=RustDesk', 'Name=EdgeDesk'))
    for path in (root / 'flatpak').rglob('*'):
        if path.is_file() and path.suffix in {'.json', '.xml'}:
            path.write_text(path.read_text().replace('com.rustdesk.RustDesk', 'com.edgealphix.desk').replace('>RustDesk<', '>EdgeDesk<'))
    # The original Firebase configuration is unused; remove its Xcode resource references too.
    firebase = root / 'flutter/ios/Runner/GoogleService-Info.plist'
    firebase.unlink(missing_ok=True)
    xcode = root / 'flutter/ios/Runner.xcodeproj/project.pbxproj'
    xcode.write_text('\n'.join(line for line in xcode.read_text().splitlines() if 'GoogleService-Info.plist' not in line) + '\n')
    for path in (root / 'flutter').glob('pubspec*.yaml'):
        path.write_text('\n'.join(line for line in path.read_text().splitlines() if 'firebase' not in line.lower()) + '\n')
    license_text = (root / 'LICENCE').read_text() if (root / 'LICENCE').exists() else (root / 'LICENSE').read_text()
    (root / 'flutter/assets/edgedesk-agpl.txt').write_text('RustDesk and EdgeDesk modifications are licensed under GNU AGPL-3.0.\nSource: ' + SOURCE + '\n\n' + license_text)
    pubspec = root / 'flutter/pubspec.yaml'
    replace(pubspec, '  assets:', '  assets:\n    - assets/edgedesk-agpl.txt')
    main = root / 'flutter/lib/main.dart'
    data = main.read_text()
    if "package:flutter/services.dart" not in data:
        data = "import 'package:flutter/services.dart';\n" + data
    if "package:flutter/foundation.dart" not in data:
        data = "import 'package:flutter/foundation.dart';\n" + data
    opening = data.index('{', data.index('void main(')) if 'void main(' in data else data.index('{', data.index('Future<void> main('))
    data = data[:opening+1] + "\n  LicenseRegistry.addLicense(() async* {\n    yield LicenseEntryWithLineBreaks(['RustDesk', 'EdgeDesk'], await rootBundle.loadString('assets/edgedesk-agpl.txt'));\n  });\n" + data[opening+1:]
    main.write_text(data)
    (root / 'edgedesk/network.json').write_text(json.dumps({'id_server': ID_SERVER, 'api_server': API_SERVER, 'key': PUBLIC_KEY, 'relay_server': '', 'source': SOURCE}, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', nargs='?', default='.')
    apply(Path(parser.parse_args().root).resolve())
