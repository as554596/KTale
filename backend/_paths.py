"""Adds backend subfolders to sys.path so modules can import each other by
plain module name (e.g. `from enhanced_epub_parser import ...`) regardless of
which subfolder they live in."""
import os
import sys

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_SUBFOLDERS = ['epub', 'txt', 'glossary', 'quality', 'language', 'utils', 'tests']

for _folder in _SUBFOLDERS:
    _path = os.path.join(_BACKEND_DIR, _folder)
    if _path not in sys.path:
        sys.path.insert(0, _path)
