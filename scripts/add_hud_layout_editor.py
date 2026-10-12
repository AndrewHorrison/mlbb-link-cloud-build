#!/usr/bin/env python3
"""Add persistent drag-to-reposition HUD editing and a manual CDR estimator."""
from __future__ import annotations

import sys
from pathlib import Path

def once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one marker, found {count}")
    return source.replace(old, new, 1)

def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: add_hud_layout_editor.py source/mlbb-link")
    root = Path(sys.argv[1])
    java_path = root / "phone-controller/app/src/main/java/com/mlbblink/controller/MainActivity.java"
    if not java_path.is_file():
        raise SystemExit("Phone controller MainActivity.java was not found")
    s = java_path.read_text(encoding="utf-8")

    # These positions are normalized to the current view dimensions and persisted per device.
    positions = (
        ("joyX", "0.165f, joyY = 0.735f"),
        ("attackX", "0.925f, attackY = 0.785f"),
        ("skill1X", "0.765f, skill1Y = 0.700f"),
        ("skill2X", "0.845f, skill2Y = 0.615f"),
        ("ultX", "0.925f, ultY = 0.565f"),
        ("recallX", "0.565f, recallY = 0.855f"),
        ("regenX", "0.635f, regenY = 0.825f"),
        ("flickerX", "0.700f, flickerY = 0.790f"),
    )
    for name, values in positions:
        old = "private final float " + name + " = " + values + ";"
        new = "private float " + name + " = " + values + ";"
        if old in s:
            s = once(s, old, new, f"mutable HUD position {name}")
        elif new not in s:
            raise SystemExit(f"HUD position marker missing: {name}")

    s = once(s,
        "        private float joyX = 0.165f, joyY = 0.735f;",
        "        private float joyX = 0.165f, joyY = 0.735f;\n"
        "        private float micX = 0.485f, micY = 0.815f;\n"
        "        private float skillPointX = 0.735f, skillPointY = 0.472f;\n"
        "        private boolean hudEditMode = false;\n"
        "        private String hudDragControl = null;\n"
        "        private int hudDragPointer = -1;\n"
        "        private int hudEditButtonPointer = -1;\n"
        "        private long hudEditButtonDownAt = 0L;\n"
        "        private int cdrPresetIndex = 0;\n"
        "        private final int[] cdrPresets = {0, 10, 20, 30, 40};",
        "HUD editor and CDR state")

    ctor = """        ControllerView(Context context) {
            super(context);
            setLayerType(View.LAYER_TYPE_SOFTWARE, null);
            setFocusable(true);
            loadSkillArt();
        }"""
    ctor_new = """        ControllerView(Context context) {
            super(context);
            setLayerType(View.LAYER_TYPE_SOFTWARE, null);
            setFocusable(true);
            loadSkillArt();
            loadHudLayout();
        }"""
    if ctor in s:
        s = once(s, ctor, ctor_new, "HUD layout load")
    elif "            loadHudLayout();" not in s:
        raise SystemExit("ControllerView constructor marker missing")

    methods = r"""
        private void loadHudLayout() {
            android.content.SharedPreferences prefs = getContext().getSharedPreferences(PREFS, MODE_PRIVATE);
            joyX = prefs.getFloat("hud_joy_x", 0.165f); joyY = prefs.getFloat("hud_joy_y", 0.735f);
            attackX = prefs.getFloat("hud_attack_x", 0.925f); attackY = prefs.getFloat("hud_attack_y", 0.785f);
            skill1X = prefs.getFloat("hud_skill1_x", 0.765f); skill1Y = prefs.getFloat("hud_skill1_y", 0.700f);
            skill2X = prefs.getFloat("hud_skill2_x", 0.845f); skill2Y = prefs.getFloat("hud_skill2_y", 0.615f);
            ultX = prefs.getFloat("hud_ult_x", 0.925f); ultY = prefs.getFloat("hud_ult_y", 0.565f);
            recallX = prefs.getFloat("hud_recall_x", 0.565f); recallY = prefs.getFloat("hud_recall_y", 0.855f);
            regenX = prefs.getFloat("hud_regen_x", 0.635f); regenY = prefs.getFloat("hud_regen_y", 0.825f);
            flickerX = prefs.getFloat("hud_flicker_x", 0.700f); flickerY = prefs.getFloat("hud_flicker_y", 0.790f);
            micX = prefs.getFloat("hud_mic_x", 0.485f); micY = prefs.getFloat("hud_mic_y", 0.815f);
            skillPointX = prefs.getFloat("hud_point_x", 0.735f); skillPointY = prefs.getFloat("hud_point_y", 0.472f);
            cdrPresetIndex = Math.max(0, Math.min(cdrPresets.length - 1, prefs.getInt("cooldown_reduction_preset", 0)));
        }

        private void saveHudLayout() {
            getContext().getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                    .putFloat("hud_joy_x", joyX).putFloat("hud_joy_y", joyY)
                    .putFloat("hud_attack_x", attackX).putFloat("hud_attack_y", attackY)
                    .putFloat("hud_skill1_x", skill1X).putFloat("hud_skill1_y", skill1Y)
                    .putFloat("hud_skill2_x", skill2X).putFloat("hud_skill2_y", skill2Y)
                    .putFloat("hud_ult_x", ultX).putFloat("hud_ult_y", ultY)
                    .putFloat("hud_recall_x", recallX).putFloat("hud_recall_y", recallY)
                    .putFloat("hud_regen_x", regenX).putFloat("hud_regen_y", regenY)
                    .putFloat("hud_flicker_x", flickerX).putFloat("hud_flicker_y", flickerY)
                    .putFloat("hud_mic_x", micX).putFloat("hud_mic_y", micY)
                    .putFloat("hud_point_x", skillPointX).putFloat("hud_point_y", skillPointY)
                    .putInt("cooldown_reduction_preset", cdrPresetIndex).apply();
        }

        private void resetHudLayout() {
            joyX = 0.165f; joyY = 0.735f;
            attackX = 0.925f; attackY = 0.785f;
            skill1X = 0.765f; skill1Y = 0.700f;
            skill2X = 0.845f; skill2Y = 0.615f;
            ultX = 0.925f; ultY = 0.565f;
            recallX = 0.565f; recallY = 0.855f;
            regenX = 0.635f; regenY = 0.825f;
            flickerX = 0.700f; flickerY = 0.790f;
            micX = 0.485f; micY = 0.815f;
            skillPointX = 0.735f; skillPointY = 0.472f;
            android.content.SharedPreferences.Editor editor = getContext().getSharedPreferences(PREFS, MODE_PRIVATE).edit();
            for (String key : new String[]{"joy", "attack", "skill1", "skill2", "ult", "recall", "regen", "flicker", "mic", "point"}) {
                editor.remove("hud_" + key + "_x").remove("hud_" + key + "_y");
            }
            editor.apply();
            hudEditMode = false;
            hudDragControl = null; hudDragPointer = -1;
            invalidate();
            Toast.makeText(MainActivity.this, "HUD layout restored to defaults", Toast.LENGTH_SHORT).show();
        }

        private float clampHudX(float x) { return Math.max(0.045f, Math.min(0.955f, x)); }
        private float clampHudY(float y) { return Math.max(0.105f, Math.min(0.915f, y)); }

        private float hudX(String key) {
            switch (key) {
                case "joy": return joyX;
                case "attack": return attackX;
                case "skill1": return skill1X;
                case "skill2": return skill2X;
                case "ult": return ultX;
                case "recall": return recallX;
                case "regen": return regenX;
                case "flicker": return flickerX;
                case "mic": return micX;
                case "point": return skillPointX;
                default: return 0.5f;
            }
        }

        private void setHudPosition(String key, float x, float y) {
            x = clampHudX(x); y = clampHudY(y);
            switch (key) {
                case "joy": joyX = x; joyY = y; break;
                case "attack": attackX = x; attackY = y; break;
                case "skill1": skill1X = x; skill1Y = y; break;
                case "skill2": skill2X = x; skill2Y = y; break;
                case "ult": ultX = x; ultY = y; break;
                case "recall": recallX = x; recallY = y; break;
                case "regen": regenX = x; regenY = y; break;
                case "flicker": flickerX = x; flickerY = y; break;
                case "mic": micX = x; micY = y; break;
                case "point": skillPointX = x; skillPointY = y; break;
                default: return;
            }
        }

        private String findHudControlAt(float x, float y) {
            if (inside(x, y, attackX, attackY, 0.115f)) return "attack";
            if (inside(x, y, ultX, ultY, 0.095f)) return "ult";
            if (inside(x, y, skill2X, skill2Y, 0.095f)) return "skill2";
            if (inside(x, y, skill1X, skill1Y, 0.095f)) return "skill1";
            if (inside(x, y, flickerX, flickerY, 0.065f)) return "flicker";
            if (inside(x, y, regenX, regenY, 0.065f)) return "regen";
            if (inside(x, y, recallX, recallY, 0.065f)) return "recall";
            if (inside(x, y, micX, micY, 0.065f)) return "mic";
            if (inside(x, y, skillPointX, skillPointY, 0.055f)) return "point";
            if (inside(x, y, joyX, joyY, 0.155f)) return "joy";
            return null;
        }

        private boolean isHudEditorButtonHit(float x, float y) {
            return x >= w * 0.775f && x <= w * 0.965f && y >= h * 0.125f && y <= h * 0.225f;
        }

        private boolean isCdrButtonHit(float x, float y) {
            return x >= w * 0.600f && x <= w * 0.765f && y >= h * 0.125f && y <= h * 0.225f;
        }

        private void drawHudEditorButton(Canvas c) {
            RectF box = new RectF(w * 0.785f, h * 0.135f, w * 0.960f, h * 0.215f);
            p.setStyle(Paint.Style.FILL); p.setShader(null);
            p.setColor(hudEditMode ? 0xFF66DDAA : 0xD9152835);
            c.drawRoundRect(box, unit * 0.012f, unit * 0.012f, p);
            p.setStyle(Paint.Style.STROKE); p.setStrokeWidth(unit * 0.0025f);
            p.setColor(hudEditMode ? 0xFFB5FFE0 : 0xFF79BDD7);
            c.drawRoundRect(box, unit * 0.012f, unit * 0.012f, p);
            p.setStyle(Paint.Style.FILL);
            text(c, hudEditMode ? "SAVE HUD" : "EDIT HUD", w * 0.8725f, h * 0.184f,
                    unit * 0.016f, hudEditMode ? 0xFF0A3023 : 0xFFF0F6FB, true, Paint.Align.CENTER);
        }

        private void drawCdrButton(Canvas c) {
            RectF box = new RectF(w * 0.610f, h * 0.135f, w * 0.755f, h * 0.215f);
            p.setStyle(Paint.Style.FILL); p.setShader(null); p.setColor(0xD9152835);
            c.drawRoundRect(box, unit * 0.012f, unit * 0.012f, p);
            p.setStyle(Paint.Style.STROKE); p.setStrokeWidth(unit * 0.0025f);
            p.setColor(0xFFFFD27B); c.drawRoundRect(box, unit * 0.012f, unit * 0.012f, p);
            p.setStyle(Paint.Style.FILL);
            text(c, "CDR " + cdrPresets[cdrPresetIndex] + "%", w * 0.6825f, h * 0.184f,
                    unit * 0.016f, 0xFFFFE5AE, true, Paint.Align.CENTER);
        }

        private void drawHudEditOverlay(Canvas c) {
            p.setShader(null); p.setStyle(Paint.Style.STROKE); p.setStrokeWidth(unit * 0.003f);
            p.setColor(0xBB69E8FF);
            String[] keys = {"joy", "attack", "skill1", "skill2", "ult", "recall", "regen", "flicker", "mic", "point"};
            String[] labels = {"JOYSTICK", "ATTACK", "SKILL 1", "SKILL 2", "ULTIMATE", "RECALL", "REGEN", "SPELL", "MIC", "LEVEL +"};
            for (int i = 0; i < keys.length; i++) {
                float x = hudX(keys[i]) * w, y;
                switch (keys[i]) {
                    case "joy": y = joyY * h; break;
                    case "attack": y = attackY * h; break;
                    case "skill1": y = skill1Y * h; break;
                    case "skill2": y = skill2Y * h; break;
                    case "ult": y = ultY * h; break;
                    case "recall": y = recallY * h; break;
                    case "regen": y = regenY * h; break;
                    case "flicker": y = flickerY * h; break;
                    case "mic": y = micY * h; break;
                    case "point": y = skillPointY * h; break;
                    default: y = h * 0.5f;
                }
                float radius = "joy".equals(keys[i]) ? unit * 0.155f :
                        ("attack".equals(keys[i]) ? unit * 0.105f :
                        (keys[i].startsWith("skill") || "ult".equals(keys[i]) ? unit * 0.085f : unit * 0.060f));
                c.drawCircle(x, y, radius, p);
                p.setStyle(Paint.Style.FILL);
                text(c, labels[i], x, Math.max(h * 0.115f, y - radius - unit * 0.008f),
                        unit * 0.010f, 0xFFB9F2FF, true, Paint.Align.CENTER);
                p.setStyle(Paint.Style.STROKE);
            }
            p.setStyle(Paint.Style.FILL);
            text(c, "DRAG CONTROLS  •  TAP SAVE HUD  •  HOLD SAVE HUD TO RESET",
                    w * 0.50f, h * 0.965f, unit * 0.012f, 0xFFE2F5FC, true, Paint.Align.CENTER);
        }

        private void cycleCooldownReduction() {
            cdrPresetIndex = (cdrPresetIndex + 1) % cdrPresets.length;
            getContext().getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                    .putInt("cooldown_reduction_preset", cdrPresetIndex).apply();
            Toast.makeText(MainActivity.this,
                    "Cooldown estimate: " + cdrPresets[cdrPresetIndex] + "% reduction",
                    Toast.LENGTH_SHORT).show();
            invalidate();
        }

        private void handleHudEditorTouch(MotionEvent event, int action, int idx, int id, float x, float y) {
            if ((action == MotionEvent.ACTION_DOWN || action == MotionEvent.ACTION_POINTER_DOWN)
                    && isHudEditorButtonHit(x, y)) {
                hudEditButtonPointer = id;
                hudEditButtonDownAt = SystemClock.uptimeMillis();
                return;
            }
            if (hudEditButtonPointer >= 0) {
                if (action == MotionEvent.ACTION_MOVE) return;
                if ((action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_POINTER_UP
                        || action == MotionEvent.ACTION_CANCEL) && (id == hudEditButtonPointer
                        || action == MotionEvent.ACTION_CANCEL)) {
                    long held = SystemClock.uptimeMillis() - hudEditButtonDownAt;
                    hudEditButtonPointer = -1;
                    if (held >= 700L) {
                        resetHudLayout();
                    } else {
                        hudEditMode = !hudEditMode;
                        if (!hudEditMode) {
                            saveHudLayout();
                            Toast.makeText(MainActivity.this, "HUD layout saved on this device", Toast.LENGTH_SHORT).show();
                        } else {
                            Toast.makeText(MainActivity.this, "Drag controls into place, then tap SAVE HUD", Toast.LENGTH_SHORT).show();
                        }
                        invalidate();
                    }
                    return;
                }
            }
            if ((action == MotionEvent.ACTION_DOWN || action == MotionEvent.ACTION_POINTER_DOWN)
                    && isCdrButtonHit(x, y)) {
                cycleCooldownReduction();
                return;
            }
            if (hudEditMode) {
                if (action == MotionEvent.ACTION_DOWN || action == MotionEvent.ACTION_POINTER_DOWN) {
                    hudDragControl = findHudControlAt(x, y);
                    hudDragPointer = hudDragControl == null ? -1 : id;
                    return;
                }
                if (action == MotionEvent.ACTION_MOVE && hudDragPointer >= 0) {
                    for (int i = 0; i < event.getPointerCount(); i++) {
                        if (event.getPointerId(i) == hudDragPointer) {
                            setHudPosition(hudDragControl, event.getX(i) / Math.max(1f, w),
                                    event.getY(i) / Math.max(1f, h));
                            invalidate();
                            return;
                        }
                    }
                    return;
                }
                if (action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_POINTER_UP
                        || action == MotionEvent.ACTION_CANCEL) {
                    if (id == hudDragPointer || action == MotionEvent.ACTION_CANCEL) {
                        if (hudDragPointer >= 0) saveHudLayout();
                        hudDragPointer = -1; hudDragControl = null;
                    }
                }
            }
        }
"""

    marker = "        private void loadSkillArt() {"
    if "private void loadHudLayout()" not in s:
        s = once(s, marker, methods + "\n" + marker, "HUD editor methods insertion")

    # Make coordinates and hit targets follow the editable normalized positions.
    s = once(s, "float x = w * 0.735f, y = h * 0.472f, r = unit * 0.022f;",
             "float x = skillPointX * w, y = skillPointY * h, r = unit * 0.022f;",
             "skill point drawing position")
    s = once(s, "float x = w * 0.485f, y = h * 0.815f, r = unit * 0.044f;",
             "float x = micX * w, y = micY * h, r = unit * 0.044f;",
             "microphone drawing position")
    s = once(s, 'if (inside(x, y, 0.735f, 0.472f, 0.035f)) return "skillpoint";',
             'if (inside(x, y, skillPointX, skillPointY, 0.035f)) return "skillpoint";',
             "skill point hit target")
    s = once(s, 'if (inside(x, y, 0.485f, 0.815f, 0.055f)) return "mic";',
             'if (inside(x, y, micX, micY, 0.055f)) return "mic";',
             "microphone hit target")
    s = once(s, "            drawShopButton(canvas);\n            drawBottomHints(canvas);",
             "            drawShopButton(canvas);\n            drawCdrButton(canvas);\n            drawHudEditorButton(canvas);\n            if (hudEditMode) drawHudEditOverlay(canvas);\n            drawBottomHints(canvas);",
             "HUD editor and CDR drawing")
    s = once(s,
        '        private long currentSkillCooldown(int skill) {\n            if (heroIndex == 2 && soraForm == 1) return new long[]{6500, 9000, 28000}[skill];\n            if (heroIndex == 2 && soraForm == 2) return new long[]{8000, 11000, 32000}[skill];\n            return cooldowns[heroIndex][skill];\n        }',
        '''        private long currentSkillCooldown(int skill) {
            long base;
            if (heroIndex == 2 && soraForm == 1) base = new long[]{6500, 9000, 28000}[skill];
            else if (heroIndex == 2 && soraForm == 2) base = new long[]{8000, 11000, 32000}[skill];
            else base = cooldowns[heroIndex][skill];
            int reduction = cdrPresets[cdrPresetIndex];
            return Math.max(500L, Math.round(base * (100 - reduction) / 100.0d));
        }''',
        "CDR-aware cooldown estimate")

    # Keep joystick and all button input regions synchronized with the editable layout.
    old_joy = "if (joystickPointer == -1 && x < w * 0.37f && y > h * 0.44f) {"
    new_joy = "if (joystickPointer == -1 && (inside(x, y, joyX, joyY, 0.155f) || (x < w * 0.37f && y > h * 0.44f))) {"
    if old_joy in s:
        s = once(s, old_joy, new_joy, "editable joystick input zone")
    elif new_joy not in s:
        raise SystemExit("Joystick input region marker missing")

    # The edit controls are handled before gameplay dispatch, so layout dragging can never cast a skill.
    method_start = "        @Override public boolean onTouchEvent(MotionEvent event) {"
    insertion = """            if (!heroPickMode && !spellPickerOpen) {
                handleHudEditorTouch(event, action, idx, id, x, y);
                if (hudEditButtonPointer >= 0 || hudEditMode || isHudEditorButtonHit(x, y) || isCdrButtonHit(x, y)) return true;
            }
"""
    if "handleHudEditorTouch(event, action, idx, id, x, y);" not in s:
        s = once(s, "            float x = event.getX(idx), y = event.getY(idx);\n",
                 "            float x = event.getX(idx), y = event.getY(idx);\n" + insertion,
                 "HUD editor touch interception")

    checks = {
        "persistent layout load/save": "private void loadHudLayout()" in s and '"hud_skill1_x"' in s and "private void saveHudLayout()" in s,
        "long-press reset": "held >= 700L" in s and "resetHudLayout()" in s,
        "editable skill centers": "skill1X = x; skill1Y = y;" in s and "ultX = x; ultY = y;" in s,
        "CDR presets": "private final int[] cdrPresets = {0, 10, 20, 30, 40};" in s,
        "CDR cooldown calculation": "base * (100 - reduction) / 100.0d" in s,
        "CDR button": "drawCdrButton(canvas)" in s and "cycleCooldownReduction()" in s,
        "edit-mode input protection": "handleHudEditorTouch(event, action, idx, id, x, y);" in s,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise SystemExit("HUD editor feature checks failed: " + ", ".join(failed))
    java_path.write_text(s, encoding="utf-8")
    print("Added persistent drag HUD editor, long-press reset, and 0/10/20/30/40% manual CDR cooldown estimates.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
