#!/usr/bin/env python3
"""Complete branding and produce platform icon formats from supplied artwork."""
from pathlib import Path
import shutil
import re
import subprocess

root = Path(__file__).resolve().parent.parent
common = root / 'flutter/lib/common.dart'
data = common.read_text().replace('return platformFFI.translate(name, localeName);', "return platformFFI.translate(name, localeName).replaceAll('RustDesk', 'EdgeDesk');")
data = data.replace('translate("powered_by_me")', "'Powered by EdgeAlphix'")
powered_start = data.index('Widget loadPowered(BuildContext context)')
powered_end = data.index('const _kDefaultLogoAsset', powered_start)
data = data[:powered_start] + data[powered_start:powered_end].replace('https://github.com/EdgeAlphix/EdgeDesk', 'https://edgealphix.com') + data[powered_end:]
data = data.replace('child: image,\n          ).marginOnly', '''child: Theme.of(context).brightness == Brightness.dark
                ? ColorFiltered(
                    colorFilter: const ColorFilter.mode(Colors.white, BlendMode.srcIn),
                    child: image,
                  )
                : image,
          ).marginOnly''')
data += '''
Widget edgeDeskCompanyInfo(BuildContext context) {
  final labelStyle = Theme.of(context).textTheme.bodySmall;
  final valueStyle = Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w500);
  return Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    mainAxisSize: MainAxisSize.min,
    children: [
      Text('Software owner', style: labelStyle),
      const SizedBox(height: 4),
      SelectableText('International Computing Group, LLC', style: valueStyle),
      const SizedBox(height: 16),
      Text('Operator', style: labelStyle),
      const SizedBox(height: 4),
      SelectableText('EdgeAlphix LLC', style: valueStyle),
      const SizedBox(height: 16),
      Text('Address', style: labelStyle),
      const SizedBox(height: 4),
      SelectableText('Anaheim, CA 92802\\nUnited States', style: valueStyle),
    ],
  );
}

Widget edgeDeskAbout(BuildContext context,
    {required String version, String? buildDate}) {
  final theme = Theme.of(context);
  return Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    mainAxisSize: MainAxisSize.min,
    children: [
      Row(children: [
        loadIcon(56),
        const SizedBox(width: 16),
        Expanded(child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('EdgeDesk', style: theme.textTheme.headlineSmall),
            const SizedBox(height: 4),
            Text('Version $version', style: theme.textTheme.bodyMedium),
            if (buildDate != null)
              Text('Built $buildDate', style: theme.textTheme.bodySmall),
          ],
        )),
      ]),
      const Divider(height: 40),
      Text('Company', style: theme.textTheme.titleMedium),
      const SizedBox(height: 16),
      edgeDeskCompanyInfo(context),
      const Divider(height: 40),
      Text('Open source', style: theme.textTheme.titleMedium),
      const SizedBox(height: 8),
      const Text('Based on RustDesk, licensed under GNU AGPL-3.0.\\nEdgeDesk modifications are available under the same license.'),
      const SizedBox(height: 8),
      Wrap(spacing: 8, children: [
        TextButton(onPressed: () => showLicensePage(context: context,
          applicationName: 'EdgeDesk'), child: const Text('Open Source Licenses')),
        TextButton(onPressed: () => launchUrlString('https://github.com/EdgeAlphix/EdgeDesk'),
          child: const Text('Source and patches')),
        TextButton(onPressed: () => launchUrlString('https://edgealphix.com'),
          child: const Text('EdgeAlphix website')),
      ]),
    ],
  );
}
'''
common.write_text(data)
p = root / 'flutter/lib/desktop/widgets/tabbar_widget.dart'
p.write_text(p.read_text().replace('"RustDesk",', '"EdgeDesk",'))
cfg = root / 'libs/hbb_common/src/config.rs'
data = cfg.read_text().replace('("language".into(), "en".into())', '("lang".into(), "en".into())')
data = data.replace('pub static ref DEFAULT_SETTINGS: RwLock<HashMap<String, String>> = Default::default();', 'pub static ref DEFAULT_SETTINGS: RwLock<HashMap<String, String>> = RwLock::new(HashMap::from([("allow-insecure-tls-fallback".into(), "N".into())]));')
cfg.write_text(data)
# Registration's fallback identity uses our own host, even if all options are absent.
data = cfg.read_text().replace('https://github.com/EdgeAlphix/EdgeDesk"]', 'api.edgedesk.edgealphix.com:21116"]')
cfg.write_text(data)
# Upstream license text and notices remain intact.
app_info = root / 'flutter/macos/Runner/Configs/AppInfo.xcconfig'
app_info.write_text(app_info.read_text().replace('Purslane Tech Pte. Ltd. All rights reserved.', 'International Computing Group, LLC; EdgeAlphix LLC. GNU AGPL-3.0.'))

