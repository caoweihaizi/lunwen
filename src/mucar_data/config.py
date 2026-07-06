from pathlib import Path

import yaml


REQUIRED_SECTIONS = {"project", "abilene", "worldpop", "timezone_boundaries", "orbit"}


def load_config(path: Path):
    with Path(path).open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    missing = REQUIRED_SECTIONS - set(config or {})
    if missing:
        raise ValueError(f"missing config sections: {sorted(missing)}")
    split_counts(1_000_000, config["project"]["time_split"])
    return config


def split_counts(total: int, fractions):
    if len(fractions) != 4 or abs(sum(fractions) - 1.0) > 1e-12:
        raise ValueError("time_split must contain four fractions summing to one")
    first = int(total * fractions[0])
    second = int(total * fractions[1])
    third = int(total * fractions[2])
    fourth = total - first - second - third
    return first, second, third, fourth
