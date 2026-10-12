# MLBB Link Emulator Tools v0.15.0

A Linux companion for the MLBB Link Android phone controller and existing PC host. It adds a saved keymap editor, a local multi-touch input engine, and a checksum-verified updater for the Linux tools. It does not replace GNOME or silently change Android images or system packages.

## Important compatibility note for this Bazzite laptop

Bazzite's official Waydroid guide currently warns that Waydroid does not work on NVIDIA hardware. This laptop has Intel integrated graphics and an NVIDIA discrete GPU, so verify which GPU the Android window uses. If Waydroid renders on the Intel iGPU, test it. If it binds to NVIDIA or shows a blank window, a keymapper cannot solve that runtime/GPU limitation.

Recommended order:

1. **Try Bazzite Waydroid first** if this hybrid-graphics setup is compatible. It has the best Wayland desktop integration and is the easiest path to test the existing MLBB Link bridge.
2. **Use QEMU/KVM and an Android-x86/BlissOS-type image as a fallback** if Waydroid cannot render. A VM does not automatically provide certified Google Play, ARM translation, or smooth GPU acceleration. GPU passthrough is advanced and is not configured here.
3. **Do not choose Redroid as the first interactive gaming runtime.** It is better suited to container/headless Android testing than a desktop 3D game window.

A Google Play image and ARM translation do not guarantee that Mobile Legends: Bang Bang will install, pass Play Integrity, be certified, or run at any particular frame rate.

## Waydroid + Google Play Store on Bazzite GNOME

### Preferred Bazzite-native path

On the host, not inside Distrobox or Toolbx, run:

~~~bash
ujust configure-waydroid
~~~

Choose **Initialize Waydroid** for a fresh setup. Then reopen the menu and choose **Configure Waydroid** to add supported extras.

For Play Store use, select **GApps** and follow Bazzite's **Get Google Device ID to Get Certified** steps. If your x86_64 image needs ARM-only native libraries, install one supported ARM translation through the Bazzite extras: **libndk OR libhoudini, never both at once**. Compatibility and speed differ by CPU, Android version, and game build.

Start Waydroid with the Bazzite launcher or:

~~~bash
waydroid show-full-ui
waydroid status
~~~

### Manual Waydroid initialization (fresh image only)

Waydroid's documented default OTA endpoints are:

- System: https://ota.waydro.id/system
- Vendor: https://ota.waydro.id/vendor

For a new setup, the equivalent command is:

~~~bash
sudo waydroid init -f -c https://ota.waydro.id/system -v https://ota.waydro.id/vendor -s GAPPS
~~~

**Do not run force-init over a configured installation without a backup.** It may reinitialize system and vendor images. This user's Waydroid has previously used custom mainline images; preserve those before altering the runtime. Keep GNOME installed—the emulator tools do not remove or replace it.

Google Play may show the guest as uncertified. Follow Bazzite's documented device-ID registration process if offered, but certification and Play Integrity acceptance cannot be promised.

### Runtime decision table

| Runtime | Best use | Google Play / ARM | Gaming caveat |
|---|---|---|---|
| Waydroid | Integrated desktop window when GPU-compatible | GApps plus one supported translation layer via Bazzite extras | Official guide warns about NVIDIA; certification and rendering are device-dependent |
| QEMU/KVM Android VM | Isolation or Waydroid fallback | Depends on the Android image; GMS and ARM aren't automatic | 3D acceleration/passthrough is hardware-dependent |
| Redroid | Headless or automated Android testing | Image-dependent | Not recommended as the first interactive game desktop |

## Architecture

~~~mermaid
flowchart LR
    Phone["MLBB Link phone controller"]
    Host["Existing Bazzite host<br/>UDP 28741 + dashboard"]
    Route{"Local route setting"}
    Bridge["Existing Waydroid accessibility bridge"]
    Relay["Loopback relay<br/>127.0.0.1:28743"]
    Engine["Input engine<br/>validation + profile mapping"]
    UInput["Linux /dev/uinput<br/>multi-touch device"]
    Compositor["GNOME / Wayland compositor"]
    Android["Android target window"]
    Editor["PySide6 overlay editor"]
    Profile["User profile JSON"]
    Update["Emulator auto-updater"]
    Manifest["emulator-latest.json"]
    Release["Versioned GitHub release asset"]

    Phone --> Host --> Route
    Route -->|bridge| Bridge
    Route -->|emulator| Relay --> Engine --> UInput --> Compositor --> Android
    Editor <--> Profile
    Profile --> Engine
    Update --> Manifest --> Release
