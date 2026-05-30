"""Summary tables back the slow per-state aggregations (states/markup, revenue-loss,
crop markup). These tests verify the summaries exist and match live computation."""
import pytest
from analysis.summaries import build_summaries, table_exists
from analysis.markup import get_state_markup, get_crop_markup
from analysis.revenue_loss import get_revenue_loss
from analysis.trends import get_available_filters
from models.predictor import available_forecasts
from database import query

SUMMARY_TABLES = ("summary_state_markup", "summary_crop_markup", "summary_revenue_loss")


@pytest.fixture(scope="module", autouse=True)
def ensure_built():
    if not all(table_exists(t) for t in SUMMARY_TABLES):
        build_summaries()


def test_summary_tables_exist():
    for t in SUMMARY_TABLES:
        assert table_exists(t), f"{t} missing"


def test_state_markup_all_states_sorted_desc():
    r = get_state_markup()
    assert len(r) == 34
    assert {"state", "avg_markup_pct", "avg_farm_gate", "avg_modal", "record_count"} <= set(r[0])
    pcts = [x["avg_markup_pct"] for x in r]
    assert pcts == sorted(pcts, reverse=True)


def test_crop_markup_matches_live_computation():
    """Summary-backed crop markup must equal a fresh (indexed, fast) live query."""
    summ = {d["state"]: d["avg_markup_pct"] for d in get_crop_markup("Tomato")}
    live = query("""
        SELECT state,
               ROUND(AVG((modal_price - farm_gate_price) / NULLIF(farm_gate_price, 0) * 100), 2) p
        FROM prices WHERE LOWER(commodity) = LOWER('Tomato') GROUP BY state
    """)
    live_map = {row.state: row.p for row in live.itertuples()}
    assert summ.keys() == live_map.keys()
    for s in summ:
        assert abs(summ[s] - live_map[s]) < 0.05, f"{s}: {summ[s]} vs {live_map[s]}"


def test_revenue_loss_structure_sorted():
    r = get_revenue_loss()
    assert r and {"state", "avg_gap_per_quintal", "estimated_loss_cr", "crop_count"} <= set(r[0])
    gaps = [x["avg_gap_per_quintal"] for x in r]
    assert gaps == sorted(gaps, reverse=True)


def test_trends_filters_match_distinct_values():
    """Summary-backed filters must equal the distinct states/commodities in the data."""
    f = get_available_filters()
    assert f["states"] == sorted(f["states"]) and "Punjab" in f["states"]
    assert f["commodities"] == sorted(f["commodities"]) and "Wheat" in f["commodities"]
    n_states = int(query("SELECT COUNT(*) n FROM summary_state_markup").iloc[0]["n"])
    n_comm = int(query("SELECT COUNT(DISTINCT commodity) n FROM summary_crop_markup").iloc[0]["n"])
    assert len(f["states"]) == n_states
    assert len(f["commodities"]) == n_comm


def test_available_forecasts_consistent():
    av = available_forecasts()
    assert "Punjab" in av and "Wheat" in av["Punjab"]
    # never advertise a combo without a model file (cross-checks the summary-backed path)
    from config import MODELS_DIR
    for state, comms in list(av.items())[:3]:
        for c in comms[:3]:
            safe = f"{state}_{c}".replace(" ", "_").replace("/", "-")
            assert (MODELS_DIR / f"{safe}.pt").exists()
