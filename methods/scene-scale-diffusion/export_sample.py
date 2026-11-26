"""Export an unconditional CarlaSC run as a platform sample package."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import numpy as np


# Remapped label IDs and colors from the Scene-Scale Diffusion carla.yaml.
LABELS = (
    ("Free", "#FFFFFF"),
    ("Building", "#FFC800"),
    ("Barrier", "#FF7832"),
    ("Other", "#375A50"),
    ("Pedestrian", "#FF1E1E"),
    ("Pole", "#FFF096"),
    ("Road", "#FF00FF"),
    ("Ground", "#AF004B"),
    ("Sidewalk", "#4B004B"),
    ("Vegetation", "#00AF00"),
    ("Vehicle", "#6496F5"),
)
GRID_SHAPE = (128, 128, 8)
MIN_BOUND = (-25.6, -25.6, -2.0)
VOXEL_SIZE = (0.4, 0.4, 0.375)
AXIS_SIGNS = (1, -1, 1)


def write_json(path, value, *, compact=False):
    options = {"separators": (",", ":")} if compact else {"indent": 2}
    path.write_text(json.dumps(value, **options) + "\n", encoding="utf-8")


def export_sample(run_dir, output, code_version):
    if output.exists():
        raise FileExistsError(f"Sample directory already exists: {output}")

    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    if run["dataset"] != "CarlaSC Cartesian":
        raise ValueError("This exporter requires a CarlaSC Cartesian run.")

    volume = np.load(run_dir / "voxels.npy", allow_pickle=False)
    if volume.shape != GRID_SHAPE or tuple(run["shape_xyz"]) != GRID_SHAPE:
        raise ValueError(f"Expected a CarlaSC volume with shape {GRID_SHAPE}.")
    if volume.dtype.kind not in "iu" or volume.min() < 0 or volume.max() >= len(LABELS):
        raise ValueError("Volume contains an invalid semantic label.")
    counts = np.bincount(volume.ravel().astype(np.intp, copy=False), minlength=len(LABELS))
    if counts.tolist() != run["label_counts"]:
        raise ValueError("The run log and semantic volume have different label counts.")

    indices = np.argwhere(volume != 0)
    centers = ((indices + 0.5) * VOXEL_SIZE + MIN_BOUND) * AXIS_SIGNS
    label_ids = volume[tuple(indices.T)]
    points = [
        [*xyz, int(label_id)]
        for xyz, label_id in zip(centers.round(4).tolist(), label_ids, strict=True)
    ]

    spatial = {
        "native_axis_order": ["x", "y", "z"],
        "native_shape_xyz": list(GRID_SHAPE),
        "native_voxel_size_xyz": list(VOXEL_SIZE),
        "coordinate_transform": {
            "native_frame": "CARLA ego sensor, left-handed, x forward, y right, z up",
            "display_frame": "right-handed, x forward, y left, z up",
            "unit": "m",
            "native_min_bound_xyz": list(MIN_BOUND),
            "axis_sign_xyz": list(AXIS_SIGNS),
            "index_to_center": "display_xyz = (native_min_bound_xyz + (index_xyz + 0.5) * native_voxel_size_xyz) * axis_sign_xyz",
        },
    }
    sample_id = f"carla-seed-{run['seed']}"
    manifest = {
        "schema_version": "1.0",
        "method": "scene_scale_diffusion",
        "sample_id": sample_id,
        "task": "generation",
        "provenance": {
            "dataset": run["dataset"],
            "code_version": code_version,
            "weights": run["checkpoint"],
            "config_path": "source/config.json",
            "log_path": "source/run.json",
        },
        "labels": [
            {"id": index, "name": name, "color": color, "role": "empty" if index == 0 else "semantic"}
            for index, (name, color) in enumerate(LABELS)
        ],
        "states": [{
            "id": "generated",
            "role": "output",
            "format": "voxel_points_json",
            "path": "display/generated.json",
            "native_path": "source/voxels.npy",
            **spatial,
        }],
    }
    config = {
        "sample_id": sample_id,
        "seed": run["seed"],
        "batch_size": run["batch_size"],
        "diffusion_steps": run["diffusion_steps"],
        "native_dtype": str(volume.dtype),
        **spatial,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        package = Path(temp) / "sample"
        (package / "source").mkdir(parents=True)
        (package / "display").mkdir()
        shutil.copyfile(run_dir / "voxels.npy", package / "source/voxels.npy")
        shutil.copyfile(run_dir / "run.json", package / "source/run.json")
        write_json(package / "source/config.json", config)
        write_json(package / "display/generated.json", {"voxel_size_xyz": VOXEL_SIZE, "points": points}, compact=True)
        write_json(package / "manifest.json", manifest)
        package.rename(output)
    print(f"Exported {sample_id} with {len(points)} occupied voxels to {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True, help="Directory containing voxels.npy and run.json")
    parser.add_argument("--output", type=Path, required=True, help="New platform sample directory")
    parser.add_argument("--code-version", required=True, help="Upstream model code commit used by the run")
    args = parser.parse_args()
    export_sample(args.run_dir, args.output.resolve(), args.code_version)


if __name__ == "__main__":
    main()
