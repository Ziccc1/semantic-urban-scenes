"""Run single-frame CarlaSC semantic scene completion and evaluate valid voxels."""

import argparse
import json
import sys
import tempfile
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

import numpy as np
import torch
import yaml


def prepare_frame(folder, label_map):
    params = json.loads((folder / "params.json").read_text(encoding="utf-8"))
    shape = tuple(int(size) for size in params["grid_size"])
    if params["coordinates"] != "cartesian" or shape != (128, 128, 8):
        raise ValueError("Expected the original CarlaSC Cartesian grid (128, 128, 8).")

    lower = np.asarray(params["min_bound"])
    upper = np.asarray(params["max_bound"])
    voxel_size = (upper - lower) / shape
    points = np.fromfile(folder / "velodyne.bin", dtype="<f4").reshape(-1, 4)[:, :3]
    in_bounds = ((points >= lower) & (points < upper)).all(axis=1)
    indices = np.floor((points[in_bounds] - lower) / voxel_size).astype(int)
    indices = np.clip(indices, 0, np.asarray(shape) - 1)
    observation = np.zeros(shape, dtype=np.uint8)
    observation[tuple(indices.T)] = 1

    raw_labels = np.fromfile(folder / "ground_truth.label", dtype="<u4").reshape(shape)
    counts = np.fromfile(folder / "eval_counts.bin", dtype="<f4").reshape(shape)
    if not np.isfinite(counts).all() or (counts < 0).any():
        raise ValueError("The evaluation counts must be finite and non-negative.")
    valid = counts > 0
    if not set(np.unique(raw_labels[valid])).issubset(label_map):
        raise ValueError("The ground truth contains an unmapped label in the evaluation region.")
    target = np.full(shape, 255, dtype=np.uint8)
    for raw_id, label_id in label_map.items():
        target[raw_labels == raw_id] = label_id
    if not observation.any() or not valid.any():
        raise ValueError("The paired frame must contain scan points and valid ground-truth voxels.")
    return observation, target, valid


def evaluate(prediction, target, valid, names):
    pred, gt = prediction[valid], target[valid]
    pred_occ, gt_occ = pred != 0, gt != 0
    tp = int((pred_occ & gt_occ).sum())
    fp = int((pred_occ & ~gt_occ).sum())
    fn = int((~pred_occ & gt_occ).sum())
    occupancy_iou = tp / (tp + fp + fn) if tp + fp + fn else None

    per_class = []
    for label_id, name in sorted(names.items()):
        if label_id == 0:
            continue
        pred_class, gt_class = pred == label_id, gt == label_id
        intersection = int((pred_class & gt_class).sum())
        union = int((pred_class | gt_class).sum())
        per_class.append({
            "id": label_id,
            "name": name,
            "intersection": intersection,
            "union": union,
            "iou": intersection / union if union else None,
        })
    class_ious = [row["iou"] for row in per_class if row["iou"] is not None]
    return {
        "valid_voxels": int(valid.sum()),
        "ignored_voxels": int((~valid).sum()),
        "occupancy_iou": occupancy_iou,
        "occupancy_tp": tp,
        "occupancy_fp": fp,
        "occupancy_fn": fn,
        "semantic_miou": sum(class_ious) / len(class_ious) if class_ious else None,
        "classes_in_miou": len(class_ious),
        "per_class_iou": per_class,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--frame-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error("--output must be a new directory")
    if not torch.cuda.is_available():
        parser.error("A CUDA-enabled PyTorch environment is required")

    sys.path.insert(0, str(args.upstream.resolve()))
    from layers.Voxel_Level.Con_Diffusion import Con_Diffusion

    config_path = args.upstream / "datasets" / "carla.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    names = config["label_to_names"]
    observation, target, valid = prepare_frame(args.frame_dir, config["learning_map"])
    frame = json.loads((args.frame_dir / "frame.json").read_text(encoding="utf-8"))

    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    state = checkpoint.pop("model")
    del checkpoint
    class_weights = state["multi_criterion.weight"]
    settings = SimpleNamespace(
        dataset="carla", num_classes=class_weights.numel(), batch_size=1,
        recon_loss=False, diffusion_steps=state["log_alpha"].numel(),
    )
    if sorted(names) != list(range(settings.num_classes)):
        raise ValueError("Checkpoint classes do not match the official remapped label table.")

    torch.manual_seed(args.seed)
    model = Con_Diffusion(settings, torch.nn.CrossEntropyLoss(weight=class_weights))
    model.load_state_dict(state, strict=True)
    del state
    model.eval().cuda()
    condition = torch.from_numpy(observation[None]).long().cuda()
    print(f"Completing {frame['scene']} frame {frame['frame']} using seed {args.seed}", flush=True)
    torch.cuda.reset_peak_memory_stats()
    start = perf_counter()
    with torch.inference_mode():
        prediction = model.sample(condition)[0].cpu().numpy()
    elapsed = perf_counter() - start

    if prediction.shape != target.shape or prediction.min() < 0 or prediction.max() >= settings.num_classes:
        raise ValueError("Unexpected prediction shape or semantic label range.")
    metrics = evaluate(prediction, target, valid, names)
    record = {
        "dataset": "CarlaSC Cartesian Test",
        "frame": frame,
        "checkpoint": args.checkpoint.name,
        "seed": args.seed,
        "batch_size": settings.batch_size,
        "diffusion_steps": settings.diffusion_steps,
        "shape_xyz": list(target.shape),
        "observed_occupied_voxels": int(observation.sum()),
        "elapsed_s": round(elapsed, 3),
        "peak_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20),
        "gpu": torch.cuda.get_device_name(),
        "torch": torch.__version__,
        "evaluation_mask": "Official evaluation counts > 0. Ignore counts == 0.",
        "semantic_average": "Mean over remapped IDs 1-10 with nonzero union; exclude Free (0).",
        **metrics,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        staging = Path(temp) / "sample"
        staging.mkdir()
        np.save(staging / "observation.npy", observation)
        np.save(staging / "prediction.npy", prediction)
        np.save(staging / "ground_truth.npy", target)
        np.save(staging / "valid_mask.npy", valid)
        (staging / "run.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        staging.rename(output)
    print(f"\nSaved completion and evaluation to {output}", flush=True)


if __name__ == "__main__":
    main()
