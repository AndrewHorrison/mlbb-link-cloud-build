# MLBB Link v0.14.0

A community controller for Mobile Legends: Bang Bang using an Android phone controller, a Python PC host, and the Waydroid touch bridge.

## v0.14.0 — skill input fix, lower latency, refreshed HUD

- **Skill taps:** quick taps now use a normal tap event; the app starts a continuous aim stroke only after your finger intentionally moves. This targets the issue where Skill 1 and Skill 2 could fail while Ultimate worked.
- **Lower input latency:** the Android sender caches the PC IP resolution and coalesces old joystick/aim movement samples instead of letting a slow queue build up.
- **HUD refresh:** added a semi-transparent minimap panel and larger skill hit areas, inspired by the custom HUD discussion linked in the issue.
- **Visible version:** launcher label and controller HUD show **MLBB Link v0.14.0**.
- **Custom HUD editor:** tap **EDIT HUD**, drag the joystick, skill buttons, attack, battle spell, Recall, Regen, microphone, or skill-point control, then tap **SAVE HUD**. Press and hold **SAVE HUD** for about 0.7 seconds to restore defaults. Positions are saved locally on the phone.
- **Manual cooldown reduction (CDR):** tap the **CDR** chip to cycle 0%, 10%, 20%, 30%, and 40%. The visible skill cooldown estimates use the selected reduction and remember it locally. It does not read the current match, equipment, buffs, or server state.
- The in-app updater keeps its progress display and SHA-256 verification before handing the APK to Android's installer.
- PC dashboard includes Overview, Wi-Fi, USB, Bluetooth Beta, Dual Connection, and Updates tabs.
- Current app version: **versionName 0.14.0 / versionCode 16**.

## Upgrade notes

The v0.14.0 build is configured to reuse the repository-scoped signing-key cache established by v0.13.0, so Android should accept this as an in-place update and retain app settings. If Android reports a signature mismatch, do not uninstall immediately if you need to preserve settings; share the exact error first. The updater verifies the APK's SHA-256 checksum and Android still asks you to approve installation.


## Install and connect

1. Download the phone controller and Waydroid bridge APKs from the [latest release](https://github.com/AndrewHorrison/mlbb-link-cloud-build/releases/tag/v0.14.0).
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

- This build is CI-compiled but still needs physical-device testing. I can't verify the skill fix against your particular device/game layout from CI alone.
- Button placements can differ from your in-game custom HUD. The controller includes larger touch targets and a stylized minimap, but it is not an exact copy of an MLBB game screen and does not read the live match state.
- Cooldowns, hero state, and Sora form helpers are estimates, not authoritative game telemetry.
- Independent community project, not affiliated with or endorsed by Moonton.

## Links

- [Download MLBB Link v0.14.0](https://github.com/AndrewHorrison/mlbb-link-cloud-build/releases/tag/v0.14.0)
- [Phone Controller APK](https://github.com/AndrewHorrison/mlbb-link-cloud-build/releases/download/v0.14.0/MLBB-Link-Phone-Controller.apk)
- [Waydroid Touch Bridge APK](https://github.com/AndrewHorrison/mlbb-link-cloud-build/releases/download/v0.14.0/MLBB-Link-Touch-Bridge.apk)
- [Build workflow](https://github.com/AndrewHorrison/mlbb-link-cloud-build/actions/workflows/android-build.yml)
- Update manifest: `updates/latest.json`
