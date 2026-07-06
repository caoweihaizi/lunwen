from dataclasses import dataclass
from typing import Sequence, Tuple

import numpy as np


def _weights(values, size, name, require_normalized=True):
    array = np.asarray(values, dtype=np.float64).copy()
    if array.shape != (size,) or not np.all(np.isfinite(array)) or np.any(array < 0):
        raise ValueError(f"{name} must be a finite nonnegative vector of length {size}")
    if require_normalized and abs(float(array.sum()) - 1.0) > 1e-12:
        raise ValueError(f"{name} must sum to one")
    array.flags.writeable = False
    return array


@dataclass(frozen=True)
class FactorizedOD:
    region_ids: Tuple[str, ...]
    coefficient_mbps: float
    origin_factors: np.ndarray
    destination_factors: np.ndarray

    @classmethod
    def from_weights(cls, total_mbps: float, region_ids: Sequence[str], origin_weights, destination_weights):
        ids = tuple(region_ids)
        if len(ids) < 2 or len(set(ids)) != len(ids) or not np.isfinite(total_mbps) or total_mbps < 0:
            raise ValueError("invalid total or region IDs")
        origin = _weights(origin_weights, len(ids), "origin_weights")
        destination = _weights(destination_weights, len(ids), "destination_weights")
        normalizer = float(origin.sum() * destination.sum() - np.dot(origin, destination))
        if normalizer <= 0:
            raise ValueError("non-self OD normalizer must be positive")
        return cls(ids, float(total_mbps) / normalizer, origin, destination)

    @property
    def total_mbps(self):
        return self.coefficient_mbps * float(self.origin_factors.sum() * self.destination_factors.sum() - np.dot(self.origin_factors, self.destination_factors))

    def flow(self, src_region: str, dst_region: str):
        if src_region == dst_region:
            return 0.0
        index = {region_id: i for i, region_id in enumerate(self.region_ids)}
        try:
            left, right = index[src_region], index[dst_region]
        except KeyError as exc:
            raise KeyError(f"unknown region: {exc.args[0]}") from exc
        return self.coefficient_mbps * self.origin_factors[left] * self.destination_factors[right]

    def materialize(self):
        matrix = self.coefficient_mbps * np.outer(self.origin_factors, self.destination_factors)
        np.fill_diagonal(matrix, 0.0)
        return matrix

    def with_origin_multipliers(self, multipliers):
        values = _weights(multipliers, len(self.region_ids), "multipliers", require_normalized=False)
        origin = np.asarray(self.origin_factors * values, dtype=np.float64)
        origin.flags.writeable = False
        return FactorizedOD(self.region_ids, self.coefficient_mbps, origin, self.destination_factors)
