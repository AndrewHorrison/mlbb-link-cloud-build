# MLBB Link (0.9.0 Beta)

A personal fan-made local-network controller for Android and Waydroid Mobile Legends: Bang Bang. Experimental input bridge; not affiliated with Moonton.

## v0.9.0 Beta
- Expands hero selection to 133 current roster entries, including all previously featured heroes first in the list.
- Sora Thunder and Torrent forms have distinct generated skill icon overlays. Actual Sora game state is not read automatically.
- Adds Wi-Fi UDP, USB-over-ADB TCP, **Dual Connection** (USB first, immediate Wi-Fi fallback on failed send), and experimental paired Bluetooth SPP.
- PC host discovers usable LAN addresses with route and interface fallbacks, and should show the reachable Wi-Fi IP in its dashboard.
- Phone controller and Touch Bridge check a published update manifest and prompt when a newer app version is available. Android still asks the user to approve installation; updates are downloaded from the release page.
- Uses the same Android package IDs and a higher versionCode for upgrades from previous versions.

## Connection setup
**Wi-Fi:** Start the PC host, read the LAN IP from its dashboard, enter it in the phone app, and press Link.

**USB:** Enable Android USB debugging, plug the phone into the Bazzite PC, authorize the PC on the phone, and keep the host script running. The host attempts `adb reverse tcp:28744 tcp:28744`. Choose USB on the phone.

**Dual Connection:** Choose DUAL. It prefers USB/TCP; when USB sends fail, events switch to Wi-Fi/UDP so the session can continue if the cable is disconnected. Make sure the Wi-Fi IP is filled in first. USB disconnect detection and network fallback should be tested on your actual devices before relying on it in ranked games.

**Bluetooth Beta:** Pair the phone and Bazzite PC first. Select BT BETA and select the paired PC. The PC needs BlueZ/RFCOMM support and the host needs permission to listen on RFCOMM channel 1. Bluetooth is experimental and may not be reliable for live gameplay.

## PC host
Run `python3 mlbb_link_host.py`. Install and enable the Waydroid Touch Bridge Accessibility service, and launch Mobile Legends in Waydroid.

## Important limitations
This is an experimental prototype. It does not read MLBB's live cooldowns, match state, enemy positions, or hero transformation state. The expanded hero roster is selectable, but many recently added heroes use generic placeholder skill labels, generic cooldown estimates, and fallback skill glyphs until hero-specific data/art is added. The Sora form icon variants are locally generated visual cues, not official in-game art. Test with practice mode first.

## Build artifacts
GitHub Actions builds APKs whenever the Android build workflow is triggered. A rolling prerelease at [MLBB Link Beta](https://github.com/augustinejacyandrew-lgtm/mlbb-link-cloud-build/releases/tag/mlbb-link-beta) serves the latest APKs and the update manifest is at `updates/latest.json`.
