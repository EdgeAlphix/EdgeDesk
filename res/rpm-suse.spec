Name:       edgedesk
Version:    1.1.9
Release:    0
Summary:    RPM package
License:    AGPL-3.0
Requires:   gtk3 libxcb1 libXfixes3 alsa-utils libXtst6 libva2 gstreamer-plugins-base gstreamer-plugin-pipewire
Recommends: libayatana-appindicator3-1 xdotool

# https://docs.fedoraproject.org/en-US/packaging-guidelines/Scriptlets/

%description
The best open-source remote desktop client software, written in Rust.

%prep
# we have no source, so nothing here

%build
# we have no source, so nothing here

%global __python %{__python3}

%install
mkdir -p %{buildroot}/usr/bin/
mkdir -p %{buildroot}/usr/share/edgedesk/
mkdir -p %{buildroot}/usr/share/edgedesk/files/
mkdir -p %{buildroot}/usr/share/icons/hicolor/256x256/apps/
mkdir -p %{buildroot}/usr/share/icons/hicolor/scalable/apps/
install -m 755 $HBB/target/release/edgedesk %{buildroot}/usr/bin/edgedesk
install $HBB/libsciter-gtk.so %{buildroot}/usr/share/edgedesk/libsciter-gtk.so
install $HBB/res/edgedesk.service %{buildroot}/usr/share/edgedesk/files/
install $HBB/res/128x128@2x.png %{buildroot}/usr/share/icons/hicolor/256x256/apps/edgedesk.png
install $HBB/res/scalable.svg %{buildroot}/usr/share/icons/hicolor/scalable/apps/edgedesk.svg
install $HBB/res/edgedesk.desktop %{buildroot}/usr/share/edgedesk/files/
install $HBB/res/edgedesk-link.desktop %{buildroot}/usr/share/edgedesk/files/

%files
/usr/bin/edgedesk
/usr/share/edgedesk/libsciter-gtk.so
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
    rm /usr/share/applications/edgedesk.desktop || true
    rm /usr/share/applications/edgedesk-link.desktop || true
    update-desktop-database
  ;;
  1)
    # for upgrade
  ;;
esac
