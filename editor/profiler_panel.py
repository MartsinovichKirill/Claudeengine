"""ProfilerPanel — панель профилировщика в редакторе.

Показывает FPS, время кадра, график FPS, замеры по системам движка
и счётчики (ноды, компоненты, эффекты). Данные берутся из глобального
профилировщика ``engine.core.profiler.profiler``.
"""

from __future__ import annotations

from typing import Any, Dict, List

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPolygonF
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QGroupBox, QGridLayout)

from engine.core.profiler import profiler
from editor.icons import get_icon


class FpsGraph(QWidget):
    """Небольшой график FPS и времени кадра."""

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(90)
        self.values: List[float] = []
        self.target_fps: float = 60.0

    def set_values(self, values: List[float]) -> None:
        self.values = list(values)[-120:]
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#121216"))
        width = max(self.width(), 1)
        height = max(self.height(), 1)

        # Сетка по 30 и 60 FPS.
        painter.setPen(QPen(QColor("#24242c"), 1))
        for fraction in (0.25, 0.5, 0.75):
            y = int(height * fraction)
            painter.drawLine(0, y, width, y)

        if len(self.values) < 2:
            painter.setPen(QColor("#66666f"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "нет данных — запустите игру (F5)")
            return

        peak = max(max(self.values), self.target_fps) * 1.1
        step = width / max(len(self.values) - 1, 1)
        points = QPolygonF()
        for index, value in enumerate(self.values):
            x = index * step
            y = height - min(value / peak, 1.0) * height
            points.append(QPointF(x, y))

        fill = QPolygonF(points)
        fill.append(QPointF(width, height))
        fill.append(QPointF(0, height))
        painter.setBrush(QBrush(QColor(71, 140, 191, 60)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(fill)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#478cbf"), 2))
        painter.drawPolyline(points)

        # Линия целевого FPS.
        target_y = height - min(self.target_fps / peak, 1.0) * height
        painter.setPen(QPen(QColor(107, 191, 107, 120), 1, Qt.PenStyle.DashLine))
        painter.drawLine(0, int(target_y), width, int(target_y))


class ProfilerPanel(QWidget):
    """Панель профилировщика."""

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.paused: bool = False
        self._build()
        self._timer = QTimer(self)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    # ------------------------------------------------------------------
    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # --- Заголовок с FPS ---
        top = QHBoxLayout()
        self.fps_label = QLabel("0.0")
        font = QFont()
        font.setPointSize(26)
        font.setBold(True)
        self.fps_label.setFont(font)
        self.fps_label.setStyleSheet("color:#6bbf6b;")
        top.addWidget(self.fps_label)

        info = QVBoxLayout()
        self.frame_label = QLabel("кадр — мс")
        self.range_label = QLabel("мин — / макс —")
        self.range_label.setStyleSheet("color:#8c8c99;font-size:11px;")
        info.addWidget(self.frame_label)
        info.addWidget(self.range_label)
        top.addLayout(info)
        top.addStretch(1)

        self.pause_button = QPushButton("Пауза")
        self.pause_button.setIcon(get_icon("pause"))
        self.pause_button.setCheckable(True)
        self.pause_button.toggled.connect(self._on_pause)
        top.addWidget(self.pause_button)

        reset_button = QPushButton("Сброс")
        reset_button.setIcon(get_icon("undo"))
        reset_button.clicked.connect(self._on_reset)
        top.addWidget(reset_button)
        layout.addLayout(top)

        # --- График ---
        self.graph = FpsGraph(self)
        layout.addWidget(self.graph)

        # --- Системы ---
        systems_box = QGroupBox("Время по системам, мс")
        systems_layout = QVBoxLayout(systems_box)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Система", "Сейчас", "Среднее", "Максимум"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        systems_layout.addWidget(self.table)
        layout.addWidget(systems_box, 1)

        # --- Счётчики ---
        counters_box = QGroupBox("Счётчики")
        self.counters_layout = QGridLayout(counters_box)
        self.counters_layout.setContentsMargins(10, 8, 10, 8)
        layout.addWidget(counters_box)

        self.status = QLabel("Нажмите F5, чтобы запустить игру и собрать статистику.")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#8c8c99;font-size:11px;")
        layout.addWidget(self.status)

    # ------------------------------------------------------------------
    def _on_pause(self, paused: bool) -> None:
        self.paused = paused
        self.pause_button.setText("Продолжить" if paused else "Пауза")
        profiler.enabled = not paused

    def _on_reset(self) -> None:
        profiler.reset()
        self._refresh()

    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        """Обновляет показания из профилировщика."""
        if self.paused:
            return
        try:
            snapshot = profiler.snapshot()
        except Exception:
            return

        frame = snapshot["frame"]
        self.fps_label.setText(f"{frame['fps']:.1f}")
        color = "#6bbf6b" if frame["fps"] >= 50 else \
            "#e0a800" if frame["fps"] >= 25 else "#e05c5c"
        self.fps_label.setStyleSheet(f"color:{color};")
        self.frame_label.setText(f"кадр {frame['frame_ms']:.2f} мс   "
                                 f"(95%: {frame.get('frame_p95', 0):.2f})")
        self.range_label.setText(f"мин {frame['fps_min']:.1f} / макс {frame['fps_max']:.1f}")

        self.graph.target_fps = float(getattr(profiler, "target_fps", 60.0))
        self.graph.set_values(snapshot["fps_history"])

        systems = snapshot["systems"]
        self.table.setRowCount(len(systems))
        for row, item in enumerate(systems):
            self.table.setItem(row, 0, QTableWidgetItem(item["title"]))
            self.table.setItem(row, 1, QTableWidgetItem(f"{item['last']:.2f}"))
            self.table.setItem(row, 2, QTableWidgetItem(f"{item['avg']:.2f}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{item['max']:.2f}"))

        counters = snapshot["counters"]
        while self.counters_layout.count():
            child = self.counters_layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()
        for index, (name, value) in enumerate(counters.items()):
            label = QLabel(name)
            label.setStyleSheet("color:#8c8c99;font-size:11px;")
            value_label = QLabel(str(value))
            value_label.setStyleSheet("font-weight:600;")
            self.counters_layout.addWidget(label, index // 3, (index % 3) * 2)
            self.counters_layout.addWidget(value_label, index // 3, (index % 3) * 2 + 1)

        if snapshot["frame_count"] == 0:
            self.status.setText("Игра не запущена. Нажмите F5 — статистика появится здесь.")
        else:
            self.status.setText(f"Замеров кадров: {snapshot['frame_count']}. "
                                f"Суммарно по системам: {snapshot['measured_ms']:.2f} мс.")

    # ------------------------------------------------------------------
    def shutdown(self) -> None:
        """Останавливает таймер обновления при закрытии редактора."""
        try:
            self._timer.stop()
        except Exception:
            pass


__all__ = ["ProfilerPanel", "FpsGraph"]
