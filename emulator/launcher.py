#!/usr/bin/env python3
"""Desktop launcher and auto-updater for MLBB Link Emulator Tools on Bazzite/GNOME."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QProcess, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon, QUrl
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QTextEdit, QVBoxLayout, QWidget
)

from profiles import (
    default_settings, load_profile, load_settings, profile_path, save_json_atomic,
    settings_path, user_config_dir, user_data_dir
)
from updater import VERSION, check_for_update, download_and_install_update

APP_TITLE = "MLBB Link Emulator Tools"
REPO_URL = "https://github.com/AndrewHorrison/mlbb-link-cloud-build"


class CheckUpdateWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        try:
            self.completed.emit(check_for_update(VERSION))
        except Exception as exc:
            self.failed.emit(str(exc))


class InstallUpdateWorker(QThread):
    progressChanged = Signal(int)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, manifest: dict[str, Any], install_root: Path) -> None:
        super().__init__()
        self.manifest = manifest
        self.install_root = install_root

    def run(self) -> None:
        try:
            version = download_and_install_update(
                self.manifest, self.install_root,
                progress=lambda value: self.progressChanged.emit(value)
            )
            self.completed.emit(version)
        except Exception as exc:
            self.failed.emit(str(exc))


def _open_url(url: str) -> None:
    QDesktopServices.openUrl(QUrl(url))


def _load_or_create_user_files() -> tuple[Path, Path]:
    cfg = user_config_dir()
    cfg.mkdir(parents=True, exist_ok=True)
    data = user_data_dir()
    data.mkdir(parents=True, exist_ok=True)
    module_dir = Path(__file__).resolve().parent
    pfile = profile_path()
    if not pfile.exists():
        import json as json_module
        raw = json_module.loads((module_dir / "profile_default.json").read_text(encoding="utf-8"))
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            geometry = screen.geometry()
            raw["screen"]["width"] = geometry.width()
            raw["screen"]["height"] = geometry.height()
            raw["screen"]["targetRect"] = {
                "x": 0, "y": 0, "width": geometry.width(), "height": geometry.height()
            }
        save_json_atomic(pfile, raw)
    settings_file = settings_path()
    if not settings_file.exists():
        save_json_atomic(settings_file, default_settings())
    load_profile(pfile)
    load_settings(settings_file)
    return pfile, settings_file


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.module_dir = Path(__file__).resolve().parent
        self.install_root = self.module_dir
        self.profile_file, self.settings_file = _load_or_create_user_files()
        self.engine: subprocess.Popen | None = None
        self.overlay: subprocess.Popen | None = None
        self.engine_log_path = user_data_dir() / "engine.log"
        self.check_worker: CheckUpdateWorker | None = None
        self.install_worker: InstallUpdateWorker | None = None
        self.pending_manifest: dict[str, Any] | None = None
        self.setWindowTitle(f"{APP_TITLE} v{VERSION}")
        self.resize(800, 620)
        self.setMinimumSize(700, 560)
        self._build_ui()
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.refresh_process_status)
        self.status_timer.start(700)
        QTimer.singleShot(1800, lambda: self.check_updates(automatic=True))

    def _button(self, label: str, callback: Any) -> QPushButton:
        button = QPushButton(label)
        button.setMinimumHeight(40)
        button.clicked.connect(callback)
        return button

    def _build_ui(self) -> None:
        root = QWidget()
        root.setStyleSheet("""
            QWidget { background:#0b121a; color:#eaf2f8; font-size:13px; }
            QFrame#panel { background:#101c28; border:1px solid #2c4051; border-radius:12px; }
            QPushButton { background:#1b2e40; color:#eaf5fb; border:1px solid #476579; border-radius:8px; padding:8px 10px; font-weight:600; }
            QPushButton:hover { background:#2a4960; }
            QPushButton:disabled { color:#728693; background:#15202a; }
            QLabel#title { font-size:22px; font-weight:800; color:#f7d98f; }
            QLabel#muted { color:#a6b8c5; }
            QTextEdit { background:#081018; border:1px solid #293d4e; border-radius:8px; }
            QCheckBox { color:#d2e1eb; }
            QProgressBar { background:#071019; border:1px solid #355064; border-radius:5px; text-align:center; color:#f7f9fb; }
            QProgressBar::chunk { background:#69d5bd; border-radius:4px; }
        """)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel(f"{APP_TITLE}  ·  v{VERSION}")
        title.setObjectName("title")
        subtitle = QLabel("Waydroid helper · floating keymap editor · multi-touch input daemon · signed-by-checksum release updates")
        subtitle.setObjectName("muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        runtime_panel = QFrame()
        runtime_panel.setObjectName("panel")
        runtime_layout = QVBoxLayout(runtime_panel)
        self.runtime_status = QLabel("Checking Waydroid…")
        self.runtime_status.setWordWrap(True)
        runtime_layout.addWidget(QLabel("ANDROID RUNTIME"))
        runtime_layout.addWidget(self.runtime_status)
        runtime_buttons = QHBoxLayout()
        runtime_buttons.addWidget(self._button("Open Waydroid", self.open_waydroid))
        runtime_buttons.addWidget(self._button("Runtime setup guide", lambda: _open_url("https://docs.bazzite.gg/Installing_and_Managing_Software/Waydroid_Setup_Guide/")))
        runtime_layout.addLayout(runtime_buttons)
        layout.addWidget(runtime_panel)

        engine_panel = QFrame()
        engine_panel.setObjectName("panel")
        engine_layout = QVBoxLayout(engine_panel)
        engine_layout.addWidget(QLabel("INPUT ENGINE & KEYMAPPING"))
        self.engine_status = QLabel("Stopped · existing Waydroid bridge route remains active")
        self.engine_status.setWordWrap(True)
        engine_layout.addWidget(self.engine_status)
        self.keyboard_checkbox = QCheckBox("Enable global keyboard capture (optional; reads physical key events)")
        try:
            self.keyboard_checkbox.setChecked(load_settings(self.settings_file)["keyboardCaptureEnabled"])
        except Exception:
            pass
        self.keyboard_checkbox.stateChanged.connect(self.save_keyboard_preference)
        engine_layout.addWidget(self.keyboard_checkbox)
        engine_buttons = QGridLayout()
        engine_buttons.addWidget(self._button("Start touch engine + route phone here", self.start_engine), 0, 0)
        engine_buttons.addWidget(self._button("Stop engine / restore bridge route", self.stop_engine), 0, 1)
        engine_buttons.addWidget(self._button("Open mapping overlay editor", self.open_overlay), 1, 0)
        engine_buttons.addWidget(self._button("Open profile JSON", self.open_profile), 1, 1)
        engine_layout.addLayout(engine_buttons)
        help_label = QLabel("Phone events still arrive at PC UDP 28741. The host relay uses loopback UDP 28743 for this engine. Routes are exclusive: Bridge or Emulator, never both.")
        help_label.setObjectName("muted")
        help_label.setWordWrap(True)
        engine_layout.addWidget(help_label)
        layout.addWidget(engine_panel)

        update_panel = QFrame()
        update_panel.setObjectName("panel")
        update_layout = QVBoxLayout(update_panel)
        update_layout.addWidget(QLabel("EMULATOR TOOLS AUTO-UPDATER"))
        self.update_status = QLabel(f"Installed version: {VERSION}. Checking GitHub releases automatically on startup.")
        self.update_status.setWordWrap(True)
        update_layout.addWidget(self.update_status)
        self.update_progress = QProgressBar()
        self.update_progress.setRange(0, 100)
        self.update_progress.setValue(0)
        self.update_progress.setVisible(False)
        update_layout.addWidget(self.update_progress)
        update_buttons = QHBoxLayout()
        update_buttons.addWidget(self._button("Check for updates", lambda: self.check_updates(automatic=False)))
        update_buttons.addWidget(self._button("Open GitHub release page", lambda: _open_url(REPO_URL + "/releases")))
        update_buttons.addWidget(self._button("README / architecture", lambda: _open_url(REPO_URL + "/tree/main/emulator")))
        update_layout.addLayout(update_buttons)
        layout.addWidget(update_panel)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(90)
        self.log.setPlainText(
            "Safety notes:\n"
            "• The emulator route needs /dev/uinput access. The daemon itself runs as your user, never as root.\n"
            "• No memory hooks, code injection, automated gameplay loops, or anti-cheat bypass are included.\n"
            "• Input routing needs testing on your exact Wayland session and Android target window."
        )
        layout.addWidget(self.log)
        self.setCentralWidget(root)
        self.refresh_runtime_status()

    def _set_route(self, route: str) -> None:
        current = load_settings(self.settings_file)
        current["route"] = route
        save_json_atomic(self.settings_file, current)

    def save_keyboard_preference(self, _state: int = 0) -> None:
        try:
            current = load_settings(self.settings_file)
            current["keyboardCaptureEnabled"] = self.keyboard_checkbox.isChecked()
            save_json_atomic(self.settings_file, current)
        except Exception as exc:
            QMessageBox.warning(self, "Cannot save setting", str(exc))

    def refresh_runtime_status(self) -> None:
        if not shutil.which("waydroid"):
            self.runtime_status.setText("Waydroid CLI not found. On Bazzite, start with: ujust configure-waydroid. This launcher does not install system packages or change your GNOME desktop.")
            return
        try:
            proc = subprocess.run(["waydroid", "status"], capture_output=True, text=True, timeout=2, check=False)
            self.runtime_status.setText(proc.stdout.strip() or proc.stderr.strip() or "Waydroid is installed; status output was empty.")
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.runtime_status.setText(f"Waydroid status could not be queried: {exc}")

    def open_waydroid(self) -> None:
        launcher = shutil.which("waydroid-launcher")
        command = [launcher] if launcher else (["waydroid", "show-full-ui"] if shutil.which("waydroid") else [])
        if not command:
            QMessageBox.information(self, "Waydroid is not installed", "Use the Bazzite runtime setup guide. The launcher will not rpm-ostree-layer packages for you.")
            return
        try:
            subprocess.Popen(command, start_new_session=True)
        except OSError as exc:
            QMessageBox.warning(self, "Could not open Waydroid", str(exc))

    def start_engine(self) -> None:
        if self.engine and self.engine.poll() is None:
            QMessageBox.information(self, "Already running", "The input engine is already running.")
            return
        profile = load_profile(self.profile_file)
        self.engine_log_path.parent.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, str(self.module_dir / "input_engine.py"),
                   "--profile", str(self.profile_file), "--settings", str(self.settings_file)]
        if self.keyboard_checkbox.isChecked():
            command.append("--capture-keyboard")
        try:
            log_stream = self.engine_log_path.open("ab")
            self.engine = subprocess.Popen(command, cwd=str(self.module_dir), stdout=log_stream,
                                           stderr=subprocess.STDOUT, start_new_session=True)
            # Let /dev/uinput/device permission or configuration errors surface before changing the route.
            time.sleep(0.35)
            if self.engine.poll() is not None:
                log_stream.close()
                tail = self._engine_log_tail()
                QMessageBox.warning(self, "Input engine failed to start",
                                    "No route change was made. Check /dev/uinput permissions and screen calibration.\n\n" + tail)
                self.engine = None
                return
            self._set_route("emulator")
            self.engine_status.setText("Running · phone events are routed to the local uinput engine")
            self.update_status.setText(f"Engine started with profile {profile['name']!r}.")
        except Exception as exc:
            self._set_route("bridge")
            QMessageBox.warning(self, "Could not start input engine", str(exc))

    def _engine_log_tail(self) -> str:
        try:
            lines = self.engine_log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            return "\n".join(lines[-12:])
        except OSError:
            return "No input-engine log is available yet."

    def stop_engine(self) -> None:
        # Switch routing first. The running host reads settings for every controller event.
        try:
            self._set_route("bridge")
        except Exception:
            pass
        process, self.engine = self.engine, None
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                process.kill()
        self.engine_status.setText("Stopped · phone events route to the existing Waydroid bridge")
        self.refresh_process_status()

    def open_overlay(self) -> None:
        if self.overlay and self.overlay.poll() is None:
            QMessageBox.information(self, "Overlay already open", "Switch to the existing overlay window.")
            return
        try:
            self.overlay = subprocess.Popen(
                [sys.executable, str(self.module_dir / "overlay.py"), "--profile", str(self.profile_file)],
                cwd=str(self.module_dir), start_new_session=True
            )
            self.statusBar().showMessage("Overlay opened. Use Edit/Play mode to switch between grabbing mouse input and pass-through.", 6000)
        except OSError as exc:
            QMessageBox.warning(self, "Could not start overlay", str(exc))

    def open_profile(self) -> None:
        if sys.platform.startswith("linux"):
            try:
                subprocess.Popen(["xdg-open", str(self.profile_file)], start_new_session=True)
            except OSError as exc:
                QMessageBox.warning(self, "Could not open profile", str(exc))

    def refresh_process_status(self) -> None:
        if self.engine and self.engine.poll() is not None:
            exit_code = self.engine.returncode
            self.engine = None
            try:
                self._set_route("bridge")
            except Exception:
                pass
            self.engine_status.setText(f"Engine stopped unexpectedly (exit {exit_code}); controller route reset to bridge.")
            self.log.append("Input engine exited. Last log lines:\n" + self._engine_log_tail())
        elif self.engine and self.engine.poll() is None:
            try:
                mode = load_settings(self.settings_file)["route"]
            except Exception:
                mode = "unknown"
            self.engine_status.setText(f"Engine running · controller route = {mode} · loopback port 28743")
        if self.overlay and self.overlay.poll() is not None:
            self.overlay = None

    def check_updates(self, automatic: bool) -> None:
        if self.check_worker and self.check_worker.isRunning():
            return
        self.update_status.setText("Checking the public emulator update manifest…")
        self.check_worker = CheckUpdateWorker(self)
        self.check_worker.completed.connect(lambda result: self._update_check_result(result, automatic))
        self.check_worker.failed.connect(lambda error: self._update_check_failed(error, automatic))
        self.check_worker.start()

    def _update_check_result(self, manifest: object, automatic: bool) -> None:
        if not manifest:
            self.update_status.setText(f"Emulator Tools v{VERSION} is up to date.")
            if not automatic:
                QMessageBox.information(self, "No update available", f"You are running emulator tools v{VERSION}.")
            return
        if not isinstance(manifest, dict):
            return
        self.pending_manifest = manifest
        version = str(manifest.get("version", ""))
        self.update_status.setText(f"Update v{version} is available. Download will be SHA-256 checked and installed only to your user data directory.")
        answer = QMessageBox.question(
            self, f"Install Emulator Tools v{version}?",
            f"Download and install MLBB Link Emulator Tools v{version}?\n\n"
            "The archive checksum is verified before any files are replaced. This updates the Linux companion only; it does not upgrade Android images or Google Play Services.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.install_update(manifest)

    def _update_check_failed(self, error: str, automatic: bool) -> None:
        self.update_status.setText("Could not check for updates. Existing controls remain available.")
        if not automatic:
            QMessageBox.warning(self, "Update check failed", error)

    def install_update(self, manifest: dict[str, Any]) -> None:
        if self.install_worker and self.install_worker.isRunning():
            return
        self.update_progress.setVisible(True)
        self.update_progress.setValue(0)
        self.install_worker = InstallUpdateWorker(manifest, self.install_root)
        self.install_worker.progressChanged.connect(self.update_progress.setValue)
        self.install_worker.completed.connect(self._update_installed)
        self.install_worker.failed.connect(self._update_failed)
        self.install_worker.start()

    def _update_installed(self, version: str) -> None:
        self.update_progress.setVisible(False)
        self.update_status.setText(f"Updated files to v{version}. Restart Emulator Tools to run the new code.")
        QMessageBox.information(self, "Update installed", f"MLBB Link Emulator Tools v{version} is installed.\n\nClose and reopen the app to load the new version.")

    def _update_failed(self, error: str) -> None:
        self.update_progress.setVisible(False)
        self.update_status.setText("Update failed; the installed version was kept.")
        QMessageBox.warning(self, "Update failed", error)

    def closeEvent(self, event: Any) -> None:
        self.stop_engine()
        overlay, self.overlay = self.overlay, None
        if overlay and overlay.poll() is None:
            overlay.terminate()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setOrganizationName("AndrewHorrison")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
