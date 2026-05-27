import os
import sys

# Add backend/ to path so `data`, `analysis`, `models`, `api` are importable without pip install
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
