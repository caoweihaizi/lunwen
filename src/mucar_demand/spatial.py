import csv
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np

from .config import ActivityConfig, DemandContract


@dataclass(frozen=True, order=True)
class DemandRegion:
    region_id: str
    centroid_lat: float
    centroid_lon: float
    population: float
    timezone: str
    population_weight: float


def activity_multiplier(local_hour: float, config: ActivityConfig) -> float:
    if not math.isfinite(local_hour):
        raise ValueError("local_hour must be finite")
    return config.floor + config.amplitude * (0.5 + 0.5 * math.cos(2 * math.pi * (local_hour - config.peak_local_hour) / config.period_hours))


def load_demand_regions(path: Path) -> Tuple[DemandRegion, ...]:
    with Path(path).open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"region_id", "centroid_lat", "centroid_lon", "population", "timezone", "population_weight"}
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(f"region file missing fields: {sorted(required - set(reader.fieldnames or ())) }")
        regions, seen = [], set()
        for row in reader:
            region_id = row["region_id"]
            if not region_id or region_id in seen:
                raise ValueError(f"duplicate or empty region_id: {region_id}")
            seen.add(region_id)
            try:
                region = DemandRegion(region_id, float(row["centroid_lat"]), float(row["centroid_lon"]), float(row["population"]), row["timezone"], float(row["population_weight"]))
                ZoneInfo(region.timezone)
            except (ValueError, ZoneInfoNotFoundError) as exc:
                raise ValueError(f"invalid region {region_id}: {exc}") from exc
            values = (region.centroid_lat, region.centroid_lon, region.population, region.population_weight)
            if not all(math.isfinite(value) for value in values) or region.population < 0 or region.population_weight < 0:
                raise ValueError(f"invalid numeric values for {region_id}")
            regions.append(region)
    regions.sort()
    if abs(sum(region.population_weight for region in regions) - 1.0) > 1e-8:
        raise ValueError("population weights do not sum to one")
    return tuple(regions)


def spatial_weights(regions: Sequence[DemandRegion], timestamp_utc: datetime, contract: DemandContract):
    if timestamp_utc.tzinfo is None or timestamp_utc.utcoffset() is None:
        raise ValueError("timestamp_utc must be timezone-aware")
    raw = []
    for region in regions:
        local = timestamp_utc.astimezone(ZoneInfo(region.timezone))
        hour = local.hour + local.minute / 60.0 + local.second / 3600.0
        raw.append(region.population_weight * activity_multiplier(hour, contract.activity))
    weights = np.asarray(raw, dtype=np.float64)
    total = float(weights.sum())
    if not math.isfinite(total) or total <= 0:
        raise ValueError("spatial weights cannot be normalized")
    weights /= total
    weights.flags.writeable = False
    return weights
