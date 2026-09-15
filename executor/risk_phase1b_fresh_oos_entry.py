"""Technical entry adapter for the frozen Risk Tool v2 Phase-1B fresh-OOS evaluator.

This module changes only physical Parquet loading. It bypasses legacy pandas
metadata when reading the already-accepted carrier, then delegates all science
to the frozen evaluator module. If the frozen logical projection cannot be
resolved from physical Parquet fields, it writes a bounded schema-only
metadata diagnostic; no row values or model outputs are exported.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

import risk_phase1b_fresh_oos_eval as ev

REQUIRED_CARRIER_COLUMNS = ("datetime", "symbol", "close")
SCHEMA_DIAGNOSTIC_NAME = "CARRIER_SCHEMA_DIAGNOSTIC.json"
SCHEMA_DIAGNOSTIC_ID = "risk_tool_v2_phase1b_carrier_schema_diagnostic@1.0"
_ORIGINAL_READ_PARQUET = pd.read_parquet
_SCHEMA_DIAGNOSTIC_PATH: Path | None = None


def _diagnostic_path_from_argv(argv: list[str]) -> Path | None:
    try:
        index = argv.index("--out")
        value = argv[index + 1]
    except (ValueError, IndexError):
        return None
    if value != "/results/study":
        return None
    return Path(value) / SCHEMA_DIAGNOSTIC_NAME


def _safe_index_columns(value) -> list:
    if not isinstance(value, list):
        return []
    safe = []
    for item in value:
        if isinstance(item, str):
            safe.append(item)
        elif isinstance(item, dict):
            safe.append({key: item.get(key) for key in ("kind", "name") if key in item})
    return safe


def _safe_pandas_columns(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    safe = []
    for item in value:
        if not isinstance(item, dict):
            continue
        safe.append(
            {
                key: item.get(key)
                for key in ("name", "field_name", "pandas_type", "numpy_type")
                if key in item
            }
        )
    return safe


def _write_schema_diagnostic(parquet: pq.ParquetFile, missing: list[str]) -> None:
    path = _SCHEMA_DIAGNOSTIC_PATH
    if path is None:
        return
    schema = parquet.schema_arrow
    pandas_metadata = {}
    raw = (schema.metadata or {}).get(b"pandas")
    if raw:
        try:
            parsed = json.loads(raw.decode("utf-8"))
            if isinstance(parsed, dict):
                pandas_metadata = parsed
        except (UnicodeDecodeError, json.JSONDecodeError):
            pandas_metadata = {}

    diagnostic = {
        "schema_id": SCHEMA_DIAGNOSTIC_ID,
        "carrier_basename": "5m_offset_0.parquet",
        "required_logical_columns": list(REQUIRED_CARRIER_COLUMNS),
        "missing_required_physical_columns": list(missing),
        "physical_fields": [
            {"name": field.name, "type": str(field.type)}
            for field in schema
        ],
        "pandas_index_columns": _safe_index_columns(pandas_metadata.get("index_columns")),
        "pandas_columns": _safe_pandas_columns(pandas_metadata.get("columns")),
        "market_values_exported": False,
        "row_level_data_exported": False,
        "model_outputs_exported": False,
        "production_authority": False,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(diagnostic, indent=2, sort_keys=True) + "\n")


def _read_carrier_without_pandas_metadata(path, columns=None, **kwargs):
    candidate = Path(path)
    requested = tuple(columns) if columns is not None else None
    if candidate.name != "5m_offset_0.parquet" or requested != REQUIRED_CARRIER_COLUMNS:
        return _ORIGINAL_READ_PARQUET(path, columns=columns, **kwargs)

    parquet = pq.ParquetFile(candidate)
    physical_names = set(parquet.schema_arrow.names)
    missing = [name for name in REQUIRED_CARRIER_COLUMNS if name not in physical_names]
    if missing:
        _write_schema_diagnostic(parquet, missing)
        raise RuntimeError("carrier_physical_columns_missing:" + "-".join(missing))

    table = parquet.read(
        columns=list(REQUIRED_CARRIER_COLUMNS),
        use_pandas_metadata=False,
    )
    frame = table.to_pandas(ignore_metadata=True)
    if tuple(frame.columns) != REQUIRED_CARRIER_COLUMNS:
        raise RuntimeError("carrier_physical_projection_mismatch")
    return frame


def main() -> None:
    global _SCHEMA_DIAGNOSTIC_PATH
    _SCHEMA_DIAGNOSTIC_PATH = _diagnostic_path_from_argv(sys.argv[1:])
    ev.pd.read_parquet = _read_carrier_without_pandas_metadata
    try:
        ev.main()
    finally:
        ev.pd.read_parquet = _ORIGINAL_READ_PARQUET
        _SCHEMA_DIAGNOSTIC_PATH = None


if __name__ == "__main__":
    main()
