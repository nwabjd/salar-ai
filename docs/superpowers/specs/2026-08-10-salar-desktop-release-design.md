# SALAR Desktop Release and WhatsApp Polish Design

## Release outcome

Ship one coherent SALAR release across the public website and Windows desktop: the same React interface and Gemini Live behavior, a downloadable Windows installer, clear future-platform availability, and a professional WhatsApp assistant identity.

## Desktop architecture

Keep Tauri 2 as the native shell and bundle the production frontend directly into it. This preserves feature parity automatically: authentication, chat, Liquid Ether, Gemini Live, pricing, and future frontend changes use the same source as salaar.cloud. The Windows installer remains per-user NSIS so users do not need administrator access. The macOS build produces the `.app` bundle for macOS 11 and later, distributed on the website as `SALAR.app.zip`.

The release script builds and tests the shared frontend, builds the Tauri installers for the current OS (base `tauri.conf.json` targets `["nsis"]` on Windows; `tauri.macos.conf.json` overrides to `["app"]` on macOS), places stable copies at `website/downloads/SALAR-Setup.exe` and `website/downloads/SALAR.app.zip` with matching `.sha256` files, and writes the same artifacts to `dist/installer`. The website can therefore use permanent download URLs even when the versioned Tauri filenames change. The macOS app is unsigned, so it ships as a zip: users unzip and drag SALAR into Applications (right-click → Open bypasses Gatekeeper).

> **Note.** The macOS `.app` can only be produced by Tauri on macOS (it needs the macOS SDK). Run `scripts/build-release.ps1` on a macOS machine (or add a macOS CI runner) to publish the macOS zip; Windows hosts publish only the Windows installer.

## Website experience

Add `Get SALAR` to the main navigation and a dedicated cross-platform section before pricing. Windows and macOS are active cards with direct downloads (`SALAR-Setup.exe`, `SALAR.app.zip`) and concise compatibility notes. iOS and Android remain visible with non-interactive `Coming soon` badges. On narrow screens the cards stack without changing the landing page's visual language or Liquid Ether performance profile.

## Android via CI

The Android APK is built in GitHub Actions (`.github/workflows/android-apk.yml`) instead of on a developer machine, so no Android SDK/NDK is required locally. The workflow:

- Runs on demand (`Actions → Android APK → Run workflow`) and on every `v*` tag push.
- Installs the toolchain (SDK preinstalled on the runner, NDK r27b, JDK 17, Rust targets for `aarch64`/`armv7`/`x86_64`), scaffolds the mobile project with `npm run android:init -- --ci`, builds the shared production frontend, and produces universal release APKs with `npm run android:build -- --target … --apk`. The generated `gen/android` project is a build artifact, never committed.
- Signs and verifies the release APKs with `apksigner` (keystore restored from secrets). With no signing secrets configured it falls back to a debug APK (auto-signed, sideload-only) so the pipeline stays runnable.
- Uploads the APKs as a workflow artifact and, on a tag push, attaches them to the GitHub release.

Signing setup (one time): create a keystore with `keytool -genkey -v -keystore upload-keystore.jks -keyalg RSA -keysize 2048 -validity 10000 -alias upload`, then add GitHub secrets `ANDROID_KEY_BASE64` (base64 of the keystore), `ANDROID_KEY_PASSWORD`, and `ANDROID_KEY_ALIAS`.

Publishing to the website: take the signed APK from the release/artifact, upload it to `website/downloads/SALAR.apk` (with a matching `.sha256`), then flip the Android card from `Coming soon` to `Available now`.

## WhatsApp behavior

SALAR identifies itself as `JD's assistant`, answers concrete queries directly when it has reliable information, and asks a focused follow-up when the sender has not provided enough detail. It never pretends to be JD, never fabricates, and does not respond with blunt refusal language. Requests to pass something to JD continue through the existing audited pass-message mechanism.

## Verification

Focused frontend tests cover the download URL, platform badges, and shared desktop source contract. Backend tests cover the WhatsApp prompt contract. The full frontend suite/build, backend suite, Rust tests, and Tauri release build must pass before deployment.
