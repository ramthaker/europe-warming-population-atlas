"""Create the EURO-11 grid and a reproducible CMIP5 manifest from the catalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from shapely.geometry import mapping, Polygon

from build_tiles import open_zarr

GHSL_2020_URL = (
    "https://jrc-ghsl.s3.eu-central-1.amazonaws.com/ghs-pop/r2023a/54009/1000m/2020/"
    "GHS_POP_E2020_GLOBE_R2023A_54009_1000_V1_0.tif"
)
GRID_SELECTION = {
    "project_id": "cordex",
    "product": "output",
    "CORDEX_domain": "EUR-11",
    "institute_id": "CLMcom",
    "model_id": "CCLM4-8-17",
    "rcm_version_id": "v1",
    "frequency": "mon",
    "variable_id": "tas",
}
EXPERIMENTS = ("historical", "rcp45", "rcp85")
# These model pairs have complete monthly coverage through December 2100 in
# both RCP archives. The MOHC pair in the catalog ends during 2099.
COMPLETE_MODEL_PAIRS = {
    "CNRM-CERFACS-CNRM-CM5-r1i1p1",
    "ICHEC-EC-EARTH-r12i1p1",
    "MPI-M-MPI-ESM-LR-r1i1p1",
}


def catalog_runs(catalog_path: Path) -> list[dict[str, str]]:
    catalog = pd.read_csv(catalog_path)
    for column, expected in GRID_SELECTION.items():
        catalog = catalog[catalog[column] == expected]
    pivot = catalog.pivot_table(
        index=["driving_model_id", "member"],
        columns="experiment_id",
        values="path",
        aggfunc="first",
    )
    matched = pivot.dropna(subset=list(EXPERIMENTS))
    if matched.empty:
        raise ValueError("The catalog has no complete historical/RCP4.5/RCP8.5 model pairs for the selected grid.")

    runs: list[dict[str, str]] = []
    for (driving_model_id, member), row in matched.iterrows():
        runs.append({
            "model_id": f"{driving_model_id}-{member}",
            "historical": str(row["historical"]),
            "rcp45": str(row["rcp45"]),
            "rcp85": str(row["rcp85"]),
        })
    complete_runs = [run for run in runs if run["model_id"] in COMPLETE_MODEL_PAIRS]
    found = {run["model_id"] for run in complete_runs}
    if found != COMPLETE_MODEL_PAIRS:
        missing = sorted(COMPLETE_MODEL_PAIRS - found)
        raise ValueError(f"Catalog is missing expected complete model pairs: {', '.join(missing)}")
    return complete_runs


def grid_features(first_historical_run: str) -> dict[str, Any]:
    with open_zarr(first_historical_run) as dataset:
        if "lat_vertices" not in dataset or "lon_vertices" not in dataset:
            raise ValueError("Selected EURO-CORDEX run does not provide cell corner coordinates.")
        latitude = dataset["lat_vertices"].values
        longitude = dataset["lon_vertices"].values
        if latitude.shape != longitude.shape or latitude.ndim != 3 or latitude.shape[-1] < 3:
            raise ValueError("Expected latitude and longitude bounds with shape (rlat, rlon, vertices).")

    height, width, _ = latitude.shape
    features: list[dict[str, Any]] = []
    for y in range(height):
        for x in range(width):
            grid_index = y * width + x
            points = [
                (float(longitude[y, x, vertex]), float(latitude[y, x, vertex]))
                for vertex in range(longitude.shape[2])
            ]
            if not np.isfinite(np.asarray(points)).all():
                raise ValueError(f"Grid cell {grid_index} has non-finite corner coordinates.")
            if points[0] != points[-1]:
                points.append(points[0])
            polygon = Polygon(points)
            if polygon.is_empty or not polygon.is_valid or polygon.area == 0:
                raise ValueError(f"Grid cell {grid_index} has invalid corner coordinates.")
            features.append({
                "type": "Feature",
                "geometry": mapping(polygon),
                "properties": {
                    "cell_id": f"EUR11-{grid_index:06d}",
                    "grid_index": grid_index,
                },
            })
    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=Path("CORDEX.csv"))
    parser.add_argument("--manifest", type=Path, default=Path("data-manifest.json"))
    parser.add_argument("--grid", type=Path, default=Path("../data/euro11-grid.geojson"))
    args = parser.parse_args()

    runs = catalog_runs(args.catalog)
    features = grid_features(runs[0]["historical"])
    args.grid.parent.mkdir(parents=True, exist_ok=True)
    args.grid.write_text(json.dumps(features, separators=(",", ":")), encoding="utf-8")
    manifest = {
        "grid_geojson": str(args.grid),
        "population_raster": GHSL_2020_URL,
        "population_band": 1,
        "runs": runs,
    }
    args.manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {len(features['features']):,} EUR-11 cells and {len(runs)} matched model pairs.")
    print(f"Manifest: {args.manifest}; grid: {args.grid}")


if __name__ == "__main__":
    main()
