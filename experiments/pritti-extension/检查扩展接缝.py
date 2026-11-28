"""Check a PrITTI ground raster pair after alignment into the same metric grid."""

import argparse
import json
from pathlib import Path

import numpy as np


def evaluate(before, after, road_ids, seam_axis, seam_edge, height_limit_m, *,
             seam_span=None, protected_height_limit_m=None):
    """Return provisional ground diagnostics with localized candidate cells."""
    old_labels, old_z, old_valid = (np.asarray(before[key]) for key in ("labels", "z_m", "valid"))
    labels, z, valid = (np.asarray(after[key]) for key in ("labels", "z_m", "valid"))
    protected = np.asarray(before["protected"])
    if labels.ndim != 2 or any(array.shape != labels.shape for array in
                               (old_labels, old_z, old_valid, z, valid, protected)):
        raise ValueError("All arrays must be aligned two-dimensional XY grids with equal shapes.")
    if any(mask.dtype != np.bool_ for mask in (old_valid, valid, protected)):
        raise ValueError("Valid and protected masks must be Boolean.")
    if not np.isfinite(old_z[old_valid]).all() or not np.isfinite(z[valid]).all():
        raise ValueError("Valid cells must have finite elevations in meters.")
    if seam_axis not in (0, 1) or not 0 < seam_edge < labels.shape[seam_axis]:
        raise ValueError("Seam must lie between cells inside the declared grid.")
    if not np.isfinite(height_limit_m) or height_limit_m < 0:
        raise ValueError("Height threshold must be finite and nonnegative.")

    length = labels.shape[1 - seam_axis]
    start, stop = seam_span if seam_span is not None else (0, length)
    if not 0 <= start < stop <= length:
        raise ValueError("Seam span must lie inside the declared grid.")
    if protected_height_limit_m is None:
        protected_height_limit_m = height_limit_m
    if not np.isfinite(protected_height_limit_m) or protected_height_limit_m < 0:
        raise ValueError("Protected height tolerance must be finite and nonnegative.")
    span = slice(start, stop)
    left = (seam_edge - 1, span) if seam_axis == 0 else (span, seam_edge - 1)
    right = (seam_edge, span) if seam_axis == 0 else (span, seam_edge)
    comparable = valid[left] & valid[right]
    left_road = np.isin(labels[left], road_ids)
    right_road = np.isin(labels[right], road_ids)
    candidates = comparable & (left_road | right_road)
    matched = comparable & left_road & right_road
    jumps = np.full(comparable.shape, np.nan)
    jumps[comparable] = np.abs(z[left][comparable] - z[right][comparable])
    both_valid = old_valid & valid
    height_changed = np.zeros(labels.shape, dtype=bool)
    height_changed[both_valid] = np.abs(old_z[both_valid] - z[both_valid]) > protected_height_limit_m
    changed = protected & ((old_valid != valid) | (both_valid & (old_labels != labels)) | height_changed)
    return {
        "seam_axis": seam_axis,
        "seam_edge": seam_edge,
        "height_threshold_m": height_limit_m,
        "comparable_pairs": int(comparable.sum()),
        "road_pairs": int(candidates.sum()),
        "road_match_fraction": float(matched.sum() / candidates.sum()) if candidates.any() else None,
        "road_mismatch_along_seam": (np.flatnonzero(candidates & ~matched) + start).tolist(),
        "height_p95_m": float(np.percentile(jumps[comparable], 95)) if comparable.any() else None,
        "height_jump_along_seam": (np.flatnonzero(jumps > height_limit_m) + start).tolist(),
        "protected_cells": int(protected.sum()),
        "protected_changed_fraction": float(changed.sum() / protected.sum()) if protected.any() else None,
        "protected_changed_xy": np.argwhere(changed).tolist(),
        "human_reviewed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--road-id", type=int, action="append", required=True)
    parser.add_argument("--axis", type=int, choices=(0, 1), required=True)
    parser.add_argument("--edge", type=int, required=True)
    parser.add_argument("--height-threshold-m", type=float, required=True)
    args = parser.parse_args()
    with np.load(args.before, allow_pickle=False) as before, np.load(args.after, allow_pickle=False) as after:
        result = evaluate(before, after, args.road_id, args.axis, args.edge, args.height_threshold_m)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
