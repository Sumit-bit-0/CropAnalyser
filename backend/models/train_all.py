from analysis.trends import get_available_filters
from models.trainer import train

if __name__ == "__main__":
    filters    = get_available_filters()
    states     = filters["states"][:5]
    commodities = filters["commodities"][:5]
    for state in states:
        for commodity in commodities:
            try:
                print(f"\nTraining: {state} / {commodity}")
                train(state, commodity, epochs=50)
            except ValueError as e:
                print(f"Skipped: {e}")
