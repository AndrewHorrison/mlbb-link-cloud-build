#!/usr/bin/env python3
"""Fix skill tap/aim handling, coalesce high-rate packets, and polish the MLBB-style controller HUD."""
from __future__ import annotations

import re
import sys
from pathlib import Path


def replace_java_method(source: str, signature: str, replacement: str) -> str:
    start = source.find(signature)
    if start < 0:
        raise SystemExit("Java method not found: " + signature)
    brace = source.find("{", start)
    if brace < 0:
        raise SystemExit("Opening brace missing for " + signature)
    depth = 0
    in_string = in_char = escaped = line_comment = block_comment = False
    i = brace
    while i < len(source):
        ch = source[i]
        nxt = source[i + 1] if i + 1 < len(source) else ""
        if line_comment:
            if ch == "\n": line_comment = False
        elif block_comment:
            if ch == "*" and nxt == "/": block_comment = False; i += 1
        elif in_string:
            if escaped: escaped = False
            elif ch == "\\": escaped = True
            elif ch == '"': in_string = False
        elif in_char:
            if escaped: escaped = False
            elif ch == "\\": escaped = True
            elif ch == "'": in_char = False
        elif ch == "/" and nxt == "/": line_comment = True; i += 1
        elif ch == "/" and nxt == "*": block_comment = True; i += 1
        elif ch == '"': in_string = True
        elif ch == "'": in_char = True
        elif ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[:start] + replacement + source[i + 1:]
        i += 1
    raise SystemExit("Unclosed Java method: " + signature)


