package com.mlbblink.controller;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.pm.PackageManager;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.PointF;
import android.graphics.RectF;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.os.Bundle;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final int PHONE_PORT = 28741;
    private static final int MIC_PORT = 28743;
    private static final int REQUEST_MIC = 501;
    private UdpSender sender;
    private MicStreamer micStreamer;
    private ControllerView controller;
    private EditText ipField;
    private TextView statusText;
    private Button heroButton;
    private Button levelButton;
    private Button micButton;
    private String hero = "Nana";
    private int skillPoints = 0;
    private String hostIp = "";

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        requestFullscreen();
        sender = new UdpSender();
        micStreamer = new MicStreamer();

        hostIp = getPreferences(MODE_PRIVATE).getString("pc_ip", "");
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(8), dp(5), dp(8), dp(3));
        root.setBackgroundColor(Color.rgb(7, 10, 16));

        LinearLayout top = new LinearLayout(this);
        top.setGravity(Gravity.CENTER_VERTICAL);
        TextView logo = new TextView(this);
        logo.setText("MLBB LINK");
        logo.setTextColor(Color.rgb(242, 194, 86));
        logo.setTextSize(16);
        logo.setTypeface(null, 1);
        logo.setPadding(dp(5), 0, dp(8), 0);
        top.addView(logo, new LinearLayout.LayoutParams(0, dp(39), 1f));

        heroButton = makeButton("HERO: " + hero, 0xFF263343);
        heroButton.setOnClickListener(v -> chooseHero());
        top.addView(heroButton, new LinearLayout.LayoutParams(dp(108), dp(39)));

        Button buildButton = makeButton("BUILD", 0xFF43351C);
        buildButton.setOnClickListener(v -> showBuild());
        LinearLayout.LayoutParams buildLp = new LinearLayout.LayoutParams(dp(65), dp(39));
        buildLp.leftMargin = dp(5);
        top.addView(buildButton, buildLp);

        levelButton = makeButton("LVL +", 0xFF244D37);
        levelButton.setOnClickListener(v -> {
            skillPoints = Math.min(5, skillPoints + 1);
            updateLevelButton();
            status("Skill point added. Tap a small + beside S1, S2 or ULT to send the upgrade tap.");
            controller.invalidate();
        });
        LinearLayout.LayoutParams levelLp = new LinearLayout.LayoutParams(dp(72), dp(39));
        levelLp.leftMargin = dp(5);
        top.addView(levelButton, levelLp);
        root.addView(top);

        LinearLayout connection = new LinearLayout(this);
        connection.setGravity(Gravity.CENTER_VERTICAL);
        ipField = new EditText(this);
        ipField.setSingleLine(true);
        ipField.setTextSize(13);
        ipField.setTextColor(Color.WHITE);
        ipField.setHintTextColor(0xFF7D8794);
        ipField.setHint("PC IP shown on PC host window");
        ipField.setText(hostIp);
        ipField.setSelectAllOnFocus(true);
        ipField.setPadding(dp(10), 0, dp(8), 0);
        ipField.setBackgroundTintList(android.content.res.ColorStateList.valueOf(0xFF46515E));
        connection.addView(ipField, new LinearLayout.LayoutParams(0, dp(38), 1f));

        Button connectButton = makeButton("CONNECT", 0xFF9B742D);
        connectButton.setTextColor(Color.WHITE);
        LinearLayout.LayoutParams connectLp = new LinearLayout.LayoutParams(dp(92), dp(38));
        connectLp.leftMargin = dp(5);
        connection.addView(connectButton, connectLp);

        micButton = makeButton("🎙  HOLD TO TALK", 0xFF6A2630);
        LinearLayout.LayoutParams micLp = new LinearLayout.LayoutParams(dp(136), dp(38));
        micLp.leftMargin = dp(5);
        connection.addView(micButton, micLp);
        root.addView(connection);

        statusText = new TextView(this);
        statusText.setTextColor(0xFF9DA8B5);
        statusText.setTextSize(10);
        statusText.setText("Enter the PC IP shown in MLBB Link Host, then tap CONNECT.");
        statusText.setPadding(dp(5), dp(3), dp(5), dp(3));
        root.addView(statusText, new LinearLayout.LayoutParams(-1, dp(23)));

        controller = new ControllerView();
        root.addView(controller, new LinearLayout.LayoutParams(-1, 0, 1f));
        setContentView(root);

        connectButton.setOnClickListener(v -> {
            String candidate = ipField.getText().toString().trim();
            if (candidate.isEmpty()) {
                Toast.makeText(this, "Enter the PC IP shown in MLBB Link Host.", Toast.LENGTH_SHORT).show();
                return;
            }
            hostIp = candidate;
            getPreferences(MODE_PRIVATE).edit().putString("pc_ip", hostIp).apply();
            sender.setHost(hostIp);
            sender.send(new JSONObjectSafe().event("hello", "connected"));
            status("Target saved: " + hostIp + ":" + PHONE_PORT + " • same Wi-Fi required");
        });

        micButton.setOnTouchListener((v, event) -> {
            if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
                if (hostIp.isEmpty()) {
                    Toast.makeText(this, "Connect to your PC first.", Toast.LENGTH_SHORT).show();
                    return true;
                }
                if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                    requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, REQUEST_MIC);
                    status("Allow microphone access, then press and hold TALK again.");
                    return true;
                }
                if (micStreamer.start(hostIp)) {
                    micButton.setText("● TALKING — RELEASE");
                    status("Phone microphone is streaming to PC port " + MIC_PORT + ".");
                } else {
                    status("Could not start microphone. Check permission and try again.");
                }
                return true;
            } else if (event.getActionMasked() == MotionEvent.ACTION_UP
                    || event.getActionMasked() == MotionEvent.ACTION_CANCEL) {
                micStreamer.stop();
                micButton.setText("🎙  HOLD TO TALK");
                status("Push-to-talk released.");
                return true;
            }
            return true;
        });
        updateLevelButton();
    }

    private Button makeButton(String label, int background) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextSize(10);
        b.setTextColor(Color.WHITE);
        b.setAllCaps(false);
        b.setPadding(dp(3), 0, dp(3), 0);
        b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(background));
        return b;
    }

    private int dp(float value) { return Math.round(value * getResources().getDisplayMetrics().density); }

    private void requestFullscreen() {
        Window w = getWindow();
        w.setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN, WindowManager.LayoutParams.FLAG_FULLSCREEN);
        w.getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
    }

    private void status(String message) {
        if (statusText != null) statusText.setText(message);
    }

    private void updateLevelButton() {
        levelButton.setText("LVL + (" + skillPoints + ")");
    }

    private void chooseHero() {
        String[] heroes = {"Sora", "Nana", "Dyrroth"};
        new AlertDialog.Builder(this)
                .setTitle("Choose hero preset")
                .setItems(heroes, (dialog, which) -> {
                    hero = heroes[which];
                    heroButton.setText("HERO: " + hero);
                    controller.resetCooldowns();
                    status(hero + " selected. Cooldowns are estimates; game patch, skill level and items can change them.");
                }).show();
    }

    private void showBuild() {
        String title = hero + " • starter build reference";
        String[] items;
        if ("Dyrroth".equals(hero)) {
            items = new String[]{"Tough Boots", "War Axe", "Hunter Strike", "Blade of the Heptaseas", "Malefic Roar", "Immortality"};
        } else if ("Sora".equals(hero)) {
            items = new String[]{"Tough Boots", "War Axe", "Queen's Wings", "Hunter Strike", "Malefic Roar", "Immortality"};
        } else {
            items = new String[]{"Arcane Boots", "Genius Wand", "Glowing Wand", "Wishing Lantern", "Divine Glaive", "Holy Crystal"};
        }
        StringBuilder build = new StringBuilder(title).append("\n\n");
        for (int i = 0; i < items.length; i++) build.append(i + 1).append(". ").append(items[i]).append("\n");
        build.append("\nStarter suggestions only — adjust for the current patch and enemy team. This app does not read MLBB match state or buy items automatically.");
        new AlertDialog.Builder(this).setTitle(title).setMessage(build.toString())
                .setPositiveButton("COPY BUILD", (d, w) -> {
                    ClipboardManager clipboard = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
                    clipboard.setPrimaryClip(ClipData.newPlainText("MLBB build", build.toString()));
                    Toast.makeText(this, "Build copied", Toast.LENGTH_SHORT).show();
                })
                .setNegativeButton("CLOSE", null).show();
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grants) {
        super.onRequestPermissionsResult(requestCode, permissions, grants);
        if (requestCode == REQUEST_MIC && grants.length > 0 && grants[0] == PackageManager.PERMISSION_GRANTED) {
            status("Microphone allowed. Press and hold TALK to use it.");
        } else if (requestCode == REQUEST_MIC) {
            status("Microphone permission denied.");
        }
    }

    @Override protected void onDestroy() {
        micStreamer.stop();
        sender.stop();
        super.onDestroy();
    }

    private void emit(JSONObject o) {
        if (hostIp.isEmpty()) {
            status("Enter PC IP and tap CONNECT first.");
            return;
        }
        sender.send(o);
    }

    private class ControllerView extends View {
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final PointF joy = new PointF();
        private boolean joyDown = false;
        private int joyPointer = -1;
        private final List<ButtonSpec> buttons = new ArrayList<>();
        private final java.util.Map<String, Long> cooldownEnds = new java.util.HashMap<>();
        private float minDim;
        private float width;
        private float height;

        ControllerView() {
            super(MainActivity.this);
            setBackgroundColor(Color.rgb(7, 10, 16));
            buttons.add(new ButtonSpec("attack", "ATK", "⚔", .90f, .73f, .92f, .80f, .105f, 0, 0xFFB9463F));
            buttons.add(new ButtonSpec("skill1", "S1", "✦", .72f, .59f, .76f, .82f, .078f, 5.5f, 0xFF4A8CB8));
            buttons.add(new ButtonSpec("skill2", "S2", "❖", .83f, .49f, .84f, .72f, .078f, 11f, 0xFF58A58C));
            buttons.add(new ButtonSpec("ult", "ULT", "✹", .93f, .59f, .95f, .72f, .087f, 32f, 0xFF9875D0));
            buttons.add(new ButtonSpec("spell", "SPELL", "⚡", .69f, .79f, .69f, .87f, .060f, 0, 0xFF9C9C61));
            buttons.add(new ButtonSpec("recall", "RECALL", "↻", .96f, .84f, .97f, .90f, .052f, 0, 0xFF607D8B));
        }

        @Override protected void onDraw(Canvas c) {
            super.onDraw(c);
            width = getWidth();
            height = getHeight();
            minDim = Math.min(width, height);
            // low-contrast guide grid gives the controller a cleaner HUD without covering the black screen
            paint.setStyle(Paint.Style.STROKE);
            paint.setStrokeWidth(1);
            paint.setColor(0x182B4659);
            for (int i = 1; i < 5; i++) c.drawLine(width * i / 5f, 0, width * i / 5f, height, paint);
            c.drawLine(0, height * .5f, width, height * .5f, paint);
            paint.setStyle(Paint.Style.FILL);

            drawJoystick(c);
            for (ButtonSpec b : buttons) drawButton(c, b);

            paint.setColor(0xFF647181);
            paint.setTextSize(Math.max(9, minDim * .032f));
            paint.setTextAlign(Paint.Align.LEFT);
            c.drawText("HOLD / DRAG JOYSTICK", width * .04f, height * .95f, paint);
            paint.setTextAlign(Paint.Align.RIGHT);
            c.drawText("Manual input • tap skills • hold TALK for voice", width * .98f, height * .96f, paint);
            paint.setTextAlign(Paint.Align.LEFT);

            boolean active = false;
            long now = System.currentTimeMillis();
            for (Long until : cooldownEnds.values()) if (until > now) active = true;
            if (active) postInvalidateDelayed(120);
        }

        private void drawJoystick(Canvas c) {
            float cx = width * .16f, cy = height * .70f, r = minDim * .145f;
            circle(c, cx, cy, r, 0x662A3643, 0xFF718395, 2f);
            circle(c, cx, cy, r * .70f, 0x222D82B7, 0x554B91C1, 1.5f);
            float nx = joyDown ? joy.x : cx;
            float ny = joyDown ? joy.y : cy;
            circle(c, nx, ny, r * .36f, 0xDD9EB8CD, Color.WHITE, 2f);
            paint.setColor(Color.WHITE);
            paint.setTextAlign(Paint.Align.CENTER);
            paint.setTextSize(Math.max(10, r * .26f));
            c.drawText("MOVE", cx, cy + r + minDim * .055f, paint);
        }

        private void drawButton(Canvas c, ButtonSpec b) {
            float x = width * b.dx, y = height * b.dy, r = minDim * b.radius;
            circle(c, x, y, r, (b.name.equals("attack") ? 0xCC4C201F : 0xC91C2937), b.color, 2.2f);
            circle(c, x, y, r * .79f, 0x332E3C4D, 0x665F778C, 1f);

            paint.setTextAlign(Paint.Align.CENTER);
            paint.setColor(Color.WHITE);
            paint.setTextSize(Math.max(16, r * .72f));
            c.drawText(b.icon, x, y - r * .03f, paint);
            paint.setTextSize(Math.max(9, r * .32f));
            paint.setTypeface(Paint.FAKE_BOLD_TEXT_FLAG != 0 ? android.graphics.Typeface.DEFAULT_BOLD : android.graphics.Typeface.DEFAULT);
            c.drawText(b.label, x, y + r * .64f, paint);
            paint.setTypeface(android.graphics.Typeface.DEFAULT);

            Long end = cooldownEnds.get(b.name);
            long now = System.currentTimeMillis();
            if (end != null && end > now) {
                float remain = (end - now) / 1000f;
                paint.setStyle(Paint.Style.FILL);
                paint.setColor(0xB9000000);
                c.drawCircle(x, y, r * .76f, paint);
                paint.setStyle(Paint.Style.STROKE);
                paint.setStrokeWidth(Math.max(2.5f, r * .12f));
                paint.setStrokeCap(Paint.Cap.ROUND);
                paint.setColor(0xFFE7BD64);
                float sweep = Math.max(0, Math.min(360, remain / b.cooldownFor(hero) * 360f));
                c.drawArc(new RectF(x - r * .86f, y - r * .86f, x + r * .86f, y + r * .86f), -90, sweep, false, paint);
                paint.setStyle(Paint.Style.FILL);
                paint.setColor(Color.WHITE);
                paint.setTextSize(Math.max(12, r * .62f));
                c.drawText(String.format(java.util.Locale.US, "%.1f", remain), x, y + r * .16f, paint);
            }
            if (b.isSkill() && skillPoints > 0) {
                float px = x + r * .69f, py = y - r * .69f, pr = r * .34f;
                circle(c, px, py, pr, 0xFFDFAD42, 0xFFFFE9AA, 1.5f);
                paint.setColor(0xFF10151D);
                paint.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
                paint.setTextSize(pr * 1.65f);
                c.drawText("+", px, py + pr * .48f, paint);
                paint.setTypeface(android.graphics.Typeface.DEFAULT);
            }
            paint.setStyle(Paint.Style.FILL);
            paint.setStrokeCap(Paint.Cap.BUTT);
        }

        private void circle(Canvas c, float x, float y, float r, int fill, int stroke, float strokeWidth) {
            paint.setStyle(Paint.Style.FILL);
            paint.setColor(fill);
            c.drawCircle(x, y, r, paint);
            paint.setStyle(Paint.Style.STROKE);
            paint.setStrokeWidth(strokeWidth);
            paint.setColor(stroke);
            c.drawCircle(x, y, r, paint);
            paint.setStyle(Paint.Style.FILL);
        }

        private ButtonSpec hitButton(float x, float y) {
            for (ButtonSpec b : buttons) {
                float bx = width * b.dx, by = height * b.dy, r = minDim * b.radius * 1.18f;
                float dx = x - bx, dy = y - by;
                if (dx * dx + dy * dy <= r * r) return b;
            }
            return null;
        }

        private ButtonSpec hitPlus(float x, float y) {
            if (skillPoints < 1) return null;
            for (ButtonSpec b : buttons) {
                if (!b.isSkill()) continue;
                float bx = width * b.dx + minDim * b.radius * .69f;
                float by = height * b.dy - minDim * b.radius * .69f;
                float r = minDim * b.radius * .43f;
                float dx = x - bx, dy = y - by;
                if (dx * dx + dy * dy <= r * r) return b;
            }
            return null;
        }

        @Override public boolean onTouchEvent(MotionEvent e) {
            int action = e.getActionMasked();
            int idx = e.getActionIndex();
            int id = e.getPointerId(idx);
            float x = e.getX(idx), y = e.getY(idx);

            if (action == MotionEvent.ACTION_DOWN || action == MotionEvent.ACTION_POINTER_DOWN) {
                ButtonSpec plus = hitPlus(x, y);
                if (plus != null) {
                    skillPoints--;
                    updateLevelButton();
                    sendButton("upgrade_" + plus.name, "down", plus.tx - .015f, Math.max(.05f, plus.ty - .075f));
                    status("Upgrade tap sent for " + plus.label + ". Points left: " + skillPoints);
                    invalidate();
                    return true;
                }
                if (x < width * .34f && y > height * .38f) {
                    joyDown = true;
                    joyPointer = id;
                    joy.set(x, y);
                    emitJoy("down", x / width, y / height);
                    invalidate();
                    return true;
                }
                ButtonSpec b = hitButton(x, y);
                if (b != null) {
                    float cd = b.cooldownFor(hero);
                    if (cd > 0) cooldownEnds.put(b.name, System.currentTimeMillis() + (long)(cd * 1000));
                    sendButton(b.name, "down", b.tx, b.ty);
                    invalidate();
                    return true;
                }
                return true;
            } else if (action == MotionEvent.ACTION_MOVE) {
                if (joyDown) {
                    for (int i = 0; i < e.getPointerCount(); i++) {
                        if (e.getPointerId(i) == joyPointer) {
                            joy.set(e.getX(i), e.getY(i));
                            float nx = Math.max(.03f, Math.min(.34f, joy.x / width));
                            float ny = Math.max(.40f, Math.min(.96f, joy.y / height));
                            emitJoy("move", nx, ny);
                            invalidate();
                            break;
                        }
                    }
                }
                return true;
            } else if (action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_POINTER_UP || action == MotionEvent.ACTION_CANCEL) {
                if (id == joyPointer) {
                    joyDown = false;
                    joyPointer = -1;
                    emitJoy("up", .16f, .70f);
                    invalidate();
                    return true;
                }
                return true;
            }
            return true;
        }

        private void sendButton(String name, String state, float x, float y) {
            try {
                JSONObject o = new JSONObject();
                o.put("type", "button");
                o.put("name", name);
                o.put("state", state);
                o.put("x", x);
                o.put("y", y);
                emit(o);
            } catch (Exception ignored) {}
        }

        private void emitJoy(String state, float x, float y) {
            try {
                JSONObject o = new JSONObject();
                o.put("type", "joystick");
                o.put("state", state);
                o.put("x", x);
                o.put("y", y);
                emit(o);
            } catch (Exception ignored) {}
        }

        void resetCooldowns() {
            cooldownEnds.clear();
            for (ButtonSpec b : buttons) {
                if ("skill1".equals(b.name)) b.baseCooldown = cooldownForSelectedHero("skill1");
                if ("skill2".equals(b.name)) b.baseCooldown = cooldownForSelectedHero("skill2");
                if ("ult".equals(b.name)) b.baseCooldown = cooldownForSelectedHero("ult");
            }
            invalidate();
        }

        private float cooldownForSelectedHero(String skill) {
            if ("Dyrroth".equals(hero)) {
                if ("skill1".equals(skill)) return 6f;
                if ("skill2".equals(skill)) return 8f;
                return 36f;
            } else if ("Sora".equals(hero)) {
                if ("skill1".equals(skill)) return 5f;
                if ("skill2".equals(skill)) return 11f;
                return 30f;
            } else {
                if ("skill1".equals(skill)) return 5.5f;
                if ("skill2".equals(skill)) return 12f;
                return 36f;
            }
        }

        private class ButtonSpec {
            String name, label, icon;
            float dx, dy, tx, ty, radius, baseCooldown;
            int color;
            ButtonSpec(String name, String label, String icon, float dx, float dy,
                       float tx, float ty, float radius, float cooldown, int color) {
                this.name = name; this.label = label; this.icon = icon;
                this.dx = dx; this.dy = dy; this.tx = tx; this.ty = ty;
                this.radius = radius; this.baseCooldown = cooldown; this.color = color;
            }
            boolean isSkill() { return name.equals("skill1") || name.equals("skill2") || name.equals("ult"); }
            float cooldownFor(String selectedHero) {
                if (name.equals("skill1") || name.equals("skill2") || name.equals("ult")) return cooldownForSelectedHero(name);
                return baseCooldown;
            }
        }
    }

    private static class JSONObjectSafe {
        JSONObject event(String type, String state) {
            JSONObject o = new JSONObject();
            try { o.put("type", type); o.put("state", state); } catch (Exception ignored) {}
            return o;
        }
    }

    private static class UdpSender {
        private final ExecutorService io = Executors.newSingleThreadExecutor();
        private volatile String host;
        private DatagramSocket socket;
        void setHost(String value) { host = value; }
        void start() {}
        void send(JSONObject o) {
            String h = host;
            if (h == null || h.isEmpty()) return;
            io.execute(() -> {
                try {
                    if (socket == null || socket.isClosed()) socket = new DatagramSocket();
                    byte[] bytes = o.toString().getBytes(StandardCharsets.UTF_8);
                    socket.send(new DatagramPacket(bytes, bytes.length, InetAddress.getByName(h), PHONE_PORT));
                } catch (Exception ignored) {}
            });
        }
        void stop() { if (socket != null) socket.close(); io.shutdownNow(); }
    }

    private class MicStreamer {
        private volatile boolean running = false;
        private Thread thread;
        private AudioRecord recorder;
        private DatagramSocket socket;
        private String target;

        synchronized boolean start(String ip) {
            if (running) return true;
            if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) return false;
            target = ip;
            int min = AudioRecord.getMinBufferSize(16000, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT);
            if (min <= 0) return false;
            try {
                recorder = new AudioRecord(MediaRecorder.AudioSource.VOICE_COMMUNICATION, 16000,
                        AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, Math.max(min * 2, 4096));
                if (recorder.getState() != AudioRecord.STATE_INITIALIZED) { recorder.release(); recorder = null; return false; }
                socket = new DatagramSocket();
                recorder.startRecording();
                running = true;
                thread = new Thread(() -> {
                    byte[] buffer = new byte[640]; // 20 ms of 16 kHz mono PCM16
                    try {
                        InetAddress address = InetAddress.getByName(target);
                        while (running) {
                            int read = recorder.read(buffer, 0, buffer.length);
                            if (read > 0) socket.send(new DatagramPacket(buffer, read, address, MIC_PORT));
                        }
                    } catch (Exception ignored) {
                    } finally {
                        running = false;
                        try { recorder.stop(); } catch (Exception ignored) {}
                        recorder.release();
                        try { socket.close(); } catch (Exception ignored) {}
                    }
                }, "MLBB-Link-Microphone");
                thread.setDaemon(true);
                thread.start();
                return true;
            } catch (Exception e) {
                running = false;
                try { if (recorder != null) recorder.release(); } catch (Exception ignored) {}
                try { if (socket != null) socket.close(); } catch (Exception ignored) {}
                recorder = null; socket = null;
                return false;
            }
        }

        synchronized void stop() {
            running = false;
            try { if (recorder != null && recorder.getRecordingState() == AudioRecord.RECORDSTATE_RECORDING) recorder.stop(); } catch (Exception ignored) {}
            try { if (socket != null) socket.close(); } catch (Exception ignored) {}
            if (thread != null) thread.interrupt();
            recorder = null;
            socket = null;
        }
    }
}
