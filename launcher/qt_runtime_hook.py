"""Runs before PyInstaller's PyQt hook imports any Qt DLLs."""
from qt_runtime import configure
configure()
