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

# Replace the generic prototype overlay with a compact, in-game HUD-inspired layout.
def replace_java_section(source, start_marker, end_marker, replacement, label):
    start_at = source.find(start_marker)
    end_at = source.find(end_marker, start_at + len(start_marker))
    if start_at < 0 or end_at < 0:
        raise SystemExit("Could not locate " + label + " section")
    return source[:start_at] + replacement + "\n\n" + source[end_at:]

s = replace_java_section(s,
    "        private void drawBackground(Canvas c) {",
    "        private void drawTopHud(Canvas c) {",
    r"""        private void drawBackground(Canvas c) {
            p.setStyle(Paint.Style.FILL);
            p.setShader(new LinearGradient(0, 0, w, h,
                    new int[]{0xFF1B302B, 0xFF122327, 0xFF0A151A}, null, Shader.TileMode.CLAMP));
            c.drawRect(0, 0, w, h, p);
            p.setShader(null);
            p.setColor(0x52030A0D);
            c.drawRect(0, 0, w, h, p);
        }""",
    "background")

s = replace_java_section(s,
    "        private void drawTopHud(Canvas c) {",
    "        private void drawPointControl(Canvas c) {",
    r"""        private void drawTopHud(Canvas c) {
            float[] heroXs = {0.045f, 0.090f, 0.135f};
            float heroY = h * 0.065f;
            float heroR = unit * 0.022f;
            for (int i = 0; i < heroes.length; i++) {
                float x = w * heroXs[i];
                p.setStyle(Paint.Style.FILL);
                p.setColor(0xD90A141A);
                c.drawCircle(x, heroY, heroR * 1.14f, p);
                p.setStyle(Paint.Style.STROKE);
                p.setStrokeWidth(i == heroIndex ? unit * 0.004f : unit * 0.0018f);
                p.setColor(i == heroIndex ? 0xFFFFD36D : 0xFF60737B);
                c.drawCircle(x, heroY, heroR, p);
                p.setStyle(Paint.Style.FILL);
                text(c, i == 0 ? "N" : (i == 1 ? "D" : "S"), x, heroY + heroR * 0.34f,
                        heroR * 1.06f, Color.WHITE, true, Paint.Align.CENTER);
            }
            RectF scoreBox = new RectF(w * 0.405f, h * 0.026f, w * 0.595f, h * 0.092f);
            p.setStyle(Paint.Style.FILL);
            p.setColor(0xC80A141A);
            c.drawRoundRect(scoreBox, unit * 0.012f, unit * 0.012f, p);
            p.setStyle(Paint.Style.STROKE);
            p.setStrokeWidth(unit * 0.0018f);
            p.setColor(0x665E8791);
            c.drawRoundRect(scoreBox, unit * 0.012f, unit * 0.012f, p);
            p.setStyle(Paint.Style.FILL);
            text(c, "0", w * 0.435f, h * 0.068f, unit * 0.025f, 0xFFF2F6F8, true, Paint.Align.CENTER);
            text(c, "00:00", w * 0.500f, h * 0.067f, unit * 0.019f, 0xFFE9D9A3, true, Paint.Align.CENTER);
            text(c, "0", w * 0.565f, h * 0.068f, unit * 0.025f, 0xFFF2F6F8, true, Paint.Align.CENTER);
            p.setColor(0x665E8791);
            c.drawLine(w * 0.468f, h * 0.039f, w * 0.468f, h * 0.079f, p);
            c.drawLine(w * 0.532f, h * 0.039f, w * 0.532f, h * 0.079f, p);
            p.setStyle(Paint.Style.FILL);
            p.setColor(targetSet ? 0xFF71E0A1 : 0xFF8B939A);
            c.drawCircle(w * 0.735f, h * 0.060f, unit * 0.007f, p);
            text(c, "◆ 0", w * 0.866f, h * 0.068f, unit * 0.017f, 0xFFEED18A, true, Paint.Align.CENTER);
        }""",
    "top HUD")

