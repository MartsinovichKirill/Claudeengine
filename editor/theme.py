"""QSS-тема редактора в стиле Godot 4 (тёмная).

Основные цвета:
- фон          #1b2633 / #223140
- акцент       #478cbf
- текст        #dce5ee
"""

from __future__ import annotations

from typing import Any

#: Основная палитра.
COLORS = {
    "bg": "#202329",
    "bg_alt": "#282c34",
    "bg_dark": "#191c22",
    "bg_light": "#343b46",
    "accent": "#538db9",
    "accent_dark": "#3d78a8",
    "text": "#e1e6ee",
    "text_dim": "#a0aab9",
    "border": "#373e49",
    "error": "#d9534f",
    "warning": "#e0a800",
    "info": "#4e9bd1",
    "selection": "#294d6b",
}

#: Таблица стилей Qt (QSS).
STYLESHEET = f"""
* {{
    outline: none;
}}
QWidget {{
    background-color: {COLORS["bg"]};
    color: {COLORS["text"]};
    font-family: "Segoe UI", "Noto Sans", sans-serif;
    font-size: 13px;
}}
QMainWindow, QDialog {{
    background-color: {COLORS["bg"]};
}}
QMenuBar {{
    background-color: {COLORS["bg_dark"]};
    border-bottom: 1px solid {COLORS["border"]};
    padding: 2px;
}}
QMenuBar::item {{
    background: transparent;
    padding: 4px 10px;
    border-radius: 6px;
}}
QMenuBar::item:selected {{
    background-color: {COLORS["bg_alt"]};
}}
QMenu {{
    background-color: {COLORS["bg_alt"]};
    border: 1px solid {COLORS["border"]};
}}
QMenu::item {{
    padding: 5px 24px 5px 20px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background-color: {COLORS["accent"]};
    color: white;
}}
QMenu::separator {{
    height: 1px;
    background-color: {COLORS["border"]};
    margin: 4px 8px;
}}
QToolBar {{
    background-color: {COLORS["bg_dark"]};
    border: none;
    border-bottom: 1px solid {COLORS["border"]};
    padding: 3px;
    spacing: 2px;
}}
QToolButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 4px 8px;
    color: {COLORS["text"]};
}}
QToolButton:hover {{
    background-color: {COLORS["bg_alt"]};
}}
QToolButton:pressed {{
    background-color: {COLORS["accent_dark"]};
}}
QToolButton:checked {{
    background-color: {COLORS["accent"]};
    color: white;
}}
QDockWidget {{
    color: {COLORS["text"]};
}}
QDockWidget::title {{
    background-color: {COLORS["bg_dark"]};
    padding: 5px 8px;
    border-bottom: 1px solid {COLORS["border"]};
    text-align: left;
}}
QTabWidget::pane {{
    border: 1px solid {COLORS["border"]};
    background-color: {COLORS["bg"]};
}}
QTabBar::tab {{
    background-color: {COLORS["bg_dark"]};
    border: 1px solid {COLORS["border"]};
    padding: 5px 12px;
    margin-right: 1px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}
QTabBar::tab:selected {{
    background-color: {COLORS["bg_alt"]};
    border-bottom-color: {COLORS["bg_alt"]};
}}
QTabBar::tab:hover {{
    background-color: {COLORS["bg_light"]};
}}
QTreeWidget, QTreeView, QListWidget, QListView {{
    background-color: {COLORS["bg"]};
    border: none;
    alternate-background-color: {COLORS["bg_dark"]};
}}
QTreeWidget::item, QTreeView::item {{
    padding: 5px 7px;
    border-radius: 6px;
}}
QTreeWidget::item:selected, QTreeView::item:selected {{
    background-color: {COLORS["selection"]};
    color: white;
}}
QTreeWidget::item:hover, QTreeView::item:hover {{
    background-color: {COLORS["bg_light"]};
}}
QSplitter::handle {{
    background-color: {COLORS["border"]};
}}
QScrollBar:vertical {{
    background: {COLORS["bg_dark"]};
    width: 9px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {COLORS["bg_light"]};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar:horizontal {{
    background: {COLORS["bg_dark"]};
    height: 9px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {COLORS["bg_light"]};
    border-radius: 5px;
    min-width: 24px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0;
    height: 0;
}}
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {COLORS["bg_dark"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    padding: 5px 8px;
    selection-background-color: {COLORS["accent"]};
}}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {COLORS["accent"]};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: {COLORS["bg_alt"]};
    border: 1px solid {COLORS["border"]};
    selection-background-color: {COLORS["accent"]};
}}
QPushButton {{
    background-color: {COLORS["bg_alt"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    padding: 5px 14px;
}}
QPushButton:hover {{
    background-color: {COLORS["bg_light"]};
}}
QPushButton:pressed {{
    background-color: {COLORS["accent_dark"]};
}}
QPushButton:disabled {{
    color: {COLORS["text_dim"]};
}}
QCheckBox {{
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    background-color: {COLORS["bg_dark"]};
}}
QCheckBox::indicator:checked {{
    background-color: {COLORS["accent"]};
    border-color: {COLORS["accent"]};
}}
QLabel {{
    color: {COLORS["text"]};
    background: transparent;
}}
QStatusBar {{
    background-color: {COLORS["bg_dark"]};
    border-top: 1px solid {COLORS["border"]};
}}
QToolTip {{
    background-color: {COLORS["bg_alt"]};
    color: {COLORS["text"]};
    border: 1px solid {COLORS["border"]};
}}
QHeaderView::section {{
    background-color: {COLORS["bg_dark"]};
    border: none;
    border-right: 1px solid {COLORS["border"]};
    border-bottom: 1px solid {COLORS["border"]};
    padding: 4px 6px;
}}
QGroupBox {{
    border: 1px solid {COLORS["border"]};
    border-radius: 7px;
    margin-top: 8px;
    padding-top: 6px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: {COLORS["text_dim"]};
}}
QProgressBar {{
    background-color: {COLORS["bg_dark"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 6px;
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {COLORS["accent"]};
}}
"""


