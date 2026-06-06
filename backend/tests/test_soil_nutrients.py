# Soil nutrient lookups are DB-backed now; see test_soil_nutrients_db.py.
# This module re-exports the DB tests so older references still collect.
from tests.test_soil_nutrients_db import (  # noqa: F401
    test_district_hit, test_state_fallback, test_national_fallback,
)
