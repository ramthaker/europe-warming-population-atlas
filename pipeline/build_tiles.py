"""Build the derived climate/population PMTiles archive from a local manifest."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import xarray as xr
from encode_pmtiles import encode_archive
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.windows import from_bounds, transform as window_transform
from shapely.geometry import mapping, shape
from shapely.ops import transform as transform_geometry

BASELINE = (1981, 2000)
FUTURE_PERIODS = {"mid": (2041, 2060), "late": (2081, 2100)}
SCENARIOS = ("rcp45", "rcp85")


def period_mean(dataset: xr.Dataset, years: tuple[int, int]) -> np.ndarray:
    """Return annual-mean near-surface temperature for a closed year interval."""
    if "tas" not in dataset:
        raise ValueError("Expected the EURO-CORDEX variable 'tas'.")
    tas = dataset["tas"]
    if "time" not in tas.dims:
        raise ValueError("Expected 'tas' to have a time dimension.")
    time_year = tas.time.dt.year
    subset = tas.where((time_year >= years[0]) & (time_year <= years[1]), drop=True)
    if subset.sizes.get("time", 0) == 0:
        raise ValueError(f"No tas data found for {years[0]}–{years[1]}.")
    month_counts = subset.time.groupby("time.year").count()
    if bool((month_counts != 12).any()):
        raise ValueError(f"Expected 12 monthly tas values in every year from {years[0]}–{years[1]}.")
    weights = subset.time.dt.days_in_month
    annual_numerator = (subset * weights).groupby("time.year").sum("time", skipna=True)
    annual_denominator = weights.broadcast_like(subset).where(subset.notnull()).groupby("time.year").sum("time")
    annual = annual_numerator / annual_denominator
    if annual.sizes.get("year", 0) != years[1] - years[0] + 1:
        raise ValueError(f"Incomplete annual coverage for {years[0]}–{years[1]}.")
    values = annual.mean("year", skipna=True).values.astype("float64")
    units = str(tas.attrs.get("units", "")).lower().replace(" ", "")
    if units in {"k", "kelvin", "degrees_k", "degree_k"}:
        values -= 273.15
    elif units not in {"c", "degc", "degree_celsius", "degrees_celsius", "celsius"}:
        raise ValueError(f"Unsupported or missing tas units: {tas.attrs.get('units')!r}")
    return values


def same_spatial_grid(historical: xr.DataArray, future: xr.DataArray) -> bool:
    spatial_dims = tuple(dimension for dimension in historical.dims if dimension != "time")
    if spatial_dims != tuple(dimension for dimension in future.dims if dimension != "time"):
        return False
    for dimension in spatial_dims:
        if historical.sizes[dimension] != future.sizes[dimension]:
            return False
        if dimension in historical.coords or dimension in future.coords:
            if dimension not in historical.coords or dimension not in future.coords:
                return False
            if not np.array_equal(historical[dimension].values, future[dimension].values):
                return False
    for coordinate in set(historical.coords) | set(future.coords):
        if coordinate == "time":
            continue
        historical_has = coordinate in historical.coords
        future_has = coordinate in future.coords
        if historical_has != future_has:
            return False
        if historical_has:
            historical_coordinate = historical[coordinate]
            future_coordinate = future[coordinate]
            if "time" in historical_coordinate.dims or "time" in future_coordinate.dims:
                continue
            if set(historical_coordinate.dims) & set(spatial_dims):
                if historical_coordinate.dims != future_coordinate.dims:
                    return False
                if not np.array_equal(historical_coordinate.values, future_coordinate.values):
                    return False
    return True


def temperature_anomaly(baseline_celsius: np.ndarray, future_celsius: np.ndarray) -> np.ndarray:
    """Return future-minus-baseline temperature change in degrees Celsius."""
    if baseline_celsius.shape != future_celsius.shape:
        raise ValueError("Baseline and future temperature arrays must have the same shape.")
    return future_celsius - baseline_celsius


def open_zarr(path: str) -> xr.Dataset:
    storage_options = {"anon": True} if path.startswith("s3://") else None
    return xr.open_zarr(path, storage_options=storage_options, consolidated=None)


def summarize_runs(runs: list[dict[str, str]]) -> dict[str, dict[str, np.ndarray]]:
    if not runs:
        raise ValueError("The manifest must contain at least one matched model run.")
    deltas = {
        scenario: {period_name: [] for period_name in FUTURE_PERIODS}
        for scenario in SCENARIOS
    }
    for run in runs:
        model_id = run.get("model_id")
        if not model_id or not run.get("historical"):
            continue
        print(f"Reading baseline for {model_id}…", flush=True)
        with open_zarr(run["historical"]) as historical:
            if "tas" not in historical:
                raise ValueError(f"Matched run {model_id} is missing tas in its historical dataset.")
            baseline = period_mean(historical, BASELINE)
            for scenario in SCENARIOS:
                if not run.get(scenario):
                    continue
                print(f"Reading {scenario} projections for {model_id}…", flush=True)
                with open_zarr(run[scenario]) as future:
                    if "tas" not in future:
                        raise ValueError(f"Matched run {model_id} is missing tas in {scenario}.")
                    if not same_spatial_grid(historical["tas"], future["tas"]):
                        raise ValueError(f"Spatial grid mismatch for matched model {model_id} / {scenario}.")
                    for period_name, future_years in FUTURE_PERIODS.items():
                        projection = period_mean(future, future_years)
                        deltas[scenario][period_name].append(temperature_anomaly(baseline, projection))

    output: dict[str, dict[str, np.ndarray]] = {}
    for scenario in SCENARIOS:
        output[scenario] = {}
        for period_name, future_years in FUTURE_PERIODS.items():
            samples = deltas[scenario][period_name]
            if not samples:
                raise ValueError(f"No matched historical and {scenario} runs cover {future_years}.")
            stack = np.stack(samples, axis=0)
            output[scenario][period_name] = {
                "p10": np.nanpercentile(stack, 10, axis=0),
                "p50": np.nanpercentile(stack, 50, axis=0),
                "p90": np.nanpercentile(stack, 90, axis=0),
            }
    return output


def aggregate_population(
    features: list[dict[str, Any]], raster: rasterio.DatasetReader, band: int
) -> tuple[np.ndarray, float]:
    """Assign each population pixel by its center, then sum once per grid cell.

    The returned source total includes only valid pixels whose centers lie within
    the climate grid footprint. Pixels outside that footprint are intentionally
    excluded; shared cell borders cannot double-count a population pixel.
    """
    transformer = Transformer.from_crs("EPSG:4326", raster.crs, always_xy=True)
    projected = [transform_geometry(transformer.transform, shape(feature["geometry"])) for feature in features]
    bounds = [geom.bounds for geom in projected]
    left = min(item[0] for item in bounds)
    bottom = min(item[1] for item in bounds)
    right = max(item[2] for item in bounds)
    top = max(item[3] for item in bounds)
    window = from_bounds(left, bottom, right, top, raster.transform).round_offsets().round_lengths()
    window = window.intersection(rasterio.windows.Window(0, 0, raster.width, raster.height))
    if window.width <= 0 or window.height <= 0:
        raise ValueError("Climate grid does not overlap the population raster.")

    grid_indexes = [int(feature["properties"]["grid_index"]) for feature in features]
    if any(index < 0 for index in grid_indexes):
        raise ValueError("Climate grid_index values must be non-negative.")
    cell_ids = [index + 1 for index in grid_indexes]
    if len(set(cell_ids)) != len(cell_ids):
        raise ValueError("Climate grid_index values must be unique.")
    zones = rasterize(
        ((geom, cell_id) for geom, cell_id in zip(projected, cell_ids)),
        out_shape=(int(window.height), int(window.width)),
        transform=window_transform(window, raster.transform),
        fill=0,
        dtype="int32",
        all_touched=False,
    )
    values = np.ma.asarray(raster.read(band, window=window), dtype="float64")
    population = values.filled(np.nan)
    valid = np.isfinite(population)
    if raster.nodata is not None:
        valid &= population != raster.nodata
    valid &= population >= 0
    included = valid & (zones > 0)
    population_by_index = np.bincount(
        zones[included].astype("int64") - 1,
        weights=population[included],
        minlength=max(cell_ids),
    )
    totals = np.asarray([population_by_index[index] for index in grid_indexes], dtype="float64")
    source_total = float(population[included].sum())
    if not np.isclose(float(totals.sum()), source_total, rtol=1e-10, atol=1e-6):
        raise AssertionError("Population aggregation did not preserve the in-domain raster total.")
    return totals, source_total


def build_feature_collection(manifest: dict[str, Any]) -> dict[str, Any]:
    with Path(manifest["grid_geojson"]).open(encoding="utf-8") as handle:
        grid = json.load(handle)
    features = grid.get("features", [])
    if not features:
        raise ValueError("Grid GeoJSON contains no features.")
    for feature in features:
        props = feature.get("properties", {})
        if "cell_id" not in props or not isinstance(props.get("grid_index"), int):
            raise ValueError("Every grid feature needs cell_id and integer grid_index properties.")

    stats = summarize_runs(manifest.get("runs", []))
    raster_source = str(manifest["population_raster"])
    if raster_source.startswith("https://"):
        raster_source = f"/vsicurl/{raster_source}"
    elif not raster_source.startswith("/vsi"):
        raster_source = str(Path(raster_source))
    with rasterio.open(raster_source) as raster:
        band = int(manifest.get("population_band", 1))
        print("Aggregating GHSL population pixels by climate-cell center…", flush=True)
        population_counts, source_total = aggregate_population(features, raster, band)
        print(f"Population total within climate grid: {source_total:,.0f}", flush=True)
        for feature, population_count in zip(features, population_counts):
            props = feature["properties"]
            index = props["grid_index"]
            props["population_2020"] = float(population_count)
            for scenario in SCENARIOS:
                for period_name in FUTURE_PERIODS:
                    for percentile, values in stats[scenario][period_name].items():
                        flattened = values.reshape(-1)
                        if index < 0 or index >= flattened.size:
                            raise ValueError(f"grid_index {index} is outside the model array.")
                        value = float(flattened[index])
                        props[f"warming_{scenario}_{period_name}_{percentile}"] = value if math.isfinite(value) else None
            props.pop("grid_index", None)
    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with args.manifest.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    collection = build_feature_collection(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    geojson_path = args.output.with_suffix(".geojson")
    cell_count = len(collection["features"])
    population_total = sum(feature["properties"]["population_2020"] for feature in collection["features"])
    with geojson_path.open("w", encoding="utf-8") as handle:
        json.dump(collection, handle, separators=(",", ":"))
    del collection
    tile_count = encode_archive(geojson_path, args.output)
    print(f"Created {args.output} with {cell_count:,} climate cells in {tile_count:,} tiles; population total {population_total:,.0f}.")
    print(f"Preserved {population_total:,.0f} GHSL residents within the climate-grid footprint.")


if __name__ == "__main__":
    main()
