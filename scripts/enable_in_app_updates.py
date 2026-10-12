#!/usr/bin/env python3
"""Replace the browser-opening APK update action with an in-app verified downloader."""
from __future__ import annotations
import sys
from pathlib import Path

REPO_PREFIX = "https://github.com/AndrewHorrison/mlbb-link-cloud-build/releases/download/"
MANIFEST_URL = "https://raw.githubusercontent.com/AndrewHorrison/mlbb-link-cloud-build/main/updates/latest.json"

def replace_method(source: str, signature: str, replacement: str) -> str:
    start = source.find(signature)
    if start < 0: raise SystemExit(f"Java method not found: {signature}")
    brace = source.find("{", start)
    if brace < 0: raise SystemExit(f"Method opening brace not found: {signature}")
    depth = 0
    in_string = in_char = escaped = line_comment = block_comment = False
    i = brace
    while i < len(source):
        ch, nxt = source[i], source[i + 1] if i + 1 < len(source) else ""
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
            if depth == 0: return source[:start] + replacement + source[i + 1:]
        i += 1
    raise SystemExit(f"Unclosed Java method: {signature}")

def ensure_import(source: str, statement: str) -> str:
    if statement in source: return source
    end = source.find("\n", source.find("package "))
    if end < 0: raise SystemExit("Java package declaration missing")
    return source[:end + 1] + "\n" + statement + source[end + 1:]

