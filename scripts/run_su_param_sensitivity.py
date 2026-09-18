#!/usr/bin/env python
"""
Internal-parameter sensitivity of the spatial-urgency policy.

Reviewer concern (Major Comment 2): the manuscript analyses the scenario-side
request radius in depth while SU's own parameters -- the prediction horizon
T_pred, the blend weight W, and the TTE decay constant alpha_d -- are held
fixed. If the paper's subject is configuration sensitivity, SU's internal
configuration deserves the same treatment.

This script performs a one-at-a-time sweep of each internal parameter around
the operating point (T_pred = 30 s, W = 0.2, alpha_d = 0.1, r_rel^SU = 800 m)
under the CONTROLLED configuration used for Table 1, so that every cell is
directly comparable with the published SU value of 55.57 % and the LFU
reference of 53.25 %.

The question each sweep answers is not "which setting is best for SU" but
"does any setting of SU's own parameters recover the reported advantage over
LFU under a deployment-realistic request radius".
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

BASE = {"urgency_weight": 0.2, "t_pred": 30.0, "alpha_d": 0.1, "r_rel": 800.0}

SWEEPS = {
    "t_pred":         [5.0, 10.0, 20.0, 30.0, 45.0, 60.0, 90.0, 120.0],
    "urgency_weight": [0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0],
    "alpha_d":        [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0],
    "r_rel":          [50.0, 100.0, 150.0, 250.0, 400.0, 800.0, 1200.0],
}


def job(args):
    param, value, seed = args
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
    if param == "LFU":
        cache = build_cache("lfu", CAP, pop_window=300.0)
    else:
        kw = dict(BASE)
        kw[param] = value
        cache = build_cache("trajectory", CAP, **kw)
    mr = compute_metrics(SimulationRunner(cache, cfg).run()).miss_rate * 100.0
    return param, value, seed, mr


def main():
    t0 = time.time()
    jobs = [("LFU", 0.0, s) for s in SEEDS]
    for param, values in SWEEPS.items():
        for v in values:
            for s in SEEDS:
                jobs.append((param, v, s))

    raw: dict = {}
    with Pool(processes=12) as pool:
        for param, value, seed, mr in pool.imap_unordered(job, jobs):
            raw.setdefault(param, {}).setdefault(value, {})[seed] = mr

    def agg(param, value):
        vals = [raw[param][value][s] for s in SEEDS]
        return {"mean": float(np.mean(vals)), "std": float(np.std(vals)),
                "per_seed": [round(v, 4) for v in vals]}

    lfu = agg("LFU", 0.0)
    out = {"LFU_reference": lfu, "sweeps": {}}
    for param, values in SWEEPS.items():
        out["sweeps"][param] = {
            str(v): {**agg(param, v),
                     "margin_vs_lfu": agg(param, v)["mean"] - lfu["mean"]}
            for v in values
        }
    out["_meta"] = {
        "seeds": SEEDS, "base_su_params": BASE, "config": "controlled 535 m",
        "r_request_m": R_REQ, "n_vehicles": 130, "mean_speed_mps": 7.7,
        "n_items": N_ITEMS, "capacity": CAP, "zipf_alpha": ZIPF,
        "warmup": WARMUP, "measure": MEASURE,
    }
    (ROOT / "experiments" / "results" / "su_param_sensitivity.json").write_text(
        json.dumps(out, indent=2)
    )

    print("=== SU INTERNAL-PARAMETER SENSITIVITY (controlled config, 10 seeds) ===")
    print(f"LFU reference: {lfu['mean']:.2f} +/- {lfu['std']:.2f}\n")
    best_overall = None
    for param, values in SWEEPS.items():
        print(f"-- {param} (others at base) --")
        print(f"{'value':>10s}{'SU miss%':>11s}{'std':>7s}{'SU-LFU':>9s}")
        for v in values:
            d = out["sweeps"][param][str(v)]
            mark = "  <-- base" if abs(v - BASE.get(param, -1)) < 1e-9 else ""
            print(f"{v:10.2f}{d['mean']:11.2f}{d['std']:7.2f}"
                  f"{d['margin_vs_lfu']:+9.2f}{mark}")
            if best_overall is None or d["margin_vs_lfu"] < best_overall[1]:
                best_overall = (f"{param}={v}", d["margin_vs_lfu"])
        print()
    print(f"Best single-parameter margin found: {best_overall[0]} "
          f"-> {best_overall[1]:+.2f} pp vs LFU")
    print("(negative would mean SU beats LFU)")
    print(f"\nElapsed {time.time()-t0:.0f}s. Saved su_param_sensitivity.json")


if __name__ == "__main__":
    main()