~~~

The phone-controller port remains **UDP 28741**. The existing host chooses one route for each validated controller event:

- **Bridge route (default):** preserve the existing MLBB Link → Waydroid Touch Bridge path.
- **Emulator route:** relay to local-only UDP 127.0.0.1:28743, then emit multi-touch through /dev/uinput.

The GUI switches to emulator route only after the engine starts. On stop or engine failure, it restores the bridge route. The local engine listener is not exposed to the LAN. Do not run a second host receiver on port 28741.

## Install on Bazzite

Download and extract the **MLBB-Link-Emulator-Tools.tar.gz** asset from:

https://github.com/AndrewHorrison/mlbb-link-cloud-build/releases/tag/v0.15.0

Open a host terminal in the extracted folder and run:

~~~bash
bash install.sh --setup-uinput
~~~

This installs PySide6 into a user-owned Python virtual environment and creates a GNOME Applications entry. The optional uinput setup creates a dedicated mlbb-uinput group and udev rule for /dev/uinput; the daemon itself does **not** run as root and no packages are layered into Bazzite. Log out and back in once after group membership changes. No reboot is normally needed. To install the GUI first without enabling injection, run bash install.sh without the option; real touch injection will remain disabled until /dev/uinput access is configured.

Global keyboard capture is optional and off by default. Install the additional dependency via bash install.sh --keyboard if you explicitly need system-wide key events. This reads physical keyboard event devices, so enable it only on your own trusted desktop. The engine only forwards configured key-down/key-up events; it does not record raw keystrokes or replay macros.

User settings are kept outside the app directory:

- Config: ~/.config/mlbb-link-emulator/
- Profile: ~/.config/mlbb-link-emulator/profile.json
- Route/settings: ~/.config/mlbb-link-emulator/settings.json
- Engine readiness marker: ~/.config/mlbb-link-emulator/engine.ready
- App and virtual environment: ~/.local/share/mlbb-link-emulator/

Normal tool updates do not overwrite the user's custom profile.

## Use the overlay editor

1. Open **MLBB Link Emulator Tools** from GNOME Applications.
2. Launch Android/Waydroid and make the game window visible. Use landscape orientation for a landscape profile.
3. Click **Open mapping overlay editor**. It opens in edit mode.
4. Drag circles to match the buttons in the Android game's own HUD. **Calibrate target** lets you draw a rectangle around the Android display area; positions are normalized relative to that rectangle.
5. Select a control. Use **Size − / Size +** or the mouse wheel to adjust its radius. **Add** and **Delete** change the map; **Save** writes it.
6. Click **Play / Click-through** to try pass-through mode where the compositor supports it. Click **Edit mappings** when changing the layout again.
7. In the launcher, click **Start touch engine + route phone here**. This opens the uinput device as your unprivileged user and switches the host route from the Android accessibility bridge to the emulator engine.

The starter profile has Q/W/E/R/F and other common key bindings, but the circles must match your actual in-game HUD.

### Keymap/profile fields

The profile has a schema version, screen dimensions, a target rectangle and normalized coordinates per mapping. Each mapping supports:

- kind: tap, skill or joystick
- buttonNames: event aliases received from the phone controller
- key: optional desktop binding (Q/W/E/R/F in the starter map)
- x/y: target center in the 0.0–1.0 range within the Android display rectangle
- radius/deadzone: aim/movement size and neutral region
- enabled: whether the control is active

A quick skill tap becomes a down/up touch at its mapped center. The phone's gesture stream becomes a held contact; movement direction is computed from the initial phone-touch position and projected onto the target skill's configured radius. The joystick gets a separate contact and maps displacement around its configured center. The uinput backend supports up to ten simultaneous Linux touch slots.

The profile_default.json file is the starter template. The user profile is reloaded after saving. If display resolution changes, recalibrate and restart the engine so the kernel input axes match the desktop dimensions.

### Keyboard hotkeys

A transparent pass-through overlay cannot guarantee keyboard interception under GNOME Wayland. Supported choices are:

