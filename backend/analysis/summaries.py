"""Precomputed summary tables for the slow per-state aggregations.

The `prices` table is ~27.6M rows and static, so aggregating it per request
(GROUP BY state with no filter) takes ~70s. We materialize the results once into
tiny tables that the API reads instantly. Rebuild with `python -m data.build_summaries`
(or whenever `prices` changes).

IMPORTANT: the aggregation expressions below MUST stay in sync with the live
fallbacks in analysis/markup.py and analysis/revenue_loss.py.
"""
import contextlib
from database import get_connection

# One GROUP BY state pass feeds BOTH state-markup and revenue-loss.
_STATE_AGG_SQL = """
    SELECT state,
           AVG((modal_price - farm_gate_price) / NULLIF(farm_gate_price, 0) * 100) AS avg_markup_pct,
           AVG(farm_gate_price)              AS avg_farm_gate,
           AVG(modal_price)                  AS avg_modal,
           AVG(modal_price - farm_gate_price) AS avg_gap_per_quintal,
           COUNT(DISTINCT commodity)         AS crop_count,
           COUNT(*)                          AS record_count
    FROM prices
    GROUP BY state
"""

# One GROUP BY state, commodity pass feeds crop-markup.
_CROP_AGG_SQL = """
    SELECT state, commodity,
           AVG((modal_price - farm_gate_price) / NULLIF(farm_gate_price, 0) * 100) AS avg_markup_pct,
           AVG(farm_gate_price) AS avg_farm_gate,
           AVG(modal_price)     AS avg_modal
    FROM prices
    GROUP BY state, commodity
"""


def table_exists(name: str) -> bool:
    with contextlib.closing(get_connection()) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
    return row is not None


def build_summaries() -> dict[str, int]:
    """(Re)build the three summary tables. Returns row counts per table."""
    import pandas as pd

    with contextlib.closing(get_connection()) as conn:
        state_df = pd.read_sql_query(_STATE_AGG_SQL, conn)
        crop_df = pd.read_sql_query(_CROP_AGG_SQL, conn)

        state_markup = state_df[
            ["state", "avg_markup_pct", "avg_farm_gate", "avg_modal", "record_count"]
        ]
        revenue = state_df[["state", "avg_gap_per_quintal", "crop_count", "record_count"]].rename(
            columns={"record_count": "records"}
        )

        state_markup.to_sql("summary_state_markup", conn, if_exists="replace", index=False)
        crop_df.to_sql("summary_crop_markup", conn, if_exists="replace", index=False)
        revenue.to_sql("summary_revenue_loss", conn, if_exists="replace", index=False)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_summary_crop_commodity ON summary_crop_markup(commodity)"
        )
        conn.commit()

    return {
        "summary_state_markup": len(state_markup),
        "summary_crop_markup": len(crop_df),
        "summary_revenue_loss": len(revenue),
    }
