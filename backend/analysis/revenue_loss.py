from database import query

PROXY_VOLUME_QUINTALS = 1000

def get_revenue_loss() -> list[dict]:
    df = query("""
        SELECT state,
               AVG(modal_price - farm_gate_price) AS avg_gap_per_quintal,
               COUNT(DISTINCT commodity)           AS crop_count,
               COUNT(*)                            AS records
        FROM prices
        GROUP BY state
        ORDER BY avg_gap_per_quintal DESC
    """)
    df["estimated_loss_cr"] = (
        df["avg_gap_per_quintal"] * PROXY_VOLUME_QUINTALS * 12 / 10_000_000
    ).round(4)
    df["avg_gap_per_quintal"] = df["avg_gap_per_quintal"].round(2)
    return df[["state", "avg_gap_per_quintal", "estimated_loss_cr", "crop_count"]].to_dict(orient="records")
