Name:       edgedesk
Version:    1.4.9
Release:    0
Summary:    RPM package
License:    AGPL-3.0
URL:        https://github.com/EdgeAlphix/EdgeDesk
Vendor:     EdgeAlphix LLC
Requires:   gtk3 libxcb libXfixes alsa-lib libva pam gstreamer1-plugins-base
Recommends: libayatana-appindicator-gtk3 libxdo
Provides:   libdesktop_drop_plugin.so()(64bit), libdesktop_multi_window_plugin.so()(64bit), libfile_selector_linux_plugin.so()(64bit), libflutter_custom_cursor_plugin.so()(64bit), libflutter_linux_gtk.so()(64bit), libscreen_retriever_plugin.so()(64bit), libtray_manager_plugin.so()(64bit), liburl_launcher_linux_plugin.so()(64bit), libwindow_manager_plugin.so()(64bit), libwindow_size_plugin.so()(64bit), libtexture_rgba_renderer_plugin.so()(64bit)

# https://docs.fedoraproject.org/en-US/packaging-guidelines/Scriptlets/

%description
The best open-source remote desktop client software, written in Rust.

%prep
# we have no source, so nothing here

%build
# we have no source, so nothing here

# %global __python %{__python3}

%install

mkdir -p "%{buildroot}/usr/share/edgedesk" && cp -r ${HBB}/flutter/build/linux/x64/release/bundle/* -t "%{buildroot}/usr/share/edgedesk"
mkdir -p "%{buildroot}/usr/bin"
install -Dm 644 $HBB/res/edgedesk.service -t "%{buildroot}/usr/share/edgedesk/files"
install -Dm 644 $HBB/res/edgedesk.desktop -t "%{buildroot}/usr/share/edgedesk/files"
install -Dm 644 $HBB/res/edgedesk-link.desktop -t "%{buildroot}/usr/share/edgedesk/files"
install -Dm 644 $HBB/res/128x128@2x.png "%{buildroot}/usr/share/icons/hicolor/256x256/apps/edgedesk.png"
install -Dm 644 $HBB/res/scalable.svg "%{buildroot}/usr/share/icons/hicolor/scalable/apps/edgedesk.svg"

%files
/usr/share/edgedesk/*
/usr/share/edgedesk/files/edgedesk.service
/usr/share/icons/hicolor/256x256/apps/edgedesk.png
/usr/share/icons/hicolor/scalable/apps/edgedesk.svg
/usr/share/edgedesk/files/edgedesk.desktop
/usr/share/edgedesk/files/edgedesk-link.desktop

%changelog
# let's skip this for now

%pre
# can do something for centos7
case "$1" in
  1)
    # for install
  ;;
  2)
    # for upgrade
    systemctl stop edgedesk || true
  ;;
esac

%post
cp /usr/share/edgedesk/files/edgedesk.service /etc/systemd/system/edgedesk.service
cp /usr/share/edgedesk/files/edgedesk.desktop /usr/share/applications/
cp /usr/share/edgedesk/files/edgedesk-link.desktop /usr/share/applications/
ln -sf /usr/share/edgedesk/edgedesk /usr/bin/edgedesk
systemctl daemon-reload
systemctl enable edgedesk
systemctl start edgedesk
update-desktop-database

%preun
case "$1" in
  0)
    # for uninstall
    systemctl stop edgedesk || true
    systemctl disable edgedesk || true
    rm /etc/systemd/system/edgedesk.service || true
  ;;
  1)
    # for upgrade
  ;;
esac

%postun
case "$1" in
  0)
    # for uninstall
    rm /usr/bin/edgedesk || true
    rmdir /usr/lib/edgedesk || true
    rmdir /usr/local/edgedesk || true
    rmdir /usr/share/edgedesk || true
    rm /usr/share/applications/edgedesk.desktop || true
    rm /usr/share/applications/edgedesk-link.desktop || true
    update-desktop-database
  ;;
  1)
    # for upgrade
    rmdir /usr/lib/edgedesk || true
    rmdir /usr/local/edgedesk || true
  ;;
esac
