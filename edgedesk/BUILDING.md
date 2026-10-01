# Building EdgeDesk

GitHub Actions checks for a new stable RustDesk release every six hours. It applies the EdgeDesk patches and builds the installers. Upstream commits do not trigger a build.

All requested package formats must pass before a release is published. If upstream changes break a patch or a build, the workflow stops.

The released upstream workflows provide platform toolchains and native dependency builds. `.github/workflows/edgedesk-build.yml`, `edgedesk-bridge.yml` and `edgedesk-topmost.yml` are reusable workflows only. There are no nightly or push build entry points.

Android secrets: `ANDROID_SIGNING_KEY` (base64 keystore), `ANDROID_ALIAS`, `ANDROID_KEY_STORE_PASSWORD`, `ANDROID_KEY_PASSWORD`. Keep the same key for updates.

Mac builds use a persistent development signing identity through `EDGEDESK_MACOS_P12` and `EDGEDESK_MACOS_P12_PASSWORD`. Keep the same identity for updates so macOS permissions continue to match. This is not Apple notarization.

Optional Apple macOS signing secrets: `MACOS_P12_BASE64`, `MACOS_P12_PASSWORD`, `MACOS_CODESIGN_IDENTITY`, `MACOS_NOTARIZE_JSON`. Without them, unsigned macOS app archives are still built. The iOS archive requires your own Apple provisioning/signing for distribution; this repository does not claim an unsigned IPA is installable on a standard iPhone.

Windows signing is optional through the inherited `SIGN_BASE_URL` and `SIGN_SECRET_KEY` integration. No signing credential is included in source.

To prepare the overlay locally, start from a clean RustDesk stable tag with submodules initialized, copy this repository's `edgedesk/` directory, install Python Pillow/PyYAML, then run:

```sh
python3 edgedesk/apply.py
python3 edgedesk/finalize.py
python3 edgedesk/workflows.py
python3 edgedesk/verify.py
```


Linux native packages require glibc 2.31 or newer (Ubuntu 20.04 or later).
