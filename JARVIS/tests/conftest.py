"""Make the JARVIS package importable from the tests folder."""

import os
import sys

# Tests never start the real GUI, so force the offscreen Qt platform plugin.
# This only affects the pytest process - the shipped application is unaffected,
# because it never reads this variable (it uses the normal Windows platform).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)
