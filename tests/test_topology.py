import unittest
from pathlib import Path

import numpy as np

from mucar_data.contracts import load_simulation_contract
from mucar_sim.constellation import build_walker_constellation
from mucar_sim.orbit import PositionSnapshot, propagate
from mucar_sim.topology import (
    build_operational_topology,
    build_planned_topology,
    earth_clearance,
    intra_plane_edge_keys,
)


ROOT = Path(__file__).resolve().parents[1]


class TopologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load_simulation_contract(ROOT / "configs/simulation_contract.yaml")
        cls.satellites = build_walker_constellation(cls.contract)

    def test_intra_plane_candidate_count_and_wraparound(self):
        edges = intra_plane_edge_keys(self.satellites)
        self.assertEqual(len(edges), 66)
        self.assertIn(("sat_p00_s00", "sat_p00_s10"), edges)

    def test_earth_clearance_rejects_diameter_and_tangent(self):
        radius = self.contract.earth.radius_km
        self.assertFalse(earth_clearance(np.array([radius + 1, 0, 0]), np.array([-radius - 1, 0, 0]), radius))
        self.assertFalse(earth_clearance(np.array([-1, radius, 0]), np.array([1, radius, 0]), radius))
        self.assertTrue(earth_clearance(np.array([-1, radius + 1, 0]), np.array([1, radius + 1, 0]), radius))

    def test_planned_topology_is_symmetric_bounded_and_has_no_seam(self):
        topology = build_planned_topology(self.contract, propagate(self.contract, self.satellites, 0), self.satellites)
        pairs = {(link.src, link.dst) for link in topology.directed_links}
        self.assertEqual(len(topology.nodes), 66)
        self.assertEqual(len(pairs), len(topology.directed_links))
        degree = {node: 0 for node in topology.nodes}
        latitude = {sat_id: float(propagate(self.contract, self.satellites, 0).latitude_deg[i]) for i, sat_id in enumerate(topology.nodes)}
        for link in topology.directed_links:
            self.assertNotEqual(link.src, link.dst)
            self.assertIn((link.dst, link.src), pairs)
            self.assertLessEqual(link.distance_km, self.contract.isl.max_distance_km)
            degree[link.src] += 1
            src_plane = int(link.src[5:7])
            dst_plane = int(link.dst[5:7])
            self.assertNotEqual({src_plane, dst_plane}, {0, 5})
            if link.link_type == "inter_plane":
                self.assertLessEqual(abs(latitude[link.src]), self.contract.isl.crosslink_max_abs_lat_deg)
                self.assertLessEqual(abs(latitude[link.dst]), self.contract.isl.crosslink_max_abs_lat_deg)
        self.assertLessEqual(max(degree.values()), 4)
        self.assertGreaterEqual(len(topology.directed_links), 132)

    def test_operational_topology_filters_both_directions_and_rejects_unknown_edges(self):
        planned = build_planned_topology(self.contract, propagate(self.contract, self.satellites, 0), self.satellites)
        self.assertEqual(build_operational_topology(planned, set()), planned)
        first = planned.directed_links[0]
        edge = tuple(sorted((first.src, first.dst)))
        operational = build_operational_topology(planned, {edge})
        self.assertEqual(len(operational.directed_links), len(planned.directed_links) - 2)
        with self.assertRaises(ValueError):
            build_operational_topology(planned, {("sat_p00_s00", "not-a-satellite")})
        with self.assertRaises(ValueError):
            build_operational_topology(planned, {(edge[1], edge[0])})
        with self.assertRaises(ValueError):
            build_operational_topology(planned, {(edge[0], edge[0])})


if __name__ == "__main__":
    unittest.main()
