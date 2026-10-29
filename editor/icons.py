"""Встроенные SVG-иконки Cloud Engine (без внешних файлов).

Иконки рисуются из SVG-строк через QSvgRenderer, поэтому выглядят чётко
на любом DPI. Если модуль QtSvg недоступен — используется запасной
вариант с отрисовкой QPainter.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, Optional

from PyQt6.QtCore import Qt, QRectF, QPointF, QSize
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QBrush, QPixmap, QPolygonF

try:
    from PyQt6.QtSvg import QSvgRenderer
    _HAS_SVG = True
except Exception:  # pragma: no cover
    QSvgRenderer = None  # type: ignore
    _HAS_SVG = False

_ACCENT = QColor("#478cbf")
_LIGHT = QColor("#e0e0e0")

# ======================================================================
# Набор SVG-иконок (viewBox 0 0 24 24, заливка currentColor)
# ======================================================================
_SVG_PATHS: Dict[str, str] = {
    'mob': 'M6 3h3v3h6V3h3v5h3v12h-5v-3H8v3H3V8h3zM6 9v4h4V9zm8 0v4h4V9z',
    # Управление воспроизведением
    "play": "M8 5v14l11-7z",
    "pause": "M6 19h4V5H6v14zm8-14v14h4V5h-4z",
    "stop": "M6 6h12v12H6z",
    "step": "M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z",
    # Файлы
    "save": ("M17 3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V7l-4-4z"
             "m-5 16c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3z"
             "m3-10H5V5h10v4z"),
    "folder": ("M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8"
               "c0-1.1-.9-2-2-2h-8l-2-2z"),
    "file": ("M6 2c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8"
             "l-6-6H6zm7 7V3.5L18.5 9H13z"),
    "image": ("M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14"
              "c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"),
    "audio": "M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z",
    # Правка
    "undo": ("M12.5 8c-2.65 0-5.05.99-6.9 2.6L2 7v9h9l-3.62-3.62c1.39-1.16 3.16-1.88 "
             "5.12-1.88 3.54 0 6.55 2.31 7.6 5.5l2.37-.78C21.08 11.03 17.15 8 12.5 8z"),
    "redo": ("M18.4 10.6C16.55 8.99 14.15 8 11.5 8c-4.65 0-8.58 3.03-9.96 7.22L3.9 16"
             "c1.05-3.19 4.06-5.5 7.6-5.5 1.95 0 3.73.72 5.12 1.88L13 16h9V7l-3.6 3.6z"),
    "add": "M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z",
    "remove": "M19 13H5v-2h14v2z",
    # Рисование по тайлам и выравнивание
    "brush": ("M7 14c-1.66 0-3 1.34-3 3 0 1.31-1.16 2-2 2 .92 1.22 2.49 2 4 2 2.21 0 4-1.79 "
              "4-4 0-1.66-1.34-3-3-3zm13.71-9.37l-1.34-1.34c-.39-.39-1.02-.39-1.41 0L9 12.25 "
              "11.75 15l8.96-8.96c.39-.39.39-1.02 0-1.41z"),
    "eraser": ("M16.24 3.56l4.2 4.2a2 2 0 0 1 0 2.83l-7.6 7.6H20v2H8.5l-4.94-4.94a2 2 0 0 1 "
               "0-2.83l9.85-9.85a2 2 0 0 1 2.83 0zM6.5 15.5l3.5 3.5h1.6l3.5-3.5-3.5-3.5z"),
    "fill": ("M16.56 8.94L7.62 0 6.21 1.41l2.38 2.38-5.15 5.15c-.59.59-.59 1.54 0 2.12l5.5 "
             "5.5c.29.29.68.44 1.06.44s.77-.15 1.06-.44l5.5-5.5c.59-.58.59-1.53 0-2.12zM5.21 "
             "10L10 5.21 14.79 10H5.21zM19 11.5s-2 2.17-2 3.5a2 2 0 1 0 4 0c0-1.33-2-3.5-2-3.5z"),
    "align": ("M3 3h18v2H3V3zm0 16h18v2H3v-2zM3 9h12v2H3V9zm0 6h8v2H3v-2z"),
    "snap": ("M4 4h6v6H4V4zm10 0h6v6h-6V4zM4 14h6v6H4v-6zm10 0h6v6h-6v-6z"),
    "delete": ("M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"),
    "copy": ("M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11"
             "c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2z"),
    "paste": ("M19 2h-4.18C14.4.84 13.3 0 12 0c-1.3 0-2.4.84-2.82 2H5c-1.1 0-2 .9-2 2v16"
              "c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-7 0c.55 0 1 .45 1 1"
              "s-.45 1-1 1-1-.45-1-1 .45-1 1-1zm7 18H5V4h2v3h10V4h2v16z"),
    # Ноды и сцены
    "node": "M22 11V3h-7v3H9V3H2v8h7V8h2v10h4v3h7v-8h-7v3h-2V8h2v3z",
    "scene": '<path fill-rule="evenodd" d="M3 3h18v18H3zm2 2v14h14V5z"/>'
             '<circle cx="12" cy="12" r="3.4"/>',
    "script": "M9.4 16.6L4.8 12l4.6-4.6L8 6l-6 6 6 6 1.4-1.4zm5.2 0l4.6-4.6-4.6-4.6L16 6l6 6-6 6-1.4-1.4z",
    "visual": '<circle cx="5" cy="6" r="2.6"/><circle cx="19" cy="6" r="2.6"/>'
              '<circle cx="12" cy="18" r="2.6"/><path d="M7.4 6h9.2v1.2H7.4z"/>'
              '<path d="M5.6 8.2l5.3 7.8-1 .7-5.3-7.8z"/>'
              '<path d="M18.4 8.2l-5.3 7.8 1 .7 5.3-7.8z"/>',
    "camera": ("M17 10.5V7c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12"
               "c.55 0 1-.45 1-1v-3.5l4 4v-11l-4 4z"),
    "timer": ("M15 1H9v2h6V1zm-4 13h2V8h-2v6zm8.03-6.61l1.42-1.42c-.43-.51-.9-.99-1.41-1.41"
              "l-1.42 1.42A8.962 8.962 0 0 0 12 4a9 9 0 0 0-9 9c0 4.97 4.02 9 9 9"
              "a8.994 8.994 0 0 0 7.03-14.61zM12 20c-3.87 0-7-3.13-7-7s3.13-7 7-7 7 3.13 7 7"
              "-3.13 7-7 7z"),
    # Инструменты (как в Unity)
    "cursor": "M21 3L3 10.53v.98l6.84 2.65L12.48 21h.98L21 3z",
    "hand": ("M23 5.5V20c0 2.2-1.8 4-4 4h-7.3c-1.08 0-2.1-.43-2.85-1.19L1 14.83"
             "s1.26-1.23 1.3-1.25c.22-.19.49-.29.79-.29.22 0 .42.06.6.16.04.01 4.31 2.46 "
             "4.31 2.46V4c0-.83.67-1.5 1.5-1.5S11 3.17 11 4v7h1V1.5c0-.83.67-1.5 1.5-1.5"
             "S15 .67 15 1.5V11h1V2.5c0-.83.67-1.5 1.5-1.5s1.5.67 1.5 1.5V11h1V5.5"
             "c0-.83.67-1.5 1.5-1.5s1.5.67 1.5 1.5z"),
    "move": ("M10 9h4V6h3l-5-5-5 5h3v3zm-1 1H6V7l-5 5 5 5v-3h3v-4zm14 2l-5-5v3h-3v4h3v3l5-5z"
             "m-9 3h-4v3H7l5 5 5-5h-3v-3z"),
    "rotate": ("M15.55 5.55L11 1v3.07C7.06 4.56 4 7.92 4 12s3.05 7.44 7 7.93v-2.02"
               "c-2.84-.48-5-2.94-5-5.91s2.16-5.43 5-5.91V10l4.55-4.45zM19.93 11"
               "a7.906 7.906 0 0 0-1.62-3.89l-1.42 1.42c.54.75.88 1.6 1.02 2.47h2.02z"
               "M13 17.91v2.02c1.39-.22 2.67-.79 3.74-1.59l-1.44-1.44c-.69.53-1.47.9-2.3 1.01z"
               "M17.3 15.89l1.42 1.42a7.9 7.9 0 0 0 1.62-3.89h-2.02c-.14.87-.48 1.72-1.02 2.47z"),
    "scale": ("M19 12h-2v3h-3v2h5v-5zM7 9h3V7H5v5h2V9zm14-6H3c-1.1 0-2 .9-2 2v14"
              "c0 1.1.9 2 2 2h18c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16.01H3V4.99h18v14.02z"),
    "grid": ("M20 2H4c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"
             "M8 20H4v-4h4v4zm0-6H4v-4h4v4zm0-6H4V4h4v4zm6 12h-4v-4h4v4zm0-6h-4v-4h4v4z"
             "m0-6h-4V4h4v4zm6 12h-4v-4h4v4zm0-6h-4v-4h4v4zm0-6h-4V4h4v4z"),
    # Интерфейс
    "settings": ("M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58a.49.49 0 0 0 "
                 ".12-.61l-1.92-3.32a.488.488 0 0 0-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94"
                 "l-.36-2.54a.484.484 0 0 0-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54"
                 "c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87"
                 "c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58"
                 "a.49.49 0 0 0-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94"
                 "l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54"
                 "c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32"
                 "c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 "
                 "3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"),
    "build": ("M22.7 19l-9.1-9.1c.9-2.3.4-5-1.5-6.9-2-2-5-2.4-7.4-1.3L9 6 6 9 1.6 4.7"
              "C.4 7.1.9 10.1 2.9 12.1c1.9 1.9 4.6 2.4 6.9 1.5l9.1 9.1c.4.4 1 .4 1.4 0"
              "l2.3-2.3c.5-.4.5-1.1.1-1.4z"),
    "eye": ("M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5"
            "c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5"
            "-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"),
    "search": ("M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16"
               "c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0"
               "C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"),
    "refresh": ("M17.65 6.35A7.958 7.958 0 0 0 12 4c-4.42 0-7.99 3.58-8 8s3.58 8 8 8"
                "c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0 1 12 18c-3.31 0-6-2.69-6-6"
                "s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"),
    "clear": "M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z",
    "check": "M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z",
    "warning": "M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z",
    "info": "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z",
    "label": "M2.5 4v3h5v12h3V7h5V4h-13zm19 5h-9v3h3v7h3v-7h3V9z",
    "button": ("M19 5H5c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2z"
               "m0 12H5V7h14v10z"),
    "progress": ("M19.5 9.5c-1.03 0-1.9.62-2.29 1.5h-2.92c-.39-.88-1.26-1.5-2.29-1.5"
                 "s-1.9.62-2.29 1.5H6.79c-.39-.88-1.26-1.5-2.29-1.5C3.12 9.5 2 10.62 2 12"
                 "s1.12 2.5 2.5 2.5c1.03 0 1.9-.62 2.29-1.5h2.92c.39.88 1.26 1.5 2.29 1.5"
                 "s1.9-.62 2.29-1.5h2.92c.39.88 1.26 1.5 2.29 1.5 1.38 0 2.5-1.12 2.5-2.5"
                 "s-1.12-2.5-2.5-2.5z"),
    "particles": ("M12 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zM5 9c-1.1 0-2 .9-2 2"
                  "s.9 2 2 2 2-.9 2-2-.9-2-2-2zm14 0c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2"
                  "-.9-2-2-2zm-7 5c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"),
    "physics": ("M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 18a8 8 0 1 1 0-16 8 8 0 0 1 0 16z"
                "m0-13a5 5 0 1 0 0 10 5 5 0 0 0 0-10zm0 8a3 3 0 1 1 0-6 3 3 0 0 1 0 6z"),
    "component": ("M12 2l2.4 4.9 5.4.8-3.9 3.8.9 5.4-4.8-2.5-4.8 2.5.9-5.4L4.2 7.7l5.4-.8z"),
    "tilemap": "M3 3h8v8H3zM13 3h8v8h-8zM3 13h8v8H3zM13 13h8v8h-8z",
    "area": '<path fill-rule="evenodd" d="M3 3h18v18H3zm2 2v14h14V5z"/>'
            '<circle cx="12" cy="12" r="4"/>',
    "ray": '<path d="M2 11.4h14v1.6H2z"/><path d="M13 7.5l7 4.5-7 4.5z"/>',
    "parallax": "M2 18h20v2H2zM4 10h6v6H4zM14 6h6v10h-6z",
    "canvas": "M4 4h16v12H4zm2 14h12v2H6z",
}

# Coherent rounded outline icons for editor controls.
_OUTLINE = {
 'play':'M8 5l11 7-11 7z', 'pause':'M8 5v14M16 5v14', 'stop':'M6 6h12v12H6z',
 'save':'M5 3h12l4 4v14H3V3h2zM7 3v6h9V3M7 21v-7h10v7',
 'folder':'M3 7V5h6l2 2h10v13H3z', 'add':'M12 5v14M5 12h14',
 'delete':'M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7',
 'undo':'M8 4L3 9l5 5M3 9h10a7 7 0 017 7', 'redo':'M16 4l5 5-5 5M21 9H11a7 7 0 00-7 7',
 'cursor':'M5 3l14 9-7 1-3 7z', 'hand':'M8 12V6a2 2 0 014 0v6M12 10V4a2 2 0 014 0v8M16 10a2 2 0 014 0v6c0 4-3 6-6 6h-2c-3 0-4-2-6-5l-3-5a2 2 0 013-2l2 2',
 'move':'M12 3v18M3 12h18M9 6l3-3 3 3M9 18l3 3 3-3M6 9l-3 3 3 3M18 9l3 3-3 3',
 'rotate':'M5 8a8 8 0 111 10M5 3v5h5', 'scale':'M4 13v7h7M13 4h7v7M4 20l7-7M20 4l-7 7',
 'grid':'M4 4h16v16H4zM4 10h16M4 15h16M10 4v16M15 4v16',
 'eye':'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM15 12a3 3 0 11-6 0 3 3 0 016 0',
 'component':'M12 3l9 5v9l-9 5-9-5V8zM3 8l9 5 9-5M12 13v9',
 'node':'M12 3l9 5v9l-9 5-9-5V8zM3 8l9 5 9-5M12 13v9',
 'image':'M3 4h18v16H3zM3 16l5-5 4 4 4-6 5 7M8 8h.01',
 'script':'M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16',
 'settings':'M4 6h16M4 12h16M4 18h16M8 3v6M16 9v6M10 15v6',
 'audio':'M4 9h4l5-5v16l-5-5H4zM17 8a6 6 0 010 8M20 5a10 10 0 010 14',
 'scene':'M4 4h16v16H4zM4 15l6-6 5 5 5-4',
 'physics':'M12 3a9 9 0 110 18 9 9 0 010-18zM12 7v5l4 2',
 'visual':'M3 4h6v6H3zM15 14h6v6h-6zM9 7h6v10',
 'more':'M12 5h.01M12 12h.01M12 19h.01',
 'chevron_down':'M6 9l6 6 6-6', 'chevron_right':'M9 6l6 6-6 6',
 'search':'M16 16l5 5M18 10a8 8 0 11-16 0 8 8 0 0116 0',
 'light':'M9 17h6M10 21h4M8 13a6 6 0 118 0l-1 4H9z',
 'camera':'M3 7h18v13H3zM7 7l2-3h6l2 3M16 13a4 4 0 11-8 0 4 4 0 018 0',
}
_SVG_PATHS.update(_OUTLINE)
_OUTLINE['close']='M6 6l12 12M18 6L6 18'
_SVG_PATHS['close']=_OUTLINE['close']
_MODERN = {
 'close':'M7 7l10 10M17 7L7 17',
 'play':'M9 5.5v13l10-6.5z','pause':'M8 5v14M16 5v14','stop':'M6.5 6.5h11v11h-11z',
 'save':'M5 3.5h11l4.5 4.5v12.5h-17v-17H5zM8 3.5v6h8v-6M8 20.5v-7h9v7',
 'file':'M6 3h8l5 5v13H5V3zM14 3v6h5M8 13h8M8 17h6',
 'folder':'M3 6h6l2 2h10v12H3zM3 6V4h7l2 2h7',
 'image':'M4 4h16v16H4zM4 16l5-5 4 4 3-3 4 4M8 8h.01',
 'cursor':'M6 3.5v16l4.5-4 3.5 6 2.5-1.5-3.5-6 6-1z',
 'hand':'M8 11V6a2 2 0 014 0v5M12 10V4a2 2 0 014 0v7M16 9a2 2 0 014 0v6c0 4-3 7-7 7h-1c-2 0-4-2-5-4l-3-5a2 2 0 013-2l1 1',
 'move':'M12 3v18M3 12h18M9 6l3-3 3 3M9 18l3 3 3-3M6 9l-3 3 3 3M18 9l3 3-3 3',
 'rotate':'M4 9a8 8 0 111 9M4 4v5h5','scale':'M4 10V4h6M14 20h6v-6M4 4l6 6M20 20l-6-6',
 'undo':'M8 5L3 10l5 5M3 10h10a7 7 0 017 7','redo':'M16 5l5 5-5 5M21 10H11a7 7 0 00-7 7',
 'copy':'M8 8h12v13H8zM16 8V3H3v13h5','paste':'M8 5H5v16h14V5h-3M9 3h6v5H9z',
 'delete':'M4 6h16M9 6V3h6v3M7 6l1 15h8l1-15M10 10v7M14 10v7',
 'add':'M12 5v14M5 12h14','remove':'M5 12h14',
 'layers':'M12 3l10 5-10 5L2 8zM3 12l9 5 9-5M3 16l9 5 9-5',
 'focus':'M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5M9 9h6v6H9z',
 'settings':'M4 6h16M4 12h16M4 18h16M8 3v6M16 9v6M10 15v6',
 'build':'M12 3l8 4v10l-8 4-8-4V7zM4 7l8 4 8-4M12 11v10M8 5l8 4',
 'align':'M4 4h16M4 20h16M7 8h10v3H7zM7 14h6v3H7z',
 'grid':'M4 4h16v16H4zM4 9h16M4 15h16M9 4v16M15 4v16',
 'snap':'M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z',
 'eye':'M2.5 12S6 5 12 5s9.5 7 9.5 7S18 19 12 19s-9.5-7-9.5-7zM15 12a3 3 0 11-6 0 3 3 0 016 0',
 'component':'M12 3l8 4.5v9L12 21l-8-4.5v-9zM4 7.5l8 4.5 8-4.5M12 12v9',
 'scene':'M4 4h16v16H4zM8 16l3-4 3 2 3-6',
 'search':'M16.5 16.5l4 4M18 10.5a7.5 7.5 0 11-15 0 7.5 7.5 0 0115 0',
 'camera':'M3 7h5l2-3h4l2 3h5v13H3zM16 13a4 4 0 11-8 0 4 4 0 018 0',
 'light':'M9 17h6M10 21h4M8 13a6 6 0 118 0l-1 4H9zM12 1v1M3 5l1 1M20 6l1-1',
 'physics':'M12 3a9 9 0 110 18 9 9 0 010-18zM12 7v5l4 2',
 'visual':'M3 4h6v6H3zM15 14h6v6h-6zM9 7h6v10',
 'chevron_down':'M7 10l5 5 5-5','chevron_right':'M10 7l5 5-5 5',
}
for _name,_body in _MODERN.items():
    if _name not in _SVG_PATHS: _SVG_PATHS[_name]=_body; _OUTLINE[_name]=_body

_SVG_TEMPLATE = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
                 'width="24" height="24" fill="{color}">{body}</svg>')

_CACHE: Dict[Any, Any] = {}


# ======================================================================
# Рендер
# ======================================================================
def _make_svg(name: str, color: str) -> str:
    """Собирает SVG-документ по имени иконки."""
    from editor.ui_profile import flavor
    modern=flavor()=='modern'
    body = _MODERN.get(name,_SVG_PATHS.get(name)) if modern else _SVG_PATHS.get(name)
    if body is None:
        return ""
    if name in _OUTLINE or (modern and name in _MODERN):
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="'+color+'" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="'+body+'"/></svg>'
    if "<" in body:
        return _SVG_TEMPLATE.format(color=color, body=body)
    return _SVG_TEMPLATE.format(color=color, body=f'<path d="{body}"/>')


def _render_svg_icon(name: str, size: int, color: str) -> Optional[QPixmap]:
    """Рисует SVG-иконку в QPixmap."""
    if not _HAS_SVG:
        return None
    svg = _make_svg(name, color)
    if not svg:
        return None
    try:
        renderer = QSvgRenderer(svg.encode("utf-8"))
        if not renderer.isValid():
            return None
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter)
        painter.end()
        return pixmap
    except Exception:
        return None


def get_pixmap(name: str, size: int = 18, color: str = "#b9ccdc") -> QPixmap:
    """Возвращает QPixmap иконки (кэшируется)."""
    key = ("pm", name, size, color)
    if key in _CACHE:
        return _CACHE[key]
    pixmap = _render_svg_icon(name, size, color)
    if pixmap is None:
        pixmap = _fallback_pixmap(name, size)
    _CACHE[key] = pixmap
    return pixmap


def get_icon(name: str, size: int = 18, color: str = "#b9ccdc") -> QIcon:
    """Возвращает QIcon по имени (SVG, с запасным вариантом)."""
    from editor.ui_profile import flavor
    key = ("icon", flavor(), name, size, color)
    if key in _CACHE:
        return _CACHE[key]
    icon = QIcon()
    for scale in (1,2,3):
        pixmap=_render_svg_icon(name,size*scale,color)
        if pixmap is None: pixmap=_fallback_pixmap(name,size*scale)
        pixmap.setDevicePixelRatio(scale); icon.addPixmap(pixmap)
        disabled=_render_svg_icon(name,size*scale,'#657185')
        if disabled is not None:
            disabled.setDevicePixelRatio(scale); icon.addPixmap(disabled,QIcon.Mode.Disabled)
    _CACHE[key] = icon
    return icon


def has_icon(name: str) -> bool:
    """Есть ли иконка с таким именем."""
    return name in _SVG_PATHS


def icon_names() -> list:
    """Список всех доступных имён иконок."""
    return sorted(_SVG_PATHS)


# ======================================================================
# Запасные иконки (если QtSvg недоступен)
# ======================================================================
def _fallback_pixmap(name: str, size: int) -> QPixmap:
    """Простая геометрическая иконка на случай отсутствия QtSvg."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    rect = QRectF(1, 1, size - 2, size - 2)
    pen = QPen(_LIGHT, 1.6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if name in ("play",):
        painter.setBrush(QBrush(QColor("#6bbf6b")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygonF([QPointF(rect.left(), rect.top()),
                                       QPointF(rect.left(), rect.bottom()),
                                       QPointF(rect.right(), rect.center().y())]))
    elif name in ("pause",):
        painter.setBrush(QBrush(QColor("#e0a800")))
        painter.setPen(Qt.PenStyle.NoPen)
        w = rect.width() / 3.2
        painter.drawRect(QRectF(rect.left(), rect.top(), w, rect.height()))
        painter.drawRect(QRectF(rect.right() - w, rect.top(), w, rect.height()))
    elif name in ("stop",):
        painter.setBrush(QBrush(QColor("#d9534f")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(rect)
    else:
        painter.drawRect(rect)
    painter.end()
    return pixmap


# ======================================================================
# Иконка и логотип приложения
# ======================================================================
def engine_root() -> str:
    """Корень установки Cloud Engine (папка с main.py)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def asset_path(*parts: str) -> str:
    """Путь внутри папки assets движка."""
    return os.path.join(engine_root(), "assets", *parts)


def get_app_icon() -> QIcon:
    """Иконка приложения: файл из assets, иначе нарисованный логотип."""
    if "app" not in _CACHE:
        icon = QIcon()
        for name in ("app_icon.png", "engine_icon.png", "default_icon.png"):
            path = asset_path(name)
            if os.path.isfile(path):
                loaded = QIcon(path)
                if not loaded.isNull():
                    icon = loaded
                    break
        if icon.isNull():
            icon = _draw_logo_icon()
        _CACHE["app"] = icon
    return _CACHE["app"]


def _draw_logo_icon() -> QIcon:
    """Аварийный логотип, если не нашлось ни одного файла иконки."""
    pixmap = QPixmap(128, 128)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(_ACCENT))
    for cx, cy, r in ((44, 76, 28), (76, 60, 36), (100, 76, 26), (60, 88, 24)):
        painter.drawEllipse(QPointF(cx, cy), r, r)
    painter.setBrush(QBrush(QColor("#2b2b2b")))
    painter.drawRect(QRectF(24, 92, 80, 14))
    painter.setBrush(QBrush(QColor("#6bbf6b")))
    painter.drawRect(QRectF(24, 92, 24, 14))
    painter.end()
    return QIcon(pixmap)


def get_logo_pixmap(size: int = 128) -> QPixmap:
    """Логотип движка как QPixmap (для панелей/заставки)."""
    path = asset_path("engine_icon.png")
    if os.path.isfile(path):
        pix = QPixmap(path)
        if not pix.isNull():
            return pix.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
    return _draw_logo_icon().pixmap(QSize(size, size))


def ensure_default_icon(path: str) -> bool:
    """Гарантирует наличие PNG-иконки по умолчанию."""
    if os.path.isfile(path):
        return True
    try:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        source = asset_path("engine_icon.png")
        if os.path.isfile(source):
            pix = QPixmap(source)
            if not pix.isNull():
                return bool(pix.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
                            .save(path, "PNG"))
        return bool(_draw_logo_icon().pixmap(QSize(128, 128)).save(path, "PNG"))
    except Exception:
        return False