from PIL import Image, ImageOps
def crop_artwork(path):
    image = Image.open(path).convert('RGBA')
    bounds = image.getchannel('A').point(lambda value: 255 if value > 128 else 0).getbbox()
    if bounds is None:
        raise ValueError(f'No artwork found: {path}')
    left, top, right, bottom = bounds
    return ImageOps.expand(image.crop((left, top, right, bottom)), border=max(2, round((bottom - top) * 0.06)))

source = crop_artwork(root / 'edgedesk/assets/logo-transparent.png')
source.save(root / 'edgedesk/assets/logo.png')
wordmark = crop_artwork(root / 'edgedesk/assets/wordmark-transparent.png')
wordmark.save(root / 'edgedesk/assets/wordmark.png')
# Crop the white margins without changing the supplied artwork.
def icon(path, size, opaque=False):
    canvas = Image.new('RGBA', (size, size), 'white' if opaque else (0, 0, 0, 0))
    converted = ImageOps.contain(source, (round(size * 0.82), round(size * 0.82)), Image.Resampling.LANCZOS)
    canvas.alpha_composite(converted, ((size-converted.width)//2, (size-converted.height)//2))
    if opaque:
        canvas = canvas.convert('RGB')
    canvas.save(path)

for base in ('flutter/android/app/src/main/res', 'flutter/ios/Runner/Assets.xcassets', 'flutter/macos/Runner/Assets.xcassets'):
    for path in (root / base).rglob('*.png'):
        if 'ic_launcher' in path.name or 'AppIcon' in str(path):
            with Image.open(path) as existing:
                size = max(existing.size)
            icon(path, size, opaque='flutter/ios/' in str(path) or 'flutter/android/' in str(path))
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
svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{source.width}" height="{source.height}" viewBox="0 0 {source.width} {source.height}"><image width="{source.width}" height="{source.height}" href="data:image/png;base64,' + base64.b64encode((root/'edgedesk/assets/logo.png').read_bytes()).decode() + '"/></svg>'
(root / 'res/scalable.svg').write_text(svg)
for path in (root/'flutter/assets').glob('*.svg'):
    if 'logo' in path.name.lower():
        path.write_text(svg)
(root / 'edgedesk/assets/wordmark.jpg').unlink(missing_ok=True)
print('EdgeDesk branding finalized')

from apply import body
desktop = root / 'flutter/lib/desktop/pages/desktop_setting_page.dart'
data = desktop.read_text()
start = data.index('class _AboutState extends State<_About>')
end = data.index('//#endregion', start)
data = data[:start] + '''class _AboutState extends State<_About> {
  @override
  Widget build(BuildContext context) {
    return futureBuilder(future: () async {
      return {
        'version': await bind.mainGetVersion(),
        'buildDate': await bind.mainGetBuildDate(),
      };
    }(), hasData: (data) {
      return SingleChildScrollView(
        child: _Card(title: 'About EdgeDesk', children: [
          Padding(
            padding: const EdgeInsets.all(24),
            child: edgeDeskAbout(context,
              version: data['version'].toString(),
              buildDate: data['buildDate'].toString()),
          ),
        ]),
      );
    });
  }
}

''' + data[end:]
desktop.write_text(data)
mobile = root / 'flutter/lib/mobile/pages/settings_page.dart'
data = mobile.read_text()
start = data.index('        SettingsSection(\n          title: Text(translate("About")),')
end = data.index('      ],\n    );\n    return settings;', start)
data = data[:start] + '''        SettingsSection(
          title: const Text('About'),
          tiles: [
            SettingsTile(
              title: const Text('EdgeDesk'),
              description: Text('Version $version'),
              leading: loadIcon(32),
              onPressed: (context) => showAbout(gFFI.dialogManager),
            ),
          ],
        ),
''' + data[end:]
mobile.write_text(data)
body(root / 'flutter/lib/mobile/pages/settings_page.dart',
     'void showAbout(OverlayDialogManager dialogManager)', '''  dialogManager.show((setState, close, context) {
    return CustomAlertDialog(
      title: const Text('About EdgeDesk'),
      content: SingleChildScrollView(
        child: edgeDeskAbout(context, version: version),
      ),
      actions: [],
    );
  }, clickMaskDismiss: true, backDismiss: true);''')
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

# Runtime header artwork and native macOS icon use the same cropped originals.
shutil.copy(root / 'edgedesk/assets/wordmark.png', root / 'flutter/assets/logo.png')
shutil.copy(root / 'edgedesk/assets/icon.png', root / 'flutter/assets/icon.png')
(root / 'flutter/assets/icon.svg').write_text(svg)
img.save(root / 'flutter/macos/Runner/AppIcon.icns', format='ICNS')
# Adaptive icons use a transparent foreground inside Android's circular safe zone.
import math
foreground = source.convert('RGBA')
cx, cy = foreground.width / 2, foreground.height / 2
radius = max(math.hypot(x - cx, y - cy) for y in range(foreground.height) for x in range(foreground.width) if foreground.getpixel((x, y))[3])
for p in (root / 'flutter/android/app/src/main/res').rglob('ic_launcher_foreground.png'):
    with Image.open(p) as existing:
        size = existing.width
    scale = size * 32 / 108 / radius
    artwork = foreground.resize((round(foreground.width * scale), round(foreground.height * scale)), Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', (size, size))
    canvas.paste(artwork, ((size - artwork.width) // 2, (size - artwork.height) // 2))
    canvas.save(p)
icon(root / 'flutter/android/app/src/main/res/drawable/edgedesk_logo.png', 128)
(root / 'flutter/android/app/src/main/res/drawable/floating_window.xml').write_text('<?xml version="1.0" encoding="utf-8"?>\n<bitmap xmlns:android="http://schemas.android.com/apk/res/android" android:src="@drawable/edgedesk_logo" android:gravity="fill" />\n')
for base in ('flutter/android', 'flutter/ios', 'flutter/macos'):
    for p in (root / base).rglob('*'):
        if p.is_file() and p.suffix in {'.xml', '.plist'}:
            p.write_text(p.read_text().replace('android:scheme="rustdesk"', 'android:scheme="edgedesk"').replace('<string>rustdesk</string>', '<string>edgedesk</string>'))

# MSI uses upstream's custom-product support so its service matches APP_NAME.
p = root / 'res/msi/preprocess.py'
p.write_text(p.read_text().replace('https://github.com/rustdesk/rustdesk', 'https://github.com/EdgeAlphix/EdgeDesk'))
license_text = (root / 'LICENCE').read_text()
rtf = license_text.replace('\\', '\\\\').replace('{', '\\{').replace('}', '\\}').replace('\n', '\\par\n')
(root / 'res/msi/Package/License.rtf').write_text('{\\rtf1\\ansi\\deff0 {\\fonttbl {\\f0 Arial;}}\\f0\\fs18\n' + rtf + '\n}')
p = root / 'libs/portable/src/main.rs'
p.write_text(p.read_text().replace('const APP_PREFIX: &str = "rustdesk";', 'const APP_PREFIX: &str = "edgedesk";'))
