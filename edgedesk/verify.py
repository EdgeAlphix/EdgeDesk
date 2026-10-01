#!/usr/bin/env python3
"""Fail closed if an upstream release stops honoring EdgeDesk policy."""
from pathlib import Path
import re
import json
root = Path(__file__).resolve().parent.parent
cfg = (root/'libs/hbb_common/src/config.rs').read_text()
assert 'RwLock::new("EdgeDesk".to_owned())' in cfg
for key in ('custom-rendezvous-server','api-server','key','relay-server'):
    assert f'("{key}".into(),' in cfg
assert '("hide-server-settings".into(), "Y".into())' in cfg
assert '("enable-udp-punch".into(), "Y".into())' in cfg
assert '("enable-ipv6-punch".into(), "Y".into())' in cfg
assert '("allow-insecure-tls-fallback".into(), "Y".into())' in cfg
assert 'get_rendezvous_server() -> String {\n        "api.edgedesk.edgealphix.com:21116".to_owned()' in cfg
common=(root/'src/common.rs').read_text()
assert 'pub async fn do_check_software_update() {\n    Ok(())' not in common
assert '// Releases are published with corresponding source on GitHub; no device telemetry.' in common
assert 'External vendor configuration cannot override EdgeDesk settings.' in common
assert 'EdgeDesk only supports its managed ID server' in (root/'src/client.rs').read_text()
for base in ('src','libs/hbb_common/src','flutter/lib'):
    for p in (root/base).rglob('*'):
        if p.is_file() and p.suffix in ('.rs','.dart'):
            assert not re.search(r'(?:[\w-]+\.)*rustdesk\.com',p.read_text()), f'Vendor destination: {p}'
for base in ('flutter/android','flutter/ios','flutter/macos'):
    files=[p for p in (root/base).rglob('*') if p.is_file() and p.suffix in ('.plist','.pbxproj','.gradle','.xml','.xcconfig','.kt')]
    assert any('com.edgealphix.desk' in p.read_text() for p in files)
    assert all('com.carriez.' not in p.read_text() for p in files)
assert not (root/'flutter/ios/Runner/GoogleService-Info.plist').exists()
assert (root/'flutter/assets/edgedesk-agpl.txt').exists()
assert 'LicenseRegistry.addLicense' in (root/'flutter/lib/main.dart').read_text()
for p in ('flutter/lib/mobile/pages/settings_page.dart','flutter/lib/desktop/pages/desktop_setting_page.dart'):
    t=(root/p).read_text()
    assert 'International Computing Group, LLC' in t and 'EdgeAlphix LLC' in t and 'Anaheim, CA 92802' in t
    assert 'Source and patches' in t
assert json.loads((root/'edgedesk/network.json').read_text())['relay_server']==''
print('EdgeDesk policy, destinations, identifiers and license checks passed')
