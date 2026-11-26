"""Compare semantic completion with the sparse LiDAR occupancy baseline."""

import argparse
import json
from pathlib import Path

import numpy as np


def occupancy_counts(occupied, truth, mask):
    pred = occupied[mask]
    target = truth[mask]
    return {
        "tp": int(np.count_nonzero(pred & target)),
        "fp": int(np.count_nonzero(pred & ~target)),
        "fn": int(np.count_nonzero(~pred & target)),
    }


def scores(counts):
    tp, fp, fn = (counts[key] for key in ("tp", "fp", "fn"))
    return {
        **counts,
        "iou": tp / (tp + fp + fn) if tp + fp + fn else None,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
    }


def compare_run(folder):
    run = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    observation, prediction, truth, valid = (
        np.load(folder / f"{name}.npy", allow_pickle=False)
        for name in ("observation", "prediction", "ground_truth", "valid_mask")
    )
    shape = tuple(run["shape_xyz"])
    if {array.shape for array in (observation, prediction, truth, valid)} != {shape}:
        raise ValueError(f"Array shape mismatch in {folder}")
    if valid.dtype != np.bool_ or int(valid.sum()) != run["valid_voxels"]:
        raise ValueError(f"Validity mask does not match the log in {folder}")
    if not np.isin(observation, [0, 1]).all() or int(observation.sum()) != run["observed_occupied_voxels"]:
        raise ValueError(f"Expected the recorded binary LiDAR occupancy in {folder}")

    hits = observation != 0
    occupied = prediction != 0
    target = truth != 0
    completion = scores(occupancy_counts(occupied, target, valid))
    if any(completion[key] != run[f"occupancy_{key}"] for key in ("tp", "fp", "fn")):
        raise ValueError(f"Recomputed occupancy counts do not match the log in {folder}")

    return {
        "scene": run["frame"]["scene"],
        "frame": run["frame"]["frame"],
        "valid_voxels": int(valid.sum()),
        "lidar_only": scores(occupancy_counts(hits, target, valid)),
        "completion": completion,
        "completion_without_lidar_hit": scores(occupancy_counts(occupied, target, valid & ~hits)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", type=Path, nargs="+", help="Directories produced by complete_scene.py")
    parser.add_argument("--output", type=Path, required=True, help="Comparison JSON path")
    args = parser.parse_args()
    frames = [compare_run(folder) for folder in args.runs]
    if len({(row["scene"], row["frame"]) for row in frames}) != len(frames):
        parser.error("each test frame must appear once")

    pooled = {
        name: scores({key: sum(row[name][key] for row in frames) for key in ("tp", "fp", "fn")})
        for name in ("lidar_only", "completion", "completion_without_lidar_hit")
    }
    comparison = {"frame_count": len(frames), "frames": frames, "pooled": pooled}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(pooled, indent=2))


if __name__ == "__main__":
    main()