- Focus the overlay while editing/testing to use its local key handlers.
- Explicitly enable **global keyboard capture** in the launcher. This uses optional python-evdev to read key codes configured in the profile and does not suppress physical keyboard events.

Global capture may require read access to /dev/input/event devices and may not work under every sandbox/session. Don't add the user to a broad input-access group just to force it. This is not enabled by default.

## Input daemon details

- The host relays validated JSON events to a loopback-only UDP socket at 127.0.0.1:28743. The engine rejects non-loopback senders, malformed/oversized datagrams, unknown event types and sustained traffic above its rate cap.
- The engine maps event aliases to profile controls and projects normalized coordinates into the selected target rectangle.
- Linux Protocol-B touch slots use ABS_MT_SLOT, ABS_MT_TRACKING_ID, ABS_MT_POSITION_X/Y, ABS_MT_PRESSURE, BTN_TOUCH and SYN_REPORT.
- A watchdog releases held contacts when input becomes idle, and shutdown releases all active contacts.
- The daemon is a user process; the dedicated udev rule is only for /dev/uinput access.

### Latency and touch-target caveats

This path avoids spawning a subprocess per movement and avoids a second LAN listener. **It cannot guarantee less than 5 ms end-to-end or zero missed touches.** Kernel scheduling, compositor routing, resolution scaling, game rendering, Wi-Fi jitter and device polling still add delay. The code has not been validated on this laptop's specific GPU/compositor or in a live MLBB match.

The uinput device is a desktop-level touchscreen. The compositor may route events to the focused/underlying surface rather than the Android guest if the graphics/runtime combination doesn't forward absolute touch as expected. Test with a harmless app first, then MLBB Practice Mode. Stop the engine to return to the previous bridge route.

No game process hooks, memory reads, executable injection, anti-cheat bypass, automatic gameplay loops, or repeated-cast macros are included. Inputs come from user-controlled phone gestures or explicit keyboard events.

## Emulator tools auto-updater

The launcher checks:

https://raw.githubusercontent.com/AndrewHorrison/mlbb-link-cloud-build/main/updates/emulator-latest.json

When a newer version appears, it asks before updating. It downloads the versioned emulator-tools tarball, verifies SHA-256, checks the embedded package version and allowed-file list, rejects unsafe paths and symlinks, stages files and atomically replaces the user-space companion files with rollback on write failure.

This updater updates **MLBB Link Emulator Tools only**. It does not update Android system/vendor images, Google Play Services, ARM translation, the kernel, or Bazzite. The Android APK updater is separate and uses updates/latest.json.

## Troubleshooting

**Engine won't start:** open ~/.local/share/mlbb-link-emulator/engine.log. Check /dev/uinput exists and is group-writable after logging out/in. Check that the uinput module is loaded. Do not run the GUI or daemon with sudo.

**No touch reaches Android:** make sure the Android display is visible, recalibrate the target window, check screen resolution/button positions, and try a basic touch. Some GNOME Wayland/Waydroid/GPU combinations don't route a virtual absolute touchscreen to the Android surface. Stop the engine to return to the bridge route.

**Overlay won't click through:** window input transparency is compositor-dependent. GNOME Wayland restricts global window/input behavior; use edit mode or the existing bridge route if pass-through is unsupported.

**Play Store unavailable or game refuses to launch:** use the Bazzite Waydroid extras and certification guide. The keymapper cannot add missing Google licensing/Play Integrity support or translate an incompatible ARM-only APK by itself.

**Updater says version is current:** emulator tools use their own emulator-latest.json manifest, separate from the phone APK version manifest. Open the emulator release page to see the published version.

## References

- Bazzite Waydroid Setup Guide: https://docs.bazzite.gg/Installing_and_Managing_Software/Waydroid_Setup_Guide/
- Waydroid desktop installation / official OTA URLs: https://docs.waydro.id/usage/install-on-desktops
- Waydroid custom images: https://docs.waydro.id/faq/using-custom-waydroid-images
- Waydroid app install / x86_64 compatibility: https://docs.waydro.id/usage/install-and-run-android-applications
- Linux uinput API: https://docs.kernel.org/input/uinput.html
- GitHub release page: https://github.com/AndrewHorrison/mlbb-link-cloud-build/releases

Independent community software; not affiliated with or endorsed by Moonton. Android/Waydroid compatibility is device-dependent.
