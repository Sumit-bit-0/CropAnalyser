from database import query
from analysis.summaries import table_exists

PROXY_VOLUME_QUINTALS = 1000

_REVENUE_LIVE = """
    SELECT state,
           AVG(modal_price - farm_gate_price) AS avg_gap_per_quintal,
           COUNT(DISTINCT commodity)           AS crop_count,
           COUNT(*)                            AS records
    FROM prices
    GROUP BY state
    ORDER BY avg_gap_per_quintal DESC
"""


def get_revenue_loss() -> list[dict]:
    if table_exists("summary_revenue_loss"):
        df = query("SELECT * FROM summary_revenue_loss ORDER BY avg_gap_per_quintal DESC")
    else:
        df = query(_REVENUE_LIVE)
    df["estimated_loss_cr"] = (
        df["avg_gap_per_quintal"].clip(lower=0) * PROXY_VOLUME_QUINTALS * 12 / 10_000_000
    ).round(4)
    df["avg_gap_per_quintal"] = df["avg_gap_per_quintal"].round(2)
    return df[["state", "avg_gap_per_quintal", "estimated_loss_cr", "crop_count"]].to_dict(orient="records")
