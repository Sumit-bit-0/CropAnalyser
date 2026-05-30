"""Summary tables back the slow per-state aggregations (states/markup, revenue-loss,
crop markup). These tests verify the summaries exist and match live computation."""
import pytest
from analysis.summaries import build_summaries, table_exists
from analysis.markup import get_state_markup, get_crop_markup
from analysis.revenue_loss import get_revenue_loss
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
