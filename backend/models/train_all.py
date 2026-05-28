from models.trainer import train

# Top states/commodities by data volume — 19/25 combinations have sufficient records
STATES = ["Gujarat", "Maharashtra", "Nct Of Delhi", "Pondicherry", "Punjab"]
COMMODITIES = ["Wheat", "Tomato", "Soyabean", "Sesamum (Sesame,Gingelly,Til)", "Rice"]

if __name__ == "__main__":
    for state in STATES:
        for commodity in COMMODITIES:
            try:
                print(f"\nTraining: {state} / {commodity}")
                train(state, commodity, epochs=400)
            except ValueError as e:
                print(f"Skipped: {e}")
