"""Authoring layouts use the same palette and inherited fonts as Classic."""
from editor.classic_theme import COLORS

STYLE = f"""
QWidget#Panel {{ background:{COLORS['bg_alt']};border:1px solid {COLORS['border']}; }}
QLabel#PanelTitle {{ background:{COLORS['bg_light']};padding:8px;font-weight:600; }}
QSlider::groove:vertical {{ background:{COLORS['bg_dark']};width:6px;border-radius:3px; }}
QSlider::handle:vertical {{ background:{COLORS['accent']};height:15px;margin:0 -10px;border:1px solid {COLORS['border']}; }}
"""


def apply(dialog):
    dialog.setStyleSheet(STYLE)
