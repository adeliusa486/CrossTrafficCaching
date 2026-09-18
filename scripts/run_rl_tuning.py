#!/usr/bin/env python
"""
Learning-rate sweep for the online linear temporal-difference baseline.

Reviewer concern (Major Comment 9): the QLearningCache baseline reaches a miss
rate near 80 %, and while the manuscript acknowledges that only one online
learner is evaluated, the surrounding discussion can be read as a statement
about learning-based caching in general.

This sweep establishes the narrower, defensible claim. We vary the learning
rate over four orders of magnitude under the controlled configuration and
record the best miss rate the learner attains. If the poor result were an
artifact of a single badly chosen step size, some setting in this range should
recover it. The purpose is not to produce a competitive learned policy: a
properly tuned deep reinforcement learning baseline remains outside the scope
of this paper and is stated as such in the limitations.

The learner is a linear TD rule over the features [U(f), P(f), 1], trained
online within each seed from a fixed initialization.
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
N_ITEMS, CAP, R_REQ, ZIPF = 200, 20, 150.0, 0.8
WARMUP, MEASURE = 150, 600
SEEDS = [84810, 15592, 4278, 98196, 37048, 33098, 30256, 19289, 97530, 14434]

LEARNING_RATES = [0.0, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.3]


def job(args):
    kind, lr, seed = args
    sys.path.insert(0, str(ROOT / "src"))
    from trajectorycache.cache import build_cache
    from trajectorycache.evaluation.metrics import compute_metrics
    from trajectorycache.simulation.runner import SimulationConfig, SimulationRunner

    cfg = SimulationConfig(
        road_length=SEG, active_zone_length=SEG, r_rel=R_REQ,
        n_vehicles=130, mean_speed=7.7, speed_std=3.0, platoon_size=10,
        unidirectional=True, n_items=N_ITEMS, zipf_alpha=ZIPF,
        cache_capacity=CAP, n_steps=MEASURE, warmup_steps=WARMUP, seed=seed,
    )
    if kind == "LFU":
        cache = build_cache("lfu", CAP, pop_window=300.0)
    else:
        cache = build_cache("qlearning", CAP, lr=lr)
    mr = compute_metrics(SimulationRunner(cache, cfg).run()).miss_rate * 100.0
    return kind, lr, seed, mr


def main():
    t0 = time.time()
    jobs = [("LFU", 0.0, s) for s in SEEDS]
    jobs += [("QL", lr, s) for lr in LEARNING_RATES for s in SEEDS]

    raw: dict = {}
    with Pool(processes=12) as pool:
        for kind, lr, seed, mr in pool.imap_unordered(job, jobs):
            raw.setdefault((kind, lr), {})[seed] = mr

    def agg(key):
        vals = [raw[key][s] for s in SEEDS]
        return {"mean": float(np.mean(vals)), "std": float(np.std(vals)),
                "per_seed": [round(v, 4) for v in vals]}

    lfu = agg(("LFU", 0.0))
    out = {"LFU_reference": lfu,
           "by_lr": {str(lr): agg(("QL", lr)) for lr in LEARNING_RATES},
           "_meta": {"seeds": SEEDS, "learning_rates": LEARNING_RATES,
                     "config": "controlled 535 m", "r_request_m": R_REQ,
                     "n_items": N_ITEMS, "capacity": CAP, "zipf_alpha": ZIPF,
                     "warmup": WARMUP, "measure": MEASURE,
                     "note": "lr=0 freezes the initial weights [0.30, 0.70, 0.0]"}}
    (ROOT / "experiments" / "results" / "rl_tuning.json").write_text(
        json.dumps(out, indent=2)
    )

    print("=== ONLINE LINEAR TD: LEARNING-RATE SWEEP (controlled config) ===")
    print(f"LFU reference: {lfu['mean']:.2f} +/- {lfu['std']:.2f}\n")
    print(f"{'lr':>8s}{'miss %':>10s}{'std':>7s}{'vs LFU':>9s}")
    best = None
    for lr in LEARNING_RATES:
        d = out["by_lr"][str(lr)]
        margin = d["mean"] - lfu["mean"]
        print(f"{lr:8.4f}{d['mean']:10.2f}{d['std']:7.2f}{margin:+9.2f}")
        if best is None or d["mean"] < best[1]:
            best = (lr, d["mean"])
    print(f"\nBest learning rate {best[0]} -> {best[1]:.2f} % miss "
          f"({best[1]-lfu['mean']:+.2f} pp vs LFU)")
    print(f"\nElapsed {time.time()-t0:.0f}s. Saved rl_tuning.json")


if __name__ == "__main__":
    main()
