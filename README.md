# MLBB Link v0.16.0

## v0.16.0 — safer input routing and diagnostics

- Repeated skill-aim or joystick `DOWN` packets keep their existing touch contact instead of reusing an active Protocol-B tracking slot.
- NaN/Infinity coordinates are rejected before coordinate projection.
- Added `--check-profile` and explicit screen-width/height options. Profile checks run without opening `/dev/uinput`, creating a touch device, or listening on the relay port.
- Added simulated-backend regression tests for taps, skill gestures, joystick movement, duplicate DOWN events, malformed coordinates and stale-contact release.
- CI now runs whenever `emulator/**` changes, so Linux companion edits are not silently skipped by the Android build/release workflow.


A community controller for Mobile Legends: Bang Bang using an Android phone controller, a Python PC host, and the Waydroid touch bridge.

## Core controller and emulator features

- **Skill taps:** quick taps now use a normal tap event; the app starts a continuous aim stroke only after your finger intentionally moves. This targets the issue where Skill 1 and Skill 2 could fail while Ultimate worked.
- **Lower input latency:** the Android sender caches the PC IP resolution and coalesces old joystick/aim movement samples instead of letting a slow queue build up.
- **HUD refresh:** added a semi-transparent minimap panel and larger skill hit areas, inspired by the custom HUD discussion linked in the issue.
- **Visible version:** launcher label and controller HUD show **MLBB Link v0.16.0**.
- **Custom HUD editor:** tap **EDIT HUD**, drag the joystick, skill buttons, attack, battle spell, Recall, Regen, microphone, or skill-point control, then tap **SAVE HUD**. Press and hold **SAVE HUD** for about 0.7 seconds to restore defaults. Positions are saved locally on the phone.
- **Manual cooldown reduction (CDR):** tap the **CDR** chip to cycle 0%, 10%, 20%, 30%, and 40%. The visible skill cooldown estimates use the selected reduction and remember it locally. It does not read the current match, equipment, buffs, or server state.
- The in-app updater keeps its progress display and SHA-256 verification before handing the APK to Android's installer.
- **Native APK installer fix:** passes a `content://` URI using `FileProvider`, explicit APK MIME type, `ClipData`, and read-grant/activity flags. It tries `ACTION_INSTALL_PACKAGE` and falls back to `ACTION_VIEW` when an OEM/Waydroid image lacks the first handler.
- **Android 8+ install permission:** the updater checks `canRequestPackageInstalls()`, opens the per-app unknown-app setting when needed, saves the verified APK path, and resumes installation when the permission is granted. Android's final confirmation remains required.
- PC dashboard includes Overview, Wi-Fi, USB, Bluetooth Beta, Dual Connection, and Updates tabs.
- Current app version: **versionName 0.16.0 / versionCode 19**.

## New Linux Emulator Tools

- **PySide6 floating keymap overlay:** drag controls, add/delete mappings, resize targets, calibrate the Android window area, and save a JSON profile.
- **Multi-touch input engine:** an opt-in unprivileged Linux uinput backend for MOBA-style skill aim gestures, joystick movement, taps, and up to ten contacts.
- **Phone integration:** phone packets continue to arrive at UDP 28741; the host can choose the existing Waydroid bridge or relay exclusively to the local engine at 127.0.0.1:28743.
- **Emulator tools auto-updater:** separately checks its GitHub manifest, verifies SHA-256, validates the package file list, and updates only the user-space companion.
- Runtime setup guide: [Bazzite/Waydroid, Google Play, ARM translation, limits and troubleshooting](emulator/README.md).
- Download the companion: [MLBB-Link-Emulator-Tools.tar.gz](https://github.com/AndrewHorrison/mlbb-link-cloud-build/releases/download/v0.16.0/MLBB-Link-Emulator-Tools.tar.gz).

The Linux companion does not promise Play Protect certification, universal game compatibility, or guaranteed sub-5ms end-to-end latency. Bazzite's current Waydroid guide warns of NVIDIA GPU compatibility issues; check the runtime guide before changing images. The overlay and input engine still need testing on the actual laptop and Android display.

## Upgrade notes

The v0.16.0 build is configured to reuse the repository-scoped signing-key cache established by v0.13.0, so Android should accept this as an in-place update and retain app settings. If Android reports a signature mismatch, do not uninstall immediately if you need to preserve settings; share the exact error first. The updater verifies the APK's SHA-256 checksum and Android still asks you to approve installation.


## Install and connect

1. Download the phone controller and Waydroid bridge APKs from the [latest release](https://github.com/AndrewHorrison/mlbb-link-cloud-build/releases/tag/v0.16.0).
2. Run `python3 mlbb_link_host.py` on Bazzite, preferably directly on the host rather than in Distrobox/Toolbx.
3. Install and enable the Touch Bridge accessibility service in Waydroid.
4. Put the PC and phone on the same trusted Wi-Fi, enter the PC LAN IPv4 address into the controller, and tap **LINK**.
5. Test in Practice Mode first. If the new controller or bridge won't install over the old one, follow the first-upgrade note above.

### Connection modes

- **Wi-Fi:** normal LAN input over UDP.
- **USB:** requires Android USB debugging, platform-tools/ADB authorization, and host-side ADB reverse support.
- **DUAL:** intended to prefer USB with Wi-Fi fallback. Real cable-unplug behavior can still cause a short interruption.
- **Bluetooth Beta:** experimental RFCOMM/SPP path; test carefully.

## Limits

- The v0.16.0 updater compiles in CI, but installer behavior still needs testing on real Android and Waydroid devices because OEM Package Installer and Settings handlers vary.
- Button placements can differ from your in-game custom HUD. The controller includes larger touch targets and a stylized minimap, but it is not an exact copy of an MLBB game screen and does not read the live match state.
- Cooldowns, hero state, and Sora form helpers are estimates, not authoritative game telemetry.
- Independent community project, not affiliated with or endorsed by Moonton.

## Links

- [Download MLBB Link v0.16.0](https://github.com/AndrewHorrison/mlbb-link-cloud-build/releases/tag/v0.16.0)
- [Phone Controller APK](https://github.com/AndrewHorrison/mlbb-link-cloud-build/releases/download/v0.16.0/MLBB-Link-Phone-Controller.apk)
- [Waydroid Touch Bridge APK](https://github.com/AndrewHorrison/mlbb-link-cloud-build/releases/download/v0.16.0/MLBB-Link-Touch-Bridge.apk)
- [Linux Emulator Tools bundle](https://github.com/AndrewHorrison/mlbb-link-cloud-build/releases/download/v0.16.0/MLBB-Link-Emulator-Tools.tar.gz)
- [Emulator runtime/keymapping guide](https://github.com/AndrewHorrison/mlbb-link-cloud-build/blob/main/emulator/README.md)
- [Build workflow](https://github.com/AndrewHorrison/mlbb-link-cloud-build/actions/workflows/android-build.yml)
- Update manifest: `updates/latest.json`
