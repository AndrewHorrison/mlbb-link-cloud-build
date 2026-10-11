# MLBB Link (0.4.0)

A personal fan-made local-network controller prototype for Android and Waydroid.

## What's included

- **Phone Controller** — full-screen landscape HUD with joystick, attack, Recall, Regen, Flicker, cooldown overlays, skill-up controls, saved PC IP and push-to-talk microphone. The latest HUD removes the extra app branding and large developer-style labels.
- **Hero skill artwork** — the build bundles the actual skill icons for Nana, Dyrroth and Sora rather than generic vector glyphs. The hero skill names now match the selected hero.
- **PC host** — LAN dashboard with a visible/copyable PC IP, incoming packet counters and microphone status.
- **Waydroid Touch Bridge** — the app uses Android network-state access, probes the detected Waydroid gateway plus common fallback addresses, and keeps a manual IP fallback, plus a shortcut to Android Accessibility settings.
- **Automatic Android builds** — GitHub Actions builds the phone and bridge APKs and uploads an artifact together with the updated source archive and patched PC host script.

This is an unofficial fan project. It does not read live MLBB match state. Cooldowns are estimates, and touch mapping/audio routing still depend on your local Waydroid configuration.

## Run the PC host on Bazzite/Linux

From the extracted updated source archive, run:

```bash
python3 host/mlbb_link_host.py
```

The PC dashboard opens at **http://127.0.0.1:28740/**. Use the LAN IP displayed in the dashboard for the phone controller. The dashboard also binds to the host's local-network interfaces so the Waydroid app can request `/api/status` from its host-side gateway and display the PC LAN IP.

The host uses UDP port 28741 for phone controls, 28742 for Waydroid touch forwarding, and 28743 for microphone audio; dashboard discovery uses TCP 28740. Use only on a network you trust and allow these ports through the firewall only when needed.

## Download the updated APKs

The workflow starts when the build workflow, patch script, bridge screen override, or source archive changes. To get installable APKs:

1. Open the repository's **Actions** tab.
2. Choose the latest **Build MLBB Link APKs** run with a successful green check.
3. Download the `MLBB-Link-APKs` artifact.

The artifact includes:
- `MLBB-Link-Phone-Controller.apk`
- `MLBB-Link-Touch-Bridge.apk`
- `MLBB-Link-Updated-Source.tar.gz`
- `mlbb_link_host.py`
- APK SHA-256 checksums

Artifacts are retained for 7 days by GitHub Actions.

## Install and connect

1. Install the Phone Controller APK on your phone.
2. Install the Touch Bridge APK in Waydroid and enable **MLBB Link Touch Bridge** in Android Accessibility settings.
3. Start `python3 host/mlbb_link_host.py` on Bazzite.
4. Open the Waydroid Touch Bridge app and tap **FIND PC**. It tries the Waydroid host gateway and reads the LAN IP from the PC dashboard; use the manual field if automatic discovery is blocked by networking/firewall settings.
5. Enter that LAN IP in the phone controller and tap **LINK**. Both the phone and PC must be on the same local network.
6. For push-to-talk, grant microphone permission on the phone and press/hold the microphone control.

The Touch Bridge app displays the detected PC IP; the phone controller still sends its UDP controls directly to that IP. The bridge only needs its Accessibility Service enabled to dispatch touches received from the PC host.
