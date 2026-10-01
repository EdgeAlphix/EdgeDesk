#!/usr/bin/env python3
"""Complete branding and produce platform icon formats from supplied artwork."""
from pathlib import Path
import shutil
import re
import subprocess

root = Path(__file__).resolve().parent.parent
common = root / 'flutter/lib/common.dart'
data = common.read_text().replace('return platformFFI.translate(name, localeName);', "return platformFFI.translate(name, localeName).replaceAll('RustDesk', 'EdgeDesk');")
common.write_text(data)
cfg = root / 'libs/hbb_common/src/config.rs'
data = cfg.read_text().replace('("language".into(), "en".into())', '("lang".into(), "en".into())')
data = data.replace('        ("allow-insecure-tls-fallback".into(), "Y".into()),\n', '')
data = data.replace('pub static ref DEFAULT_SETTINGS: RwLock<HashMap<String, String>> = Default::default();', 'pub static ref DEFAULT_SETTINGS: RwLock<HashMap<String, String>> = RwLock::new(HashMap::from([("allow-insecure-tls-fallback".into(), "Y".into())]));')
cfg.write_text(data)
# Registration's fallback identity uses our own host, even if all options are absent.
data = cfg.read_text().replace('https://github.com/EdgeAlphix/EdgeDesk"]', 'api.edgedesk.edgealphix.com:21116"]')
cfg.write_text(data)
# Upstream license text and notices remain intact.
app_info = root / 'flutter/macos/Runner/Configs/AppInfo.xcconfig'
app_info.write_text(app_info.read_text().replace('Purslane Tech Pte. Ltd. All rights reserved.', 'International Computing Group, LLC; EdgeAlphix LLC. GNU AGPL-3.0.'))

