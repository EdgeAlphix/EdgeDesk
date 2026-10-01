EdgeDesk is based on the upstream stable RustDesk release recorded in the attached upstream manifest. Native clients use the managed EdgeDesk ID/API server and geographically selected healthy relays. LAN connections remain direct when available.

Software owner: International Computing Group, LLC
Operator: EdgeAlphix LLC
Anaheim, CA 92802, United States

RustDesk and EdgeDesk modifications are licensed under GNU AGPL-3.0. Complete corresponding source, both patch sets and build instructions accompany the installers. The dependency source is included, rather than an unresolvable modified Git submodule.

Android APKs are signed with the persistent EdgeDesk release key. iOS IPA is unsigned and requires appropriate Apple signing before installation. macOS app archives preserve symlinks; notarization requires configured Apple credentials. Windows executables are unsigned unless a signing service is configured.

No RustDesk public ID, API, version-check or telemetry destination is enabled. Required EdgeDesk registration, authentication and remote connection traffic remain. UDP hole punching, IPv6 P2P and insecure TLS fallback are enabled by default as requested. WebSocket defaults off to preserve direct connections.