def main() -> int:
    if len(sys.argv) != 2: raise SystemExit("Usage: enable_in_app_updates.py source/mlbb-link")
    root = Path(sys.argv[1])
    app = root / "phone-controller/app"
    java_path = app / "src/main/java/com/mlbblink/controller/MainActivity.java"
    manifest_path = app / "src/main/AndroidManifest.xml"
    gradle_path = app / "build.gradle"
    if not all(p.is_file() for p in (java_path, manifest_path, gradle_path)):
        raise SystemExit("Phone controller source, manifest, or Gradle file is missing")
    java = java_path.read_text(encoding="utf-8")
    for imp in (
        "import android.app.ProgressDialog;", "import android.content.ActivityNotFoundException;",
        "import android.content.ClipData;", "import android.content.Intent;", "import android.net.Uri;",
        "import android.provider.Settings;", "import java.io.File;", "import java.io.FileOutputStream;",
        "import java.io.IOException;", "import java.io.InputStream;", "import java.security.MessageDigest;",
        "import java.util.Locale;", "import androidx.core.content.FileProvider;",
    ):
        java = ensure_import(java, imp)
    java = java.replace(
        'private static final String UPDATE_INFO_URL = "https://raw.githubusercontent.com/augustinejacyandrew-lgtm/mlbb-link-cloud-build/main/updates/latest.json";',
        f'private static final String UPDATE_INFO_URL = "{MANIFEST_URL}";')
    if "private volatile File pendingUpdateApk;" not in java:
        old = "    private final ExecutorService updateExecutor = Executors.newSingleThreadExecutor();"
        if old not in java: raise SystemExit("Updater executor field missing")
        java = java.replace(old, old + "\n    private volatile File pendingUpdateApk;\n    private volatile boolean updateDownloading = false;\n    private static final String PENDING_UPDATE_APK_KEY = \"pending_update_apk_path\";\n    private static final int REQUEST_INSTALL_UNKNOWN_SOURCES = 6410;\n    private static final String APK_MIME_TYPE = \"application/vnd.android.package-archive\";", 1)

    replacement = r'''    private void checkForUpdates() {
        updateExecutor.execute(() -> {
            HttpURLConnection conn = null;
            try {
                conn = (HttpURLConnection) new URL(UPDATE_INFO_URL).openConnection();
                conn.setConnectTimeout(7000); conn.setReadTimeout(7000);
                conn.setUseCaches(false); conn.setInstanceFollowRedirects(true);
                if (conn.getResponseCode() != HttpURLConnection.HTTP_OK) return;
                StringBuilder json = new StringBuilder();
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8))) {
                    String line; while ((line = reader.readLine()) != null) json.append(line);
                }
                JSONObject data = new JSONObject(json.toString());
                int remoteCode = data.optInt("versionCode", 0);
                String remoteName = data.optString("versionName", "new version");
                String download = data.optString(UPDATE_ASSET, "");
                String expectedSha = data.optString("phoneApkSha256", "").trim().toLowerCase(Locale.ROOT);
                if (remoteCode <= BuildConfig.VERSION_CODE || download.isEmpty()) return;
                if (!download.startsWith("''' + REPO_PREFIX + r'''")) return;
                SharedPreferences pref = getSharedPreferences(PREFS, MODE_PRIVATE);
                if (pref.getInt("update_prompted_code", 0) >= remoteCode) return;
                final int code = remoteCode;
                runOnUiThread(() -> {
                    if (isFinishing() || isDestroyed()) return;
                    new AlertDialog.Builder(MainActivity.this)
                        .setTitle("MLBB Link update available")
                        .setMessage("Installed v" + BuildConfig.VERSION_NAME + " · New v" + remoteName + " is ready.\n\nTap Download to save the update inside MLBB Link. Android will ask you to confirm installation afterward.")
                        .setPositiveButton("DOWNLOAD IN APP", (dialog, which) -> downloadAndInstallApk(download, expectedSha, remoteName, code))
                        .setNegativeButton("LATER", (dialog, which) -> pref.edit().putInt("update_prompted_code", code).apply())
                        .show();
                });
            } catch (Exception ignored) {
                // The updater is best-effort; offline controller use must keep working.
            } finally { if (conn != null) conn.disconnect(); }
        });
    }

    private void downloadAndInstallApk(String downloadUrl, String expectedSha, String remoteName, int remoteCode) {
        if (updateDownloading) return;
        if (downloadUrl == null || !downloadUrl.startsWith("''' + REPO_PREFIX + r'''")) {
            Toast.makeText(this, "Update URL is not trusted", Toast.LENGTH_LONG).show(); return;
        }
        updateDownloading = true;
        ProgressDialog progress = new ProgressDialog(this);
        progress.setTitle("Downloading MLBB Link v" + remoteName);
        progress.setMessage("Preparing secure in-app download…");
        progress.setProgressStyle(ProgressDialog.STYLE_HORIZONTAL);
        progress.setIndeterminate(true); progress.setCancelable(false); progress.setProgress(0); progress.show();
        updateExecutor.execute(() -> {
            HttpURLConnection conn = null; File part = null;
            try {
                File base = getExternalFilesDir(null);
                if (base == null) throw new IOException("Android app storage is unavailable");
                File updatesDir = new File(base, "updates");
                if (!updatesDir.isDirectory() && !updatesDir.mkdirs()) throw new IOException("Cannot create update folder");
                part = new File(updatesDir, "mlbb-link-controller.apk.part");
                File apk = new File(updatesDir, "mlbb-link-controller-v" + remoteName.replaceAll("[^A-Za-z0-9._-]", "_") + ".apk");
                conn = (HttpURLConnection) new URL(downloadUrl).openConnection();
                conn.setConnectTimeout(15000); conn.setReadTimeout(20000);
                conn.setUseCaches(false); conn.setInstanceFollowRedirects(true);
                conn.setRequestProperty("User-Agent", "MLBB-Link-Updater/1.0");
                int status = conn.getResponseCode();
                if (status != HttpURLConnection.HTTP_OK) throw new IOException("Download server returned HTTP " + status);
                long total = conn.getContentLengthLong();
                if (total > 120L * 1024L * 1024L) throw new IOException("Update file is unexpectedly large");
                MessageDigest digest = MessageDigest.getInstance("SHA-256");
                long received = 0L, lastUi = 0L;
                try (InputStream in = conn.getInputStream(); FileOutputStream out = new FileOutputStream(part)) {
                    byte[] buffer = new byte[16 * 1024]; int count;
                    while ((count = in.read(buffer)) != -1) {
                        out.write(buffer, 0, count); digest.update(buffer, 0, count); received += count;
                        long now = android.os.SystemClock.uptimeMillis();
                        if (now - lastUi >= 150) {
                            final long got = received, expected = total;
                            runOnUiThread(() -> {
                                if (!progress.isShowing()) return;
                                if (expected > 0L) {
                                    progress.setIndeterminate(false); progress.setMax(100);
                                    progress.setProgress((int)Math.min(100L, got * 100L / expected));
                                    progress.setMessage((got / 1024L) + " KB / " + (expected / 1024L) + " KB");
                                } else {
                                    progress.setIndeterminate(true); progress.setMessage((got / 1024L) + " KB downloaded");
                                }
                            });
                            lastUi = now;
                        }
                    }
                    out.flush();
                }
                if (received <= 0L) throw new IOException("The downloaded file is empty");
                if (total > 0L && received != total) throw new IOException("Download ended before the whole APK arrived");
                StringBuilder hex = new StringBuilder();
                for (byte value : digest.digest()) hex.append(String.format(Locale.ROOT, "%02x", value & 0xff));
                if (!expectedSha.isEmpty() && !hex.toString().equalsIgnoreCase(expectedSha))
                    throw new IOException("SHA-256 verification failed. The update was not installed.");
                if (apk.exists() && !apk.delete()) throw new IOException("Cannot replace the previous downloaded update");
                if (!part.renameTo(apk)) throw new IOException("Cannot finalize the downloaded APK");
                final File ready = apk;
                final boolean checksumChecked = !expectedSha.isEmpty();
                // Do not mark this version as handled until the user chooses LATER.
                // If Android installation is cancelled or rejected, offer the update again next launch.
                runOnUiThread(() -> {
                    if (progress.isShowing()) progress.dismiss();
                    updateDownloading = false;
                    Toast.makeText(MainActivity.this,
                        checksumChecked ? "Download complete · SHA-256 verified" : "Download complete · checksum not provided",
                        Toast.LENGTH_SHORT).show();
                    installApk(ready);
                });
            } catch (Exception e) {
                if (part != null && part.exists()) part.delete();
                final String error = e.getMessage() == null ? "Check your connection and try again." : e.getMessage();
                runOnUiThread(() -> {
                    if (progress.isShowing()) progress.dismiss();
                    updateDownloading = false;
                    new AlertDialog.Builder(MainActivity.this).setTitle("Update download failed").setMessage(error)
                        .setPositiveButton("RETRY", (d, w) -> downloadAndInstallApk(downloadUrl, expectedSha, remoteName, remoteCode))
                        .setNegativeButton("CLOSE", null).show();
                });
            } finally { if (conn != null) conn.disconnect(); }
        });
    }

    private void clearPendingInstall() {
        pendingUpdateApk = null;
        getSharedPreferences(PREFS, MODE_PRIVATE).edit().remove(PENDING_UPDATE_APK_KEY).apply();
    }

    private void installApk(File file) {
        if (isFinishing() || isDestroyed()) return;
        if (file == null || !file.isFile() || !file.canRead() || file.length() <= 0L) {
            Toast.makeText(this, "Downloaded APK is missing or unreadable. Download it again.", Toast.LENGTH_LONG).show();
            clearPendingInstall();
            return;
        }

        try {
            File baseDir = getExternalFilesDir(null);
            if (baseDir == null) throw new IOException("App storage is unavailable");
            File updatesRoot = new File(baseDir, "updates").getCanonicalFile();
            File apk = file.getCanonicalFile();
            String updatesPrefix = updatesRoot.getPath() + File.separator;
            if (!apk.getPath().startsWith(updatesPrefix)
                    || !apk.getName().toLowerCase(Locale.ROOT).endsWith(".apk")) {
                Toast.makeText(this, "Only an APK downloaded by MLBB Link can be installed.", Toast.LENGTH_LONG).show();
                clearPendingInstall();
                return;
            }

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !getPackageManager().canRequestPackageInstalls()) {
                pendingUpdateApk = apk;
                getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                        .putString(PENDING_UPDATE_APK_KEY, apk.getAbsolutePath()).apply();
                new AlertDialog.Builder(this)
                    .setTitle("Allow MLBB Link to install updates")
                    .setMessage("Android blocks APK installation until you allow this app to install unknown apps. Enable “Allow from this source” on the next screen, then return. The verified APK will open automatically.")
                    .setPositiveButton("OPEN SETTINGS", (dialog, which) -> {
                        try {
                            Intent settings = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                                    Uri.parse("package:" + getPackageName()));
                            settings.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP);
                            startActivityForResult(settings, REQUEST_INSTALL_UNKNOWN_SOURCES);
                        } catch (ActivityNotFoundException settingsNotAvailable) {
                            try {
                                startActivity(new Intent(Settings.ACTION_SECURITY_SETTINGS)
                                        .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP));
                            } catch (Exception fallbackFailure) {
                                Toast.makeText(MainActivity.this,
                                    "Open Settings → Apps → Special app access → Install unknown apps, then allow MLBB Link.",
                                    Toast.LENGTH_LONG).show();
                            }
                        }
                    })
                    .setNegativeButton("NOT NOW", (dialog, which) -> clearPendingInstall())
                    .show();
                return;
            }

            Uri apkUri = FileProvider.getUriForFile(
                    this, getPackageName() + ".fileprovider", apk);
            int flags = Intent.FLAG_GRANT_READ_URI_PERMISSION
                    | Intent.FLAG_ACTIVITY_NEW_TASK
                    | Intent.FLAG_ACTIVITY_CLEAR_TOP;
            Intent installIntent = new Intent(Intent.ACTION_INSTALL_PACKAGE);
            installIntent.setDataAndType(apkUri, APK_MIME_TYPE);
            installIntent.setClipData(ClipData.newRawUri("MLBB Link update APK", apkUri));
            installIntent.addFlags(flags);
            installIntent.putExtra(Intent.EXTRA_RETURN_RESULT, true);

            // Clear the saved request before leaving for Package Installer, preventing
            // onResume from accidentally opening a second installer after focus returns.
            clearPendingInstall();
            try {
                startActivity(installIntent);
            } catch (ActivityNotFoundException noInstallPackageHandler) {
                // Some OEM / Waydroid images expose ACTION_VIEW instead of ACTION_INSTALL_PACKAGE.
                Intent viewIntent = new Intent(Intent.ACTION_VIEW);
                viewIntent.setDataAndType(apkUri, APK_MIME_TYPE);
                viewIntent.setClipData(ClipData.newRawUri("MLBB Link update APK", apkUri));
                viewIntent.addFlags(flags);
                startActivity(viewIntent);
            }
        } catch (ActivityNotFoundException e) {
            Toast.makeText(this, "Android's package installer is unavailable or disabled.", Toast.LENGTH_LONG).show();
        } catch (SecurityException e) {
            Toast.makeText(this, "Android blocked installation. Check “Allow from this source” for MLBB Link.", Toast.LENGTH_LONG).show();
        } catch (Exception e) {
            String message = e.getMessage();
            Toast.makeText(this, "Could not open Android installer" +
                    (message == null || message.trim().isEmpty() ? "." : ": " + message),
                    Toast.LENGTH_LONG).show();
        }
    }
'''
    java = replace_method(java, "    private void checkForUpdates()", replacement)
    if "protected void onResume()" not in java:
        on_resume = '''    @Override protected void onResume() {
        super.onResume();
        if (isFinishing() || isDestroyed()) return;
        File ready = pendingUpdateApk;
        if (ready == null) {
            String path = getSharedPreferences(PREFS, MODE_PRIVATE).getString(PENDING_UPDATE_APK_KEY, null);
            if (path != null && !path.trim().isEmpty()) ready = new File(path);
        }
        if (ready == null) return;
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O || getPackageManager().canRequestPackageInstalls()) {
            pendingUpdateApk = null;
            installApk(ready);
        } else {
            Toast.makeText(this, "Allow MLBB Link to install unknown apps in Android Settings, then return.", Toast.LENGTH_LONG).show();
        }
    }

'''
        marker = "    @Override public void onCreate(Bundle savedInstanceState)"
        if marker not in java: raise SystemExit("Cannot locate onCreate insertion point")
        java = java.replace(marker, on_resume + marker, 1)
    java_path.write_text(java, encoding="utf-8")

    manifest = manifest_path.read_text(encoding="utf-8")
    if "android.permission.REQUEST_INSTALL_PACKAGES" not in manifest:
        marker = '    <uses-permission android:name="android.permission.INTERNET" />'
        if marker not in manifest: raise SystemExit("Internet permission missing from manifest")
        manifest = manifest.replace(marker, marker + '\n    <uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES" />', 1)
    if "androidx.core.content.FileProvider" not in manifest:
        provider = '''        <provider
            android:name="androidx.core.content.FileProvider"
            android:authorities="$\u007bapplicationId\u007d.fileprovider"
            android:exported="false"
            android:grantUriPermissions="true">
            <meta-data android:name="android.support.FILE_PROVIDER_PATHS" android:resource="@xml/file_paths" />
        </provider>
'''
        manifest = manifest.replace("    </application>", provider + "    </application>", 1)
    manifest_path.write_text(manifest, encoding="utf-8")
    paths_dir = app / "src/main/res/xml"
    paths_dir.mkdir(parents=True, exist_ok=True)
    (paths_dir / "file_paths.xml").write_text('''<?xml version="1.0" encoding="utf-8"?>
<paths xmlns:android="http://schemas.android.com/apk/res/android">
    <external-files-path name="downloaded_updates" path="updates/" />
</paths>
''', encoding="utf-8")
    gradle = gradle_path.read_text(encoding="utf-8")
    if "androidx.core:core:" not in gradle:
        gradle = gradle.rstrip() + "\n\ndependencies { implementation 'androidx.core:core:1.15.0' }\n"
    gradle_path.write_text(gradle, encoding="utf-8")
    if 'startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(download)))' in java:
        raise SystemExit("Browser-based APK update action still present")
    for marker in ("DOWNLOAD IN APP", "downloadAndInstallApk", "SHA-256 verification failed",
                   "private void installApk(File file)", "FileProvider.getUriForFile",
                   "setDataAndType(apkUri, APK_MIME_TYPE)", "Intent.FLAG_GRANT_READ_URI_PERMISSION",
                   "Intent.FLAG_ACTIVITY_NEW_TASK", "Intent.FLAG_ACTIVITY_CLEAR_TOP",
                   "canRequestPackageInstalls()", "Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES",
                   "PENDING_UPDATE_APK_KEY", "setClipData("):
        if marker not in java: raise SystemExit("In-app updater verification failed: " + marker)
    if "android.permission.REQUEST_INSTALL_PACKAGES" not in manifest or "androidx.core.content.FileProvider" not in manifest:
        raise SystemExit("Installer permission / FileProvider manifest setup is missing")
    print("Installed in-app APK updater: progress UI, SHA-256 verification, FileProvider, and Android install approval.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
