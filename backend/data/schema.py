from dataclasses import dataclass

@dataclass
class RawPrice:
    state: str
    district: str
    market: str
    commodity: str
    variety: str
    date: str
    min_price: float
    max_price: float
    modal_price: float

@dataclass
class CleanPrice:
    state: str
    commodity: str
    year: int
    month: int
    farm_gate_price: float
    modal_price: float

    @property
    def markup_pct(self) -> float:
        if self.farm_gate_price == 0:
            return 0.0
        return ((self.modal_price - self.farm_gate_price) / self.farm_gate_price) * 100