def once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one marker, found {count}")
    return source.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: fix_skill_connection_ui.py source/mlbb-link")
    root = Path(sys.argv[1])
    java_path = root / "phone-controller/app/src/main/java/com/mlbblink/controller/MainActivity.java"
    bridge_path = root / "waydroid-touch-bridge/app/src/main/java/com/mlbblink/bridge/TouchAccessibilityService.java"
    manifest_path = root / "phone-controller/app/src/main/AndroidManifest.xml"
    gradle_path = root / "phone-controller/app/build.gradle"
    if not all(path.is_file() for path in (java_path, bridge_path, manifest_path, gradle_path)):
        raise SystemExit("Expected phone controller, bridge, manifest, and Gradle files")

    java = java_path.read_text(encoding="utf-8")
    gradle = gradle_path.read_text(encoding="utf-8")
    match = re.search(r"versionName\s+['\"]([^'\"]+)['\"]", gradle)
    if not match:
        raise SystemExit("Could not read versionName from phone-controller Gradle file")
    version = match.group(1)

    if "private boolean aimGestureStarted = false;" not in java:
        java = once(java, "private boolean aimCancelHovered = false;",
                    "private boolean aimCancelHovered = false;\n        private boolean aimGestureStarted = false;",
                    "skill-gesture state")

    java = replace_java_method(java, "        private void beginSkillAim(int pointerId, String name, float x, float y)", r"""        private void beginSkillAim(int pointerId, String name, float x, float y) {
            aimPointer = pointerId;
            aimSkill = Integer.parseInt(name.substring("skill".length()));
            aimStartX = aimX = x;
            aimStartY = aimY = y;
            aimCancelHovered = false;
            aimGestureStarted = false;
            soraFormPreview = 0;
            // Do not send a held/drag gesture yet. A stationary finger is a normal skill tap.
            invalidate();
        }""")

    java = replace_java_method(java, "        private void finishSkillAim(int pointerId, String name, float x, float y, boolean systemCancelled)", r"""        private void finishSkillAim(int pointerId, String name, float x, float y, boolean systemCancelled) {
            int skill = Integer.parseInt(name.substring("skill".length()));
            boolean cancel = systemCancelled || (pointerId == aimPointer && aimGestureStarted
                    && (aimCancelHovered || isAimCancelZone(x, y)));
            if (cancel) {
                if (aimGestureStarted) emitGesture(name, "cancel", 0.86f, 0.18f);
                Toast.makeText(MainActivity.this, "Skill cancelled", Toast.LENGTH_SHORT).show();
            } else {
                if (aimGestureStarted) {
                    emitGesture(name, "up", x / w, y / h);
                } else {
                    // A quick tap is delivered as the bridge's reliable 50 ms tap, not a zero-length stroke.
                    emitButton("skill" + (skill + 1), "down", aimStartX / w, aimStartY / h);
                }
                long now = SystemClock.uptimeMillis();
                if (heroIndex == 2 && skill == 2 && soraForm == 0 && soraFormPreview != 0) {
                    soraForm = soraFormPreview; soraFormUntil = now + 10000L; soraCloudstep = 0;
                    Toast.makeText(MainActivity.this, "Sora transformed to " + (soraForm == 1 ? "Thunder" : "Torrent") + " for 10 seconds", Toast.LENGTH_SHORT).show();
                    cooldownUntil[skill] = now + currentSkillCooldown(skill);
                } else {
                    cooldownUntil[skill] = now + currentSkillCooldown(skill);
                    if (heroIndex == 2 && skill == 2 && soraForm != 0 && soraCloudstep >= 5) {
                        soraCloudstep = 0;
                        Toast.makeText(MainActivity.this, "True Art used • reset Cloudstep tracker", Toast.LENGTH_SHORT).show();
                    }
                }
            }
            if (pointerId == aimPointer) {
                aimPointer = -1; aimSkill = -1; aimCancelHovered = false;
                aimGestureStarted = false; soraFormPreview = 0;
            }
            invalidate();
        }""")

    # Start a touch stroke only after intentional movement, rather than interpreting every tap as a drag.
    move_call = 'emitGesture(heldName, "move", aimX / w, aimY / h);'
    move_replacement = r"""if (!aimGestureStarted) {
                            float moveX = aimX - aimStartX, moveY = aimY - aimStartY;
                            if (moveX * moveX + moveY * moveY >= unit * unit * 0.000324f) {
                                aimGestureStarted = true;
                                emitGesture(heldName, "down", aimStartX / w, aimStartY / h);
                            }
                        }
                        if (aimGestureStarted) emitGesture(heldName, "move", aimX / w, aimY / h);"""
    if move_call in java:
        java = once(java, move_call, move_replacement, "delayed aim gesture start")
    elif "moveX * moveX + moveY * moveY >= unit * unit * 0.000324f" not in java:
        raise SystemExit("Skill aim MOVE dispatch marker missing")

    # Use a single in-flight network worker, cache the IP resolution, and keep only the newest movement sample.
    sender_sig = "        void send(JSONObject event) {"
    sender_replacement = r"""        void send(JSONObject event) {
            if (event == null) return;
            String type = event.optString("type");
            String state = event.optString("state");
            if ("move".equals(state) && "joystick".equals(type)) {
                pendingJoystickMove.set(event);
                scheduleMovementDrain();
                return;
            }
            if ("move".equals(state) && "gesture".equals(type)) {
                pendingGestureMove.set(event);
                scheduleMovementDrain();
                return;
            }
            io.execute(() -> transmit(event));
        }
        private void scheduleMovementDrain() {
            if (movementDrainQueued.compareAndSet(false, true)) io.execute(this::drainMovement);
        }
        private void drainMovement() {
            while (true) {
                JSONObject joystick = pendingJoystickMove.getAndSet(null);
                JSONObject gesture = pendingGestureMove.getAndSet(null);
                if (joystick != null) transmit(joystick);
                if (gesture != null) transmit(gesture);
                movementDrainQueued.set(false);
                if ((pendingJoystickMove.get() != null || pendingGestureMove.get() != null)
                        && movementDrainQueued.compareAndSet(false, true)) continue;
                return;
            }
        }
        private void transmit(JSONObject event) {
            InetAddress address = targetAddress;
            if (address == null) return;
            try {
                ensureSocket();
                if (socket == null || socket.isClosed()) return;
                byte[] bytes = event.toString().getBytes(StandardCharsets.UTF_8);
                socket.send(new DatagramPacket(bytes, bytes.length, address, PHONE_PORT));
            } catch (Exception ignored) { }
        }"""
    if sender_sig in java:
        java = replace_java_method(java, sender_sig, sender_replacement)
    elif "private void scheduleMovementDrain()" not in java:
        raise SystemExit("Could not locate UdpSender send method")

    if "private final java.util.concurrent.atomic.AtomicReference<JSONObject> pendingJoystickMove" not in java:
        java = once(java,
            "        private final ExecutorService io = Executors.newSingleThreadExecutor();",
            "        private final ExecutorService io = Executors.newSingleThreadExecutor();\n"
            "        private final java.util.concurrent.atomic.AtomicReference<JSONObject> pendingJoystickMove = new java.util.concurrent.atomic.AtomicReference<>();\n"
            "        private final java.util.concurrent.atomic.AtomicReference<JSONObject> pendingGestureMove = new java.util.concurrent.atomic.AtomicReference<>();\n"
            "        private final java.util.concurrent.atomic.AtomicBoolean movementDrainQueued = new java.util.concurrent.atomic.AtomicBoolean(false);\n"
            "        private volatile InetAddress targetAddress;",
            "low-latency sender fields")
        java = once(java, "        void setHost(String value) { host = value; }",
            r"""        void setHost(String value) {
            host = value == null ? null : value.trim();
            try { targetAddress = host == null || host.isEmpty() ? null : InetAddress.getByName(host); }
            catch (Exception ignored) { targetAddress = null; }
        }""", "cached target resolution")
    elif "targetAddress" not in java:
        raise SystemExit("Movement coalescing exists but destination cache is missing")

    # Slightly larger touch targets follow the community's preference for larger skill buttons.
    for old, new in (("0.059f", "0.066f"), ("0.060f", "0.067f"), ("0.063f", "0.071f"),
                     ("0.074f", "0.082f"), ("0.078f", "0.087f")):
        java = java.replace(old, new)

    # A semi-transparent minimap makes the controller resemble a customizable MLBB HUD.
    minimap = r"""        private void drawMiniMap(Canvas c) {
            float left = w * 0.024f, top = h * 0.122f, mw = w * 0.205f, mh = h * 0.245f;
            RectF map = new RectF(left, top, left + mw, top + mh);
            p.setStyle(Paint.Style.FILL); p.setShader(null); p.setColor(0xC916342F);
            c.drawRoundRect(map, unit * 0.012f, unit * 0.012f, p);
            p.setStyle(Paint.Style.STROKE); p.setStrokeWidth(unit * 0.002f); p.setColor(0xB9A7C8B5);
            c.drawRoundRect(map, unit * 0.012f, unit * 0.012f, p);
            float padX = mw * 0.10f, padY = mh * 0.10f;
            float x1 = left + padX, x2 = left + mw - padX, y1 = top + padY, y2 = top + mh - padY;
            p.setColor(0x886F9F82); p.setStrokeWidth(unit * 0.012f);
            Path lane = new Path(); lane.moveTo(x1, y1); lane.lineTo(x2, y2); c.drawPath(lane, p);
            lane.reset(); lane.moveTo(x1, y2); lane.lineTo(x2, y1); c.drawPath(lane, p);
            lane.reset(); lane.moveTo(left + mw * 0.50f, y1); lane.lineTo(left + mw * 0.50f, y2); c.drawPath(lane, p);
            p.setColor(0xFF66BDE9); p.setStyle(Paint.Style.FILL); c.drawCircle(x1, y1, unit * 0.010f, p);
            p.setColor(0xFFFF7777); c.drawCircle(x2, y2, unit * 0.010f, p);
            p.setColor(0xFF9BDCF6); c.drawCircle(left + mw * 0.24f, top + mh * 0.25f, unit * 0.006f, p);
            c.drawCircle(left + mw * 0.31f, top + mh * 0.36f, unit * 0.006f, p);
            c.drawCircle(left + mw * 0.43f, top + mh * 0.60f, unit * 0.006f, p);
            p.setColor(0xFFFFA2A2); c.drawCircle(left + mw * 0.70f, top + mh * 0.34f, unit * 0.006f, p);
            c.drawCircle(left + mw * 0.77f, top + mh * 0.72f, unit * 0.006f, p);
            p.setColor(0xFFD9E9D9); p.setTextSize(unit * 0.012f); p.setTypeface(Typeface.create("sans-serif", Typeface.BOLD));
            p.setTextAlign(Paint.Align.LEFT); c.drawText("MAP", left + unit * 0.008f, top + unit * 0.018f, p);
            p.setStyle(Paint.Style.FILL);
        }

"""
    if "private void drawMiniMap(Canvas c)" not in java:
        java = once(java, "        private void drawTopHud(Canvas c) {",
                    minimap + "        private void drawTopHud(Canvas c) {", "minimap method insertion")
    if "drawMiniMap(canvas);" not in java:
        java = once(java,
            "            drawBackground(canvas);\n            drawTopHud(canvas);",
            "            drawBackground(canvas);\n            drawMiniMap(canvas);\n            drawTopHud(canvas);",
            "minimap display")
    if 'text(c, "MLBB LINK v' not in java:
        java = once(java, "            drawShopButton(canvas);",
                    '            drawShopButton(canvas);\n            text(canvas, "MLBB LINK v' + version + '", w * 0.82f, h * 0.035f, unit * 0.015f, 0xFFC8D9E5, true, Paint.Align.CENTER);',
                    "controller visible version")
    java_path.write_text(java, encoding="utf-8")

    # Make the app's launcher label visibly include the exact version.
    manifest = manifest_path.read_text(encoding="utf-8")
    label = f'MLBB Link v{version}'
    if re.search(r'android:label="[^"]*"', manifest):
        manifest = re.sub(r'android:label="[^"]*"', f'android:label="{label}"', manifest)
    else:
        manifest, count = re.subn(r'(<application\b)', r'\1 android:label="' + label + '"', manifest, count=1)
        if count != 1:
            raise SystemExit("Could not add versioned application label to AndroidManifest.xml")
    manifest_path.write_text(manifest, encoding="utf-8")

    # Ensure the bridge can recognize the new down/up strategy using its existing tap handler.
    bridge = bridge_path.read_text(encoding="utf-8")
    if '"button".equals(type)' not in bridge or 'tap(screenPoint' not in bridge:
        raise SystemExit("Bridge button tap handler is missing; normal skill taps cannot be delivered")
    required = ("aimGestureStarted", "pendingJoystickMove", "drawMiniMap(canvas)",
                'android:label="MLBB Link v' + version + '"', "MLBB LINK v" + version)
    checks = {
        "delayed aim gesture": "aimGestureStarted" in java,
        "movement coalescing": "pendingJoystickMove" in java and "drainMovement" in java,
        "cached PC IP": "targetAddress = host == null" in java,
        "minimap": "drawMiniMap(canvas)" in java and "private void drawMiniMap(Canvas c)" in java,
        "versioned launcher label": f'android:label="{label}"' in manifest,
        "visible UI version": f'MLBB LINK v{version}' in java,
    }
    failed = [key for key, passed in checks.items() if not passed]
    if failed:
        raise SystemExit("Feature checks failed: " + ", ".join(failed))
    print(f"Applied v{version} fixes: skill taps cast directly; held drags aim; movement packets coalesced; larger skills, minimap, and versioned app name.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
