# MLBB Link (0.2.0)

A personal, local-network controller prototype with a landscape Android controller, a PC dashboard, UDP input, and a Waydroid accessibility touch bridge.

## What's included

- **Phone Controller** — landscape game-style HUD, joystick, attack/skill buttons, hero presets (Nana, Dyrroth, and Sora), cooldown display, skill-up controls, starter build reference, a PC IP field, and push-to-talk microphone.
- **PC host** — browser dashboard showing the host's LAN IP, connection/activity information, controller packets, and microphone packet counts.
- **Waydroid Touch Bridge** — Android accessibility service that translates bridge messages into touch actions.
- **Automatic build** — GitHub Actions builds both debug APKs and publishes an `MLBB-Link-APKs` artifact.

This is an unofficial personal prototype. It does not read live game state; cooldowns and build references are estimates/suggestions. Audio routing and touch mapping depend on device and Waydroid configuration.

## Run the PC host on Bazzite/Linux

1. Download this repository's `MLBB-Link-MVP.tar.gz` file (or use the source ZIP in the repo's latest releases if one is added) and extract it:
   ```bash
   tar -xzf MLBB-Link-MVP.tar.gz
   cd mlbb-link
   ```
2. Start the host:
   ```bash
   python3 host/mlbb_link_host.py
   ```
3. Open **http://127.0.0.1:28740/**. Copy the LAN IP shown on the dashboard into the phone controller. Keep both devices on the same local network.

The host uses UDP ports 28741 (phone controller), 28742 (Waydroid bridge), and 28743 (microphone). Only open these ports on a trusted local network if your firewall requires it.

## Build and download APKs

A source or workflow update automatically starts the build workflow. You can also start it manually:

1. Open the repository's **Actions** tab.
2. Select **Build MLBB Link APKs**.
3. Open a successful run and download the **MLBB-Link-APKs** artifact.

The artifact contains `MLBB-Link-Phone-Controller.apk`, `MLBB-Link-Touch-Bridge.apk`, and SHA256 checksums. GitHub Actions retains the artifact for 7 days.

## Install and connect

1. Install the Phone Controller APK on your Android phone.
2. Install the Touch Bridge APK in Waydroid and enable its Accessibility Service as directed by the app.
3. Start the PC host and copy the LAN IP from its dashboard into the phone app.
4. Tap **CONNECT**. For push-to-talk, grant microphone permission and hold **HOLD TO TALK**.

Use the controller with your own devices and a network you trust. Test touch mapping before relying on it in a match.
