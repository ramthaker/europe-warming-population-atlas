"""Focused checks for climate calculations and population conservation."""

import unittest
from contextlib import nullcontext
from unittest.mock import patch

import cftime
import numpy as np
import pandas as pd
import rasterio
import xarray as xr
from affine import Affine
from rasterio.io import MemoryFile
from shapely.geometry import mapping, box

from build_tiles import aggregate_population, period_mean, same_spatial_grid, summarize_runs, temperature_anomaly


class ClimateCalculationTests(unittest.TestCase):
    def test_period_mean_converts_kelvin_to_celsius(self) -> None:
        time = pd.date_range("1981-01-01", "2000-12-01", freq="MS")
        values = np.full((len(time), 1, 1), 283.15)
        tas = xr.DataArray(values, dims=("time", "y", "x"), coords={"time": time})
        tas.attrs["units"] = "K"

        result = period_mean(xr.Dataset({"tas": tas}), (1981, 2000))

        np.testing.assert_allclose(result, [[10.0]], atol=1e-10)

    def test_period_mean_supports_360_day_calendar(self) -> None:
        time = [cftime.Datetime360Day(year, month, 1) for year in range(1981, 2001) for month in range(1, 13)]
        values = np.full((len(time), 1, 1), 283.15)
        tas = xr.DataArray(values, dims=("time", "y", "x"), coords={"time": time})
        tas.attrs["units"] = "K"

        result = period_mean(xr.Dataset({"tas": tas}), (1981, 2000))

        np.testing.assert_allclose(result, [[10.0]], atol=1e-10)

    def test_temperature_anomaly_is_future_minus_baseline(self) -> None:
        result = temperature_anomaly(np.array([[10.0, 12.5]]), np.array([[13.0, 11.0]]))

        np.testing.assert_allclose(result, [[3.0, -1.5]])

    def test_spatial_grid_comparison_checks_auxiliary_coordinates(self) -> None:
        historical = xr.DataArray(
            np.zeros((2, 2, 2)), dims=("time", "y", "x"),
            coords={"nav_lon": (("y", "x"), [[1, 2], [1, 2]])},
        )
        future = historical.copy(deep=True)
        future.coords["nav_lon"].values[0, 0] = 9

        self.assertFalse(same_spatial_grid(historical, future))

    def test_matched_runs_produce_ensemble_percentiles_for_each_scenario(self) -> None:
        historical_dates = pd.date_range("1981-01-01", "2000-12-01", freq="MS")
        future_dates = pd.date_range("2041-01-01", "2100-12-01", freq="MS")

        def dataset(dates: pd.DatetimeIndex, celsius: float) -> xr.Dataset:
            tas = xr.DataArray(
                np.full((len(dates), 1, 1), celsius + 273.15),
                dims=("time", "y", "x"), coords={"time": dates},
            )
            tas.attrs["units"] = "K"
            return xr.Dataset({"tas": tas})

        datasets = {
            "hist-a": dataset(historical_dates, 10), "hist-b": dataset(historical_dates, 10),
            "45-a": dataset(future_dates, 12), "45-b": dataset(future_dates, 14),
            "85-a": dataset(future_dates, 13), "85-b": dataset(future_dates, 17),
        }
        runs = [
            {"model_id": "a", "historical": "hist-a", "rcp45": "45-a", "rcp85": "85-a"},
            {"model_id": "b", "historical": "hist-b", "rcp45": "45-b", "rcp85": "85-b"},
        ]

        def open_dataset(path: str):
            return nullcontext(datasets[path])

        with patch("build_tiles.open_zarr", side_effect=open_dataset):
            result = summarize_runs(runs)

        np.testing.assert_allclose(result["rcp45"]["mid"]["p10"], [[2.2]], atol=1e-10)
        np.testing.assert_allclose(result["rcp45"]["mid"]["p50"], [[3.0]], atol=1e-10)
        np.testing.assert_allclose(result["rcp45"]["mid"]["p90"], [[3.8]], atol=1e-10)
        np.testing.assert_allclose(result["rcp85"]["late"]["p50"], [[5.0]], atol=1e-10)


class PopulationAggregationTests(unittest.TestCase):
    def test_adjacent_cells_assign_each_pixel_once_and_preserve_total(self) -> None:
        features = [
            {"type": "Feature", "geometry": mapping(box(0, 0, 1, 1)), "properties": {"grid_index": 0}},
            {"type": "Feature", "geometry": mapping(box(1, 0, 2, 1)), "properties": {"grid_index": 1}},
        ]
        profile = {
            "driver": "GTiff", "height": 1, "width": 2, "count": 1,
            "dtype": "int16", "crs": "EPSG:4326", "transform": Affine(1, 0, 0, 0, -1, 1),
            "nodata": -1,
        }
        with MemoryFile() as memory_file:
            with memory_file.open(**profile) as raster:
                raster.write(np.array([[2, 3]], dtype="int16"), 1)
                totals, source_total = aggregate_population(features, raster, 1)

        np.testing.assert_allclose(totals, [2, 3])
        self.assertEqual(source_total, 5)
        self.assertEqual(float(totals.sum()), source_total)


if __name__ == "__main__":
    unittest.main()
