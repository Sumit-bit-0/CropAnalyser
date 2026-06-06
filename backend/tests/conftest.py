import os
import sys

# Add backend/ to path so `data`, `analysis`, `models`, `api` are importable without pip install
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from sqlalchemy import text

from database import get_engine
from tools.ingest import schema

_SOIL_ROWS = [
    ("Bihar", "Gopalganj", 270, 22, 210, 7.4),
    ("Bihar", "Patna", 240, 18, 190, 7.6),
    ("Punjab", "Ludhiana", 280, 21, 240, 7.8),
]


@pytest.fixture
def seeded():
    """Seed soil_nutrients with 3 known rows (clears ALL rows first for determinism)."""
    schema.ensure_tables()
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM soil_nutrients"))
        for s, d, n, p, k, ph in _SOIL_ROWS:
            c.execute(text('''INSERT INTO soil_nutrients
                (state, district, "N", "P", "K", ph, source)
                VALUES (:s,:d,:n,:p,:k,:ph,'test')'''),
                {"s": s, "d": d, "n": n, "p": p, "k": k, "ph": ph})
    yield
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM soil_nutrients WHERE source='test'"))


@pytest.fixture(autouse=True)
def _disable_live_weather(monkeypatch):
    """Tests must not hit the Open-Meteo network. Default the weather module OFF.

    A test that exercises weather must override this by patching the name on the
    FUSION module — e.g. monkeypatch.setattr(analysis.fusion, "weather_fit_scores",
    ...) or the "analysis.fusion.weather_fit_scores" string path. Patching the
    source module analysis.weather_fit will NOT win; this fixture's patch takes
    precedence because fusion imported the name at import time.
    """
    monkeypatch.setattr("analysis.fusion.weather_fit_scores",
                        lambda *a, **k: {}, raising=False)
