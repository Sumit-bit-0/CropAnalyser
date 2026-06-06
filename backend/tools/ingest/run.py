"""CLI orchestrator: fetch -> normalize -> validate -> load, then record
provenance. Usage:
    python -m tools.ingest.run <adapter_name>
    python -m tools.ingest.run all
"""
import sys

from sqlalchemy import text

from database import get_engine
from tools.ingest import schema, registry


def _record_provenance(adapter, rows: int) -> None:
    with get_engine().begin() as conn:
        conn.execute(
            text("""INSERT INTO data_provenance
                    (source_name, target_table, method, source_ref, rows_loaded)
                    VALUES (:s, :t, :m, :r, :n)"""),
            {"s": adapter.source_name, "t": adapter.target_table,
             "m": adapter.method, "r": adapter.source_ref, "n": rows},
        )


def run_adapter(name: str) -> int:
    schema.ensure_tables()
    adapter = registry.get_adapter(name)
    df = adapter.validate(adapter.normalize(adapter.fetch()))
    rows = adapter.load(df)
    _record_provenance(adapter, rows)
    return rows


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: python -m tools.ingest.run <adapter_name|all>")
        return 2
    target = argv[0]
    names = list(registry.ADAPTERS) if target == "all" else [target]
    for name in names:
        try:
            n = run_adapter(name)
            print(f"[ok]   {name}: {n} rows -> "
                  f"{registry.get_adapter(name).target_table}")
        except Exception as e:  # adapters fail loudly, one bad source doesn't halt 'all'
            print(f"[fail] {name}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
