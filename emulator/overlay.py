#!/usr/bin/env python3
"""Transparent desktop editor / click-through overlay for MLBB Link key mappings."""
from __future__ import annotations

import argparse
import json
import socket
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPen, QGuiApplication, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget

from profiles import load_profile, profile_path, save_profile, settings_path, user_config_dir

ACCENT = QColor(255, 207, 100)
CYAN = QColor(106, 224, 255)
WHITE = QColor(238, 246, 252)
PANEL = "background:rgba(9,18,29,232); color:#edf6fc; border:1px solid #3f5d70; border-radius:8px; padding:6px 10px;"
BUTTON = "QPushButton{background:#1b2e40;color:#eaf5fb;border:1px solid #476579;border-radius:7px;padding:7px 10px;font-weight:600;} QPushButton:hover{background:#2a4960;} QPushButton:disabled{color:#7f929e;}"
MAPPING_LABEL = {"skill": "SKILL", "joystick": "MOVE", "tap": "TAP"}


def point_for(mapping: dict[str, Any], rect: dict[str, int]) -> QPointF:
    return QPointF(rect["x"] + mapping["x"] * rect["width"],
                   rect["y"] + mapping["y"] * rect["height"])


class Overlay(QMainWindow):
    def __init__(self, profile_file: Path) -> None:
        super().__init__()
        self.profile_file = profile_file
        self.profile = load_profile(profile_file)
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            raise RuntimeError("No primary desktop display was found")
        self.desktop = screen.geometry()
        self.setGeometry(self.desktop)
        self.setWindowTitle("MLBB Link Keymapping Overlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.edit_mode = True
        self.calibrating = False
        self.calibration_start: QPoint | None = None
        self.calibration_end: QPoint | None = None
        self.dragging_id: str | None = None
        self.drag_offset = QPointF(0, 0)
        self.selected_id = self.profile["mappings"][0]["id"] if self.profile["mappings"] else None
        self.last_error = ""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._build_toolbar()
        self._apply_window_mode()

    def _build_toolbar(self) -> None:
        toolbar = QFrame(self)
        toolbar.setObjectName("toolbar")
        toolbar.setStyleSheet(PANEL + "QFrame#toolbar{background:rgba(9,18,29,230);}")
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(6)
        self.status = QLabel("EDIT MODE · drag a control, use Size − / Size +, then Save")
        self.status.setStyleSheet("color:#bdefff; border:0;")
        self.status.setMinimumWidth(290)
        layout.addWidget(self.status)
        self.mode_button = self._add_button(layout, "Play / Click-through", self.toggle_mode)
        self._add_button(layout, "Add", self.add_mapping)
        self._add_button(layout, "Delete", self.delete_mapping)
        self._add_button(layout, "Size −", lambda: self.resize_selected(-0.01))
        self._add_button(layout, "Size +", lambda: self.resize_selected(0.01))
        self._add_button(layout, "Calibrate target", self.toggle_calibration)
        self._add_button(layout, "Save", self.save_now)
        self._add_button(layout, "Quit", self.close)
        toolbar.adjustSize()
        toolbar.move(max(8, (self.desktop.width() - toolbar.sizeHint().width()) // 2), 12)
        self.toolbar = toolbar
        self.toolbar.raise_()

    def _add_button(self, layout: QHBoxLayout, label: str, callback: Any) -> QPushButton:
        button = QPushButton(label)
        button.setStyleSheet(BUTTON)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def _apply_window_mode(self) -> None:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        if not self.edit_mode:
            transparent_flag = getattr(Qt.WindowType, "WindowTransparentForInput", None)
            if transparent_flag is not None:
                flags |= transparent_flag
            else:
                self.status.setText("Pass-through is not supported by this Qt backend")
        self.setWindowFlags(flags)
        self.setGeometry(self.desktop)
        self.show()
        self.toolbar.setVisible(self.edit_mode)
        self.toolbar.raise_()
        self.update()

    def toggle_mode(self) -> None:
        if self.edit_mode:
            self.save_now()
            self.edit_mode = False
            self.calibrating = False
            self.status.setText("PLAY MODE · input passes through when the compositor supports it")
        else:
            self.edit_mode = True
            self.status.setText("EDIT MODE · drag a control, use Size − / Size +, then Save")
        self.mode_button.setText("Play / Click-through" if self.edit_mode else "Edit mappings")
        self._apply_window_mode()

    def _selected(self) -> dict[str, Any] | None:
        return next((m for m in self.profile["mappings"] if m["id"] == self.selected_id), None)

    def add_mapping(self) -> None:
        if not self.edit_mode:
            return
        base = "control"
        existing = {m["id"] for m in self.profile["mappings"]}
        index = 1
        while f"{base}_{index}" in existing:
            index += 1
        identifier = f"{base}_{index}"
        self.profile["mappings"].append({
            "id": identifier, "label": f"Control {index}", "kind": "tap",
            "buttonNames": [identifier], "key": "", "x": 0.5, "y": 0.5,
            "radius": 0.05, "deadzone": 0.0, "enabled": True
        })
        self.selected_id = identifier
        self.status.setText(f"Added {identifier} · position it and edit profile.json for a key/name binding")
        self.update()

    def delete_mapping(self) -> None:
        if not self.edit_mode:
            return
        if len(self.profile["mappings"]) <= 1:
            self.status.setText("At least one mapping must remain")
            return
        selected = self._selected()
        if selected is None:
            return
        self.profile["mappings"] = [m for m in self.profile["mappings"] if m["id"] != selected["id"]]
        self.selected_id = self.profile["mappings"][0]["id"]
        self.status.setText("Mapping deleted · Save to keep the change")
        self.update()

    def resize_selected(self, amount: float) -> None:
        if not self.edit_mode:
            return
        selected = self._selected()
        if selected is None:
            return
        selected["radius"] = round(max(0.005, min(0.35, selected["radius"] + amount)), 3)
        self.status.setText(f"{selected['label']} size: {selected['radius']:.3f} of target short edge")
        self.update()

    def toggle_calibration(self) -> None:
        if not self.edit_mode:
            return
        self.calibrating = not self.calibrating
        self.calibration_start = self.calibration_end = None
        self.setCursor(Qt.CursorShape.CrossCursor if self.calibrating else Qt.CursorShape.ArrowCursor)
        self.status.setText("Drag a rectangle around the Android display area" if self.calibrating else "Calibration cancelled")
        self.update()

    def save_now(self) -> None:
        try:
            self.profile = save_profile(self.profile, self.profile_file)
            self.status.setText(f"Saved mapping profile: {self.profile_file}")
        except Exception as exc:
            self.last_error = str(exc)
            self.status.setText("Save failed: " + str(exc)[:90])
        self.update()

    def _target_rect(self) -> dict[str, int]:
        return self.profile["screen"]["targetRect"]

    def _to_profile(self, point: QPointF) -> tuple[float, float]:
        rect = self._target_rect()
        x = (point.x() - rect["x"]) / max(1, rect["width"])
        y = (point.y() - rect["y"]) / max(1, rect["height"])
        return max(0.0, min(1.0, x)), max(0.0, min(1.0, y))

    def _hit_control(self, point: QPointF) -> dict[str, Any] | None:
        rect = self._target_rect()
        for mapping in reversed(self.profile["mappings"]):
            centre = point_for(mapping, rect)
            radius = max(18.0, float(mapping.get("radius", 0.05)) * min(rect["width"], rect["height"]) * 0.75)
            if math_distance(point, centre) <= radius:
                return mapping
        return None

    def paintEvent(self, _event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        target = self._target_rect()
        target_box = QRectF(target["x"], target["y"], target["width"], target["height"])
        painter.setPen(QPen(QColor(106, 224, 255, 180), 2, Qt.PenStyle.DashLine))
        painter.setBrush(QColor(10, 24, 36, 18 if self.edit_mode else 0))
        painter.drawRoundedRect(target_box, 8, 8)
        painter.setFont(QFont("Sans Serif", 10, QFont.Weight.DemiBold))
        painter.setPen(QPen(QColor(170, 230, 248, 210), 1))
        painter.drawText(target_box.adjusted(8, 5, -8, -5), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                         "ANDROID TARGET AREA · calibrate this box to the Android window")
        for mapping in self.profile["mappings"]:
            if not mapping.get("enabled", True):
                continue
            centre = point_for(mapping, target)
            radius = max(14.0, min(75.0, float(mapping.get("radius", 0.05)) * min(target["width"], target["height"]) * 0.55))
            selected = mapping["id"] == self.selected_id
            color = ACCENT if selected else CYAN if mapping["kind"] == "skill" else QColor(133, 209, 169)
            painter.setPen(QPen(color, 3 if selected else 2))
            painter.setBrush(QColor(color.red(), color.green(), color.blue(), 64 if self.edit_mode else 28))
            painter.drawEllipse(centre, radius, radius)
            painter.setPen(QPen(WHITE, 1))
            painter.setFont(QFont("Sans Serif", 10, QFont.Weight.Bold))
            painter.drawText(QRectF(centre.x() - radius - 20, centre.y() - 11, 2 * radius + 40, 22),
                             Qt.AlignmentFlag.AlignCenter, mapping["label"][:18])
            key = mapping.get("key", "")
            if key:
                painter.setFont(QFont("Sans Serif", 9, QFont.Weight.Bold))
                painter.drawText(QRectF(centre.x() - 18, centre.y() + radius + 2, 36, 18),
                                 Qt.AlignmentFlag.AlignCenter, key)
            if mapping["kind"] in ("joystick", "skill"):
                painter.setPen(QPen(color, 1, Qt.PenStyle.DotLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(centre, radius * 1.45, radius * 1.45)
        if self.calibrating and self.calibration_start is not None and self.calibration_end is not None:
            box = QRect(self.calibration_start, self.calibration_end).normalized()
            painter.setPen(QPen(ACCENT, 2, Qt.PenStyle.DashLine))
            painter.setBrush(QColor(255, 207, 100, 45))
            painter.drawRect(box)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self.edit_mode or event.button() != Qt.MouseButton.LeftButton:
            return
        position = event.position()
        if self.calibrating:
            self.calibration_start = position.toPoint()
            self.calibration_end = position.toPoint()
            self.update()
            return
        node = self._hit_control(position)
        if node is not None:
            self.selected_id = node["id"]
            self.dragging_id = node["id"]
            self.drag_offset = position - point_for(node, self._target_rect())
            self.update()
            return
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.calibrating and self.calibration_start is not None:
            self.calibration_end = event.position().toPoint()
            self.update()
            return
        if not self.edit_mode or not self.dragging_id:
            return
        mapping = self._selected()
        if mapping is None:
            return
        logical = event.position() - self.drag_offset
        mapping["x"], mapping["y"] = self._to_profile(logical)
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.calibrating and self.calibration_start is not None:
            end = event.position().toPoint()
            left, right = sorted((self.calibration_start.x(), end.x()))
            top, bottom = sorted((self.calibration_start.y(), end.y()))
            width, height = right - left, bottom - top
            if width >= 160 and height >= 120:
                self.profile["screen"]["width"] = self.desktop.width()
                self.profile["screen"]["height"] = self.desktop.height()
                self.profile["screen"]["targetRect"] = {"x": left, "y": top, "width": width, "height": height}
                self.status.setText(f"Target rectangle set to {width}×{height} at ({left},{top}) · Save and restart engine")
            else:
                self.status.setText("Target area too small; drag a larger rectangle")
            self.calibrating = False
            self.calibration_start = self.calibration_end = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.update()
            return
        self.dragging_id = None
        self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if not self.edit_mode:
            return
        amount = 0.005 if event.angleDelta().y() > 0 else -0.005
        node = self._hit_control(event.position())
        if node is not None:
            self.selected_id = node["id"]
            self.resize_selected(amount)
            event.accept()

    def keyPressEvent(self, event: Any) -> None:
        if event.key() == Qt.Key.Key_Escape and self.edit_mode:
            self.calibrating = False
            self.calibration_start = self.calibration_end = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.update()
            return
        if not self.edit_mode and event.isAutoRepeat() is False:
            name = event.text().strip().upper()
            if name:
                self.socket.sendto(json.dumps({"type": "key", "name": name, "state": "down"}).encode(),
                                   ("127.0.0.1", 28743))
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: Any) -> None:
        if not self.edit_mode and not event.isAutoRepeat():
            name = event.text().strip().upper()
            if name:
                self.socket.sendto(json.dumps({"type": "key", "name": name, "state": "up"}).encode(),
                                   ("127.0.0.1", 28743))
        super().keyReleaseEvent(event)

    def closeEvent(self, event: Any) -> None:
        try:
            self.save_now()
            self.socket.close()
        finally:
            super().closeEvent(event)


def math_distance(a: QPointF, b: QPointF) -> float:
    return ((a.x() - b.x()) ** 2 + (a.y() - b.y()) ** 2) ** 0.5


def main() -> int:
    parser = argparse.ArgumentParser(description="MLBB Link transparent keymapping overlay")
    parser.add_argument("--profile", default=str(profile_path()))
    parser.add_argument("--version", action="version", version="MLBB Link Overlay 0.15.0")
    args = parser.parse_args()
    app = QApplication(sys.argv)
    try:
        overlay = Overlay(Path(args.profile).expanduser())
        overlay.show()
        return app.exec()
    except Exception as exc:
        print(f"MLBB Link overlay error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
