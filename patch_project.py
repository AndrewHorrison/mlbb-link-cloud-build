#!/usr/bin/env python3
"""Patch the archived MLBB Link sources before the Android build."""
from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
phone = root / "phone-controller/app/src/main/java/com/mlbblink/controller/MainActivity.java"
host = root / "host/mlbb_link_host.py"
bridge_manifest = root / "waydroid-touch-bridge/app/src/main/AndroidManifest.xml"

s = phone.read_text()
if "import android.graphics.Bitmap;" not in s:
    s = s.replace("import android.graphics.Canvas;", "import android.graphics.Bitmap;\nimport android.graphics.BitmapFactory;\nimport android.graphics.Rect;\nimport android.graphics.Canvas;", 1)

start = s.find("        private final String[][] skillNames = {")
end = s.find("        private final int[] heroColors", start)
if start < 0 or end < 0:
    raise SystemExit("Could not locate skill names/cooldowns in phone controller")
block = """        private final String[][] skillNames = {
                {"MAGIC BOOMERANG", "MOLINA SMOOCH", "MOLINA BLITZ"},
                {"BURST STRIKE", "SPECTRE STEP", "ABYSM STRIKE"},
                {"SUNDERING STRIKE", "WINDSTRIDE", "SHIFTING SKIES"}
        };
        private final long[][] cooldowns = {
                {5500, 14500, 32000},
                {5000, 8000, 36000},
                {5000, 8000, 24000}
        };
"""
s = s[:start] + block + s[end:]

marker = "        private final int[] skillColors = {0xFF48B7E8, 0xFFAA62E8, 0xFFF0A94E};"
if "private final Bitmap[][] skillArt = new Bitmap[3][3];" not in s:
    if marker not in s: raise SystemExit("Skill color insertion point not found")
    s = s.replace(marker, marker + "\n        private final Bitmap[][] skillArt = new Bitmap[3][3];", 1)

old_ctor = """        ControllerView(Context context) {
            super(context);
            setLayerType(View.LAYER_TYPE_SOFTWARE, null);
            setFocusable(true);
        }"""
new_ctor = """        ControllerView(Context context) {
            super(context);
            setLayerType(View.LAYER_TYPE_SOFTWARE, null);
            setFocusable(true);
            loadSkillArt();
        }

        private void loadSkillArt() {
            String[] keys = {"nana", "dyrroth", "sora"};
            for (int hero = 0; hero < keys.length; hero++) {
                for (int skill = 0; skill < 3; skill++) {
                    int id = getResources().getIdentifier("skill_" + keys[hero] + "_" + (skill + 1),
                            "drawable", getContext().getPackageName());
                    if (id != 0) {
                        try { skillArt[hero][skill] = BitmapFactory.decodeResource(getResources(), id); }
                        catch (RuntimeException ignored) { skillArt[hero][skill] = null; }
                    }
                }
            }
        }"""
if old_ctor in s:
    s = s.replace(old_ctor, new_ctor, 1)
elif "private void loadSkillArt()" not in s:
    raise SystemExit("Could not patch ControllerView constructor")

bg_start = s.find("        private void drawBackground(Canvas c) {")
bg_end = s.find("        private void drawTopHud(Canvas c) {", bg_start)
if bg_start < 0 or bg_end < 0:
    raise SystemExit("Could not locate background drawing method")
bg = """        private void drawBackground(Canvas c) {
            // Minimal dark HUD backdrop; let the authentic circular skill art be the focus.
            p.setStyle(Paint.Style.FILL);
            p.setShader(new LinearGradient(0, 0, 0, h,
                    new int[]{0xFF080D14, 0xFF111A24, 0xFF080C12}, null, Shader.TileMode.CLAMP));
            c.drawRect(0, 0, w, h, p);
            p.setShader(null);
            p.setColor(0xCC080E16); c.drawRect(0, 0, w, h * 0.235f, p);
            p.setColor(0x663E5668); c.drawRect(0, h * 0.235f, w, h * 0.237f, p);
            p.setColor(0x22000000); c.drawRect(0, h * 0.90f, w, h, p);
        }

"""
s = s[:bg_start] + bg + s[bg_end:]

