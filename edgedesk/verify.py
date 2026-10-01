#!/usr/bin/env python3
"""Fail closed if an upstream release stops honoring EdgeDesk policy."""
from pathlib import Path
import re
import json
import ipaddress
from urllib.parse import urlparse
root = Path(__file__).resolve().parent.parent
cfg = (root/'libs/hbb_common/src/config.rs').read_text()
assert 'RwLock::new("EdgeDesk".to_owned())' in cfg
for key in ('custom-rendezvous-server','api-server','key','relay-server'):
    assert f'("{key}".into(),' in cfg
assert '("hide-server-settings".into(), "Y".into())' in cfg
assert '("enable-udp-punch".into(), "Y".into())' in cfg
assert '("enable-ipv6-punch".into(), "Y".into())' in cfg
assert '("allow-insecure-tls-fallback".into(), "N".into())' in cfg
assert '("allow-insecure-tls-fallback".into(), "Y".into())' not in cfg
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
    assert 'edgeDeskAbout(context' in t
about = (root / 'flutter/lib/common.dart').read_text()
assert 'International Computing Group, LLC' in about and 'EdgeAlphix LLC' in about and 'Anaheim, CA 92802' in about
assert "SelectableText('Anaheim, CA 92802\\nUnited States', style: valueStyle)" in about
assert 'Powered by EdgeAlphix' in about and 'Source and patches' in about
assert 'Powered by EdgeAlphix Global Network Infrastructure' in about
assert 'launchUrlString' not in about
powered = about[about.index('Widget loadPowered'):about.index('const _kDefaultLogoAsset')]
assert 'https://edgealphix.com' in powered and 'github.com' not in powered
network = json.loads((root/'edgedesk/network.json').read_text())
assert network['relay_server'] == ''
for address in (network['id_server'], network['api_server']):
    host = urlparse(address if '://' in address else '//' + address).hostname
    assert host and host.endswith('.edgedesk.edgealphix.com')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise AssertionError('Managed endpoints must use DNS names')

assert 'rustdesk.com' not in (root / 'build.py').read_text()
assert 'com.carriez' not in (root / 'flutter/linux/CMakeLists.txt').read_text()

manifest = json.loads((root / 'flatpak/rustdesk.json').read_text())
assert manifest['id'] == 'com.edgealphix.desk'
for source in manifest['modules'][-1]['sources']:
    if source.get('path', '').endswith('.xml'):
        assert (root / 'flatpak' / source['path']).is_file()
assert 'com.rustdesk.RustDesk' not in (root / '.github/workflows/edgedesk-build.yml').read_text()
build_workflow = (root / '.github/workflows/edgedesk-build.yml').read_text()
assert 'ubuntu:24.04 bash -euo pipefail' in build_workflow
assert 'flatpak flatpak-builder appstream-compose' in build_workflow
assert 'for name in rustdesk*??.rpm' not in build_workflow
assert 'distro: ubuntu18.04' not in build_workflow
assert 'distro: ubuntu20.04' in build_workflow
assert 'Start-Process -FilePath' in build_workflow and '-Wait -PassThru' in build_workflow
assert 'bash edgedesk/sign_macos.sh' in build_workflow
assert 'EDGEDESK_MACOS_P12_PASSWORD' in build_workflow
assert 'Depends: libc6 (>= 2.31)' in (root / 'build.py').read_text()
assert 'if (isMacOS) setState(() {});' in (root / 'flutter/lib/desktop/pages/desktop_home_page.dart').read_text()

# Native service management and package layouts use the same executable name.
assert 'set(BINARY_NAME "edgedesk")' in (root / 'flutter/linux/CMakeLists.txt').read_text()
assert 'ExecStart=/usr/bin/edgedesk --service' in (root / 'res/edgedesk.service').read_text()
assert '/usr/share/edgedesk/edgedesk /usr/bin/edgedesk' in (root / 'res/DEBIAN/postinst').read_text()
for name in ('edgedesk.service', 'edgedesk.desktop', 'edgedesk-link.desktop', 'pam.d/edgedesk.debian'):
    assert (root / 'res' / name).is_file()

assert (root / 'flutter/assets/logo.png').read_bytes() == (root / 'edgedesk/assets/wordmark.png').read_bytes()
assert (root / 'flutter/assets/icon.png').read_bytes() == (root / 'edgedesk/assets/icon.png').read_bytes()
assert (root / 'flutter/macos/Runner/AppIcon.icns').stat().st_size > 1000
assert 'GNU AFFERO GENERAL PUBLIC LICENSE' in (root / 'res/msi/Package/License.rtf').read_text()
assert '--app-name EdgeDesk --manufacturer "International Computing Group, LLC"' in (root / '.github/workflows/edgedesk-build.yml').read_text()
assert 'const APP_PREFIX: &str = "edgedesk";' in (root / 'libs/portable/src/main.rs').read_text()
from PIL import Image
import math
for name in ('logo.png', 'wordmark.png', 'icon.png'):
    im = Image.open(root / 'edgedesk/assets' / name)
    assert im.mode == 'RGBA' and im.getchannel('A').getextrema()[0] == 0
    bounds = im.getchannel('A').point(lambda value: 255 if value > 128 else 0).getbbox()
    assert bounds and all((bounds[0] > 0, bounds[1] > 0, bounds[2] < im.width, bounds[3] < im.height)), f'Logo has no padding: {name}'
foreground_icons = list((root / 'flutter/android/app/src/main/res').rglob('ic_launcher_foreground.png'))
assert foreground_icons
for p in foreground_icons:
    im = Image.open(p)
    assert im.mode == 'RGBA'
    assert all(math.hypot(x - im.width / 2, y - im.height / 2) <= im.width * 33 / 108 for y in range(im.height) for x in range(im.width) if im.getpixel((x, y))[3] > 128), f'Adaptive icon clipped: {p}'
assert '@drawable/edgedesk_logo' in (root / 'flutter/android/app/src/main/res/drawable/floating_window.xml').read_text()
print('EdgeDesk policy, destinations, identifiers and license checks passed')
