#!/bin/sh
set -e
tmp=$(mktemp) || exit 1
trap 'rm -f "$tmp"' EXIT

# Legacy root files
for f in antennas.json population.json; do
  [ -f "$f" ] && { jq -c . "$f" >"$tmp" && mv "$tmp" "$f"; }
done

# Per-state antenna files
for f in data/antennas/*.json; do
  [ -f "$f" ] && { jq -c . "$f" >"$tmp" && mv "$tmp" "$f"; }
done

# Population + municipalities index
for f in data/population.json data/municipalities.json; do
  [ -f "$f" ] && { jq -c . "$f" >"$tmp" && mv "$tmp" "$f"; }
done

# Stats files
for f in data/stats/*.json; do
  [ -f "$f" ] && { jq -c . "$f" >"$tmp" && mv "$tmp" "$f"; }
done

# Tile files
for f in data/tiles/*.json; do
  [ -f "$f" ] && { jq -c . "$f" >"$tmp" && mv "$tmp" "$f"; }
done
