#!/usr/bin/env python
"""
Demand-model sensitivity: does LFU's advantage survive when the request
generator stops being Zipf-shaped?

Reviewer concern (Major Comment 7): requests are drawn by weighting the
spatially reachable candidates with Zipf popularity weights. Sliding-window
LFU estimates exactly that weight, so LFU may be near-optimal *by
construction* and the reported SU deficit may be an artifact of the demand
model rather than a property of the spatial signal.

Decisive test: sweep the Zipf skew alpha down to 0. At alpha = 0 every item
carries identical popularity weight, so windowed popularity contains no rank
information at all and LFU's structural advantage is removed. If the SU-LFU
ordering persists at alpha = 0, the deficit is not a demand-model artifact.

Controlled configuration throughout (535 m segment, forward request radius
150 m, 130 vehicles at 7.7 m/s) -- identical to the Table 1 controlled cells,
so the alpha = 0.8 column reproduces the published Table 1 synthetic values.
"""
from __future__ import annotations

import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SEG = 535.0
N_ITEMS, CAP, R_REQ = 200, 20, 150.0
WARMUP, MEASURE = 150, 600
SEEDS = [84810, 15592, 4278, 98196, 37048, 33098, 30256, 19289, 97530, 14434]

ALPHAS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2]

POLICIES = [
    ("LRU", "lru", {}),
    ("LFU", "lfu", {"pop_window": 300.0}),
    ("Proximity", "proximity", {}),
    ("SU", "trajectory", {"urgency_weight": 0.2}),
    ("EDC", "expected_demand", {"r_req": R_REQ}),
]


def job(args):
    alpha, pname, pkey, kw, seed = args
    sys.path.insert(0, str(ROOT / "src"))
    from trajectorycache.cache import build_cache
    from trajectorycache.evaluation.metrics import compute_metrics
    from trajectorycache.simulation.runner import SimulationConfig, SimulationRunner

    cfg = SimulationConfig(
        road_length=SEG, active_zone_length=SEG, r_rel=R_REQ,
        n_vehicles=130, mean_speed=7.7, speed_std=3.0, platoon_size=10,
        unidirectional=True, n_items=N_ITEMS, zipf_alpha=alpha,
        cache_capacity=CAP, n_steps=MEASURE, warmup_steps=WARMUP, seed=seed,
    )
    mr = compute_metrics(
        SimulationRunner(build_cache(pkey, CAP, **kw), cfg).run()
    ).miss_rate * 100.0
    return alpha, pname, seed, mr


def main():
    t0 = time.time()
    jobs = [(a, pn, pk, kw, s) for a in ALPHAS
            for (pn, pk, kw) in POLICIES for s in SEEDS]
    raw: dict = {}
    with Pool(processes=12) as pool:
        for alpha, pn, seed, mr in pool.imap_unordered(job, jobs):
            raw.setdefault(alpha, {}).setdefault(pn, {})[seed] = mr

    out: dict = {}
    for a in ALPHAS:
        out[f"alpha_{a}"] = {
            p: {
                "mean": float(np.mean([raw[a][p][s] for s in SEEDS])),
                "std": float(np.std([raw[a][p][s] for s in SEEDS])),
                "per_seed": [round(raw[a][p][s], 4) for s in SEEDS],
            }
            for p in raw[a]
        }
    out["_meta"] = {
        "seeds": SEEDS, "alphas": ALPHAS, "tier": "synthetic",
        "segment_m": SEG, "r_request_m": R_REQ, "n_vehicles": 130,
        "mean_speed_mps": 7.7, "n_items": N_ITEMS, "capacity": CAP,
        "warmup": WARMUP, "measure": MEASURE,
        "note": "alpha=0 gives uniform item popularity (no rank signal for LFU)",
    }
    (ROOT / "experiments" / "results" / "zipf_sensitivity.json").write_text(
        json.dumps(out, indent=2)
    )

    print("=== ZIPF SKEW SENSITIVITY (synthetic, controlled config, 10 seeds) ===")
    hdr = f"{'alpha':>6s}" + "".join(f"{p:>11s}" for p, _, _ in POLICIES)
    print(hdr + f"{'SU-LFU':>9s}{'EDC-LFU':>9s}")
    for a in ALPHAS:
        row = f"{a:6.1f}"
        for p, _, _ in POLICIES:
            row += f"{out[f'alpha_{a}'][p]['mean']:11.2f}"
        su = out[f"alpha_{a}"]["SU"]["mean"]
        lfu = out[f"alpha_{a}"]["LFU"]["mean"]
        edc = out[f"alpha_{a}"]["EDC"]["mean"]
        row += f"{su-lfu:+9.2f}{edc-lfu:+9.2f}"
        print(row)
    print(f"\nElapsed {time.time()-t0:.0f}s. Saved zipf_sensitivity.json")


if __name__ == "__main__":
    main()
