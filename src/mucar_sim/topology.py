from dataclasses import dataclass
from typing import AbstractSet, Dict, Sequence, Tuple

import numpy as np

from mucar_data.contracts import SimulationContract
from .constellation import Satellite
from .orbit import PositionSnapshot


@dataclass(frozen=True, order=True)
class DirectedLink:
    src: str
    dst: str
    distance_km: float
    propagation_delay_s: float
    link_type: str


@dataclass(frozen=True)
class TopologySnapshot:
    time_s: int
    nodes: Tuple[str, ...]
    directed_links: Tuple[DirectedLink, ...]


def _edge_key(left: str, right: str) -> Tuple[str, str]:
    if left == right:
        raise ValueError("self-loop edge is invalid")
    return tuple(sorted((left, right)))


def intra_plane_edge_keys(satellites: Sequence[Satellite]):
    by_plane: Dict[int, Dict[int, str]] = {}
    for satellite in satellites:
        by_plane.setdefault(satellite.plane, {})[satellite.slot] = satellite.sat_id
    edges = set()
    for slots in by_plane.values():
        count = len(slots)
        if set(slots) != set(range(count)):
            raise ValueError("plane slots must be contiguous from zero")
        for slot, sat_id in slots.items():
            edges.add(_edge_key(sat_id, slots[(slot + 1) % count]))
    return tuple(sorted(edges))


def earth_clearance(left, right, earth_radius_km: float) -> bool:
    a, b = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    if a.shape != (3,) or b.shape != (3,) or not np.all(np.isfinite([a, b])):
        raise ValueError("endpoints must be finite three-dimensional vectors")
    direction = b - a
    denominator = float(np.dot(direction, direction))
    if denominator == 0:
        raise ValueError("link endpoints must differ")
    fraction = min(1.0, max(0.0, -float(np.dot(a, direction)) / denominator))
    closest = a + fraction * direction
    return float(np.linalg.norm(closest)) > earth_radius_km


def _eligible(contract, positions, left_index, right_index):
    left, right = positions.eci_km[left_index], positions.eci_km[right_index]
    distance = float(np.linalg.norm(right - left))
    return distance if (
        distance <= contract.isl.max_distance_km
        and earth_clearance(left, right, contract.earth.radius_km)
    ) else None


def build_planned_topology(contract: SimulationContract, positions: PositionSnapshot, satellites: Sequence[Satellite]) -> TopologySnapshot:
    nodes = tuple(satellite.sat_id for satellite in satellites)
    if positions.sat_ids != nodes or len(nodes) != contract.total_satellites:
        raise ValueError("position and satellite order differ")
    index = {sat_id: position for position, sat_id in enumerate(nodes)}
    undirected = {}
    for edge in intra_plane_edge_keys(satellites):
        distance = _eligible(contract, positions, index[edge[0]], index[edge[1]])
        if distance is None:
            raise ValueError(f"intra-plane edge violates visibility contract: {edge}")
        undirected[edge] = (distance, "intra_plane")
    planes = {plane: [s for s in satellites if s.plane == plane] for plane in range(contract.planes)}
    latitude = {sat_id: float(positions.latitude_deg[i]) for i, sat_id in enumerate(nodes)}
    for left_plane in range(contract.planes - 1):
        right_plane = left_plane + 1
        candidates = {}
        for left in planes[left_plane]:
            if abs(latitude[left.sat_id]) > contract.isl.crosslink_max_abs_lat_deg:
                continue
            for right in planes[right_plane]:
                if abs(latitude[right.sat_id]) > contract.isl.crosslink_max_abs_lat_deg:
                    continue
                distance = _eligible(contract, positions, index[left.sat_id], index[right.sat_id])
                if distance is not None:
                    candidates[(left.sat_id, right.sat_id)] = distance
        left_choice = {}
        for left in planes[left_plane]:
            options = [(distance, right) for (candidate_left, right), distance in candidates.items() if candidate_left == left.sat_id]
            if options:
                left_choice[left.sat_id] = min(options)[1]
        right_choice = {}
        for right in planes[right_plane]:
            options = [(distance, left) for (left, candidate_right), distance in candidates.items() if candidate_right == right.sat_id]
            if options:
                right_choice[right.sat_id] = min(options)[1]
        for left, right in left_choice.items():
            if right_choice.get(right) == left:
                undirected[_edge_key(left, right)] = (candidates[(left, right)], "inter_plane")
    links = []
    for (left, right), (distance, link_type) in sorted(undirected.items()):
        delay = distance / contract.earth.light_speed_km_s
        links.extend((DirectedLink(left, right, distance, delay, link_type), DirectedLink(right, left, distance, delay, link_type)))
    links.sort(key=lambda link: (link.src, link.dst))
    degree = {node: 0 for node in nodes}
    for link in links:
        degree[link.src] += 1
    if max(degree.values(), default=0) > contract.isl.intra_plane_neighbors + contract.isl.inter_plane_neighbors_max:
        raise ValueError("planned topology exceeds degree contract")
    return TopologySnapshot(positions.time_s, nodes, tuple(links))


def build_operational_topology(planned: TopologySnapshot, unavailable_undirected_edges: AbstractSet[Tuple[str, str]]) -> TopologySnapshot:
    planned_edges = {_edge_key(link.src, link.dst) for link in planned.directed_links}
    failures = set()
    for edge in unavailable_undirected_edges:
        if not isinstance(edge, tuple) or len(edge) != 2 or edge != tuple(sorted(edge)):
            raise ValueError(f"failure edge must be a canonical tuple: {edge}")
        key = _edge_key(*edge)
        if key not in planned_edges:
            raise ValueError(f"failure edge not present in planned topology: {edge}")
        failures.add(key)
    links = tuple(link for link in planned.directed_links if _edge_key(link.src, link.dst) not in failures)
    return TopologySnapshot(planned.time_s, planned.nodes, links)
