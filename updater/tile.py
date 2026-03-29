#!/usr/bin/env python3
"""
Spatial tiling for antenna data.

Reads per-state files from data/antennas/ and splits them into
spatial tiles of ~TARGET antennas each using recursive quadtree
subdivision. Outputs tiles + a manifest to data/tiles/.

Usage:
    uv run tile.py                  # Tile all states
    uv run tile.py --target 1000    # Custom target per tile (default: 1000)
"""

import argparse
import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
ANTENNAS_DIR = DATA_DIR / "antennas"
TILES_DIR = DATA_DIR / "tiles"

DEFAULT_TARGET = 1000


def quadtree_split(
    antennas: list[dict],
    target: int,
) -> list[tuple[list[dict], tuple[float, float, float, float]]]:
    """Recursively split antennas into spatial tiles.

    Uses median-based splitting to avoid degenerate quadtree behavior
    from outliers. Returns list of (antennas, bounds) leaf nodes.
    """
    if len(antennas) <= target:
        return [(antennas, compute_bounds(antennas))]

    # Split on the axis with more geographic spread
    lats = [a["lat"] for a in antennas]
    lons = [a["lon"] for a in antennas]
    lat_spread = max(lats) - min(lats)
    lon_spread = max(lons) - min(lons)

    # Use median for a balanced split
    if lat_spread >= lon_spread:
        key = "lat"
    else:
        key = "lon"

    sorted_antennas = sorted(antennas, key=lambda a: a[key])
    mid = len(sorted_antennas) // 2

    # Avoid splitting identical coordinates — advance past duplicates
    mid_val = sorted_antennas[mid][key]
    while mid < len(sorted_antennas) and sorted_antennas[mid][key] == mid_val:
        mid += 1

    # All antennas at the same coordinate on this axis — try the other axis
    if mid == 0 or mid >= len(sorted_antennas):
        other_key = "lon" if key == "lat" else "lat"
        sorted_antennas = sorted(antennas, key=lambda a: a[other_key])
        mid = len(sorted_antennas) // 2
        mid_val = sorted_antennas[mid][other_key]
        while mid < len(sorted_antennas) and sorted_antennas[mid][other_key] == mid_val:
            mid += 1

    # Truly can't split (all same coordinates)
    if mid == 0 or mid >= len(sorted_antennas):
        return [(antennas, compute_bounds(antennas))]

    left = sorted_antennas[:mid]
    right = sorted_antennas[mid:]

    result: list[tuple[list[dict], tuple[float, float, float, float]]] = []
    result.extend(quadtree_split(left, target))
    result.extend(quadtree_split(right, target))
    return result


def compute_bounds(antennas: list[dict]) -> tuple[float, float, float, float]:
    lats = [a["lat"] for a in antennas]
    lons = [a["lon"] for a in antennas]
    return (min(lats), min(lons), max(lats), max(lons))


def tile_state(uf: str, antennas: list[dict], target: int) -> list[dict]:
    """Tile one state's antennas. Returns manifest entries."""
    if not antennas:
        return []

    leaves = quadtree_split(antennas, target)

    entries = []
    for i, (tile_antennas, tile_bounds) in enumerate(leaves):
        filename = f"{uf}_{i}.json"
        out_path = TILES_DIR / filename
        out_path.write_text(
            json.dumps(tile_antennas, ensure_ascii=False),
            encoding="utf-8",
        )
        min_lat, min_lon, max_lat, max_lon = tile_bounds
        entries.append({
            "file": filename,
            "bounds": [[min_lat, min_lon], [max_lat, max_lon]],
            "count": len(tile_antennas),
        })

    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description="Tile antenna data spatially")
    parser.add_argument(
        "--target",
        type=int,
        default=DEFAULT_TARGET,
        help=f"Target antennas per tile (default: {DEFAULT_TARGET})",
    )
    args = parser.parse_args()

    TILES_DIR.mkdir(parents=True, exist_ok=True)

    # Clean old tiles
    for old in TILES_DIR.glob("*.json"):
        old.unlink()

    manifest: dict[str, list[dict]] = {}
    total_antennas = 0
    total_tiles = 0

    state_files = sorted(ANTENNAS_DIR.glob("*.json"))
    if not state_files:
        print("No antenna files found in data/antennas/", file=sys.stderr)
        sys.exit(1)

    for path in state_files:
        uf = path.stem
        antennas = json.loads(path.read_text(encoding="utf-8"))
        entries = tile_state(uf, antennas, args.target)
        manifest[uf] = entries
        n_antennas = sum(e["count"] for e in entries)
        total_antennas += n_antennas
        total_tiles += len(entries)

        sizes = [e["count"] for e in entries]
        print(
            f"  {uf}: {n_antennas:,} antennas → {len(entries)} tiles "
            f"(min {min(sizes):,}, max {max(sizes):,})",
            file=sys.stderr,
        )

    manifest_path = TILES_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )

    print(
        f"\n{total_antennas:,} antennas → {total_tiles} tiles "
        f"(target: {args.target})",
        file=sys.stderr,
    )
    print(f"Output: {TILES_DIR}/", file=sys.stderr)


if __name__ == "__main__":
    main()
