#!/bin/bash
set -euo pipefail
umask 077

signing_dir=$(mktemp -d)
trap 'security delete-keychain "$signing_dir/signing.keychain-db" >/dev/null 2>&1 || true; rm -rf "$signing_dir"' EXIT
printf '%s' "$EDGEDESK_MACOS_P12" | base64 -D > "$signing_dir/identity.p12"
security create-keychain -p "$EDGEDESK_MACOS_P12_PASSWORD" "$signing_dir/signing.keychain-db"
security unlock-keychain -p "$EDGEDESK_MACOS_P12_PASSWORD" "$signing_dir/signing.keychain-db"
security import "$signing_dir/identity.p12" -k "$signing_dir/signing.keychain-db" -P "$EDGEDESK_MACOS_P12_PASSWORD" -T /usr/bin/codesign >/dev/null
security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$EDGEDESK_MACOS_P12_PASSWORD" "$signing_dir/signing.keychain-db" >/dev/null
codesign --force --deep --sign 'EdgeDesk Development' --keychain "$signing_dir/signing.keychain-db" --entitlements flutter/macos/Runner/Release.entitlements "$1"
codesign --verify --deep --strict "$1"
