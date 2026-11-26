"""Run one unconditional CarlaSC sample with the upstream discrete model."""

import argparse
import json
import sys
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

import numpy as np
import torch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()

    if not torch.cuda.is_available():
        parser.error("A CUDA-enabled PyTorch environment is required.")
    if not (args.upstream / "layers" / "Voxel_Level" / "Gen_Diffusion.py").is_file():
        parser.error("--upstream must point to the official source directory.")
    if args.output.exists():
        parser.error("--output must be a new directory.")

    sys.path.insert(0, str(args.upstream.resolve()))
    from layers.Voxel_Level.Gen_Diffusion import Diffusion

    state = torch.load(args.checkpoint, map_location="cpu", weights_only=True)["model"]
    class_weights = state["multi_criterion.weight"]
    config = SimpleNamespace(
        num_classes=class_weights.numel(),
        diffusion_steps=state["log_alpha"].numel(),
        batch_size=1,
        recon_loss=False,
    )
    torch.manual_seed(args.seed)
    model = Diffusion(config, torch.nn.CrossEntropyLoss(weight=class_weights))
    model.load_state_dict(state, strict=True)
    del state
    model.eval().cuda()

    shape = (128, 128, 8)
    print(f"Sampling seed {args.seed} on {torch.cuda.get_device_name()}", flush=True)
    torch.cuda.reset_peak_memory_stats()
    start = perf_counter()
    with torch.inference_mode():
        # Upstream sample() uses this tensor only to determine the spatial shape.
        shape_reference = torch.empty((1, *shape), dtype=torch.uint8)
        voxels = model.sample(shape_reference)[0].cpu().numpy()
    elapsed = perf_counter() - start

    if voxels.shape != shape or voxels.min() < 0 or voxels.max() >= config.num_classes:
        raise ValueError(f"Unexpected sampled volume with shape {voxels.shape}")
    args.output.mkdir(parents=True)
    np.save(args.output / "voxels.npy", voxels)
    record = {
        "dataset": "CarlaSC Cartesian",
        "checkpoint": args.checkpoint.name,
        "seed": args.seed,
        "shape_xyz": list(shape),
        "batch_size": config.batch_size,
        "diffusion_steps": config.diffusion_steps,
        "label_counts": np.bincount(voxels.ravel(), minlength=config.num_classes).tolist(),
        "elapsed_s": round(elapsed, 3),
        "peak_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20),
        "gpu": torch.cuda.get_device_name(),
        "torch": torch.__version__,
    }
    (args.output / "run.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"\nSaved {args.output / 'voxels.npy'} in {elapsed:.1f} s", flush=True)


if __name__ == "__main__":
    main()
