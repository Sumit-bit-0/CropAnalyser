from database import query


def plan_profit(area_acres, yield_q_per_acre, input_cost, labour_cost,
                transport_cost, market_price, desired_margin_pct=20.0):
    total_yield_q = area_acres * yield_q_per_acre
    total_cost = input_cost + labour_cost + transport_cost
    total_revenue = total_yield_q * market_price
    profit = total_revenue - total_cost

    if total_yield_q > 0:
        break_even_price = round(total_cost / total_yield_q, 2)
        target_sale_price = round(break_even_price * (1 + desired_margin_pct / 100), 2)
    else:
        break_even_price = None
        target_sale_price = None

    margin_pct = round((profit / total_revenue * 100), 1) if total_revenue > 0 else None

    if break_even_price is None:
        rec = "Enter a yield greater than zero to plan profit."
    elif market_price < break_even_price:
        rec = (f"Loss risk — current price ₹{market_price}/q is below your break-even "
               f"₹{break_even_price}/q. Reconsider this crop or cut costs.")
    elif target_sale_price is not None and market_price >= target_sale_price:
        rec = (f"Sell now — current price ₹{market_price}/q already beats your target "
               f"₹{target_sale_price}/q.")
    else:
        rec = (f"Wait or negotiate — you cover costs, but aim for ₹{target_sale_price}/q "
               f"to hit your {desired_margin_pct:.0f}% margin.")

    return {
        "total_yield_q": round(total_yield_q, 2),
        "total_cost": round(total_cost, 2),
        "total_revenue": round(total_revenue, 2),
        "profit": round(profit, 2),
        "profit_margin_pct": margin_pct,
        "break_even_price": break_even_price,
        "target_sale_price": target_sale_price,
        "recommendation": rec,
    }


def get_price_reference(state: str, commodity: str) -> dict:
    df = query(
        """
        SELECT modal_price, year, month FROM prices
        WHERE LOWER(state) = LOWER(?) AND LOWER(commodity) = LOWER(?)
        ORDER BY year, month
        """,
        (state, commodity),
    )
    if df.empty:
        return {"latest_price": None, "avg_price": None,
                "volatility_cv": None, "risk_level": "unknown"}
    mean = float(df["modal_price"].mean())
    std = float(df["modal_price"].std(ddof=0))
    cv = (std / mean) if mean else 0.0
    if cv < 0.15:
        risk = "low"
    elif cv <= 0.30:
        risk = "medium"
    else:
        risk = "high"
    return {
        "latest_price": round(float(df["modal_price"].iloc[-1]), 2),
        "avg_price": round(mean, 2),
        "volatility_cv": round(cv, 3),
        "risk_level": risk,
    }
