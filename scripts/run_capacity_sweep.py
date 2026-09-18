#!/usr/bin/env python
"""
Cache-capacity sensitivity.

Reviewer concern (Minor Comment 4): the manuscript fixes the cache at 20 items
out of a 200-item catalog (a 10 % ratio) without justifying that this ratio is
representative or showing that conclusions survive other capacities.

This sweep holds the catalog at 200 items and varies the capacity across
2.5 %, 5 %, 10 % (the published setting), 20 %, 30 % and 50 % of the catalog,
under the controlled configuration used for Table 1. All eight policies are
run so that the full ranking, not just the SU-LFU margin, can be checked for
stability.
"""
from __future__ import annotations

import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from scipy.stats import kendalltau

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SEG = 535.0
N_ITEMS, R_REQ, ZIPF = 200, 150.0, 0.8
WARMUP, MEASURE = 150, 600
SEEDS = [84810, 15592, 4278, 98196, 37048, 33098, 30256, 19289, 97530, 14434]

CAPACITIES = [5, 10, 20, 40, 60, 100]

POLICIES = [
    ("LRU", "lru", {}),
    ("FIFO", "fifo", {}),
    ("Random", "random", {}),
    ("LFU", "lfu", {"pop_window": 300.0}),
    ("Proximity", "proximity", {}),
    ("SU", "trajectory", {"urgency_weight": 0.2}),
    ("EDC", "expected_demand", {"r_req": R_REQ}),
    ("QLearning", "qlearning", {"lr": 0.05}),
]


def job(args):
    cap, pname, pkey, kw, seed = args
    sys.path.insert(0, str(ROOT / "src"))
    from trajectorycache.cache import build_cache
    from trajectorycache.evaluation.metrics import compute_metrics
    from trajectorycache.simulation.runner import SimulationConfig, SimulationRunner

    cfg = SimulationConfig(
        road_length=SEG, active_zone_length=SEG, r_rel=R_REQ,
        n_vehicles=130, mean_speed=7.7, speed_std=3.0, platoon_size=10,
        unidirectional=True, n_items=N_ITEMS, zipf_alpha=ZIPF,
        cache_capacity=cap, n_steps=MEASURE, warmup_steps=WARMUP, seed=seed,
    )
    mr = compute_metrics(
        SimulationRunner(build_cache(pkey, cap, **kw), cfg).run()
    ).miss_rate * 100.0
    return cap, pname, seed, mr


def main():
    t0 = time.time()
    jobs = [(c, pn, pk, kw, s) for c in CAPACITIES
            for (pn, pk, kw) in POLICIES for s in SEEDS]
    raw: dict = {}
    with Pool(processes=12) as pool:
        for cap, pn, seed, mr in pool.imap_unordered(job, jobs):
            raw.setdefault(cap, {}).setdefault(pn, {})[seed] = mr

    out: dict = {}
    for c in CAPACITIES:
        out[f"cap_{c}"] = {
            p: {"mean": float(np.mean([raw[c][p][s] for s in SEEDS])),
                "std": float(np.std([raw[c][p][s] for s in SEEDS])),
                "per_seed": [round(raw[c][p][s], 4) for s in SEEDS]}
            for p in raw[c]
        }

    names = [p for p, _, _ in POLICIES]
    ref = [out[f"cap_20"][p]["mean"] for p in names]
    taus = {}
    for c in CAPACITIES:
        cur = [out[f"cap_{c}"][p]["mean"] for p in names]
        taus[str(c)] = float(kendalltau(ref, cur).correlation)

    out["_meta"] = {
        "seeds": SEEDS, "capacities": CAPACITIES, "n_items": N_ITEMS,
        "capacity_ratios_pct": [100.0 * c / N_ITEMS for c in CAPACITIES],
        "kendall_tau_vs_cap20": taus, "segment_m": SEG, "r_request_m": R_REQ,
        "n_vehicles": 130, "mean_speed_mps": 7.7, "zipf_alpha": ZIPF,
        "warmup": WARMUP, "measure": MEASURE,
    }
    (ROOT / "experiments" / "results" / "capacity_sweep.json").write_text(
        json.dumps(out, indent=2)
    )

    print("=== CACHE-CAPACITY SENSITIVITY (controlled config, 10 seeds) ===")
    hdr = f"{'C_max':>6s}{'ratio':>7s}" + "".join(f"{p:>11s}" for p in names)
    print(hdr + f"{'SU-LFU':>9s}{'EDC-LFU':>9s}{'tau':>7s}")
    for c in CAPACITIES:
        row = f"{c:6d}{100.0*c/N_ITEMS:6.1f}%"
        for p in names:
            row += f"{out[f'cap_{c}'][p]['mean']:11.2f}"
        su = out[f"cap_{c}"]["SU"]["mean"]
        lfu = out[f"cap_{c}"]["LFU"]["mean"]
        edc = out[f"cap_{c}"]["EDC"]["mean"]
        row += f"{su-lfu:+9.2f}{edc-lfu:+9.2f}{taus[str(c)]:7.2f}"
        print(row)
    print(f"\nElapsed {time.time()-t0:.0f}s. Saved capacity_sweep.json")


if __name__ == "__main__":
    main()