def apply_theme(app: Any) -> None:
    """Применяет QSS-тему к приложению."""
    from editor.appearance import apply_application_theme
    apply_application_theme(app)


REFINEMENTS = """
QMainWindow::separator { background:#18222d; width:5px; height:5px; }
QMainWindow::separator:hover { background:#537d9e; }
QToolBar { padding:7px 10px; spacing:4px; }
QToolBar#SceneToolsBar { background:#1c2a37; padding:5px 10px; border-bottom:1px solid #35495b; }
QToolBar::separator { background:#354657; width:1px; margin:7px 9px; }
QToolButton { min-width:20px; min-height:20px; }
QToolButton:checked { background:#2c536f; border:1px solid #5084a8; }
QDockWidget::title { padding:9px 12px; font-weight:600; color:#aec1d3; }
QGroupBox { background:#223140; border:1px solid #35495b; margin-top:15px; padding:12px 8px 8px; }
QGroupBox QWidget { background:transparent; }
QGroupBox QLineEdit, QGroupBox QSpinBox, QGroupBox QDoubleSpinBox, QGroupBox QComboBox { background:#182430; }
QGroupBox#ComponentCard { margin-top:0; padding:0; border-radius:10px; }
QGroupBox::title { color:#b7cddd; font-weight:600; left:12px; }
QPushButton { padding:8px 14px; border-color:#3b5063; }
QPushButton[primary="true"] { background:#396f97; border-color:#538cb5; color:#f1f7fc; font-weight:600; }
QPushButton[primary="true"]:hover { background:#437fa9; }
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover { border-color:#506a80; }
QTabBar::tab { padding:8px 15px; color:#93aabe; }
QTabBar::tab:selected { color:#e2edf7; border-top:2px solid #72a8cc; }
QListWidget::item { padding:12px; border-radius:7px; margin:3px; }
QListWidget::item:selected { background:#294d6b; }
QScrollArea { border:none; }
QTableWidget { background:#1b2633; gridline-color:#304151; border:1px solid #304151; }
QTableWidget::item { padding:6px; }
QToolTip { padding:8px; border-radius:5px; }
QFrame#HubCard { background:#223140; border:1px solid #35495b; border-radius:12px; }
QFrame#HubCard QLabel { background:transparent; }
QLabel#SectionTitle { font-size:17px; font-weight:600; color:#d7e6f2; }
QLabel#SecondaryText { color:#96adbf; }
"""

REFINEMENTS += """
QMainWindow::separator { background:#15181d; width:4px; height:4px; }
QMenuBar, QStatusBar, QToolBar { background:#1b1e24; }
QMenuBar::item { padding:6px 10px; border-radius:3px; }
QToolBar#SceneToolsBar { background:#242932; border-bottom:1px solid #373e49; }
QToolButton { border-radius:4px; }
QToolButton:checked { background:#30465a; border:1px solid #6086a6; }
QDockWidget::title { background:#252a32; padding:8px 11px; color:#c4ccd7; font-weight:600; }
QGroupBox { background:#272c34; border:1px solid #3b424e; border-radius:5px; padding:12px 8px 8px; }
QGroupBox#ComponentCard { background:#262b33; border-radius:6px; }
QGroupBox::title { color:#bcc7d5; }
QPushButton { background:#303742; border:1px solid #454e5b; border-radius:4px; padding:7px 12px; }
QPushButton:hover { background:#3a4553; border-color:#667c92; }
QPushButton:pressed { background:#263747; }
QPushButton:disabled { background:#252930; color:#6e7887; border-color:#333b45; }
QPushButton[primary="true"] { background:#416e91; border-color:#6591b3; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background:#1b1f26; border:1px solid #3c4552; border-radius:4px; padding:5px 7px; min-height:19px; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color:#78a3c5; }
QGroupBox QLineEdit, QGroupBox QSpinBox, QGroupBox QDoubleSpinBox, QGroupBox QComboBox { background:#1b1f26; }
QTabWidget::pane { border:1px solid #3a424e; }
QTabBar::tab { background:#22262e; padding:7px 13px; border-radius:0; }
QTabBar::tab:selected { background:#2c333e; color:#edf2f8; border-top:2px solid #7fa8c8; }
QHeaderView::section { background:#2b313b; padding:7px; border:0; border-right:1px solid #3b4451; color:#b9c5d4; }
QTableWidget, QTreeWidget, QListWidget { background:#1d2128; alternate-background-color:#252b34; gridline-color:#353e4a; border:1px solid #353e4a; }
QListWidget::item { padding:8px 10px; border-radius:4px; margin:2px; }
QTableWidget::item:selected, QTreeWidget::item:selected, QListWidget::item:selected { background:#344e65; color:#f2f5fa; }
QCheckBox::indicator { width:14px; height:14px; border-radius:3px; }
QScrollBar:vertical { width:10px; background:#1b1f25; }
QScrollBar::handle:vertical { background:#485564; border-radius:4px; min-height:28px; }
QSplitter::handle { background:#15191f; }
QLabel#SectionTitle { font-size:18px; font-weight:600; color:#edf2f8; }
QLabel#SecondaryText { color:#a3afbe; }
"""
