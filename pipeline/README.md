# Data pipeline

The pipeline reads the monthly EURO-CORDEX Zarr runs and GHSL population raster, creates scenario deltas for matched historical/future model pairs, and encodes a vector PMTiles archive. `encode_pmtiles.py` writes Mapbox vector tiles using the PMTiles Python library; Tippecanoe is not required.

## Inputs

Create `data-manifest.json` (do not commit it if it contains local paths). The file must have this shape:

```json
{
  "grid_geojson": "../data/euro11-grid.geojson",
  "population_raster": "../data/GHS_POP_E2020_GLOBE_R2023A_54009_1000_V1_0.tif",
  "population_band": 1,
  "runs": [
    {
      "model_id": "model-pair-01",
      "historical": "s3://euro-cordex/path/to/historical.zarr",
      "rcp45": "s3://euro-cordex/path/to/rcp45.zarr",
      "rcp85": "s3://euro-cordex/path/to/rcp85.zarr"
    }
  ]
}
```

`grid_geojson` must contain one polygon per climate grid cell with `cell_id` and integer `grid_index` properties. `grid_index` is the flattened `y, x` index for the `tas` values in the selected EURO-CORDEX archive. Keep only paired historical/RCP runs with the same grid. Confirm paths, coordinates, time coverage, and original source-use terms in the downloaded catalog before running.

The population raster can be the 1 km GHSL 2020 product in EPSG:54009. The script reprojects the grid cells into the raster CRS and assigns each raster pixel by its center, so no population pixel is counted by two cells. It expects population counts rather than density values and checks that aggregated cell totals equal the valid GHSL pixel total inside the climate-grid footprint. Pixels outside the model domain are excluded.

## Build

Install the Python dependencies, then run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python build_tiles.py --manifest data-manifest.json --output ../data/climate-cells.pmtiles
```

The script writes an intermediate GeoJSON next to the PMTiles archive, then encodes zoom levels 4–8 to keep low-zoom tiles a practical size. The resulting vector layer is named `climate_cells` and contains `cell_id`, `population_2020`, and `warming_{scenario}_{period}_{p10|p50|p90}` properties. Units are degrees Celsius of change. To build tiles independently from an existing feature collection, run `python encode_pmtiles.py ../data/climate-cells.geojson ../data/climate-cells.pmtiles`.

Run the focused calculation checks with `python -m unittest test_build_tiles.py` from this directory. They cover Kelvin conversion, future-minus-baseline anomaly direction, spatial-coordinate pairing, and unique population pixel assignment with total preservation.
