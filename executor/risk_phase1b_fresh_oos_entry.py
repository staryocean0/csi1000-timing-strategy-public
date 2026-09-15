"""Technical entry adapter for the frozen Risk Tool v2 Phase-1B fresh-OOS evaluator.

This module changes only physical Parquet loading. It bypasses legacy pandas
metadata when reading the already-accepted carrier, then delegates all science
to the frozen evaluator module.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

import risk_phase1b_fresh_oos_eval as ev

REQUIRED_CARRIER_COLUMNS = ("datetime", "symbol", "close")
_ORIGINAL_READ_PARQUET = pd.read_parquet


def _read_carrier_without_pandas_metadata(path, columns=None, **kwargs):
    candidate = Path(path)
    requested = tuple(columns) if columns is not None else None
    if candidate.name != "5m_offset_0.parquet" or requested != REQUIRED_CARRIER_COLUMNS:
        return _ORIGINAL_READ_PARQUET(path, columns=columns, **kwargs)

    parquet = pq.ParquetFile(candidate)
    physical_names = set(parquet.schema_arrow.names)
    missing = [name for name in REQUIRED_CARRIER_COLUMNS if name not in physical_names]
    if missing:
        raise RuntimeError("carrier_physical_columns_missing:" + "-".join(missing))

    table = pq.read_table(
        candidate,
        columns=list(REQUIRED_CARRIER_COLUMNS),
        use_pandas_metadata=False,
    )
    frame = table.to_pandas(ignore_metadata=True)
    if tuple(frame.columns) != REQUIRED_CARRIER_COLUMNS:
        raise RuntimeError("carrier_physical_projection_mismatch")
    return frame


def main() -> None:
    ev.pd.read_parquet = _read_carrier_without_pandas_metadata
    try:
        ev.main()
    finally:
        ev.pd.read_parquet = _ORIGINAL_READ_PARQUET


if __name__ == "__main__":
    main()
