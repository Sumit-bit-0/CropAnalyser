"""Maps adapter names to instances. Add new adapters here."""
from tools.ingest.adapters.facility_crop_seed import FacilityCropSeed
from tools.ingest.adapters.isma_sugar import IsmaSugar
from tools.ingest.adapters.shc_soil import ShcSoil
from tools.ingest.adapters.datagov_mills import DatagovMills
from tools.ingest.adapters.mofpi_units import MofpiUnits
from tools.ingest.adapters.state_signature import StateSignature
from tools.ingest.adapters.msme_udyam import MsmeUdyam
from tools.ingest.adapters.web_curated import WebCurated

ADAPTERS = {
    "facility_crop_seed": FacilityCropSeed,
    "isma_sugar": IsmaSugar,
    "shc_soil": ShcSoil,
    "datagov_mills": DatagovMills,
    "mofpi_units": MofpiUnits,
    "state_signature": StateSignature,
    "msme_udyam": MsmeUdyam,
    "web_curated": WebCurated,
}


def get_adapter(name: str):
    if name not in ADAPTERS:
        raise KeyError(f"Unknown adapter '{name}'. Known: {sorted(ADAPTERS)}")
    return ADAPTERS[name]()


def all_adapters():
    return [cls() for cls in ADAPTERS.values()]