old_art = """            p.setStyle(Paint.Style.FILL); p.setShader(new LinearGradient(x - r, y - r, x + r, y + r, new int[]{accent, 0xFF263343, 0xFF0B111B}, null, Shader.TileMode.CLAMP)); c.drawCircle(x, y, r * 0.87f, p); p.setShader(null);
            drawSkillGlyph(c, skill, x, y - r * 0.04f, r * 0.49f, accent);
            text(c, skill == 2 ? "ULT" : "S" + (skill + 1), x, y + r * 0.67f, r * 0.29f, Color.WHITE, true, Paint.Align.CENTER);"""
new_art = """            p.setStyle(Paint.Style.FILL); p.setShader(null); p.setColor(0xFF101722); c.drawCircle(x, y, r * 0.87f, p);
            Bitmap artwork = skillArt[heroIndex][skill];
            if (artwork != null) {
                int save = c.save();
                Path clip = new Path(); clip.addCircle(x, y, r * 0.845f, Path.Direction.CW); c.clipPath(clip);
                Rect src = new Rect(0, 0, artwork.getWidth(), artwork.getHeight());
                RectF dst = new RectF(x - r * 0.845f, y - r * 0.845f, x + r * 0.845f, y + r * 0.845f);
                p.setStyle(Paint.Style.FILL); p.setShader(null); p.setColor(Color.WHITE);
                c.drawBitmap(artwork, src, dst, p); c.restoreToCount(save);
            } else {
                p.setShader(new LinearGradient(x - r, y - r, x + r, y + r, new int[]{accent, 0xFF263343, 0xFF0B111B}, null, Shader.TileMode.CLAMP));
                c.drawCircle(x, y, r * 0.87f, p); p.setShader(null);
                drawSkillGlyph(c, skill, x, y - r * 0.04f, r * 0.49f, accent);
            }
            p.setStyle(Paint.Style.STROKE); p.setStrokeWidth(unit * 0.0025f); p.setColor(0xFFB5C8D8); c.drawCircle(x, y, r * 0.87f, p); p.setStyle(Paint.Style.FILL);"""
if old_art in s:
    s = s.replace(old_art, new_art, 1)
elif "Bitmap artwork = skillArt[heroIndex][skill];" not in s:
    raise SystemExit("Could not locate skill glyph draw lines")

s = s.replace('''            text(c, skillNames[heroIndex][skill], x, y + r * 1.27f, unit * 0.0092f, 0xFFC7D3DE, true, Paint.Align.CENTER);
            text(c, "Lv." + skillLevels[skill], x, y + r * 1.48f, unit * 0.009f, 0xFFFFD77A, false, Paint.Align.CENTER);
''', "", 1)
phone.write_text(s)

# The dashboard API must be reachable through the Waydroid host gateway.
h = host.read_text().replace(
    'ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)',
    'ThreadingHTTPServer(("0.0.0.0", port), DashboardHandler)')
h = h.replace(
    'Dashboard listens on this PC only; UDP control ports are used on your local network.',
    'Dashboard is reachable on the trusted local network for Waydroid IP discovery; UDP control ports are used on your local network.')
if 'ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)' in h:
    raise SystemExit("PC dashboard bind change failed")
host.write_text(h)

m = bridge_manifest.read_text()
if 'android:usesCleartextTraffic="true"' not in m:
    m = m.replace("<application ", '<application android:usesCleartextTraffic="true" ', 1)
bridge_manifest.write_text(m)
# Mark the updated controller and bridge as release 0.3.0.
for gradle_file in [
    root / "phone-controller/app/build.gradle",
    root / "waydroid-touch-bridge/app/build.gradle",
]:
    gradle_text = gradle_file.read_text()
    gradle_text = gradle_text.replace("versionCode 2; versionName '0.2.0'", "versionCode 3; versionName '0.3.0'")
    gradle_file.write_text(gradle_text)

print("Patched hero skill art, IP discovery, clean HUD, LAN dashboard binding, and app version 0.3.0.")
