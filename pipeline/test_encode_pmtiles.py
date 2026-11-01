"""Focused checks for the generated PMTiles archive format."""

import gzip
import json
import tempfile
import unittest
from pathlib import Path

import mapbox_vector_tile
import mercantile
from pmtiles.reader import MemorySource, Reader

from encode_pmtiles import encode_archive


class EncodePmtilesTests(unittest.TestCase):
    def test_archive_keeps_cell_properties_and_vector_layer_metadata(self) -> None:
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[14, 52], [16, 52], [16, 54], [14, 54], [14, 52]]],
            },
            "properties": {
                "cell_id": "EUR11-000001",
                "population_2020": 12,
                "warming_rcp45_mid_p50": 1.25,
            },
        }
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            source = Path(folder) / "cells.geojson"
            archive = Path(folder) / "cells.pmtiles"
            source.write_text(json.dumps({"type": "FeatureCollection", "features": [feature]}), encoding="utf-8")

            tile_count = encode_archive(source, archive, max_zoom=4)

            reader = Reader(MemorySource(archive.read_bytes()))
            self.assertEqual(reader.header()["min_zoom"], 4)
            self.assertEqual(reader.header()["max_zoom"], 4)
            self.assertEqual(reader.metadata()["vector_layers"][0]["id"], "climate_cells")
            tile = mercantile.tile(15, 53, 4)
            encoded = reader.get(tile.z, tile.x, tile.y)

            self.assertIsNotNone(encoded)
            decoded = mapbox_vector_tile.decode(gzip.decompress(encoded))
            properties = decoded["climate_cells"]["features"][0]["properties"]
            self.assertEqual(properties["cell_id"], "EUR11-000001")
            self.assertEqual(properties["population_2020"], 12)
            self.assertEqual(properties["warming_rcp45_mid_p50"], 1.25)
            self.assertGreater(tile_count, 0)


if __name__ == "__main__":
    unittest.main()
