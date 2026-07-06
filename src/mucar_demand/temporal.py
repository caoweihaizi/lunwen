import csv
import datetime as dt
import gzip
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional


@dataclass(frozen=True)
class TemporalSlot:
    timestamp_index: int
    timestamp: str
    timestamp_utc: dt.datetime
    total_demand_mbps: float
    global_intensity: float


def _timestamp(value: str):
    try:
        return dt.datetime.strptime(value, "%Y%m%d-%H%M").replace(tzinfo=dt.timezone.utc)
    except ValueError as exc:
        raise ValueError(f"invalid Abilene timestamp: {value}") from exc


def iter_temporal_slots(path: Path, expected_rows_per_slot: Optional[int] = 132) -> Iterator[TemporalSlot]:
    previous_slot = -1
    previous_time = None
    current_key = None
    current_values = None
    row_count = 0
    with gzip.open(Path(path), "rt", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"timestamp_index", "timestamp", "total_demand", "global_intensity"}
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(f"temporal file missing fields: {sorted(required - set(reader.fieldnames or ())) }")
        for row in reader:
            try:
                key = int(row["timestamp_index"])
                total = float(row["total_demand"])
                intensity = float(row["global_intensity"])
            except ValueError as exc:
                raise ValueError("invalid temporal numeric value") from exc
            values = (row["timestamp"], total, intensity)
            if not math.isfinite(total) or not math.isfinite(intensity) or total < 0 or intensity < 0:
                raise ValueError(f"non-finite or negative temporal value at slot {key}")
            if current_key is None:
                current_key, current_values, row_count = key, values, 1
            elif key == current_key:
                if values != current_values:
                    raise ValueError(f"inconsistent rows within slot {key}")
                row_count += 1
            else:
                if key != current_key + 1:
                    raise ValueError(f"non-contiguous slot index: {current_key} -> {key}")
                if expected_rows_per_slot is not None and row_count != expected_rows_per_slot:
                    raise ValueError(f"slot {current_key} has {row_count} rows")
                timestamp = _timestamp(current_values[0])
                if previous_time is not None and timestamp <= previous_time:
                    raise ValueError(f"timestamp is not strictly increasing at slot {current_key}")
                yield TemporalSlot(current_key, current_values[0], timestamp, current_values[1], current_values[2])
                previous_slot, previous_time = current_key, timestamp
                current_key, current_values, row_count = key, values, 1
        if current_key is None:
            raise ValueError("temporal file is empty")
        if expected_rows_per_slot is not None and row_count != expected_rows_per_slot:
            raise ValueError(f"slot {current_key} has {row_count} rows")
        timestamp = _timestamp(current_values[0])
        if previous_time is not None and timestamp <= previous_time:
            raise ValueError(f"timestamp is not strictly increasing at slot {current_key}")
        yield TemporalSlot(current_key, current_values[0], timestamp, current_values[1], current_values[2])
