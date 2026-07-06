import math
from dataclasses import dataclass
from typing import Callable, Mapping, Tuple


@dataclass(frozen=True)
class CalibrationResult:
    scale: float
    statistic: float
    iterations: int
    trace: Tuple[Tuple[float, float], ...]


def calibrate_demand_scale(evaluate: Callable[[float], float], config: Mapping[str, object]):
    lower, upper = float(config["search_min"]), float(config["search_max"])
    target = float(config["target"])
    accepted_min, accepted_max = float(config["accepted_min"]), float(config["accepted_max"])
    max_iterations, tolerance = int(config["max_iterations"]), float(config["relative_tolerance"])
    lower_value, upper_value = float(evaluate(lower)), float(evaluate(upper))
    if not all(math.isfinite(value) for value in (lower_value, upper_value)):
        raise ValueError("calibration evaluator returned a non-finite value")
    if lower_value > accepted_max or upper_value < accepted_min:
        raise ValueError("calibration target is not bracketed by frozen search bounds")
    trace = [(lower, lower_value), (upper, upper_value)]
    best = min(trace, key=lambda item: abs(item[1] - target))
    for iteration in range(1, max_iterations + 1):
        midpoint = (lower + upper) / 2.0
        value = float(evaluate(midpoint))
        if not math.isfinite(value):
            raise ValueError("calibration evaluator returned a non-finite value")
        trace.append((midpoint, value))
        if abs(value - target) < abs(best[1] - target):
            best = (midpoint, value)
        if accepted_min <= value <= accepted_max and abs(value - target) / target <= tolerance:
            return CalibrationResult(midpoint, value, iteration, tuple(trace))
        if value < target:
            lower = midpoint
        else:
            upper = midpoint
    if accepted_min <= best[1] <= accepted_max:
        return CalibrationResult(best[0], best[1], max_iterations, tuple(trace))
    raise ValueError("calibration did not reach the accepted interval within max_iterations")
