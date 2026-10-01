#!/usr/bin/env python3
"""Publish installers together with matching AGPL source, patches and checksums."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

root=Path(__file__).resolve().parent.parent
out=root/'release-packages'
version=os.environ['VERSION']
for path in list(out.iterdir()):
    if path.is_file() and path.name.startswith('rustdesk-'):
        name=path.name.replace('rustdesk-', 'EdgeDesk-',1).replace('-signed.apk','.apk').replace('-aligned.apk','.apk')
        path.rename(out/name)
required=('.apk','.ipa','.app.zip','.exe','.deb','.rpm','-suse.rpm','.pkg.tar.zst','.AppImage','.flatpak')
for suffix in required:
    assert any(p.name.endswith(suffix) for p in out.iterdir()), f'Missing requested release format: {suffix}'
archive=out/f'EdgeDesk-{version}-source.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
    for entry in root.iterdir():
        if entry.name not in ('.git','release-packages','target','__pycache__'):
            tar.add(entry,arcname=f'EdgeDesk-{version}/{entry.name}',filter=lambda info: None if '/.git/' in info.name or '/__pycache__/' in info.name else info)
shutil.copy(root/'edgedesk/patches/client.patch',out/f'EdgeDesk-{version}-client.patch')
shutil.copy(root/'edgedesk/patches/hbb-common.patch',out/f'EdgeDesk-{version}-hbb-common.patch')
shutil.copy(root/'edgedesk/upstream.json',out/f'EdgeDesk-{version}-upstream.json')
deb=next(p for p in out.iterdir() if p.name.endswith('-x86_64.deb'))
sha=hashlib.sha256(deb.read_bytes()).hexdigest()
nix=f'''{{ pkgs ? import <nixpkgs> {{}} }}:
pkgs.stdenv.mkDerivation {{
  pname = "edgedesk";
  version = "{version}";
  src = pkgs.fetchurl {{
    url = "https://github.com/EdgeAlphix/EdgeDesk/releases/download/v{version}-edgedesk.1/{deb.name}";
    sha256 = "{sha}";
  }};
  nativeBuildInputs = with pkgs; [ autoPatchelfHook dpkg makeWrapper ];
  buildInputs = with pkgs; [ gtk3 glib libGL alsa-lib libpulseaudio libva libvdpau libappindicator-gtk3 libnotify pam stdenv.cc.cc.lib xorg.libX11 xorg.libXfixes xorg.libXrandr xorg.libXtst xorg.libXcursor xorg.libXi xorg.libxcb xorg.libXext xdotool gst_all_1.gstreamer gst_all_1.gst-plugins-base gst_all_1.gst-plugins-good ];
  unpackPhase = "dpkg-deb -x $src .";
  installPhase = \'\'
    mkdir -p $out/lib/edgedesk $out/bin $out/share
    cp -r usr/share/rustdesk/* $out/lib/edgedesk/
    cp -r usr/share/applications usr/share/icons $out/share/
    makeWrapper $out/lib/edgedesk/rustdesk $out/bin/edgedesk --prefix LD_LIBRARY_PATH : $out/lib/edgedesk/lib
    substituteInPlace $out/share/applications/*.desktop --replace-fail /usr/bin/rustdesk $out/bin/edgedesk
  \'\';
  meta = {{ description = "EdgeDesk managed remote desktop"; homepage = "https://github.com/EdgeAlphix/EdgeDesk"; license = pkgs.lib.licenses.agpl3Only; platforms = [ "x86_64-linux" ]; mainProgram = "edgedesk"; }};
}}
'''
(out/f'EdgeDesk-{version}.nix').write_text(nix)
(out/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in sorted(out.iterdir()) if p.is_file() and p.name!='SHA256SUMS'))
print('Verified required formats; packaged matching source, patches, Nix and checksums')