s = replace_java_section(s,
    "        private void drawPointControl(Canvas c) {",
    "        private void drawJoystick(Canvas c) {",
    r"""        private void drawPointControl(Canvas c) {
            float x = w * 0.735f, y = h * 0.472f, r = unit * 0.022f;
            p.setStyle(Paint.Style.FILL);
            p.setColor(skillPoints > 0 ? 0xFFFFD34F : 0xBB1A2830);
            c.drawCircle(x, y, r, p);
            p.setStyle(Paint.Style.STROKE);
            p.setStrokeWidth(unit * 0.0025f);
            p.setColor(skillPoints > 0 ? 0xFFFFF0A2 : 0xFF65737B);
            c.drawCircle(x, y, r, p);
            p.setStyle(Paint.Style.FILL);
            text(c, "+", x, y + r * 0.42f, r * 1.62f,
                    skillPoints > 0 ? 0xFF392906 : 0xFF89939A, true, Paint.Align.CENTER);
        }""",
    "skill-point control")

s = replace_java_section(s,
    "        private void drawMicButton(Canvas c) {",
    "        private void drawSmallButton(Canvas c,",
    r"""        private void drawMicButton(Canvas c) {
            float x = w * 0.485f, y = h * 0.815f, r = unit * 0.044f;
            int accent = micActive ? 0xFF74F0B1 : 0xFF73B6D8;
            p.setStyle(Paint.Style.FILL);
            p.setColor(0xC809151A);
            c.drawCircle(x, y, r * 1.14f, p);
            p.setStyle(Paint.Style.STROKE);
            p.setStrokeWidth(unit * 0.0035f);
            p.setColor(accent);
            c.drawCircle(x, y, r, p);
            p.setStyle(Paint.Style.FILL);
            p.setShader(new LinearGradient(x-r, y-r, x+r, y+r, 0xFF345B68, 0xFF101A22, Shader.TileMode.CLAMP));
            c.drawCircle(x, y, r * 0.84f, p);
            p.setShader(null);
            p.setStyle(Paint.Style.STROKE);
            p.setStrokeCap(Paint.Cap.ROUND);
            p.setStrokeWidth(r * 0.16f);
            p.setColor(Color.WHITE);
            c.drawRoundRect(new RectF(x - r*0.18f, y - r*0.57f, x + r*0.18f, y + r*0.10f), r*0.2f, r*0.2f, p);
            c.drawArc(new RectF(x-r*0.46f, y-r*0.22f, x+r*0.46f, y+r*0.40f), 0, 180, false, p);
            c.drawLine(x, y+r*0.40f, x, y+r*0.61f, p);
            c.drawLine(x-r*0.25f, y+r*0.61f, x+r*0.25f, y+r*0.61f, p);
            p.setStyle(Paint.Style.FILL);
        }""",
    "microphone button")

