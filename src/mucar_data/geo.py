import math
from typing import Iterable, Optional
from pathlib import Path


def normalize_longitude(longitude: float) -> float:
    value = (float(longitude) + 180.0) % 360.0 - 180.0
    return 0.0 if value == -0.0 else value


def normalize_population(values: Iterable[float], nodata: Optional[float] = None):
    cleaned = []
    valid = []
    for raw in values:
        value = float(raw)
        is_valid = math.isfinite(value) and value >= 0 and not (
            nodata is not None and value == float(nodata)
        )
        valid.append(is_valid)
        cleaned.append(value if is_valid else 0.0)
    total = sum(cleaned)
    if total <= 0:
        raise ValueError("valid population total must be positive")
    return [value / total for value in cleaned], valid


def aggregate_population_grid(path: Path, grid_degrees: float = 5.0):
    import numpy as np
    import rasterio

    if 360 % grid_degrees != 0 or 180 % grid_degrees != 0:
        raise ValueError("grid_degrees must divide both 360 and 180")
    sums = {}
    invalid_cell_count = 0
    valid_cell_count = 0
    with rasterio.open(path) as source:
        if source.count != 1 or source.crs is None or source.crs.to_epsg() != 4326:
            raise ValueError("population raster must be single-band EPSG:4326")
        nodata = source.nodata
        for _, window in source.block_windows(1):
            values = source.read(1, window=window).astype("float64", copy=False)
            valid = np.isfinite(values) & (values >= 0)
            if nodata is not None:
                valid &= values != nodata
            invalid_cell_count += int(values.size - valid.sum())
            valid_cell_count += int(valid.sum())
            rows, cols = np.nonzero(valid & (values > 0))
            if not len(rows):
                continue
            global_rows = rows + int(window.row_off)
            global_cols = cols + int(window.col_off)
            xs = source.transform.c + (global_cols + 0.5) * source.transform.a
            ys = source.transform.f + (global_rows + 0.5) * source.transform.e
            lon_bins = np.floor((xs + 180.0) / grid_degrees).astype(int)
            lat_bins = np.floor((ys + 90.0) / grid_degrees).astype(int)
            lon_bins = np.clip(lon_bins, 0, int(360 / grid_degrees) - 1)
            lat_bins = np.clip(lat_bins, 0, int(180 / grid_degrees) - 1)
            for lon_bin, lat_bin, value in zip(lon_bins, lat_bins, values[rows, cols]):
                key = (int(lon_bin), int(lat_bin))
                sums[key] = sums.get(key, 0.0) + float(value)
        raster_metadata = {
            "crs": source.crs.to_string(), "width": source.width, "height": source.height,
            "nodata": nodata, "transform": tuple(source.transform), "bounds": tuple(source.bounds),
        }
    total = sum(sums.values())
    if total <= 0:
        raise ValueError("population raster has no positive valid population")
    regions = []
    for (lon_bin, lat_bin), population in sorted(sums.items(), key=lambda item: (item[0][1], item[0][0])):
        regions.append({
            "region_id": f"g{grid_degrees:g}_{lat_bin:02d}_{lon_bin:03d}",
            "centroid_lat": -90.0 + (lat_bin + 0.5) * grid_degrees,
            "centroid_lon": -180.0 + (lon_bin + 0.5) * grid_degrees,
            "population": population,
            "population_weight": population / total,
        })
    return regions, {
        **raster_metadata,
        "grid_degrees": grid_degrees,
        "region_count": len(regions),
        "valid_cell_count": valid_cell_count,
        "invalid_cell_count": invalid_cell_count,
        "valid_population_total": total,
        "population_weight_sum": sum(item["population_weight"] for item in regions),
    }


def assign_timezones(regions, features):
    from shapely.geometry import Point, shape
    from shapely.strtree import STRtree

    geometries = [shape(feature["geometry"]) for feature in features]
    tzids = [feature["properties"]["tzid"] for feature in features]
    tree = STRtree(geometries)
    output = []
    unmatched = 0
    nearest_distances = []
    for region in regions:
        point = Point(normalize_longitude(region["centroid_lon"]), region["centroid_lat"])
        matches = tree.query(point, predicate="intersects")
        if len(matches):
            timezone_name = tzids[int(matches[0])]
            match_method = "intersects"
            distance = 0.0
        else:
            unmatched += 1
            index = int(tree.nearest(point))
            timezone_name = tzids[index]
            match_method = "nearest"
            distance = float(point.distance(geometries[index]))
            nearest_distances.append(distance)
        output.append({**region, "timezone": timezone_name, "timezone_match": match_method})
    return output, {
        "timezone_feature_count": len(features),
        "unmatched_region_count": unmatched,
        "maximum_nearest_distance_degrees": max(nearest_distances, default=0.0),
    }
