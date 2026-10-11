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
                    if (hero == 2) {
                        String[] variants = {"sora_thunder_", "sora_torrent_"};
                        for (int form = 0; form < 2; form++) {
                            int variantId = getResources().getIdentifier(variants[form] + (skill + 1), "drawable", getContext().getPackageName());
                            if (variantId != 0) {
                                try { soraVariantArt[form][skill] = BitmapFactory.decodeResource(getResources(), variantId); }
                                catch (RuntimeException ignored) { soraVariantArt[form][skill] = null; }
                            }
                        }
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
            Bitmap artwork = heroIndex == 2 && soraForm > 0 && soraVariantArt[soraForm - 1][skill] != null
                    ? soraVariantArt[soraForm - 1][skill] : skillArt[heroIndex][skill];
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

# v0.5.0 connection, hero picker and battle-spell artwork.
h = host.read_text()
h = h.replace("import json\nimport re", "import json\nimport ipaddress\nimport re", 1)
ip_start = h.find("def detect_lan_ip() -> str:")
ip_end = h.find("\ndef detect_waydroid_ip()", ip_start)
if ip_start < 0 or ip_end < 0: raise SystemExit("LAN detector marker missing")
ip_detector = r'''def _usable_lan_ip(value: str) -> bool:
    try: address = ipaddress.ip_address(value.strip())
    except (ValueError, AttributeError): return False
    if not isinstance(address, ipaddress.IPv4Address): return False
    if address.is_loopback or address.is_link_local or address.is_unspecified or address.is_multicast: return False
    if value.startswith(("192.168.240.", "192.168.241.")): return False
    return True


def _ignored_interface(name: str) -> bool:
    n = name.lower().split("@", 1)[0]
    return n.startswith(("lo", "docker", "podman", "virbr", "br-", "veth", "waydroid",
                         "tailscale", "wg", "tun", "zt", "cni", "flannel", "pter"))


def _likely_container_ip(value: str, interface: str) -> bool:
    """Reject common rootless-container addresses when they are presented as eth0."""
    name = interface.lower().split("@", 1)[0]
    if name not in {"eth0", "eth1", "ens3"}:
        return False
    try:
        address = ipaddress.IPv4Address(value)
    except ValueError:
        return False
    container_ranges = (
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("10.88.0.0/16"),
        ipaddress.ip_network("10.89.0.0/16"),
        ipaddress.ip_network("10.0.2.0/24"),
        ipaddress.ip_network("10.0.3.0/24"),
    )
    return any(address in network for network in container_ranges)


def detect_lan_ip() -> str:
    """Prefer a usable default-route IPv4 address; never pretend localhost is a LAN IP."""
    try:
        route = subprocess.run(["ip", "-4", "route", "get", "1.1.1.1"],
                               text=True, capture_output=True, timeout=1.5, check=False).stdout
        src = re.search(r"\bsrc\s+([0-9.]+)", route)
        dev = re.search(r"\bdev\s+([^\s]+)", route)
        if src and dev and _usable_lan_ip(src.group(1)) and not _ignored_interface(dev.group(1)) and not _likely_container_ip(src.group(1), dev.group(1)):
            return src.group(1)
    except (OSError, subprocess.SubprocessError): pass
    try:
        routes = subprocess.run(["ip", "-4", "route", "show", "default"],
                                text=True, capture_output=True, timeout=1.5, check=False).stdout.splitlines()
        default_dev = None
        if routes:
            match = re.search(r"\bdev\s+([^\s]+)", routes[0])
            if match: default_dev = match.group(1)
        output = subprocess.run(["ip", "-o", "-4", "addr", "show", "scope", "global"],
                                text=True, capture_output=True, timeout=1.5, check=False).stdout
        candidates = []
        for line in output.splitlines():
            match = re.search(r"\d+:\s+([^\s]+).*?\binet\s+([0-9.]+)/", line)
            if not match: continue
            interface, address = match.group(1), match.group(2)
            if _ignored_interface(interface) or not _usable_lan_ip(address) or _likely_container_ip(address, interface): continue
            low = interface.lower()
            score = 100 if interface == default_dev else 0
            score += 40 if low.startswith(("wl", "wlan")) else 30 if low.startswith(("en", "eth")) else 0
            candidates.append((score, address))
        if candidates:
            candidates.sort(reverse=True)
            return candidates[0][1]
    except (OSError, subprocess.SubprocessError): pass
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("1.1.1.1", 80))
        address = sock.getsockname()[0]
        if _usable_lan_ip(address) and not _likely_container_ip(address, "eth0"): return address
    except OSError: pass
    finally: sock.close()
    try:
        addresses = sorted({info[4][0] for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
                            if info[0] == socket.AF_INET and _usable_lan_ip(info[4][0]) and not _likely_container_ip(info[4][0], "eth0")})
        if addresses: return addresses[0]
    except OSError: pass
    # NetworkManager fallback for Bazzite Wi-Fi/Ethernet addresses.
    try:
        devices = subprocess.run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"], text=True, capture_output=True, timeout=2.0, check=False).stdout.splitlines()
        candidates = []
        for line in devices:
            fields = line.split(":")
            if len(fields) < 3 or fields[2].strip().lower() != "connected": continue
            device, kind = fields[0].strip(), fields[1].strip().lower()
            if _ignored_interface(device): continue
            output = subprocess.run(["nmcli", "-g", "IP4.ADDRESS", "device", "show", device], text=True, capture_output=True, timeout=2.0, check=False).stdout
            for item in output.splitlines():
                address = item.strip().split("/", 1)[0]
                if _usable_lan_ip(address) and not _likely_container_ip(address, device):
                    candidates.append((2 if kind == "wifi" else 1, address))
        if candidates:
            candidates.sort(reverse=True)
            return candidates[0][1]
    except (OSError, subprocess.SubprocessError): pass
    try:
        output = subprocess.run(["hostname", "-I"], text=True, capture_output=True, timeout=1.5, check=False).stdout
        for value in output.split():
            if _usable_lan_ip(value) and not value.startswith(("10.88.", "10.89.", "192.168.240.", "192.168.241.")):
                return value
    except (OSError, subprocess.SubprocessError): pass
    return "not detected"
'''
h=h[:ip_start]+ip_detector+h[ip_end:]
if '"phone_connected": False' not in h:
    h=h.replace('    "last_seen": None,','''    "last_seen": None,
    "phone_seen_epoch": 0.0,
    "phone_connected": False,
    "selected_hero": "Not selected",''',1)
h=h.replace('''def valid_event(obj: object) -> bool:
    return isinstance(obj, dict) and obj.get("type") in {"button", "joystick"}''',
'''def valid_event(obj: object) -> bool:
    return isinstance(obj, dict) and obj.get("type") in {"button", "joystick", "heartbeat", "hero", "gesture"}''',1)
# Dashboard header now reflects the phone heartbeat, not just the running Python process.
js_old="document.getElementById('hostStatus').textContent=d.last_error||'Listening for UDP input';document.getElementById('runState').textContent='HOST RUNNING';document.getElementById('stateDot').classList.add('ok');"
js_new="document.getElementById('hostStatus').textContent=d.last_error||(d.phone_connected?'Phone heartbeat received':'Waiting for phone heartbeat');document.getElementById('selectedHero').textContent=d.selected_hero||'Not selected';document.getElementById('runState').textContent=d.phone_connected?'PHONE CONNECTED':'PHONE DISCONNECTED';document.getElementById('stateDot').classList.toggle('ok',!!d.phone_connected);"
if js_old in h: h=h.replace(js_old,js_new,1)
elif "document.getElementById('selectedHero')" not in h: raise SystemExit("Dashboard status JS missing")
h = h.replace("document.getElementById('hostIp').textContent=d.host_ip||'Not detected';",
            "document.getElementById('hostIp').textContent=(!d.host_ip||d.host_ip==='not detected')?'LAN IP NOT DETECTED':d.host_ip;", 1)
h = h.replace("document.getElementById('hostStatus').textContent=d.last_error||(d.phone_connected?'Phone heartbeat received':'Waiting for phone heartbeat');",
            "document.getElementById('hostStatus').textContent=(!d.host_ip||d.host_ip==='not detected')?'No usable LAN IPv4 found; run the host on Bazzite outside Distrobox/Toolbx':(d.last_error||(d.phone_connected?'Phone heartbeat received':'Waiting for phone heartbeat'));", 1)
if 'id="selectedHero"' not in h:
    row='<div class="row"><span class="muted">Waydroid IP</span><span class="value" id="waydroidIp">Not detected</span></div>'
    if row not in h: raise SystemExit("Dashboard Waydroid row missing")
    h=h.replace(row,row+'<div class="row"><span class="muted">Phone hero</span><span class="value" id="selectedHero">Not selected</span></div>',1)
if "def refresh_dashboard_state()" not in h:
    runtime=r'''

_NETWORK_REFRESH_LOCK = threading.Lock()
_LAST_NETWORK_REFRESH = 0.0


def refresh_dashboard_state() -> None:
    global _LAST_NETWORK_REFRESH
    now = time.time()
    with STATE_LOCK:
        seen = float(STATE.get("phone_seen_epoch") or 0.0)
        STATE["phone_connected"] = bool(seen and now - seen <= 5.5)
    monotonic_now = time.monotonic()
    if monotonic_now - _LAST_NETWORK_REFRESH < 4.0: return
    if not _NETWORK_REFRESH_LOCK.acquire(blocking=False): return
    try:
        monotonic_now = time.monotonic()
        if monotonic_now - _LAST_NETWORK_REFRESH < 4.0: return
        detected = detect_lan_ip()
        if _usable_lan_ip(detected):
            with STATE_LOCK: STATE["host_ip"] = detected
        _LAST_NETWORK_REFRESH = monotonic_now
    finally:
        _NETWORK_REFRESH_LOCK.release()
'''
    marker="\n\nclass DashboardHandler(BaseHTTPRequestHandler):"
    if marker not in h: raise SystemExit("DashboardHandler missing")
    h=h.replace(marker,runtime+marker,1)
h=h.replace('''        if self.path == "/api/status":
            with STATE_LOCK:''','''        if self.path == "/api/status":
            refresh_dashboard_state()
            with STATE_LOCK:''',1)
old_event='''            if not valid_event(obj):
                continue

            forwarded = False'''
new_event='''            if not valid_event(obj):
                continue
            event_type = obj.get("type")
            if event_type in {"heartbeat", "hero"}:
                now = time.time()
                with STATE_LOCK:
                    STATE["phone_seen_epoch"] = now
                    STATE["phone_connected"] = True
                    STATE["last_phone"] = addr[0]
                    STATE["last_seen"] = time.strftime("%H:%M:%S", time.localtime(now))
                    if event_type == "hero":
                        STATE["selected_hero"] = str(obj.get("name", "unknown")).strip().upper()[:32] or "Unknown"
                        STATE["last_event"] = f"Selected hero: {STATE['selected_hero']}"
                    else:
                        STATE["last_event"] = "Phone heartbeat"
                continue
            forwarded = False'''
if old_event in h: h=h.replace(old_event,new_event,1)
elif 'event_type in {"heartbeat", "hero"}' not in h: raise SystemExit("Host receive loop marker missing")
h=h.replace('''                STATE["last_phone"] = addr[0]
                STATE["last_event"] = event_label''','''                STATE["last_phone"] = addr[0]
                STATE["phone_seen_epoch"] = now
                STATE["phone_connected"] = True
                STATE["last_event"] = event_label''',1)
h=h.replace('''            "last_error": None,
            "started_at": time.time(),''','''            "last_error": None,
            "phone_connected": False,
            "phone_seen_epoch": 0.0,
            "selected_hero": "Not selected",
            "started_at": time.time(),''',1)
host.write_text(h)

s=phone.read_text()
s=s.replace("import java.net.InetAddress;","import java.net.InetAddress;\nimport java.net.HttpURLConnection;\nimport java.net.URL;",1)
s=s.replace("import java.util.concurrent.Executors;","import java.util.concurrent.Executors;\nimport java.util.concurrent.ScheduledExecutorService;\nimport java.util.concurrent.TimeUnit;",1)
s=s.replace('''    private TextView linkStatus;
    private EditText hostInput;''','''    private TextView linkStatus;
    private EditText hostInput;
    private final ScheduledExecutorService statusScheduler = Executors.newSingleThreadScheduledExecutor();''',1)
old_init='''        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        String lastHost = prefs.getString("host", "");
        hostInput.setText(lastHost);
        if (!lastHost.isEmpty()) {
            sender.setHost(lastHost);
            controller.setTargetSet(true);
            linkStatus.setText("TARGET SAVED");
        }'''
new_init='''        SharedPreferences prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        String lastHost = prefs.getString("host", "");
        controller.setInitialHero(prefs.getInt("hero_index", 0));
        controller.setInitialSpell(prefs.getInt("spell_index", 0));
        hostInput.setText(lastHost);
        if (!lastHost.isEmpty()) {
            sender.setHost(lastHost);
            sender.start();
            controller.setTargetSet(false);
            linkStatus.setText("CONNECTING");
            linkStatus.setTextColor(0xFFFFD36D);
        } else {
            linkStatus.setText("DISCONNECTED");
            linkStatus.setTextColor(0xFFFFB4A9);
            controller.setTargetSet(false);
        }
        startStatusMonitor();'''
if old_init not in s: raise SystemExit("Phone startup block missing")
s=s.replace(old_init,new_init,1)
old_click='''            sender.setHost(target);
            sender.start();
            getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString("host", target).apply();
            controller.setTargetSet(true);
            linkStatus.setText("TARGET SET");
            linkStatus.setTextColor(0xFFB9F5CB);
            Toast.makeText(this, "Target set to " + target + ":" + PHONE_PORT, Toast.LENGTH_SHORT).show();'''
new_click='''            sender.setHost(target);
            sender.start();
            getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString("host", target).apply();
            controller.setTargetSet(false);
            linkStatus.setText("CONNECTING");
            linkStatus.setTextColor(0xFFFFD36D);
            controller.sendCurrentHero();
            Toast.makeText(MainActivity.this, "Checking PC connection at " + target + ":" + PHONE_PORT, Toast.LENGTH_SHORT).show();'''
if old_click not in s: raise SystemExit("Phone Link handler missing")
s=s.replace(old_click,new_click,1)
if "private void startStatusMonitor()" not in s:
    monitor=r'''
    private void startStatusMonitor() {
        statusScheduler.scheduleWithFixedDelay(() -> {
            String target = sender == null ? null : sender.getHost();
            if (target == null || target.trim().isEmpty()) {
                runOnUiThread(() -> {
                    if (linkStatus != null) {
                        linkStatus.setText("DISCONNECTED");
                        linkStatus.setTextColor(0xFFFFB4A9);
                        if (controller != null) controller.setTargetSet(false);
                    }
                });
                return;
            }
            boolean reachable = probePcDashboard(target.trim());
            runOnUiThread(() -> {
                if (sender == null || !target.trim().equals(sender.getHost()) || linkStatus == null) return;
                linkStatus.setText(reachable ? "CONNECTED" : "DISCONNECTED");
                linkStatus.setTextColor(reachable ? 0xFF71E0A1 : 0xFFFFB4A9);
                if (controller != null) controller.setTargetSet(reachable);
            });
        }, 0, 2, TimeUnit.SECONDS);
    }

    private boolean probePcDashboard(String target) {
        HttpURLConnection connection = null;
        try {
            URL url = new URL("http://" + target + ":28740/api/status");
            connection = (HttpURLConnection) url.openConnection();
            connection.setRequestMethod("GET");
            connection.setConnectTimeout(1500);
            connection.setReadTimeout(1500);
            connection.setUseCaches(false);
            connection.setRequestProperty("Connection", "close");
            return connection.getResponseCode() == 200;
        } catch (Exception ignored) {
            return false;
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

'''
    s=s.replace("    @Override protected void onDestroy() {",monitor+"    @Override protected void onDestroy() {",1)
s=s.replace('''        if (sender != null) sender.stop();
        if (micSender != null) micSender.stop();''','''        statusScheduler.shutdownNow();
        if (sender != null) sender.stop();
        if (micSender != null) micSender.stop();''',1)

if "private boolean heroPickMode = true;" not in s:
    s=s.replace('''        private int heroIndex = 0;
        private final String[] heroes''','''        private int heroIndex = 0;
        private boolean heroPickMode = true;
        private boolean spellPickerOpen = false;
        private int battleSpellIndex = 0;
        private long spellCooldownUntil = 0L;
        private final Map<Integer, Long> buttonDownTimes = new HashMap<>();
        private final String[] battleSpells = {"FLICKER", "RETRIBUTION", "PURIFY", "SPRINT",
                "EXECUTE", "PETRIFY", "INSPIRE", "AEGIS", "VENGEANCE", "FLAMESHOT", "ARRIVAL", "REVITALIZE"};
        private final int[] battleSpellCooldowns = {120, 35, 90, 100, 90, 75, 75, 75, 75, 50, 75, 75};
        private final Bitmap[] spellArt = new Bitmap[12];
        private final String[] heroes''',1)
old_load_end='''                }
            }
        }

        void setTargetSet(boolean value) { targetSet = value; invalidate(); }'''
new_load_end='''                }
            }
            String[] spellKeys = {"flicker", "retribution", "purify", "sprint", "execute", "petrify",
                    "inspire", "aegis", "vengeance", "flameshot", "arrival", "revitalize"};
            for (int i = 0; i < spellKeys.length; i++) {
                int id = getResources().getIdentifier("spell_" + spellKeys[i], "drawable", getContext().getPackageName());
                if (id != 0) {
                    try { spellArt[i] = BitmapFactory.decodeResource(getResources(), id); }
                    catch (RuntimeException ignored) { spellArt[i] = null; }
                }
            }
        }

        void setTargetSet(boolean value) { targetSet = value; invalidate(); }
        void setInitialHero(int index) { if (index >= 0 && index < heroes.length) heroIndex = index; }
        void setInitialSpell(int index) { if (index >= 0 && index < battleSpells.length) battleSpellIndex = index; }
        void sendCurrentHero() { sendHeroSelection(); }
        private void sendHeroSelection() {
            try {
                JSONObject event = new JSONObject();
                event.put("type", "hero");
                event.put("name", heroes[heroIndex].toLowerCase(java.util.Locale.ROOT));
                send(event);
            } catch (Exception ignored) { }
        }
        private void selectHero(int index) {
            if (index < 0 || index >= heroes.length) return;
            heroIndex = index;
            heroPickMode = false;
            spellPickerOpen = false;
            for (int i = 0; i < cooldownUntil.length; i++) cooldownUntil[i] = 0L;
            skillLevels = new int[]{1, 0, 0};
            skillPoints = 1;
            getSharedPreferences(PREFS, MODE_PRIVATE).edit().putInt("hero_index", heroIndex).apply();
            sendHeroSelection();
            Toast.makeText(MainActivity.this, heroes[heroIndex] + " selected", Toast.LENGTH_SHORT).show();
            invalidate();
        }'''
if old_load_end not in s: raise SystemExit("Skill art load method end missing")
s=s.replace(old_load_end,new_load_end,1)

s=s.replace('''            if (w <= 0 || h <= 0) return;
            drawBackground(canvas);
            drawTopHud(canvas);''','''            if (w <= 0 || h <= 0) return;
            if (heroPickMode) {
                drawBackground(canvas);
                drawHeroPicker(canvas);
                return;
            }
            drawBackground(canvas);
            drawTopHud(canvas);''',1)
s=s.replace('''            drawBottomHints(canvas);
            boolean cooling = false;''','''            drawBottomHints(canvas);
            if (spellPickerOpen) drawBattleSpellPicker(canvas);
            boolean cooling = spellCooldownUntil > SystemClock.uptimeMillis();''',1)

picker=r'''
        private void drawHeroPicker(Canvas c) {
            p.setStyle(Paint.Style.FILL); p.setColor(0xE80A1218); c.drawRect(0, 0, w, h, p);
            text(c, "CHOOSE HERO", w * 0.50f, h * 0.105f, unit * 0.050f, 0xFFFFD77A, true, Paint.Align.CENTER);
            int pages = (heroes.length + 8) / 9;
            heroPage = Math.max(0, Math.min(heroPage, pages - 1));
            float cellW = w * 0.235f, cellH = h * 0.185f, gapX = w * 0.035f, gapY = h * 0.025f;
            float leftStart = (w - (3 * cellW + 2 * gapX)) * 0.5f, topStart = h * 0.205f;
            for (int slot = 0; slot < 9; slot++) {
                int hero = heroPage * 9 + slot;
                if (hero >= heroes.length) continue;
                int row = slot / 3, col = slot % 3;
                float left = leftStart + col * (cellW + gapX), top = topStart + row * (cellH + gapY);
                RectF card = new RectF(left, top, left + cellW, top + cellH);
                p.setStyle(Paint.Style.FILL); p.setColor(hero == heroIndex ? 0xDD27382F : 0xD5101D25);
                c.drawRoundRect(card, unit * 0.018f, unit * 0.018f, p);
                p.setStyle(Paint.Style.STROKE); p.setStrokeWidth(hero == heroIndex ? unit * 0.0038f : unit * 0.0015f);
                p.setColor(hero == heroIndex ? 0xFFFFD36D : 0xFF536B78); c.drawRoundRect(card, unit * 0.018f, unit * 0.018f, p);
                p.setStyle(Paint.Style.FILL);
                float radius = Math.min(cellW * 0.31f, cellH * 0.48f), x = left + cellW * 0.5f, y = top + cellH * 0.42f;
                Bitmap portrait = heroPortraits[hero];
                if (portrait != null) {
                    int save = c.save(); Path clip = new Path(); clip.addCircle(x, y, radius, Path.Direction.CW); c.clipPath(clip);
                    Rect src = new Rect(0, 0, portrait.getWidth(), portrait.getHeight());
                    RectF dst = new RectF(x-radius, y-radius, x+radius, y+radius);
                    p.setColor(Color.WHITE); c.drawBitmap(portrait, src, dst, p); c.restoreToCount(save);
                } else {
                    p.setColor(heroColors[hero]); c.drawCircle(x, y, radius, p);
                    if (hero == 2) {
                        p.setColor(0xFFEAF8FF); c.drawCircle(x-radius*0.19f, y-radius*0.08f, radius*0.40f, p);
                        c.drawCircle(x+radius*0.18f, y-radius*0.18f, radius*0.50f, p);
                        c.drawCircle(x+radius*0.43f, y+radius*0.03f, radius*0.31f, p);
                        Path bolt = new Path(); bolt.moveTo(x+radius*0.06f,y-radius*0.05f); bolt.lineTo(x-radius*0.17f,y+radius*0.24f); bolt.lineTo(x+radius*0.03f,y+radius*0.24f); bolt.lineTo(x-radius*0.04f,y+radius*0.53f); bolt.lineTo(x+radius*0.25f,y+radius*0.13f); bolt.lineTo(x+radius*0.09f,y+radius*0.13f); bolt.close();
                        p.setColor(0xFF2273B9); c.drawPath(bolt, p);
                    } else {
                        p.setColor(0xFF14212A); c.drawCircle(x, y, radius * 0.78f, p);
                        text(c, heroes[hero].substring(0, 1), x, y + radius * 0.34f, radius * 1.05f, Color.WHITE, true, Paint.Align.CENTER);
                    }
                }
                p.setStyle(Paint.Style.STROKE); p.setStrokeWidth(unit * 0.002f);
                p.setColor(hero == heroIndex ? 0xFFFFD36D : 0xFF8DA2AD); c.drawCircle(x, y, radius, p);
                p.setStyle(Paint.Style.FILL);
                String name = heroes[hero].substring(0,1) + heroes[hero].substring(1).toLowerCase(java.util.Locale.ROOT);
                text(c, name, x, top + cellH * 0.87f, unit * 0.026f, Color.WHITE, true, Paint.Align.CENTER);
            }
            text(c, "‹ PREV", w * 0.20f, h * 0.865f, unit * 0.023f, heroPage > 0 ? 0xFFFFD77A : 0xFF60717C, true, Paint.Align.CENTER);
            text(c, "PAGE " + (heroPage + 1) + " / " + pages, w * 0.50f, h * 0.865f, unit * 0.022f, 0xFFD2DFE8, true, Paint.Align.CENTER);
            text(c, "NEXT ›", w * 0.80f, h * 0.865f, unit * 0.023f, heroPage < pages - 1 ? 0xFFFFD77A : 0xFF60717C, true, Paint.Align.CENTER);
            text(c, "TAP A HERO ICON TO SELECT", w * 0.50f, h * 0.945f, unit * 0.018f, 0xFF9DAFBC, false, Paint.Align.CENTER);
        }

        private void drawCircularArt(Canvas c, Bitmap art, float x, float y, float r) {
            p.setStyle(Paint.Style.FILL); p.setShader(null); p.setColor(0xFF172630); c.drawCircle(x, y, r * 1.08f, p);
            if (art != null) {
                int save = c.save(); Path clip = new Path(); clip.addCircle(x, y, r, Path.Direction.CW); c.clipPath(clip);
                Rect src = new Rect(0, 0, art.getWidth(), art.getHeight()); RectF dst = new RectF(x-r, y-r, x+r, y+r);
                p.setColor(Color.WHITE); c.drawBitmap(art, src, dst, p); c.restoreToCount(save);
            }
            p.setStyle(Paint.Style.STROKE); p.setStrokeWidth(unit * 0.0025f); p.setColor(0xFFCAD7DF); c.drawCircle(x, y, r, p); p.setStyle(Paint.Style.FILL);
        }

        private void drawBattleSpellPicker(Canvas c) {
            p.setStyle(Paint.Style.FILL); p.setColor(0xD900060A); c.drawRect(0, 0, w, h, p);
            RectF panel = new RectF(w * 0.135f, h * 0.155f, w * 0.865f, h * 0.845f);
            p.setColor(0xF0182733); c.drawRoundRect(panel, unit * 0.025f, unit * 0.025f, p);
            p.setStyle(Paint.Style.STROKE); p.setStrokeWidth(unit * 0.003f); p.setColor(0xFFE4BF6B); c.drawRoundRect(panel, unit * 0.025f, unit * 0.025f, p);
            p.setStyle(Paint.Style.FILL); text(c, "CHOOSE BATTLE SPELL", w * 0.50f, h * 0.245f, unit * 0.045f, 0xFFFFD77A, true, Paint.Align.CENTER);
            for (int index = 0; index < battleSpells.length; index++) {
                int col = index % 4, row = index / 4; float x = w * (0.22f + col * 0.187f), y = h * (0.395f + row * 0.155f);
                float radius = unit * 0.043f;
                if (index == battleSpellIndex) { p.setStyle(Paint.Style.STROKE); p.setStrokeWidth(unit * 0.0035f); p.setColor(0xFFFFD36D); c.drawCircle(x, y, radius * 1.18f, p); p.setStyle(Paint.Style.FILL); }
                drawCircularArt(c, spellArt[index], x, y, radius);
                text(c, battleSpells[index], x, y + radius * 1.48f, unit * 0.019f, index == battleSpellIndex ? 0xFFFFD77A : 0xFFE0E8EF, true, Paint.Align.CENTER);
                text(c, battleSpellCooldowns[index] + "s CD", x, y + radius * 1.93f, unit * 0.015f, 0xFF9FB0BC, false, Paint.Align.CENTER);
            }
            text(c, "TAP A SPELL TO EQUIP IT • COOLDOWNS ARE BASE ESTIMATES", w * 0.50f, h * 0.812f, unit * 0.019f, 0xFFB5C4CE, false, Paint.Align.CENTER);
        }
'''
if "private void drawHeroPicker(Canvas c)" not in s:
    s=s.replace("        private void drawTopHud(Canvas c) {",picker+"        private void drawTopHud(Canvas c) {",1)

s=s.replace('''            drawSmallButton(c, flickerX * w, flickerY * h, unit * 0.034f, "ϟ", "FLICKER", 0xFFFFD16C, "flicker");''',
'''            drawSmallButton(c, flickerX * w, flickerY * h, unit * 0.034f,
                    battleSpells[battleSpellIndex], battleSpells[battleSpellIndex], 0xFFFFD16C, "battle_spell");
            long remainingSpell = spellCooldownUntil - SystemClock.uptimeMillis();
            if (remainingSpell > 0) {
                float sx = flickerX * w, sy = flickerY * h, sr = unit * 0.030f;
                p.setStyle(Paint.Style.FILL); p.setShader(null); p.setColor(0xBF05090D);
                c.drawCircle(sx, sy, sr, p);
                text(c, String.valueOf((remainingSpell + 999) / 1000), sx, sy + sr * 0.33f,
                        unit * 0.027f, Color.WHITE, true, Paint.Align.CENTER);
            }''',1)
small_anchor='''            p.setShader(null);
            p.setStrokeCap(Paint.Cap.ROUND);
            p.setStrokeJoin(Paint.Join.ROUND);
            Path path = new Path();'''
small_branch='''            p.setShader(null);
            if ("battle_spell".equals(name)) {
                drawCircularArt(c, spellArt[battleSpellIndex], x, y, r * 0.83f);
                text(c, battleSpells[battleSpellIndex], x, y + r * 1.43f,
                        unit * 0.0095f, 0xFFD0DCE3, false, Paint.Align.CENTER);
                return;
            }
            p.setStrokeCap(Paint.Cap.ROUND);
            p.setStrokeJoin(Paint.Join.ROUND);
            Path path = new Path();'''
if small_anchor in s: s=s.replace(small_anchor,small_branch,1)
elif 'drawCircularArt(c, spellArt[battleSpellIndex]' not in s: raise SystemExit("Utility icon painter marker missing")

old_down='''            if (action == MotionEvent.ACTION_DOWN || action == MotionEvent.ACTION_POINTER_DOWN) {
                if (heroTabHit(x, y)) { chooseHero(x); return true; }'''
new_down='''            if (spellPickerOpen) {
                if (action == MotionEvent.ACTION_DOWN) {
                    if (y >= h * 0.31f && y <= h * 0.77f && x >= w * 0.16f && x <= w * 0.84f) {
                        int col = Math.max(0, Math.min(3, (int) ((x / w - 0.17f) / 0.187f)));
                        int row = y < h * 0.47f ? 0 : (y < h * 0.625f ? 1 : 2);
                        int selected = row * 4 + col;
                        if (selected >= 0 && selected < battleSpells.length) {
                            battleSpellIndex = selected;
                            spellCooldownUntil = 0L;
                            getSharedPreferences(PREFS, MODE_PRIVATE).edit().putInt("spell_index", selected).apply();
                        }
                        spellPickerOpen = false;
                        invalidate();
                    } else if (x < w * 0.13f || x > w * 0.87f || y < h * 0.15f || y > h * 0.85f) {
                        spellPickerOpen = false;
                        invalidate();
                    }
                }
                return true;
            }
            if (action == MotionEvent.ACTION_DOWN || action == MotionEvent.ACTION_POINTER_DOWN) {
                if (heroPickMode) {
                    if (y >= h * 0.30f && y <= h * 0.80f) {
                        int selectedHero = x < w * 0.34f ? 0 : (x < w * 0.66f ? 1 : 2);
                        selectHero(selectedHero);
                    }
                    return true;
                }
                if (heroTabHit(x, y)) { heroPickMode = true; invalidate(); return true; }'''
if old_down not in s: raise SystemExit("Phone touch-down dispatch marker missing")
s=s.replace(old_down,new_down,1)
s=s.replace('''                    buttonPointers.put(id, name);
                    fireButton(name, x, y);
                    invalidate(); return true;''','''                    buttonPointers.put(id, name);
                    buttonDownTimes.put(id, SystemClock.uptimeMillis());
                    if (!"battle_spell".equals(name)) fireButton(name, x, y);
                    invalidate(); return true;''',1)
s=s.replace('''                String name = buttonPointers.remove(id);
                if ("mic".equals(name)) endMicrophone();
                else if (name != null) emitButton(name, "up", x, y);''','''                String name = buttonPointers.remove(id);
                Long downAt = buttonDownTimes.remove(id);
                if ("mic".equals(name)) endMicrophone();
                else if ("battle_spell".equals(name)) {
                    long held = downAt == null ? 0L : SystemClock.uptimeMillis() - downAt;
                    if (held >= 500L) {
                        spellPickerOpen = true;
                        invalidate();
                    } else {
                        fireButton("battle_spell", x, y);
                        emitButton("battle_spell", "up", x / w, y / h);
                    }
                } else if (name != null) emitButton(name, "up", x, y);''',1)
s=s.replace('''        private void fireButton(String name, float touchX, float touchY) {
            if ("mic".equals(name)) { beginMicrophone(); return; }''','''        private void fireButton(String name, float touchX, float touchY) {
            if ("mic".equals(name)) { beginMicrophone(); return; }
            if ("battle_spell".equals(name)) {
                long now = SystemClock.uptimeMillis();
                if (spellCooldownUntil <= now) spellCooldownUntil = now + battleSpellCooldowns[battleSpellIndex] * 1000L;
                emitButton("battle_spell", "down", touchX / w, touchY / h);
                invalidate();
                return;
            }''',1)
s=s.replace('''            if (inside(x, y, flickerX, flickerY, 0.045f)) return "flicker";''','''            if (inside(x, y, flickerX, flickerY, 0.045f)) return "battle_spell";''',1)
s=s.replace('''        private void chooseHero(float x) {
            int next = Math.round((x / w - 0.045f) / 0.045f);
            if (next >= 0 && next < heroes.length && next != heroIndex) {
                heroIndex = next;
                for (int i = 0; i < 3; i++) cooldownUntil[i] = 0;
                invalidate();
            }
        }''','''        private void chooseHero(float x) {
            int next = Math.round((x / w - 0.045f) / 0.045f);
            if (next >= 0 && next < heroes.length) selectHero(next);
        }''',1)
# Send a continuing heartbeat over UDP so the PC can distinguish a live controller from a saved IP.
if "heartbeatScheduler" not in s:
    s = s.replace(
        'private final ExecutorService io = Executors.newSingleThreadExecutor();',
        'private final ExecutorService io = Executors.newSingleThreadExecutor();\n        private final ScheduledExecutorService heartbeatScheduler = Executors.newSingleThreadScheduledExecutor();\n        private volatile boolean heartbeatStarted = false;',
        1)
    old_start = 'void start() { io.execute(this::ensureSocket); }'
    new_start = """void start() {
            io.execute(this::ensureSocket);
            synchronized (this) {
                if (!heartbeatStarted) {
                    heartbeatStarted = true;
                    heartbeatScheduler.scheduleAtFixedRate(() -> {
                        try {
                            JSONObject ping = new JSONObject();
                            ping.put("type", "heartbeat");
                            send(ping);
                        } catch (Exception ignored) { }
                    }, 0, 1500, TimeUnit.MILLISECONDS);
                }
            }
        }"""
    if old_start not in s:
        raise SystemExit("Could not patch UDP sender start for heartbeat")
    s = s.replace(old_start, new_start, 1)
    old_stop = 'void stop() { if (socket != null) socket.close(); io.shutdownNow(); }'
    new_stop = 'void stop() { heartbeatScheduler.shutdownNow(); if (socket != null) socket.close(); io.shutdownNow(); }'
    if old_stop not in s:
        raise SystemExit("Could not patch UDP sender stop for heartbeat")
    s = s.replace(old_stop, new_stop, 1)


# Extend the selectable hero roster and skill tables.
s=s.replace('private final String[] heroes = {"NANA", "DYRROTH", "SORA"};', 'private final String[] heroes = {"NANA", "DYRROTH", "SORA", "MIYA", "LAYLA", "ALUCARD", "TIGREAL", "GUSION", "FANNY", "ALICE", "SABER", "BALMOND", "EUDORA", "ZILONG", "FRANCO", "AKAI", "KARINA", "CLINT", "BRUNO", "BANE"};', 1)
s=s.replace('''                {"SUNDERING STRIKE", "WINDSTRIDE", "SHIFTING SKIES"}
        };''', '''                {"SUNDERING STRIKE", "WINDSTRIDE", "SHIFTING SKIES"},
                {"MOON ARROW", "ARROW OF ECLIPSE", "MOONLIGHT SONATA"},
                {"MALEFIC BOMB", "VOID PROJECTILE", "DESTRUCTION RUSH"},
                {"GROUND SPLITTER", "SPINNING SLASH", "FISSION WAVE"},
                {"ATTACK WAVE", "SACRED HAMMER", "IMPALE"},
                {"SWORDSPIKE", "SHADOWBLADE SLAUGHTER", "INCANDESCENCE"},
                {"TORNADO STRIKE", "STEEL CABLE", "CUT THROAT"},
                {"FLOWING BLOOD", "BLOOD AWE", "BLOOD ODE"},
                {"FLYING SWORD", "CHARGE", "TRIPLE SWEEP"},
                {"SOUL LOCK", "CYCLONE SWEEP", "LETHAL COUNTER"},
                {"FORKED LIGHTNING", "BALL LIGHTNING", "THUNDER'S WRATH"},
                {"SPEAR FLIP", "SPEAR STRIKE", "SUPREME WARRIOR"},
                {"IRON HOOK", "FURY SHOCK", "BLOODY HUNT"},
                {"HEADBUTT", "BODY SLAM", "HEAVY SPIN"},
                {"DANCE OF BLADES", "DANCE OF DEATH", "SHADOW ASSAULT"},
                {"QUICK DRAW", "TRAPPING RECOIL", "HOWITZER"},
                {"VOLLEY SHOT", "FLYING TACKLE", "WORLDIE"},
                {"CRAB CLAW CANNON", "ALE", "DEADLY CATCH"}
        };''', 1)
s=s.replace('''                {5000, 8000, 24000}
        };''', '''                {5000, 8000, 24000},
                {5000, 12000, 30000},
                {5000, 9000, 40000},
                {6000, 9000, 35000},
                {7000, 12000, 40000},
                {5000, 9000, 30000},
                {6000, 12000, 25000},
                {5000, 10000, 40000},
                {8000, 12000, 30000},
                {8000, 7000, 40000},
                {7000, 9000, 45000},
                {10000, 7000, 30000},
                {15000, 7000, 50000},
                {9000, 6000, 40000},
                {6000, 9000, 40000},
                {10000, 9000, 30000},
                {8000, 7000, 30000},
                {6000, 9000, 40000}
        };''', 1)
s=s.replace('private final int[] heroColors = {0xFF51C9E8, 0xFFB14DFF, 0xFFFFA24A};', 'private final int[] heroColors = {0xFF51C9E8, 0xFFB14DFF, 0xFFFFA24A, 0xFF78C8FF, 0xFFFFC85C, 0xFF7D7CF5, 0xFF7CE6C0, 0xFFBA8CFF, 0xFF8EDCFF, 0xFFB8A4F4, 0xFF97D4FF, 0xFFC7764D, 0xFF8E9CFF, 0xFF70C9EE, 0xFF7AB6B0, 0xFF67B6D7, 0xFFDC8CFF, 0xFFEEB76F, 0xFF5D9DE0, 0xFFE5B86D};', 1)
s=s.replace('private final Bitmap[][] skillArt = new Bitmap[3][3];', 'private final Bitmap[][] skillArt = new Bitmap[20][3];\n        private final Bitmap[] heroPortraits = new Bitmap[20];\n        private final Bitmap[][] soraVariantArt = new Bitmap[2][3];', 1)
s=s.replace('String[] keys = {"nana", "dyrroth", "sora"};', 'String[] keys = {"nana", "dyrroth", "sora", "miya", "layla", "alucard", "tigreal", "gusion", "fanny", "alice", "saber", "balmond", "eudora", "zilong", "franco", "akai", "karina", "clint", "bruno", "bane"};\n            for (int hero = 0; hero < keys.length; hero++) { int id = getResources().getIdentifier("hero_" + keys[hero], "drawable", getContext().getPackageName()); if (id != 0) { try { heroPortraits[hero] = BitmapFactory.decodeResource(getResources(), id); } catch (RuntimeException ignored) { } } }', 1)

s=s.replace('''            float[] lefts = {0.035f, 0.355f, 0.675f};
            for (int hero = 0; hero < heroes.length; hero++) {
                float left = w * lefts[hero], right = left + w * 0.29f;''', '''            float[] lefts = {0.035f, 0.355f, 0.675f};
            int pages = (heroes.length + 2) / 3;
            heroPage = Math.max(0, Math.min(heroPage, pages - 1));
            for (int slot = 0; slot < 3; slot++) {
                int hero = heroPage * 3 + slot;
                if (hero >= heroes.length) continue;
                float left = w * lefts[slot], right = left + w * 0.29f;''', 1)
s=s.replace('''            text(c, "LONG-PRESS THE BATTLE SPELL BUTTON IN-GAME TO CHANGE SPELL",
                    w * 0.50f, h * 0.875f, unit * 0.020f, 0xFF9DAFBC, false, Paint.Align.CENTER);''', '''            text(c, "‹ PREV", w * 0.19f, h * 0.855f, unit * 0.025f, heroPage > 0 ? 0xFFFFD77A : 0xFF60717C, true, Paint.Align.CENTER);
            text(c, "PAGE " + (heroPage + 1) + " / " + pages, w * 0.50f, h * 0.855f, unit * 0.022f, 0xFFD2DFE8, true, Paint.Align.CENTER);
            text(c, "NEXT ›", w * 0.81f, h * 0.855f, unit * 0.025f, heroPage < pages - 1 ? 0xFFFFD77A : 0xFF60717C, true, Paint.Align.CENTER);
            text(c, "LONG-PRESS THE BATTLE SPELL BUTTON TO CHANGE SPELL",
                    w * 0.50f, h * 0.925f, unit * 0.018f, 0xFF9DAFBC, false, Paint.Align.CENTER);''', 1)
s=s.replace('''            float[] heroXs = {0.045f, 0.090f, 0.135f};
            float heroY = h * 0.065f;
            float heroR = unit * 0.022f;
            for (int i = 0; i < heroes.length; i++) {
                float x = w * heroXs[i];''', '''            float heroY = h * 0.065f;
            float heroR = unit * (heroes.length > 5 ? 0.0155f : 0.022f);
            for (int i = 0; i < heroes.length; i++) {
                float x = w * (0.045f + i * 0.035f);''', 1)
s=s.replace('''                text(c, i == 0 ? "N" : (i == 1 ? "D" : "S"), x, heroY + heroR * 0.34f,
                        heroR * 1.06f, Color.WHITE, true, Paint.Align.CENTER);
            }
            RectF scoreBox''', '''                text(c, heroes[i].substring(0, 1), x, heroY + heroR * 0.34f,
                        heroR * 1.05f, Color.WHITE, true, Paint.Align.CENTER);
            }
            if (heroIndex == 2) text(c, "SORA FORM: " + (soraForm == 0 ? "BASE" : (soraForm == 1 ? "THUNDER" : "TORRENT")),
                    w * 0.285f, h * 0.165f, unit * 0.020f, 0xFFFFD77A, true, Paint.Align.CENTER);
            RectF scoreBox''', 1)
s=s.replace('''                if (heroPickMode) {
                    if (y >= h * 0.30f && y <= h * 0.80f) {
                        int selectedHero = x < w * 0.34f ? 0 : (x < w * 0.66f ? 1 : 2);
                        selectHero(selectedHero);
                    }
                    return true;
                }
                if (heroTabHit(x, y)) { heroPickMode = true; invalidate(); return true; }''', '''                if (heroPickMode) {
                    float cellW = w * 0.235f, cellH = h * 0.205f, gapX = w * 0.035f, gapY = h * 0.035f;
                    float leftStart = (w - (3 * cellW + 2 * gapX)) * 0.5f, topStart = h * 0.205f;
                    if (x >= leftStart && x <= w - leftStart && y >= topStart && y <= topStart + 3 * cellH + 2 * gapY) {
                        int col = Math.min(2, Math.max(0, (int)((x - leftStart) / (cellW + gapX))));
                        int row = Math.min(2, Math.max(0, (int)((y - topStart) / (cellH + gapY))));
                        int selectedHero = row * 3 + col;
                        if (selectedHero < heroes.length) selectHero(selectedHero);
                    }
                    return true;
                }
                if (heroTabHit(x, y)) { heroPickMode = true; heroPage = heroIndex / 3; invalidate(); return true; }
                if (heroIndex == 2 && y >= h * 0.11f && y <= h * 0.20f && x >= w * 0.18f && x <= w * 0.39f) {
                    soraForm = (soraForm + 1) % 3;
                    for (int i = 0; i < cooldownUntil.length; i++) cooldownUntil[i] = 0L;
                    Toast.makeText(MainActivity.this, "Sora form: " + (soraForm == 0 ? "Base" : (soraForm == 1 ? "Thunder" : "Torrent")), Toast.LENGTH_SHORT).show();
                    invalidate(); return true;
                }
                if (y >= h * 0.025f && y <= h * 0.105f && x >= w * 0.18f && x <= w * 0.37f) {
                    chooseHero(x); return true;
                }''', 1)
s=s.replace('int next = Math.round((x / w - 0.045f) / 0.045f);','int next = Math.round((x / w - 0.045f) / 0.035f);',1)
s=s.replace('''            heroIndex = index;
            heroPickMode = false;''', '''            heroIndex = index;
            heroPage = index / 3;
            soraForm = 0;
            heroPickMode = false;''', 1)
s=s.replace('long total = cooldowns[heroIndex][skill];','long total = currentSkillCooldown(skill);',1)
s=s.replace('text(c, skillNames[heroIndex][skill], x, y + r * 1.27f,','text(c, currentSkillName(skill), x, y + r * 1.27f,',1)
s=s.replace('if (cooldownUntil[skill] <= now) cooldownUntil[skill] = now + cooldowns[heroIndex][skill];','if (cooldownUntil[skill] <= now) cooldownUntil[skill] = now + currentSkillCooldown(skill);',1)
s=s.replace("        private void drawSkillButton(Canvas c,", "        private String currentSkillName(int skill) {\n            if (heroIndex == 2 && soraForm == 1) return new String[]{\"SUNDERING STRIKE — THUNDERFLASH\", \"WINDSTRIDE — THUNDER RUSH\", \"HEAVEN'S WRATH\"}[skill];\n            if (heroIndex == 2 && soraForm == 2) return new String[]{\"SUNDERING STRIKE — OVERWHELM\", \"WINDSTRIDE — SKYFALL\", \"STORMBIND\"}[skill];\n            return skillNames[heroIndex][skill];\n        }\n        private long currentSkillCooldown(int skill) {\n            if (heroIndex == 2 && soraForm == 1) return new long[]{6500, 9000, 28000}[skill];\n            if (heroIndex == 2 && soraForm == 2) return new long[]{8000, 11000, 32000}[skill];\n            return cooldowns[heroIndex][skill];\n        }\n        private void drawSkillButton(Canvas c,", 1)
s=s.replace("private boolean heroPickMode = true;", "private int heroPage = 0;\n        private int soraForm = 0;\n        private boolean heroPickMode = true;", 1)

# MLBB skill targeting: hold on skill down, move to aim, release to cast.
s = s.replace(
    'private final Map<Integer, Long> buttonDownTimes = new HashMap<>();',
    'private final Map<Integer, Long> buttonDownTimes = new HashMap<>();\n        private int aimPointer = -1;\n        private int aimSkill = -1;\n        private float aimStartX, aimStartY, aimX, aimY;\n        private boolean aimCancelHovered = false;\n        private int soraFormPreview = 0;\n        private long soraFormUntil = 0L;\n        private int soraCloudstep = 0;',
    1)
s = s.replace('heroPage = index / 3;\n            soraForm = 0;\n            heroPickMode = false;',
              'heroPage = index / 9;\n            soraForm = 0;\n            soraFormUntil = 0L;\n            soraCloudstep = 0;\n            heroPickMode = false;', 1)
s = s.replace('''            drawBottomHints(canvas);
            if (spellPickerOpen) drawBattleSpellPicker(canvas);
            boolean cooling = spellCooldownUntil > SystemClock.uptimeMillis();
            long now = SystemClock.uptimeMillis();''',
'''            drawBottomHints(canvas);
            if (aimPointer >= 0) drawAimOverlay(canvas);
            if (spellPickerOpen) drawBattleSpellPicker(canvas);
            long now = SystemClock.uptimeMillis();
            if (heroIndex == 2 && soraForm != 0 && soraFormUntil > 0L && now >= soraFormUntil) {
                soraForm = 0; soraFormUntil = 0L; invalidate();
            }
            boolean cooling = spellCooldownUntil > now || (heroIndex == 2 && soraForm != 0 && soraFormUntil > now);''', 1)

top_old = '''            float heroY = h * 0.065f;
            float heroR = unit * (heroes.length > 5 ? 0.0155f : 0.022f);
            for (int i = 0; i < heroes.length; i++) {
                float x = w * (0.045f + i * 0.035f);
                p.setStyle(Paint.Style.FILL);
                p.setColor(0xD90A141A);
                c.drawCircle(x, heroY, heroR * 1.14f, p);
                p.setStyle(Paint.Style.STROKE);
                p.setStrokeWidth(i == heroIndex ? unit * 0.004f : unit * 0.0018f);
                p.setColor(i == heroIndex ? 0xFFFFD36D : 0xFF60737B);
                c.drawCircle(x, heroY, heroR, p);
                p.setStyle(Paint.Style.FILL);
                text(c, heroes[i].substring(0, 1), x, heroY + heroR * 0.34f,
                        heroR * 1.05f, Color.WHITE, true, Paint.Align.CENTER);
            }
            if (heroIndex == 2) text(c, "SORA FORM: " + (soraForm == 0 ? "BASE" : (soraForm == 1 ? "THUNDER" : "TORRENT")),
                    w * 0.285f, h * 0.165f, unit * 0.020f, 0xFFFFD77A, true, Paint.Align.CENTER);'''
top_new = '''            float heroY = h * 0.065f, heroX = w * 0.067f, heroR = unit * 0.027f;
            Bitmap activePortrait = heroPortraits[heroIndex];
            if (activePortrait != null) drawCircularArt(c, activePortrait, heroX, heroY, heroR);
            else {
                p.setStyle(Paint.Style.FILL); p.setColor(heroColors[heroIndex]); c.drawCircle(heroX, heroY, heroR, p);
                if (heroIndex == 2) {
                    p.setColor(0xFFEAF8FF); c.drawCircle(heroX-heroR*0.18f, heroY-heroR*0.08f, heroR*0.40f, p);
                    c.drawCircle(heroX+heroR*0.18f, heroY-heroR*0.18f, heroR*0.50f, p);
                    c.drawCircle(heroX+heroR*0.43f, heroY+heroR*0.03f, heroR*0.31f, p);
                    Path bolt = new Path(); bolt.moveTo(heroX+heroR*0.06f,heroY-heroR*0.05f); bolt.lineTo(heroX-heroR*0.17f,heroY+heroR*0.24f); bolt.lineTo(heroX+heroR*0.03f,heroY+heroR*0.24f); bolt.lineTo(heroX-heroR*0.04f,heroY+heroR*0.53f); bolt.lineTo(heroX+heroR*0.25f,heroY+heroR*0.13f); bolt.lineTo(heroX+heroR*0.09f,heroY+heroR*0.13f); bolt.close();
                    p.setColor(0xFF2273B9); c.drawPath(bolt, p);
                } else text(c, heroes[heroIndex].substring(0,1), heroX, heroY+heroR*0.34f, heroR, Color.WHITE, true, Paint.Align.CENTER);
            }
            p.setStyle(Paint.Style.STROKE); p.setStrokeWidth(unit * 0.003f); p.setColor(0xFFFFD36D); c.drawCircle(heroX, heroY, heroR, p); p.setStyle(Paint.Style.FILL);
            String activeName = heroes[heroIndex].substring(0,1) + heroes[heroIndex].substring(1).toLowerCase(java.util.Locale.ROOT);
            text(c, activeName, w * 0.145f, h * 0.069f, unit * 0.025f, 0xFFF4F7FA, true, Paint.Align.LEFT);
            if (heroIndex == 2) {
                String formName = soraForm == 0 ? "BASE" : (soraForm == 1 ? "THUNDER" : "TORRENT");
                text(c, formName + "  CLOUDSTEP " + soraCloudstep + "/5", w * 0.255f, h * 0.165f, unit * 0.018f, 0xFFFFD77A, true, Paint.Align.CENTER);
                text(c, "TAP STACK WHEN A HERO HIT CONFIRMS", w * 0.255f, h * 0.195f, unit * 0.0105f, 0xFF9FB4C3, false, Paint.Align.CENTER);
            }'''
if top_old not in s: raise SystemExit("Top HUD block not found")
s = s.replace(top_old, top_new, 1)

s = s.replace('''                if (heroPickMode) {
                    float cellW = w * 0.235f, cellH = h * 0.205f, gapX = w * 0.035f, gapY = h * 0.035f;
                    float leftStart = (w - (3 * cellW + 2 * gapX)) * 0.5f, topStart = h * 0.205f;
                    if (x >= leftStart && x <= w - leftStart && y >= topStart && y <= topStart + 3 * cellH + 2 * gapY) {
                        int col = Math.min(2, Math.max(0, (int)((x - leftStart) / (cellW + gapX))));
                        int row = Math.min(2, Math.max(0, (int)((y - topStart) / (cellH + gapY))));
                        int selectedHero = row * 3 + col;
                        if (selectedHero < heroes.length) selectHero(selectedHero);
                    }
                    return true;
                }
                if (heroTabHit(x, y)) { heroPickMode = true; heroPage = heroIndex / 3; invalidate(); return true; }
                if (heroIndex == 2 && y >= h * 0.11f && y <= h * 0.20f && x >= w * 0.18f && x <= w * 0.39f) {
                    soraForm = (soraForm + 1) % 3;
                    for (int i = 0; i < cooldownUntil.length; i++) cooldownUntil[i] = 0L;
                    Toast.makeText(MainActivity.this, "Sora form: " + (soraForm == 0 ? "Base" : (soraForm == 1 ? "Thunder" : "Torrent")), Toast.LENGTH_SHORT).show();
                    invalidate(); return true;
                }''',
'''                if (heroPickMode) {
                    float cellW = w * 0.235f, cellH = h * 0.185f, gapX = w * 0.035f, gapY = h * 0.025f;
                    float leftStart = (w - (3 * cellW + 2 * gapX)) * 0.5f, topStart = h * 0.205f;
                    int pages = (heroes.length + 8) / 9;
                    if (y >= h * 0.825f && y <= h * 0.90f) {
                        if (x < w * 0.34f) heroPage = Math.max(0, heroPage - 1);
                        else if (x > w * 0.66f) heroPage = Math.min(pages - 1, heroPage + 1);
                        invalidate(); return true;
                    }
                    if (x >= leftStart && x <= w - leftStart && y >= topStart && y <= topStart + 3 * cellH + 2 * gapY) {
                        int col = Math.min(2, Math.max(0, (int)((x - leftStart) / (cellW + gapX))));
                        int row = Math.min(2, Math.max(0, (int)((y - topStart) / (cellH + gapY))));
                        int selectedHero = heroPage * 9 + row * 3 + col;
                        if (selectedHero < heroes.length) selectHero(selectedHero);
                    }
                    return true;
                }
                if (heroTabHit(x, y)) { heroPickMode = true; heroPage = heroIndex / 9; invalidate(); return true; }
                if (heroIndex == 2 && y >= h * 0.11f && y <= h * 0.20f && x >= w * 0.18f && x <= w * 0.39f) {
                    soraCloudstep = soraCloudstep >= 5 ? 0 : soraCloudstep + 1;
                    Toast.makeText(MainActivity.this, soraCloudstep >= 5 ? "True Art ready • use Sora ultimate" : "Cloudstep " + soraCloudstep + "/5 • count confirmed hero/summon hits", Toast.LENGTH_SHORT).show();
                    invalidate(); return true;
                }''',1)

s = s.replace('''                    if (!"battle_spell".equals(name)) fireButton(name, x, y);''',
'''                    if (name.startsWith("skill")) beginSkillAim(id, name, x, y);
                    else if (!"battle_spell".equals(name)) fireButton(name, x, y);''',1)

old_move = '''            if (action == MotionEvent.ACTION_MOVE) {
                if (joystickDown) {
                    for (int i = 0; i < event.getPointerCount(); i++) {
                        if (event.getPointerId(i) == joystickPointer) {
                            joystickPoint.set(event.getX(i), event.getY(i));
                            emitJoy("move", joystickPoint.x / w, joystickPoint.y / h);
                            invalidate(); break;
                        }
                    }
                }
                return true;
            }'''
new_move = '''            if (action == MotionEvent.ACTION_MOVE) {
                if (joystickDown) {
                    for (int i = 0; i < event.getPointerCount(); i++) {
                        if (event.getPointerId(i) == joystickPointer) {
                            joystickPoint.set(event.getX(i), event.getY(i));
                            emitJoy("move", joystickPoint.x / w, joystickPoint.y / h);
                            break;
                        }
                    }
                }
                for (int i = 0; i < event.getPointerCount(); i++) {
                    int pointerId = event.getPointerId(i);
                    String heldName = buttonPointers.get(pointerId);
                    if (pointerId == aimPointer && heldName != null && heldName.startsWith("skill")) {
                        aimX = event.getX(i); aimY = event.getY(i);
                        aimCancelHovered = isAimCancelZone(aimX, aimY);
                        if (heroIndex == 2 && aimSkill == 2 && soraForm == 0) {
                            float deltaX = aimX - aimStartX;
                            soraFormPreview = deltaX < -w * 0.025f ? 1 : (deltaX > w * 0.025f ? 2 : 0);
                        }
                        emitGesture(heldName, "move", aimX / w, aimY / h);
                        invalidate();
                    }
                }
                return true;
            }'''
if old_move not in s: raise SystemExit("Move handler not found")
s=s.replace(old_move,new_move,1)

old_up = '''            if (action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_POINTER_UP || action == MotionEvent.ACTION_CANCEL) {
                if (id == joystickPointer) {
                    joystickDown = false; emitJoy("up", joyX, joyY); joystickPointer = -1; invalidate(); return true;
                }
                String name = buttonPointers.remove(id);
                Long downAt = buttonDownTimes.remove(id);
                if ("mic".equals(name)) endMicrophone();
                else if ("battle_spell".equals(name)) {
                    long held = downAt == null ? 0L : SystemClock.uptimeMillis() - downAt;
                    if (held >= 500L) {
                        spellPickerOpen = true;
                        invalidate();
                    } else {
                        fireButton("battle_spell", x, y);
                        emitButton("battle_spell", "up", x / w, y / h);
                    }
                } else if (name != null) emitButton(name, "up", x, y);
                invalidate(); return true;
            }'''
new_up = '''            if (action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_POINTER_UP || action == MotionEvent.ACTION_CANCEL) {
                if (id == joystickPointer) {
                    joystickDown = false; emitJoy("up", joyX, joyY); joystickPointer = -1; invalidate(); return true;
                }
                String name = buttonPointers.remove(id);
                Long downAt = buttonDownTimes.remove(id);
                if (name != null && name.startsWith("skill")) finishSkillAim(id, name, x, y, action == MotionEvent.ACTION_CANCEL);
                else if ("mic".equals(name)) endMicrophone();
                else if ("battle_spell".equals(name)) {
                    long held = downAt == null ? 0L : SystemClock.uptimeMillis() - downAt;
                    if (held >= 500L) {
                        spellPickerOpen = true;
                        invalidate();
                    } else {
                        fireButton("battle_spell", x, y);
                        emitButton("battle_spell", "up", x / w, y / h);
                    }
                } else if (name != null) emitButton(name, "up", x, y);
                invalidate(); return true;
            }'''
if old_up not in s: raise SystemExit("Up handler not found")
s=s.replace(old_up,new_up,1)

aim_methods = '''        private boolean isAimCancelZone(float x, float y) {
            return Math.abs(x - w * 0.56f) <= unit * 0.052f
                    && Math.abs(y - h * 0.225f) <= unit * 0.043f;
        }

        private void drawAimOverlay(Canvas c) {
            if (aimPointer < 0 || aimSkill < 0) return;
            p.setStyle(Paint.Style.FILL); p.setShader(null); p.setColor(0xD909151F);
            c.drawRoundRect(new RectF(w*0.20f, h*0.105f, w*0.80f, h*0.175f), unit*0.012f, unit*0.012f, p);
            String prompt = heroIndex == 2 && aimSkill == 2 && soraForm == 0
                    ? "SWIPE LEFT: THUNDER     •     RIGHT: TORRENT"
                    : "DRAG TO AIM   •   RELEASE TO CAST";
            text(c, prompt, w*0.50f, h*0.148f, unit*0.019f, 0xFFFFD77A, true, Paint.Align.CENTER);
            p.setStyle(Paint.Style.STROKE); p.setStrokeWidth(unit*0.004f); p.setColor(0xFFFFD77A);
            c.drawLine(aimStartX, aimStartY, aimX, aimY, p); c.drawCircle(aimX, aimY, unit*0.018f, p);
            float cx = w*0.56f, cy = h*0.225f, cr = unit*0.050f;
            p.setStyle(Paint.Style.FILL); p.setColor(aimCancelHovered ? 0xFFE23E4D : 0xCC401E29); c.drawCircle(cx, cy, cr, p);
            p.setStyle(Paint.Style.STROKE); p.setStrokeWidth(unit*0.003f); p.setColor(aimCancelHovered ? Color.WHITE : 0xFFFF8791); c.drawCircle(cx, cy, cr, p);
            p.setStyle(Paint.Style.FILL); text(c, "CANCEL", cx, cy + unit*0.006f, unit*0.017f, Color.WHITE, true, Paint.Align.CENTER);
            if (heroIndex == 2 && aimSkill == 2 && soraForm == 0 && soraFormPreview != 0) {
                text(c, soraFormPreview == 1 ? "THUNDER SELECTED" : "TORRENT SELECTED",
                        w*0.50f, h*0.205f, unit*0.018f, 0xFF86DBFF, true, Paint.Align.CENTER);
            }
        }

        private void beginSkillAim(int pointerId, String name, float x, float y) {
            aimPointer = pointerId; aimSkill = Integer.parseInt(name.substring("skill".length()));
            aimStartX = aimX = x; aimStartY = aimY = y;
            aimCancelHovered = false; soraFormPreview = 0;
            emitGesture(name, "down", x / w, y / h); invalidate();
        }

        private void finishSkillAim(int pointerId, String name, float x, float y, boolean systemCancelled) {
            int skill = Integer.parseInt(name.substring("skill".length()));
            boolean cancel = systemCancelled || (pointerId == aimPointer && (aimCancelHovered || isAimCancelZone(x, y)));
            if (cancel) {
                emitGesture(name, "cancel", 0.56f, 0.225f);
                Toast.makeText(MainActivity.this, "Skill cancelled", Toast.LENGTH_SHORT).show();
            } else {
                emitGesture(name, "up", x / w, y / h);
                long now = SystemClock.uptimeMillis();
                if (heroIndex == 2 && skill == 2 && soraForm == 0 && soraFormPreview != 0) {
                    soraForm = soraFormPreview; soraFormUntil = now + 10000L; soraCloudstep = 0;
                    cooldownUntil[0] = 0L; cooldownUntil[1] = 0L; cooldownUntil[2] = 0L;
                    Toast.makeText(MainActivity.this, "Sora transformed to " + (soraForm == 1 ? "Thunder" : "Torrent") + " for 10 seconds", Toast.LENGTH_SHORT).show();
                } else {
                    cooldownUntil[skill] = now + currentSkillCooldown(skill);
                    if (heroIndex == 2 && skill == 2 && soraForm != 0 && soraCloudstep >= 5) {
                        soraCloudstep = 0;
                        Toast.makeText(MainActivity.this, "True Art used • reset Cloudstep tracker", Toast.LENGTH_SHORT).show();
                    }
                }
            }
            if (pointerId == aimPointer) { aimPointer = -1; aimSkill = -1; aimCancelHovered = false; soraFormPreview = 0; }
            invalidate();
        }

        private void emitGesture(String name, String state, float nx, float ny) {
            try {
                JSONObject o = new JSONObject(); o.put("type", "gesture"); o.put("name", name); o.put("state", state);
                o.put("x", Math.max(0f, Math.min(1f, nx))); o.put("y", Math.max(0f, Math.min(1f, ny))); send(o);
            } catch (Exception ignored) { }
        }

'''
if "private void drawBattleSpellPicker(Canvas c)" not in s:
    raise SystemExit("Spell picker insertion marker missing")
s=s.replace("        private void drawBattleSpellPicker(Canvas c) {",aim_methods+"        private void drawBattleSpellPicker(Canvas c) {",1);

old_skill_names = '''        private String currentSkillName(int skill) {
            if (heroIndex == 2 && soraForm == 1) return new String[]{"SUNDERING STRIKE — THUNDERFLASH", "WINDSTRIDE — THUNDER RUSH", "HEAVEN'S WRATH"}[skill];
            if (heroIndex == 2 && soraForm == 2) return new String[]{"SUNDERING STRIKE — OVERWHELM", "WINDSTRIDE — SKYFALL", "STORMBIND"}[skill];
            return skillNames[heroIndex][skill];
        }'''
new_skill_names = '''        private String currentSkillName(int skill) {
            if (heroIndex == 2 && skill == 2 && soraCloudstep >= 5 && soraForm != 0) return soraForm == 1 ? "THUNDER TRUE ART" : "TORRENT TRUE ART";
            if (heroIndex == 2 && soraForm == 1) return new String[]{"SUNDERING STRIKE • THUNDER", "WINDSTRIDE • THUNDER", "SHIFTING SKIES • THUNDER"}[skill];
            if (heroIndex == 2 && soraForm == 2) return new String[]{"SUNDERING STRIKE • TORRENT", "WINDSTRIDE • TORRENT", "SHIFTING SKIES • TORRENT"}[skill];
            return skillNames[heroIndex][skill];
        }'''
if old_skill_names in s: s=s.replace(old_skill_names,new_skill_names,1)

phone.write_text(s)

phone_manifest = root / "phone-controller/app/src/main/AndroidManifest.xml"
pm = phone_manifest.read_text()
if 'android:usesCleartextTraffic="true"' not in pm:
    pm=pm.replace("<application ",'<application android:usesCleartextTraffic="true" ',1)
phone_manifest.write_text(pm)

for gradle_file in [root / "phone-controller/app/build.gradle", root / "waydroid-touch-bridge/app/build.gradle"]:
    text_gradle=gradle_file.read_text()
    text_gradle=text_gradle.replace("versionCode 2; versionName '0.2.0'","versionCode 5; versionName '0.5.0'")
    text_gradle=text_gradle.replace("versionCode 3; versionName '0.3.0'","versionCode 5; versionName '0.5.0'")
    text_gradle=text_gradle.replace("versionCode 4; versionName '0.4.0'","versionCode 5; versionName '0.5.0'")
    text_gradle=text_gradle.replace("versionCode 5; versionName '0.5.0'","versionCode 6; versionName '0.5.1'")
    text_gradle=text_gradle.replace("versionCode 6; versionName '0.5.1'","versionCode 7; versionName '0.5.2'")
    text_gradle=text_gradle.replace("versionCode 8; versionName '0.6.1'","versionCode 9; versionName '0.7.0'")
    text_gradle=text_gradle.replace("versionCode 7; versionName '0.5.2'","versionCode 8; versionName '0.6.1'")
    text_gradle=text_gradle.replace("versionCode 8; versionName '0.6.1'","versionCode 10; versionName '0.8.0'")
    gradle_file.write_text(text_gradle)


# Allow the Waydroid Accessibility bridge to hold, move, and release a skill touch.
touch_path = root / "waydroid-touch-bridge/app/src/main/java/com/mlbblink/bridge/TouchAccessibilityService.java"
ts = touch_path.read_text()
if 'if("gesture".equals(type))' not in ts:
    old_gesture_dispatch = '''    if("button".equals(type) && "down".equals(o.optString("state"))){tap(screenPoint((float)o.optDouble("x",0.5),(float)o.optDouble("y",0.5)));return;}'''
    new_gesture_dispatch = '''    if("button".equals(type) && "down".equals(o.optString("state"))){tap(screenPoint((float)o.optDouble("x",0.5),(float)o.optDouble("y",0.5)));return;}
    if("gesture".equals(type)){handleSkillGesture(o);return;}'''
    if old_gesture_dispatch not in ts:
        raise SystemExit("Touch bridge button dispatch marker missing")
    ts = ts.replace(old_gesture_dispatch, new_gesture_dispatch, 1)
ts = ts.replace('''  private GestureDescription.StrokeDescription activeStroke;
  private PointF lastPoint;''',
'''  private GestureDescription.StrokeDescription activeStroke;
  private PointF lastPoint;
  private GestureDescription.StrokeDescription skillStroke;
  private PointF skillLastPoint;''', 1)
if "private void handleSkillGesture(JSONObject o)" not in ts:
    skill_methods = """
  private void handleSkillGesture(JSONObject o){
    String state=o.optString("state");
    PointF p=screenPoint((float)o.optDouble("x",0.5),(float)o.optDouble("y",0.5));
    if("down".equals(state))startSkillTouch(p);
    else if("move".equals(state))moveSkillTouch(p);
    else if("up".equals(state)||"cancel".equals(state))endSkillTouch(p);
  }

  private void startSkillTouch(PointF p){
    if(skillStroke!=null)endSkillTouch(skillLastPoint==null?p:skillLastPoint);
    Path path=new Path();path.moveTo(p.x,p.y);
    skillStroke=new GestureDescription.StrokeDescription(path,0,100,true);
    skillLastPoint=p;
    dispatchGesture(new GestureDescription.Builder().addStroke(skillStroke).build(),null,null);
  }

  private void moveSkillTouch(PointF p){
    if(skillStroke==null){startSkillTouch(p);return;}
    Path path=new Path();path.moveTo(skillLastPoint.x,skillLastPoint.y);path.lineTo(p.x,p.y);
    GestureDescription.StrokeDescription next=skillStroke.continueStroke(path,0,55,true);
    if(dispatchGesture(new GestureDescription.Builder().addStroke(next).build(),null,null))skillStroke=next;
    skillLastPoint=p;
  }

  private void endSkillTouch(PointF p){
    if(skillStroke==null)return;
    PointF end=p==null?(skillLastPoint==null?new PointF(0,0):skillLastPoint):p;
    Path path=new Path();path.moveTo(skillLastPoint.x,skillLastPoint.y);path.lineTo(end.x,end.y);
    GestureDescription.StrokeDescription next=skillStroke.continueStroke(path,0,55,false);
    dispatchGesture(new GestureDescription.Builder().addStroke(next).build(),null,null);
    skillStroke=null;skillLastPoint=null;
  }

"""
    ts = ts.replace("  private void startStick(PointF p){", skill_methods + "  private void startStick(PointF p){", 1)
touch_path.write_text(ts)
print("Patched MLBB Link v0.5.0: LAN IP detection, connected/disconnected status, hero selection and battle spells.")