s = replace_java_section(s,
    "        private void drawSmallButton(Canvas c,",
    "        private void drawSkillButton(Canvas c,",
    r"""        private void drawSmallButton(Canvas c, float x, float y, float r, String icon, String label, int accent, String name) {
            p.setStyle(Paint.Style.FILL);
            p.setColor(0xD0071118);
            c.drawCircle(x, y, r * 1.12f, p);
            p.setStyle(Paint.Style.STROKE);
            p.setStrokeWidth(unit * 0.003f);
            p.setColor(accent);
            c.drawCircle(x, y, r, p);
            p.setStyle(Paint.Style.FILL);
            p.setShader(new LinearGradient(x-r, y-r, x+r, y+r, 0xFF354D57, 0xFF101920, Shader.TileMode.CLAMP));
            c.drawCircle(x, y, r * 0.85f, p);
            p.setShader(null);
            p.setStrokeCap(Paint.Cap.ROUND);
            p.setStrokeJoin(Paint.Join.ROUND);
            Path path = new Path();
            if ("recall".equals(name)) {
                p.setStyle(Paint.Style.STROKE);
                p.setStrokeWidth(r * 0.16f);
                p.setColor(0xFFBCEBFF);
                c.drawArc(new RectF(x-r*0.48f, y-r*0.48f, x+r*0.48f, y+r*0.48f), -65, 285, false, p);
                path.moveTo(x+r*0.26f, y-r*0.43f);
                path.lineTo(x+r*0.52f, y-r*0.42f);
                path.lineTo(x+r*0.39f, y-r*0.18f);
                c.drawPath(path, p);
            } else if ("regen".equals(name)) {
                p.setStyle(Paint.Style.STROKE);
                p.setStrokeWidth(r * 0.13f);
                p.setColor(0xFFD9FFD1);
                path.moveTo(x, y+r*0.48f); path.lineTo(x, y-r*0.39f);
                c.drawPath(path, p);
                path.reset(); path.moveTo(x, y-r*0.02f); path.quadTo(x-r*0.48f,y-r*0.45f,x-r*0.43f,y-r*0.04f); path.quadTo(x-r*0.18f,y+r*0.19f,x,y-r*0.02f);
                c.drawPath(path, p);
                path.reset(); path.moveTo(x, y+r*0.10f); path.quadTo(x+r*0.47f,y-r*0.34f,x+r*0.41f,y+r*0.06f); path.quadTo(x+r*0.18f,y+r*0.28f,x,y+r*0.10f);
                c.drawPath(path, p);
                p.setStrokeWidth(r * 0.08f);
                c.drawLine(x-r*0.22f, y+r*0.48f, x+r*0.22f, y+r*0.48f, p);
            } else {
                p.setStyle(Paint.Style.FILL);
                p.setColor(0xFFFFE8A0);
                path.moveTo(x+r*0.10f, y-r*0.55f);
                path.lineTo(x-r*0.27f, y+r*0.02f);
                path.lineTo(x-r*0.02f, y+r*0.02f);
                path.lineTo(x-r*0.16f, y+r*0.51f);
                path.lineTo(x+r*0.31f, y-r*0.12f);
                path.lineTo(x+r*0.06f, y-r*0.12f);
                path.close();
                c.drawPath(path, p);
            }
            p.setStyle(Paint.Style.FILL);
            String pretty = "recall".equals(name) ? "Recall" : ("regen".equals(name) ? "Regen" : "Flicker");
            text(c, pretty, x, y + r * 1.43f, unit * 0.0095f, 0xFFD0DCE3, false, Paint.Align.CENTER);
        }""",
    "utility buttons")

s = replace_java_section(s,
    "        private void drawAttackButton(Canvas c) {",
    "        private void drawShopButton(Canvas c) {",
    r"""        private void drawAttackButton(Canvas c) {
            float x = attackX * w, y = attackY * h, r = unit * 0.082f;
            p.setStyle(Paint.Style.FILL);
            p.setColor(0xD807121A);
            c.drawCircle(x, y, r * 1.16f, p);
            p.setStyle(Paint.Style.STROKE);
            p.setStrokeWidth(unit * 0.006f);
            p.setColor(0xFF7BD7F5);
            c.drawCircle(x, y, r, p);
            p.setStyle(Paint.Style.FILL);
            p.setShader(new LinearGradient(x-r, y-r, x+r, y+r, 0xFF6DAFD0, 0xFF152D43, Shader.TileMode.CLAMP));
            c.drawCircle(x, y, r * 0.86f, p);
            p.setShader(null);
            Path sword = new Path();
            sword.moveTo(x-r*0.12f, y+r*0.52f);
            sword.lineTo(x+r*0.32f, y-r*0.36f);
            sword.lineTo(x+r*0.46f, y-r*0.16f);
            sword.lineTo(x+r*0.03f, y+r*0.60f);
            sword.close();
            p.setColor(0xFFEAF7FF);
            c.drawPath(sword, p);
            p.setStyle(Paint.Style.STROKE);
            p.setStrokeWidth(r * 0.10f);
            p.setStrokeCap(Paint.Cap.ROUND);
            p.setColor(0xFF172A38);
            c.drawLine(x-r*0.25f, y+r*0.20f, x+r*0.23f, y+r*0.40f, p);
            c.drawLine(x-r*0.08f, y+r*0.36f, x-r*0.20f, y+r*0.50f, p);
            p.setStyle(Paint.Style.FILL);
        }""",
    "attack button")

