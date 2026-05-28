import sqlite3

DB = "../data/processed/agri.db"
MIN_RECORDS = 12 + 6 + 5  # SEQUENCE_LEN + FORECAST_LEN + 5

conn = sqlite3.connect(DB)
cur = conn.cursor()

print("=== Top 10 states by trainable (year,month) series count ===")
cur.execute("""
    SELECT state, COUNT(DISTINCT year || '-' || month) AS periods
    FROM prices
    GROUP BY state
    ORDER BY periods DESC
    LIMIT 10
""")
top_states = cur.fetchall()
for s, p in top_states:
    print(f"  {s:<30} {p} periods")

print("\n=== Top 10 commodities by trainable (year,month) series count ===")
cur.execute("""
    SELECT commodity, COUNT(DISTINCT year || '-' || month) AS periods
    FROM prices
    GROUP BY commodity
    ORDER BY periods DESC
    LIMIT 10
""")
top_commodities = cur.fetchall()
for c, p in top_commodities:
    print(f"  {c:<30} {p} periods")

# Best 5x5 grid
states_5 = [r[0] for r in top_states[:5]]
commodities_5 = [r[0] for r in top_commodities[:5]]

print(f"\n=== Trainability: top-5 states x top-5 commodities (min={MIN_RECORDS}) ===")
print(f"{'State':<30} {'Commodity':<25} {'Periods':>8} {'OK?':>5}")
print("-" * 75)

ok = 0
for state in states_5:
    for commodity in commodities_5:
        # Count distinct year-month combinations (what get_price_trend returns)
        cur.execute("""
            SELECT COUNT(DISTINCT year || '-' || month)
            FROM prices
            WHERE LOWER(state)=LOWER(?) AND LOWER(commodity)=LOWER(?)
        """, (state, commodity))
        count = cur.fetchone()[0]
        trainable = "YES" if count >= MIN_RECORDS else "NO"
        if count >= MIN_RECORDS:
            ok += 1
        print(f"{state:<30} {commodity:<25} {count:>8} {trainable:>5}")

print(f"\n{ok}/25 series trainable with top-5 selection.")
print(f"\nSuggested states: {states_5}")
print(f"Suggested commodities: {commodities_5}")

conn.close()
