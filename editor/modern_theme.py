"""Parametric modern editor skin. Geometry and project content stay untouched."""
from PyQt6.QtGui import QColor
from pathlib import Path

PALETTES={
 'midnight':{'bg':'#151922','panel':'#1c222e','surface':'#222b38','input':'#111720','border':'#303b4d','text':'#e4eaf4','muted':'#95a4ba'},
 'graphite':{'bg':'#191b20','panel':'#22252d','surface':'#2b2f39','input':'#14171c','border':'#3a404c','text':'#e9ebf2','muted':'#a3acbd'},
 'slate':{'bg':'#17212b','panel':'#202e3b','surface':'#293a4a','input':'#111c27','border':'#3a5063','text':'#e5eef6','muted':'#9eb3c6'},
}


def stylesheet(options):
    c=PALETTES.get(options.get('palette'),PALETTES['midnight'])
    accent=QColor(options.get('accent','#88aef5'))
    if not accent.isValid(): accent=QColor('#88aef5')
    a=accent.name(); selection=QColor(accent); selection.setHsv(accent.hsvHue(),100,90)
    selected=selection.name(); font=max(10,min(18,int(options.get('font_size',13))))
    family=str(options.get('font_family','Segoe UI')).replace('"','').replace(';','')
    pad={'compact':4,'comfortable':7,'spacious':10}.get(options.get('density'),7)
    radius=max(0,min(12,int(options.get('radius',6))))
    icon_root=(Path(__file__).resolve().parents[1]/'assets'/'ui').as_posix()
    return f'''
* {{ outline:0; }}
QWidget {{ background:{c['bg']}; color:{c['text']}; font-family:"{family}"; font-size:{font}px; }}
QMainWindow, QDialog {{ background:{c['bg']}; }}
QMenuBar {{ background:{c['bg']}; padding:4px 10px; border-bottom:1px solid {c['border']}; }}
QMenuBar::item {{ background:transparent; padding:6px 12px; border-radius:4px; color:{c['muted']}; }}
QMenuBar::item:selected {{ background:{c['surface']}; color:{c['text']}; }}
QMenu {{ background:{c['panel']}; border:1px solid {c['border']}; padding:6px; }}
QMenu::item {{ padding:{pad+1}px 30px {pad+1}px 14px; border-radius:4px; }}
QMenu::item:selected {{ background:{selected}; color:#ffffff; }}
QMenu::separator {{ height:1px; background:{c['border']}; margin:5px 10px; }}
QToolBar {{ background:{c['bg']}; border:0; border-bottom:1px solid {c['border']}; padding:8px 12px; spacing:8px; }}
QToolBar::separator {{ background:{c['border']}; width:1px; margin:5px; }}
QWidget#EditorCommandStrip {{ background:transparent; }}
QFrame#ToolGroup {{ background:{c['panel']}; border:1px solid {c['border']}; border-radius:{radius}px; }}
QFrame#ToolGroup QToolButton {{ background:transparent; border:1px solid transparent; border-radius:{max(0,radius-2)}px; padding:{pad}px; min-width:20px; min-height:18px; }}
QToolButton, QPushButton {{ background:{c['surface']}; border:1px solid {c['border']}; border-radius:{radius}px; padding:{pad}px {pad+5}px; }}
QToolButton:hover, QPushButton:hover {{ background:{selected}; border-color:{a}; color:#ffffff; }}
QToolButton:checked, QFrame#ToolGroup QToolButton:checked {{ background:{selected}; border:1px solid {a}; color:#ffffff; }}
QPushButton[primary="true"], QToolButton#PrimaryBuild {{ background:{selected}; border-color:{a}; color:#ffffff; }}
QPushButton:disabled, QToolButton:disabled {{ color:#647084; border-color:{c['border']}; background:{c['panel']}; }}
QToolButton#CommandSearch {{ background:transparent; color:{c['muted']}; padding:3px 8px; border-color:transparent; }}
QToolButton#SceneTabClose {{ background:transparent; border:0; padding:2px; min-width:12px; min-height:12px; border-radius:4px; }}
QToolButton#SceneTabClose:hover {{ background:#4a3442; }}
QMainWindow::separator, QSplitter::handle {{ background:{c['bg']}; width:5px; height:5px; }}
QMainWindow::separator:hover {{ background:{a}; }}
QDockWidget {{ border:0; }}
QDockWidget::title {{ background:{c['panel']}; color:{c['muted']}; padding:9px 12px; border-bottom:1px solid {c['border']}; font-weight:600; }}
QGroupBox {{ background:{c['panel']}; border:1px solid {c['border']}; border-radius:{radius}px; margin-top:18px; padding:14px 9px 9px; }}
QGroupBox::title {{ color:{c['muted']}; left:12px; padding:0 5px; }}
QGroupBox QWidget {{ background:transparent; }}
QGroupBox#ComponentCard {{ margin-top:0; padding:0; background:{c['panel']}; }}
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background:{c['input']}; border:1px solid {c['border']}; border-radius:{radius}px; padding:{pad}px 8px; selection-background-color:{selected}; selection-color:#ffffff; }}
QGroupBox QLineEdit, QGroupBox QSpinBox, QGroupBox QDoubleSpinBox, QGroupBox QComboBox {{ background:{c['input']}; }}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color:{a}; }}
QComboBox::drop-down {{ width:20px; border:0; }}
QComboBox::down-arrow {{ image:url("{icon_root}/chevron-down.svg"); width:10px; height:10px; }}
QComboBox QAbstractItemView {{ background:{c['panel']}; border:1px solid {c['border']}; selection-background-color:{selected}; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width:15px; border:0; background:{c['surface']}; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image:url("{icon_root}/chevron-up.svg"); width:8px; height:8px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image:url("{icon_root}/chevron-down.svg"); width:8px; height:8px; }}
QTabWidget::pane {{ border:0; border-top:1px solid {c['border']}; }}
QTabBar::tab {{ background:{c['bg']}; color:{c['muted']}; padding:9px 14px; border:0; border-bottom:2px solid transparent; margin-right:3px; }}
QTabBar::tab:selected {{ background:{c['panel']}; color:{c['text']}; border-bottom:2px solid {a}; }}
QTabBar::tab:hover {{ background:{c['surface']}; }}
QTreeWidget, QTreeView, QListWidget, QTableWidget {{ background:{c['input']}; alternate-background-color:{c['panel']}; border:1px solid {c['border']}; gridline-color:{c['border']}; border-radius:{radius}px; }}
QTreeWidget::item, QListWidget::item {{ padding:{pad}px 7px; border:0; border-radius:3px; margin:1px; }}
QTreeWidget::item:selected, QListWidget::item:selected, QTableWidget::item:selected {{ background:{selected}; color:#ffffff; }}
QTreeWidget::item:hover, QListWidget::item:hover {{ background:{c['surface']}; }}
QHeaderView::section {{ background:{c['panel']}; color:{c['muted']}; padding:8px; border:0; border-bottom:1px solid {c['border']}; text-align:left; }}
QTableWidget::item {{ padding:5px; }}
QCheckBox {{ spacing:7px; background:transparent; }}
QCheckBox::indicator {{ width:14px; height:14px; background:{c['input']}; border:1px solid {c['border']}; border-radius:4px; }}
QCheckBox::indicator:checked {{ background:{selected}; border:2px solid {a}; }}
QScrollArea {{ border:0; }}
QScrollBar:vertical {{ width:9px; background:{c['bg']}; margin:2px; }}
QScrollBar::handle:vertical {{ background:{c['border']}; border-radius:3px; min-height:28px; }}
QScrollBar::handle:vertical:hover {{ background:{c['muted']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar:horizontal {{ height:9px; background:{c['bg']}; margin:2px; }}
QScrollBar::handle:horizontal {{ background:{c['border']}; border-radius:3px; min-width:28px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width:0; }}
QStatusBar {{ background:{c['bg']}; color:{c['muted']}; border-top:1px solid {c['border']}; padding:3px 8px; }}
QStatusBar::item {{ border:0; }}
QLabel {{ background:transparent; }}
QLabel#SectionTitle {{ font-size:{font+5}px; font-weight:600; color:{c['text']}; }}
QLabel#SecondaryText {{ color:{c['muted']}; }}
QLabel#ProductBrand {{ color:{c['muted']}; font-size:{max(10,font-1)}px; padding:0 8px; }}
QProgressBar {{ background:{c['input']}; border:1px solid {c['border']}; border-radius:4px; text-align:center; }}
QProgressBar::chunk {{ background:{a}; }}
QToolTip {{ background:{c['surface']}; color:{c['text']}; border:1px solid {c['border']}; padding:8px; }}
'''
