import os
import sys

# Ensure repository root and ml directory are on sys.path
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

_ml_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ml_dir not in sys.path:
    sys.path.insert(0, _ml_dir)
