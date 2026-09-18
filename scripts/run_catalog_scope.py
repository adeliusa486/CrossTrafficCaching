#!/usr/bin/env python
"""
Catalog-size and content-dispersion sensitivity.

Reviewer concern (Minor Comment 10): the limitations should account for a fixed
catalog size and for possible sensitivity to how content is distributed in
space. Both are held constant in the main experiments ($N=200$ items spread
uniformly over the whole segment), so neither is currently supported by
evidence.

Two sweeps are run under the controlled configuration:

  (a) catalog size N in {50, 100, 200, 400, 800}, with the cache held at 10 %
      of the catalog so that the cache-to-catalog ratio stays at the value used
      in the main experiments and only the absolute scale changes;

  (b) content dispersion, by shrinking the active content zone from the full
      535 m segment down to 150 m, which concentrates the catalog into a
      fraction of the road and changes how strongly item location varies.

Both sweeps report LFU, SU and EDC so that the SU-LFU ordering can be checked
for stability along each axis.
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
R_REQ, ZIPF = 150.0, 0.8
WARMUP, MEASURE = 150, 600
SEEDS = [84810, 15592, 4278, 98196, 37048, 33098, 30256, 19289, 97530, 14434]

CATALOG_SIZES = [50, 100, 200, 400, 800]        # cache held at 10 % of each
ZONES = [150.0, 267.5, 400.0, 535.0]            # active content zone length

POLICIES = [
    ("LFU", "lfu", {"pop_window": 300.0}),
    ("SU", "trajectory", {"urgency_weight": 0.2}),
    ("EDC", "expected_demand", {"r_req": R_REQ}),
]


def job(args):
    sweep, level, pname, pkey, kw, seed = args
    sys.path.insert(0, str(ROOT / "src"))
    from trajectorycache.cache import build_cache
    from trajectorycache.evaluation.metrics import compute_metrics
    from trajectorycache.simulation.runner import SimulationConfig, SimulationRunner

    if sweep == "catalog":
        n_items = int(level)
        cap = max(1, round(0.10 * n_items))
        zone = SEG
    else:
        n_items, cap, zone = 200, 20, float(level)

    cfg = SimulationConfig(
        road_length=SEG, active_zone_length=zone, r_rel=R_REQ,
        n_vehicles=130, mean_speed=7.7, speed_std=3.0, platoon_size=10,
        unidirectional=True, n_items=n_items, zipf_alpha=ZIPF,
        cache_capacity=cap, n_steps=MEASURE, warmup_steps=WARMUP, seed=seed,
    )
    mr = compute_metrics(
        SimulationRunner(build_cache(pkey, cap, **kw), cfg).run()
    ).miss_rate * 100.0
    return sweep, level, pname, seed, mr


def main():
    t0 = time.time()
    jobs = []
    for n in CATALOG_SIZES:
        for pn, pk, kw in POLICIES:
            for s in SEEDS:
                jobs.append(("catalog", n, pn, pk, kw, s))
    for z in ZONES:
        for pn, pk, kw in POLICIES:
            for s in SEEDS:
                jobs.append(("zone", z, pn, pk, kw, s))

    raw: dict = {}
    with Pool(processes=12) as pool:
        for sweep, level, pn, seed, mr in pool.imap_unordered(job, jobs):
            raw.setdefault(sweep, {}).setdefault(level, {}).setdefault(pn, {})[seed] = mr

    def agg(sweep, level, p):
        vals = [raw[sweep][level][p][s] for s in SEEDS]
        return {"mean": float(np.mean(vals)), "std": float(np.std(vals)),
                "per_seed": [round(v, 4) for v in vals]}

    out = {"catalog": {}, "zone": {}}
    for n in CATALOG_SIZES:
        out["catalog"][str(n)] = {p: agg("catalog", n, p) for p, _, _ in POLICIES}
    for z in ZONES:
        out["zone"][str(z)] = {p: agg("zone", z, p) for p, _, _ in POLICIES}
    out["_meta"] = {
        "seeds": SEEDS, "catalog_sizes": CATALOG_SIZES,
        "cache_ratio": 0.10, "zones_m": ZONES, "segment_m": SEG,
        "r_request_m": R_REQ, "zipf_alpha": ZIPF, "n_vehicles": 130,
        "mean_speed_mps": 7.7, "warmup": WARMUP, "measure": MEASURE,
    }
    (ROOT / "experiments" / "results" / "catalog_scope.json").write_text(
        json.dumps(out, indent=2)
    )

    print("=== CATALOG SIZE (cache held at 10 % of catalog) ===")
    print(f"{'N':>6s}{'C_max':>7s}{'LFU':>9s}{'SU':>9s}{'EDC':>9s}"
          f"{'SU-LFU':>9s}{'EDC-LFU':>9s}")
    for n in CATALOG_SIZES:
        c = out["catalog"][str(n)]
        print(f"{n:6d}{max(1,round(0.1*n)):7d}{c['LFU']['mean']:9.2f}"
              f"{c['SU']['mean']:9.2f}{c['EDC']['mean']:9.2f}"
              f"{c['SU']['mean']-c['LFU']['mean']:+9.2f}"
              f"{c['EDC']['mean']-c['LFU']['mean']:+9.2f}")

    print("\n=== CONTENT DISPERSION (active zone length on a 535 m segment) ===")
    print(f"{'zone':>7s}{'LFU':>9s}{'SU':>9s}{'EDC':>9s}{'SU-LFU':>9s}{'EDC-LFU':>9s}")
    for z in ZONES:
        c = out["zone"][str(z)]
        print(f"{z:7.0f}{c['LFU']['mean']:9.2f}{c['SU']['mean']:9.2f}"
              f"{c['EDC']['mean']:9.2f}"
              f"{c['SU']['mean']-c['LFU']['mean']:+9.2f}"
              f"{c['EDC']['mean']-c['LFU']['mean']:+9.2f}")
    print(f"\nElapsed {time.time()-t0:.0f}s. Saved catalog_scope.json")


if __name__ == "__main__":
    main()
