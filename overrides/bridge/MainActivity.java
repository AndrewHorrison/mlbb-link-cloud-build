package com.mlbblink.bridge;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.ConnectivityManager;
import android.net.LinkProperties;
import android.net.Network;
import android.net.RouteInfo;
import android.os.Bundle;
import android.provider.Settings;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final int DASHBOARD_PORT = 28740;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private TextView ipValue, statusValue, gatewayValue;
    private EditText manualIp;
    private String detectedIp = "";
    private String gatewayIp = "";

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.rgb(8, 13, 20));
        getWindow().setNavigationBarColor(Color.rgb(8, 13, 20));

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.rgb(8, 13, 20));
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(22), dp(24), dp(22), dp(24));
        scroll.addView(root);

        TextView eyebrow = new TextView(this);
        eyebrow.setText("MLBB LINK  /  WAYDROID");
        eyebrow.setTextColor(0xFFFFD36D);
        eyebrow.setTextSize(12);
        eyebrow.setTypeface(Typeface.DEFAULT_BOLD);
        eyebrow.setLetterSpacing(0.09f);
        root.addView(eyebrow);

        TextView title = new TextView(this);
        title.setText("Touch Bridge");
        title.setTextColor(Color.WHITE);
        title.setTextSize(28);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setPadding(0, dp(6), 0, dp(3));
        root.addView(title);

        TextView intro = new TextView(this);
        intro.setText("Find the PC address automatically, then enable the accessibility service so controller touches can reach Waydroid.");
        intro.setTextColor(0xFF9AAAB9);
        intro.setTextSize(14);
        intro.setLineSpacing(dp(3), 1f);
        intro.setPadding(0, 0, 0, dp(18));
        root.addView(intro);

        LinearLayout ipCard = card(root);
        label(ipCard, "PC LAN IP  ·  USE THIS IN THE PHONE CONTROLLER");
        ipValue = new TextView(this);
        ipValue.setText("Searching for PC…");
        ipValue.setTextColor(Color.WHITE);
        ipValue.setTextSize(27);
        ipValue.setTypeface(Typeface.create("monospace", Typeface.BOLD));
        ipValue.setPadding(0, dp(12), 0, dp(8));
        ipCard.addView(ipValue);

        statusValue = new TextView(this);
        statusValue.setText("Looking for the PC host dashboard on the Waydroid gateway…");
        statusValue.setTextColor(0xFF9AAAB9);
        statusValue.setTextSize(13);
        ipCard.addView(statusValue);

        gatewayValue = new TextView(this);
        gatewayValue.setText("Waydroid gateway: checking…");
        gatewayValue.setTextColor(0xFF7EA7C2);
        gatewayValue.setTextSize(12);
        gatewayValue.setPadding(0, dp(8), 0, dp(2));
        ipCard.addView(gatewayValue);

        LinearLayout ipActions = new LinearLayout(this);
        ipActions.setOrientation(LinearLayout.HORIZONTAL);
        ipActions.setPadding(0, dp(12), 0, 0);
        Button refresh = button("FIND PC", true);
        ipActions.addView(refresh, new LinearLayout.LayoutParams(0, dp(45), 1f));
        Button copy = button("COPY IP", false);
        LinearLayout.LayoutParams copyLp = new LinearLayout.LayoutParams(0, dp(45), 1f);
        copyLp.leftMargin = dp(8);
        ipActions.addView(copy, copyLp);
        ipCard.addView(ipActions);

        LinearLayout manualCard = card(root);
        label(manualCard, "MANUAL IP FALLBACK");
        TextView help = new TextView(this);
        help.setText("If automatic discovery cannot reach the PC, enter the PC LAN IP shown by the PC host. Do not use 127.0.0.1 or the Waydroid IP.");
        help.setTextColor(0xFF9AAAB9);
        help.setTextSize(13);
        help.setPadding(0, dp(6), 0, dp(10));
        manualCard.addView(help);

        manualIp = new EditText(this);
        manualIp.setSingleLine(true);
        manualIp.setTextColor(Color.WHITE);
        manualIp.setHintTextColor(0xFF738394);
        manualIp.setHint("e.g. 192.168.1.23");
        manualIp.setTextSize(15);
        manualIp.setPadding(dp(12), 0, dp(12), 0);
        manualIp.setBackgroundColor(0xFF192635);
        manualCard.addView(manualIp, new LinearLayout.LayoutParams(-1, dp(46)));

        Button useManual = button("USE THIS IP", true);
        LinearLayout.LayoutParams manualLp = new LinearLayout.LayoutParams(-1, dp(45));
        manualLp.topMargin = dp(10);
        manualCard.addView(useManual, manualLp);

        LinearLayout serviceCard = card(root);
        label(serviceCard, "TOUCH INPUT SERVICE");
        TextView note = new TextView(this);
        note.setText("Enable “MLBB Link Touch Bridge” in Android Accessibility settings to allow touch gestures to be dispatched.");
        note.setTextColor(0xFF9AAAB9);
        note.setTextSize(13);
        note.setPadding(0, dp(6), 0, dp(12));
        serviceCard.addView(note);
        Button access = button("OPEN ACCESSIBILITY SETTINGS", false);
        serviceCard.addView(access, new LinearLayout.LayoutParams(-1, dp(45)));

        TextView foot = new TextView(this);
        foot.setText("PC dashboard: http://127.0.0.1:28740/ on the PC itself  ·  Bridge UDP 28742");
        foot.setTextColor(0xFF65788A);
        foot.setTextSize(11);
        foot.setPadding(dp(2), dp(14), dp(2), 0);
        root.addView(foot);

        setContentView(scroll);
        refresh.setOnClickListener(v -> discoverHost());
        copy.setOnClickListener(v -> copyIp());
        useManual.setOnClickListener(v -> {
            String value = manualIp.getText().toString().trim();
            if (!isIpv4(value) || value.startsWith("127.")) {
                Toast.makeText(this, "Enter the PC LAN IPv4 address, not 127.0.0.1", Toast.LENGTH_SHORT).show();
                return;
            }
            detectedIp = value;
            ipValue.setText(value);
            statusValue.setText("Manual PC IP selected. Confirm it matches the PC host dashboard.");
        });
        access.setOnClickListener(v -> startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));
        discoverHost();
    }

    private void discoverHost() {
        gatewayIp = defaultGateway();
        gatewayValue.setText("Waydroid gateway: " + (gatewayIp.isEmpty() ? "not detected" : gatewayIp));
        ipValue.setText("Searching…");
        statusValue.setText("Checking the Waydroid gateway and common host addresses…");
        java.util.LinkedHashSet<String> candidateSet = new java.util.LinkedHashSet<>();
        if (gatewayIp != null && !gatewayIp.isEmpty()) candidateSet.add(gatewayIp);
        candidateSet.add("192.168.240.1");
        candidateSet.add("192.168.241.1");
        candidateSet.add("10.0.2.2");
        candidateSet.add("10.0.3.2");
        final java.util.List<String> candidates = new java.util.ArrayList<>(candidateSet);
        worker.execute(() -> {
            String ip = null;
            String via = null;
            for (String candidate : candidates) {
                String found = fetchHostIp(candidate);
                if (found != null && isIpv4(found) && !found.startsWith("127.")) {
                    ip = found;
                    via = candidate;
                    break;
                }
            }
            final String finalIp = ip;
            final String finalVia = via;
            runOnUiThread(() -> {
                if (finalIp != null) {
                    detectedIp = finalIp;
                    ipValue.setText(finalIp);
                    statusValue.setText("PC found through " + finalVia + ". Use this IP in the phone controller.");
                    if (manualIp != null && manualIp.getText().toString().trim().isEmpty()) manualIp.setText(finalIp);
                } else {
                    statusValue.setText("PC dashboard is unreachable. Start mlbb_link_host.py and allow TCP 28740 from Waydroid, or enter the PC LAN IP below.");
                    ipValue.setText("Not found");
                }
            });
        });
    }

    private String fetchHostIp(String gateway) {
        if (gateway == null || gateway.isEmpty()) return null;
        HttpURLConnection conn = null;
        try {
            URL url = new URL("http://" + gateway + ":" + DASHBOARD_PORT + "/api/status");
            conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("GET");
            conn.setConnectTimeout(1200);
            conn.setReadTimeout(1200);
            conn.setUseCaches(false);
            if (conn.getResponseCode() != 200) return null;
            try (InputStream in = conn.getInputStream();
                 BufferedReader reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
                StringBuilder body = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) body.append(line);
                return new JSONObject(body.toString()).optString("host_ip", null);
            }
        } catch (Exception ignored) {
            return null;
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    private String defaultGateway() {
        try {
            ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
            Network active = cm == null ? null : cm.getActiveNetwork();
            LinkProperties lp = active == null ? null : cm.getLinkProperties(active);
            if (lp != null) {
                for (RouteInfo route : lp.getRoutes()) {
                    java.net.InetAddress gateway = route.getGateway();
                    if (route.isDefaultRoute() && gateway != null && !gateway.isAnyLocalAddress()) {
                        return gateway.getHostAddress();
                    }
                }
            }
        } catch (Exception ignored) { }
        // Standard Waydroid NAT gateway; manual entry remains available for custom networks.
        return "192.168.240.1";
    }

    private void copyIp() {
        if (detectedIp == null || detectedIp.isEmpty()) {
            Toast.makeText(this, "No PC IP yet — tap FIND PC or enter one manually", Toast.LENGTH_LONG).show();
            return;
        }
        ClipboardManager clipboard = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        clipboard.setPrimaryClip(ClipData.newPlainText("MLBB Link PC IP", detectedIp));
        Toast.makeText(this, "Copied PC IP: " + detectedIp, Toast.LENGTH_SHORT).show();
    }

    private boolean isIpv4(String value) {
        if (value == null || !value.matches("[0-9]{1,3}(\\.[0-9]{1,3}){3}")) return false;
        String[] parts = value.split("\\.");
        try {
            for (String part : parts) if (Integer.parseInt(part) > 255) return false;
        } catch (NumberFormatException e) { return false; }
        return true;
    }

    private LinearLayout card(LinearLayout parent) {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(16), dp(15), dp(16), dp(16));
        android.graphics.drawable.GradientDrawable bg = new android.graphics.drawable.GradientDrawable();
        bg.setColor(0xFF101A26);
        bg.setCornerRadius(dp(16));
        bg.setStroke(dp(1), 0xFF2B4052);
        box.setBackground(bg);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
        lp.topMargin = dp(10);
        parent.addView(box, lp);
        return box;
    }

    private void label(LinearLayout parent, String text) {
        TextView t = new TextView(this);
        t.setText(text);
        t.setTextColor(0xFFE6C274);
        t.setTextSize(10);
        t.setTypeface(Typeface.DEFAULT_BOLD);
        t.setLetterSpacing(0.06f);
        parent.addView(t);
    }

    private Button button(String text, boolean primary) {
        Button b = new Button(this);
        b.setText(text);
        b.setAllCaps(false);
        b.setTextSize(12);
        b.setTypeface(Typeface.DEFAULT_BOLD);
        b.setMinHeight(0);
        b.setMinimumHeight(0);
        b.setPadding(dp(6), 0, dp(6), 0);
        android.graphics.drawable.GradientDrawable bg = new android.graphics.drawable.GradientDrawable();
        bg.setCornerRadius(dp(10));
        if (primary) {
            bg.setColor(0xFFE4BD68);
            bg.setStroke(dp(1), 0xFFFFE4A5);
            b.setTextColor(0xFF21190A);
        } else {
            bg.setColor(0xFF1A2938);
            bg.setStroke(dp(1), 0xFF415A6E);
            b.setTextColor(Color.WHITE);
        }
        b.setBackground(bg);
        return b;
    }

    private int dp(float px) {
        return Math.round(px * getResources().getDisplayMetrics().density);
    }

    @Override protected void onDestroy() {
        worker.shutdownNow();
        super.onDestroy();
    }
}
