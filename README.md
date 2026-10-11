# MLBB Link (0.11.0 Beta)

## v0.11.0 Beta — PC connection center and versioned updates

- Adds dedicated **Overview, Wi-Fi, USB, Bluetooth Beta, Dual Connection, and Updates** tabs to the PC host dashboard, with live transport status and copyable setup commands.
- The dashboard detects a newer PC host version through `updates/latest.json` and links to the matching host script release asset. Stop and restart the Python host after replacing its script.
- Releases now include the PC host script and an updated-source archive alongside the phone controller and Waydroid bridge APKs.
- Both Android apps use versionCode 13 / versionName 0.11.0 with the retained beta signing key so compatible installs can update in place.
- **Important:** the tabs are diagnostics/setup guides; select Wi-Fi, USB, BT BETA or DUAL in the phone controller. DUAL is documented as USB-preferred with Wi-Fi fallback, but unplug latency and Bluetooth require real-device testing.


A personal fan-made local-network controller for Android and Waydroid Mobile Legends: Bang Bang. Experimental input bridge; not affiliated with Moonton.

## v0.10.0 Beta improvements
- **133 selectable hero entries** with **399 bundled skill icon resources** (three per hero). The build prefers public Moonton game data and artwork; if a slot cannot be fetched, it creates a legible hero-specific fallback icon.
- Loads official skill names and skill descriptions where the game data source returns them, and displays the current skill name/description while aiming.
- Adds six separate Sora form visual variants: three Thunder and three Torrent icons.
- PC host version is bumped to 0.10.0 and keeps retrying `adb reverse tcp:28744 tcp:28744`, so USB can become available when you plug in or authorize the phone after starting the host.
- Refines host LAN IP detection and TCP acknowledgement handling.
- Both Android apps use versionCode 12 / versionName 0.10.0. The workflow reuses the beta signing key for future in-place updates, and checks all 399 skill icons, skill metadata, and six Sora form icons before compilation.
- GitHub Actions build and source/resource checks passed on [run 38134270885](https://github.com/augustinejacyandrew-lgtm/mlbb-link-cloud-build/actions/runs/38134270885).

## Connection setup

**Wi-Fi:** Start the PC host, read the LAN IP from its dashboard, enter it in the phone app, and press Link.

**USB:** Enable Android USB debugging, plug the phone into the Bazzite PC, accept the debugging authorization prompt, and keep the host script running. The host retries `adb reverse tcp:28744 tcp:28744`. Choose USB on the phone.

**Dual Connection:** Choose DUAL. It prefers USB/TCP; when USB sends fail, events fall back to Wi-Fi/UDP. Set the Wi-Fi IP first. The build verifies the host and controller code, but actual unplug/reconnect timing still needs testing on the specific phone/PC.

**Bluetooth Beta:** Pair the phone and Bazzite PC first. Select BT BETA and choose the paired PC. Bluetooth SPP remains experimental and is not recommended for competitive matches.

## PC host

Run `python3 mlbb_link_host.py` on Bazzite. Install the Touch Bridge APK in Waydroid and enable its Accessibility service, then launch Mobile Legends.

## Known limits

- CI verified compilation and checked all 133 metadata entries, 399 skill icons and six Sora form icons. The app has not been physically tested with every hero or on every device.
- Some skill icons may be generated fallbacks where upstream image URLs are unavailable. Official descriptions can also be absent for some entries.
- Cooldowns are not read from live match state. Enemy positions, match state and Sora's actual live transformation are not detected. Treat any local cooldown/form display as a helper, not authoritative game telemetry.
- The update checker is included, but this repository and its raw update manifest are private. Automatic updates may not be accessible to anonymous users. Android also requires the user to approve APK installation.

## Downloads

- [Latest MLBB Link Beta release](https://github.com/augustinejacyandrew-lgtm/mlbb-link-cloud-build/releases/tag/mlbb-link-beta)
- [Successful v0.10.0 build](https://github.com/augustinejacyandrew-lgtm/mlbb-link-cloud-build/actions/runs/38134270885)
- Update manifest: `updates/latest.json`
