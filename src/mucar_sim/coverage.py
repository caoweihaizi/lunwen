import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Tuple

import numpy as np

from mucar_data.contracts import SimulationContract
from .orbit import PositionSnapshot


@dataclass(frozen=True, order=True)
class GroundRegion:
    region_id: str
    centroid_lat: float
    centroid_lon: float


@dataclass(frozen=True)
class AccessAssignment:
    region_id: str
    visible_count: int
    selected_sat_id: Optional[str]
    selected_elevation_deg: Optional[float]
    access_backlog: bool


def load_ground_regions(path: Path) -> Tuple[GroundRegion, ...]:
    path = Path(path)
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"region_id", "centroid_lat", "centroid_lon"}
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(f"ground region CSV missing fields: {sorted(required - set(reader.fieldnames or ())) }")
        regions = []
        seen = set()
        for row in reader:
            region_id = row["region_id"]
            if not region_id or region_id in seen:
                raise ValueError(f"duplicate or empty region_id: {region_id}")
            seen.add(region_id)
            try:
                latitude, longitude = float(row["centroid_lat"]), float(row["centroid_lon"])
            except ValueError as exc:
                raise ValueError(f"invalid coordinates for {region_id}") from exc
            if not math.isfinite(latitude) or not math.isfinite(longitude) or not -90 <= latitude <= 90 or not -180 <= longitude < 180:
                raise ValueError(f"coordinates outside canonical range for {region_id}")
            regions.append(GroundRegion(region_id, latitude, longitude))
    return tuple(sorted(regions))


def _ground_ecef(region: GroundRegion, radius_km: float):
    latitude, longitude = math.radians(region.centroid_lat), math.radians(region.centroid_lon)
    return radius_km * np.array([math.cos(latitude) * math.cos(longitude), math.cos(latitude) * math.sin(longitude), math.sin(latitude)])


def assign_access(contract: SimulationContract, positions: PositionSnapshot, regions: Sequence[GroundRegion]) -> Tuple[AccessAssignment, ...]:
    assignments = []
    for region in sorted(regions):
        ground = _ground_ecef(region, contract.earth.radius_km)
        line_of_sight = positions.ecef_km - ground
        lengths = np.linalg.norm(line_of_sight, axis=1)
        elevations = np.degrees(np.arcsin(np.clip((line_of_sight @ (ground / contract.earth.radius_km)) / lengths, -1.0, 1.0)))
        visible = np.flatnonzero(elevations >= contract.coverage.minimum_elevation_deg)
        if len(visible) == 0:
            assignments.append(AccessAssignment(region.region_id, 0, None, None, True))
            continue
        best_elevation = float(np.max(elevations[visible]))
        tied = [int(i) for i in visible if abs(float(elevations[i]) - best_elevation) <= 1e-12]
        best = min(tied, key=lambda i: positions.sat_ids[i])
        assignments.append(AccessAssignment(region.region_id, len(visible), positions.sat_ids[best], float(elevations[best]), False))
    return tuple(assignments)
