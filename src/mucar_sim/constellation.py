from dataclasses import dataclass
from typing import Tuple

from mucar_data.contracts import SimulationContract


@dataclass(frozen=True, order=True)
class Satellite:
    sat_id: str
    plane: int
    slot: int
    raan_deg: float
    phase_deg: float


def build_walker_constellation(contract: SimulationContract) -> Tuple[Satellite, ...]:
    satellites = []
    for plane in range(contract.planes):
        for slot in range(contract.satellites_per_plane):
            index = plane * contract.satellites_per_plane + slot
            satellites.append(Satellite(
                sat_id=f"sat_p{plane:02d}_s{slot:02d}",
                plane=plane,
                slot=slot,
                raan_deg=float(contract.raan_deg[plane]),
                phase_deg=float(contract.phase_deg[index]),
            ))
    if len(satellites) != contract.total_satellites:
        raise ValueError("Walker constellation size differs from contract")
    return tuple(satellites)