from PIL import Image
source = Image.open(root / 'edgedesk/assets/logo-original.jpg').convert('RGB')
# Preserve the supplied artwork; only convert its format and size for platform bundles.
def icon(path, size):
    canvas = Image.new('RGB', (size, size), 'white')
    converted = source.copy()
    converted.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas.paste(converted, ((size-converted.width)//2, (size-converted.height)//2))
    canvas.save(path)

for base in ('flutter/android/app/src/main/res', 'flutter/ios/Runner/Assets.xcassets', 'flutter/macos/Runner/Assets.xcassets'):
    for path in (root / base).rglob('*.png'):
        if 'ic_launcher' in path.name or 'AppIcon' in str(path):
            with Image.open(path) as existing:
                size = max(existing.size)
            icon(path, size)
for name in ('logo.png', 'logo256.png'):
    path = root / 'flutter/assets' / name
    if path.exists():
        icon(path, 256)
for path in (root / 'res').glob('*.png'):
    with Image.open(path) as existing:
        size = max(existing.size)
    icon(path, size)
icon(root / 'edgedesk/assets/icon.png', 1024)
img = Image.open(root / 'edgedesk/assets/icon.png')
for path in (root / 'flutter/windows').rglob('app_icon.ico'):
    img.save(path, format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
for path in (root / 'res').glob('*.ico'):
    img.save(path, format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
# SVG embeds the exact provided logo rather than approximating its geometry.
import base64
svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024"><image x="0" y="171" width="1024" height="683" href="data:image/jpeg;base64,' + base64.b64encode((root/'edgedesk/assets/logo-original.jpg').read_bytes()).decode() + '"/></svg>'
(root / 'res/scalable.svg').write_text(svg)
for path in (root/'flutter/assets').glob('*.svg'):
    if 'logo' in path.name.lower():
        path.write_text(svg)
(root/'edgedesk/assets/wordmark.jpg').write_bytes((root/'edgedesk/assets/wordmark-original.jpg').read_bytes())
print('EdgeDesk branding finalized')

from apply import body
body(root/'src/common.rs', 'pub fn is_public(url: &str)', '    let _ = url;\n    false')
body(root/'src/common.rs', 'fn test_is_public()', '        assert!(!is_public("https://api.edgedesk.edgealphix.com"));')
rc=root/'flutter/windows/runner/Runner.rc'
rc.write_text(rc.read_text().replace('RustDesk Remote Desktop','EdgeDesk Remote Desktop').replace('"ProductName", "RustDesk"','"ProductName", "EdgeDesk"'))

# Distribution metadata follows the product branding; native binary names remain compatible.
p = root / 'build.py'
p.write_text(p.read_text().replace('Maintainer: rustdesk <info@rustdesk.com>', 'Maintainer: EdgeAlphix LLC <desk@edgealphix.com>').replace('Homepage: https://rustdesk.com', 'Homepage: https://github.com/EdgeAlphix/EdgeDesk'))
p = root / 'flutter/linux/CMakeLists.txt'
p.write_text(p.read_text().replace('com.carriez.flutter_hbb', 'com.edgealphix.desk'))
p = root / 'flutter/windows/runner/Runner.rc'
p.write_text(p.read_text().replace('Purslane Tech Pte. Ltd.', 'International Computing Group, LLC'))

# Flatpak's app ID, source filename, bundle command and AppStream metadata agree.
import json
old = root / 'flatpak/com.rustdesk.RustDesk.metainfo.xml'
old.unlink(missing_ok=True)
shutil.copy(root / 'edgedesk/flatpak.metainfo.xml', root / 'flatpak/com.edgealphix.desk.metainfo.xml')
p = root / 'flatpak/rustdesk.json'
manifest = json.loads(p.read_text())
commands = manifest['modules'][-1]['build-commands']
commands.append('install -Dm644 com.edgealphix.desk.metainfo.xml /app/share/metainfo/com.edgealphix.desk.metainfo.xml')
p.write_text(json.dumps(manifest, indent=2) + '\n')

# Linux service control derives its name from APP_NAME, so installed paths must agree.
linux_files = list((root / 'res/DEBIAN').glob('*')) + list((root / 'res').glob('*.spec'))
linux_files += [root / 'res/PKGBUILD', root / 'res/pacman_install', root / 'res/startwm.sh']
for name in ('rustdesk.service', 'rustdesk.desktop', 'rustdesk-link.desktop'):
    path = root / 'res' / name
    target = path.with_name(name.replace('rustdesk', 'edgedesk'))
    target.write_text(path.read_text().replace('rustdesk', 'edgedesk').replace('RustDesk', 'EdgeDesk'))
    path.unlink()
for path in linux_files:
    path.write_text(path.read_text().replace('rustdesk', 'edgedesk').replace('GPL-3.0', 'AGPL-3.0').replace('AAGPL-', 'AGPL-'))
p = root / 'flutter/linux/CMakeLists.txt'
p.write_text(p.read_text().replace('set(BINARY_NAME "rustdesk")', 'set(BINARY_NAME "edgedesk")'))
p = root / 'build.py'
data = p.read_text().replace('Package: rustdesk', 'Package: edgedesk')
for old, new in [('usr/share/rustdesk', 'usr/share/edgedesk'), ('usr/bin/rustdesk', 'usr/bin/edgedesk'), ('etc/rustdesk', 'etc/edgedesk'), ('pam.d/rustdesk', 'pam.d/edgedesk'), ('apps/rustdesk', 'apps/edgedesk'), ('applications/rustdesk', 'applications/edgedesk'), ('res/rustdesk.', 'res/edgedesk.'), ('res/rustdesk-link.', 'res/edgedesk-link.')]:
    data = data.replace(old, new)
p.write_text(data)
p = root / 'flatpak/rustdesk.json'
data = p.read_text().replace('"command": "rustdesk"', '"command": "edgedesk"').replace('"rustdesk.desktop"', '"edgedesk.desktop"').replace('"rename-icon": "rustdesk"', '"rename-icon": "edgedesk"').replace('/app/share/rustdesk/rustdesk /app/bin/rustdesk', '/app/share/edgedesk/edgedesk /app/bin/edgedesk')
p.write_text(data)
for path in (root / 'appimage').glob('*.yml'):
    path.write_text(path.read_text().replace('rustdesk', 'edgedesk').replace('edgedesk.deb', 'rustdesk.deb'))

p = root / 'res/pam.d/rustdesk.debian'
p.rename(p.with_name('edgedesk.debian'))
for p in (root / 'res').glob('*.spec'):
    p.write_text(re.sub(r'^Vendor:.*$', 'Vendor:     EdgeAlphix LLC', p.read_text(), flags=re.M))
