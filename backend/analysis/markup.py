from database import query
from analysis.summaries import table_exists

# Live (slow, full-table) fallbacks — used only when summary tables aren't built.
_STATE_MARKUP_LIVE = """
    SELECT state,
           AVG((modal_price - farm_gate_price) / NULLIF(farm_gate_price, 0) * 100) AS avg_markup_pct,
           AVG(farm_gate_price) AS avg_farm_gate,
           AVG(modal_price)     AS avg_modal,
           COUNT(*)             AS record_count
    FROM prices
    GROUP BY state
    ORDER BY avg_markup_pct DESC
"""

_CROP_MARKUP_LIVE = """
    SELECT state,
           AVG((modal_price - farm_gate_price) / NULLIF(farm_gate_price, 0) * 100) AS avg_markup_pct,
           AVG(farm_gate_price) AS avg_farm_gate,
           AVG(modal_price)     AS avg_modal
    FROM prices
    WHERE LOWER(commodity) = LOWER(?)
    GROUP BY state
    ORDER BY avg_markup_pct DESC
"""


def get_state_markup() -> list[dict]:
    if table_exists("summary_state_markup"):
        df = query("SELECT * FROM summary_state_markup ORDER BY avg_markup_pct DESC")
    else:
        df = query(_STATE_MARKUP_LIVE)
    return df.round(2).to_dict(orient="records")


def get_crop_markup(commodity: str) -> list[dict]:
    if table_exists("summary_crop_markup"):
        df = query(
            "SELECT state, avg_markup_pct, avg_farm_gate, avg_modal "
            "FROM summary_crop_markup WHERE LOWER(commodity) = LOWER(?) "
            "ORDER BY avg_markup_pct DESC",
            (commodity,),
        )
    else:
        df = query(_CROP_MARKUP_LIVE, (commodity,))
    return df.round(2).to_dict(orient="records")