s = replace_java_section(s,
    "        private void drawShopButton(Canvas c) {",
    "        private void drawBottomHints(Canvas c) {",
    r"""        private void drawShopButton(Canvas c) {
            float x = w * 0.963f, y = h * 0.075f, r = unit * 0.033f;
            p.setStyle(Paint.Style.FILL);
            p.setColor(0xCC101A21);
            c.drawCircle(x, y, r * 1.12f, p);
            p.setStyle(Paint.Style.STROKE);
            p.setStrokeWidth(unit * 0.0025f);
            p.setColor(0xFFE5C273);
            c.drawCircle(x, y, r, p);
            p.setStyle(Paint.Style.FILL);
            p.setColor(0xFF243540);
            c.drawRoundRect(new RectF(x-r*0.48f, y-r*0.12f, x+r*0.48f, y+r*0.43f), r*0.08f, r*0.08f, p);
            p.setStyle(Paint.Style.STROKE);
            p.setStrokeWidth(r*0.12f);
            p.setColor(0xFFFFE7A1);
            c.drawArc(new RectF(x-r*0.29f, y-r*0.53f, x+r*0.29f, y+r*0.06f), 180, 180, false, p);
            p.setStyle(Paint.Style.FILL);
        }""",
    "shop button")

s = replace_java_section(s,
    "        private void drawBottomHints(Canvas c) {",
    "        private void text(Canvas c,",
    r"""        private void drawBottomHints(Canvas c) {
            // Keep the landscape HUD clean; no developer disclaimers over the play area.
        }""",
    "bottom hints")

s = s.replace('            text(c, "MOVE", x, y + joyRadius * 1.48f, unit * 0.016f, 0xFFC0CEDA, true, Paint.Align.CENTER);\n', '')
s = s.replace('if (x >= w * 0.378f && x <= w * 0.493f && y >= h * 0.205f && y <= h * 0.257f) return "skillpoint";',
              'if (inside(x, y, 0.735f, 0.472f, 0.035f)) return "skillpoint";')
s = s.replace('''        private boolean heroTabHit(float x, float y) {
            return y < h * 0.23f && x < w * 0.36f && y > h * 0.09f;
        }

        private void chooseHero(float x) {
            float tabW = w * 0.095f, gap = w * 0.008f;
            int next = (int) ((x - w * 0.028f) / (tabW + gap));''',
'''        private boolean heroTabHit(float x, float y) {
            return y >= h * 0.025f && y <= h * 0.105f && x < w * 0.17f;
        }

        private void chooseHero(float x) {
            int next = Math.round((x / w - 0.045f) / 0.045f);''')

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

if 'android.permission.ACCESS_NETWORK_STATE' not in m:
    permission = '  <uses-permission android: name="android.permission.ACCESS_NETWORK_STATE" />'.replace('android: name', 'android:name')
    internet_permission = '  <uses-permission android:permission="android.permission.INTERNET" />'.replace('android:permission=', 'android:name=')
    if internet_permission in m:
        m = m.replace(internet_permission, internet_permission + chr(10) + permission, 1)
    else:
        pos = m.find('>')
        if pos < 0:
            raise SystemExit("Bridge manifest opening tag not found")
        m = m[:pos + 1] + chr(10) + permission + m[pos + 1:]

bridge_manifest.write_text(m)
# Mark the updated controller and bridge as release 0.3.0.
for gradle_file in [
    root / "phone-controller/app/build.gradle",
    root / "waydroid-touch-bridge/app/build.gradle",
]:
    gradle_text = gradle_file.read_text()
    gradle_text = gradle_text.replace("versionCode 2; versionName '0.2.0'", "versionCode 4; versionName '0.4.0'")
    gradle_file.write_text(gradle_text)

print("Patched hero skill art, IP discovery, clean HUD, LAN dashboard binding, and app version 0.3.0.")
