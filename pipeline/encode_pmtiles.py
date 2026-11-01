"""Encode a climate GeoJSON FeatureCollection as a PMTiles v3 vector archive."""

from __future__ import annotations

import argparse
import gzip
import json
from collections import defaultdict
from pathlib import Path

import mapbox_vector_tile
import mercantile
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import Writer
from shapely.geometry import box, mapping, shape
from shapely.ops import transform
from pyproj import Transformer

WEB_MERCATOR = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
MAX_LATITUDE = 85.0511287798066
EXTENT = 4096
BUFFER = 64


def encode_archive(source: Path, destination: Path, max_zoom: int = 8) -> int:
    with source.open(encoding="utf-8") as handle:
        collection = json.load(handle)
    features = collection.get("features", [])
    if not features:
        raise ValueError("The GeoJSON collection has no features.")

    # Index one zoom at a time to bound memory while keeping tile IDs ordered.
    def tiles_for_zoom(zoom: int) -> dict[tuple[int, int, int], list[dict]]:
        zoom_tiles: dict[tuple[int, int, int], list[dict]] = defaultdict(list)
        for index, feature in enumerate(features, start=1):
            geom_wgs84 = shape(feature["geometry"])
            geom_mercator = transform(WEB_MERCATOR.transform, geom_wgs84)
            min_lon, min_lat, max_lon, max_lat = geom_wgs84.bounds
            min_lat, max_lat = max(-MAX_LATITUDE, min_lat), min(MAX_LATITUDE, max_lat)
            properties = feature["properties"]
            feature_id = index
            for tile in mercantile.tiles(min_lon, min_lat, max_lon, max_lat, zoom):
                tile_key = (tile.z, tile.x, tile.y)
                tile_bounds = mercantile.xy_bounds(tile)
                tile_width = tile_bounds.right - tile_bounds.left
                buffer = tile_width * BUFFER / EXTENT
                clip_bounds = box(
                    tile_bounds.left - buffer,
                    tile_bounds.bottom - buffer,
                    tile_bounds.right + buffer,
                    tile_bounds.top + buffer,
                )
                clipped = geom_mercator.intersection(clip_bounds)
                if not clipped.is_empty:
                    zoom_tiles[tile_key].append({
                        "id": feature_id,
                        "properties": properties,
                        "geometry": mapping(clipped),
                    })
            if index % 50000 == 0:
                print(f"Indexed zoom {zoom}: {index:,}/{len(features):,} cells…", flush=True)
        return zoom_tiles

    destination.parent.mkdir(parents=True, exist_ok=True)
    min_lon = min(shape(feature["geometry"]).bounds[0] for feature in features)
    min_lat = min(shape(feature["geometry"]).bounds[1] for feature in features)
    max_lon = max(shape(feature["geometry"]).bounds[2] for feature in features)
    max_lat = max(shape(feature["geometry"]).bounds[3] for feature in features)
    header = {
        "tile_type": TileType.MVT,
        "tile_compression": Compression.GZIP,
        "min_lon_e7": int(min_lon * 10_000_000),
        "min_lat_e7": int(min_lat * 10_000_000),
        "max_lon_e7": int(max_lon * 10_000_000),
        "max_lat_e7": int(max_lat * 10_000_000),
        "center_lon_e7": int(((min_lon + max_lon) / 2) * 10_000_000),
        "center_lat_e7": int(((min_lat + max_lat) / 2) * 10_000_000),
        "center_zoom": 3,
    }
    metadata = {
        "name": "Europe warming and population",
        "description": "EURO-CORDEX CMIP5 temperature changes and GHSL 2020 population by climate grid cell.",
        "attribution": "EURO-CORDEX; GHSL (European Commission, Joint Research Centre)",
        "version": "1.0.0",
        "type": "overlay",
        "format": "pbf",
        "minzoom": 4,
        "maxzoom": max_zoom,
        "bounds": [min_lon, min_lat, max_lon, max_lat],
        "center": [(min_lon + max_lon) / 2, (min_lat + max_lat) / 2, 3],
        "vector_layers": [{
            "id": "climate_cells",
            "description": "EURO-CORDEX grid cell warming ensemble and GHSL 2020 population.",
            "minzoom": 4,
            "maxzoom": max_zoom,
            "fields": {
                "cell_id": "Number",
                "population_2020": "Number",
                **{
                    f"warming_{scenario}_{period}_{percentile}": "Number"
                    for scenario in ("rcp45", "rcp85")
                    for period in ("mid", "late")
                    for percentile in ("p10", "p50", "p90")
                },
            },
        }],
    }
    count = 0
    with destination.open("wb") as output:
        writer = Writer(output)
        for zoom in range(4, max_zoom + 1):
            zoom_tiles = tiles_for_zoom(zoom)
            for (tile_zoom, x, y), tile_features in sorted(
                zoom_tiles.items(), key=lambda item: zxy_to_tileid(*item[0])
            ):
                bounds = mercantile.xy_bounds(x, y, tile_zoom)
                tile_width = bounds.right - bounds.left
                buffer = tile_width * BUFFER / EXTENT
                quantize_bounds = (
                    bounds.left - buffer,
                    bounds.bottom - buffer,
                    bounds.right + buffer,
                    bounds.top + buffer,
                )
                tile_data = mapbox_vector_tile.encode(
                    {"name": "climate_cells", "features": tile_features},
                    default_options={"quantize_bounds": quantize_bounds, "extents": EXTENT},
                )
                writer.write_tile(zxy_to_tileid(tile_zoom, x, y), gzip.compress(tile_data, mtime=0))
                count += 1
                if count % 5000 == 0:
                    print(f"Encoded {count:,} vector tiles…", flush=True)
        writer.finalize(header, metadata)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Input climate GeoJSON")
    parser.add_argument("destination", type=Path, help="Output .pmtiles archive")
    parser.add_argument("--max-zoom", type=int, default=8)
    args = parser.parse_args()
    count = encode_archive(args.source, args.destination, args.max_zoom)
    print(f"Created {args.destination} with {count:,} vector tiles.")


if __name__ == "__main__":
    main()
