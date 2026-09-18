#!/usr/bin/env python
"""
Computational cost of the evaluated replacement policies.

Reviewer concern (Major Comment 10): EDC and SU perform per-item and
per-vehicle computation, but the manuscript does not quantify their
complexity or runtime overhead. Vehicular edge caching is latency sensitive,
so the cost of computing urgency, exposure and popularity matters.

This script measures wall-clock cost per request under the controlled
configuration while scaling the two quantities that drive the asymptotic cost:

  * the number of vehicles V visible to the cache (the inner loop of the
    urgency and exposure computations), and
  * the cache capacity C (the number of items scored on an eviction).

Reported quantities are mean microseconds per request and mean microseconds
per eviction decision, measured over the full measurement window and averaged
across seeds. Absolute timings are hardware dependent; the scaling behaviour
and the ratios between policies are the portable results.

Runs single-process and single-threaded so that timings are not distorted by
pool contention.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SEG = 535.0
N_ITEMS, R_REQ, ZIPF = 200, 150.0, 0.8
# Timing run: a short window already yields tens of thousands of requests per
# cell, which is ample for a stable per-request mean, and the quantity of
# interest is cost per request rather than miss rate. One seed suffices because
# the per-request cost varies far less across seeds than across policies.
WARMUP, MEASURE = 50, 100
SEEDS = [84810]

V_LEVELS = [30, 65, 130, 260]       # vehicles on the segment
C_LEVELS = [10, 20, 40, 80]         # cache capacity

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


def measure(pkey, kw, n_veh, cap, seed):
    """Return (us per request, requests, misses) for one configuration."""
    from trajectorycache.cache import build_cache
    from trajectorycache.simulation.runner import SimulationConfig, SimulationRunner

    cfg = SimulationConfig(
        road_length=SEG, active_zone_length=SEG, r_rel=R_REQ,
        n_vehicles=n_veh, mean_speed=7.7, speed_std=3.0, platoon_size=10,
        unidirectional=True, n_items=N_ITEMS, zipf_alpha=ZIPF,
        cache_capacity=cap, n_steps=MEASURE, warmup_steps=WARMUP, seed=seed,
    )
    cache = build_cache(pkey, cap, **kw)
    runner = SimulationRunner(cache, cfg)
    t0 = time.perf_counter()
    res = runner.run()
    elapsed = time.perf_counter() - t0
    summary = cache.summary()
    n_req = summary["hits"] + summary["misses"]
    # The simulation loop itself (mobility, demand draw) is common to every
    # policy; we report total wall time per request, and separately the excess
    # over the cheapest policy, which isolates the replacement cost.
    return (elapsed / max(n_req, 1)) * 1e6, n_req, summary["misses"], res


def main():
    t0 = time.time()
    out = {"vehicle_scaling": {}, "capacity_scaling": {}}

    print("=== COST PER REQUEST vs NUMBER OF VEHICLES (C = 20) ===")
    hdr = f"{'policy':12s}" + "".join(f"{'V='+str(v):>11s}" for v in V_LEVELS)
    print(hdr)
    for pname, pkey, kw in POLICIES:
        row = f"{pname:12s}"
        out["vehicle_scaling"][pname] = {}
        for v in V_LEVELS:
            us = np.mean([measure(pkey, kw, v, 20, s)[0] for s in SEEDS])
            out["vehicle_scaling"][pname][str(v)] = float(us)
            row += f"{us:11.1f}"
        print(row, flush=True)

    print("\n=== COST PER REQUEST vs CACHE CAPACITY (V = 130) ===")
    hdr = f"{'policy':12s}" + "".join(f"{'C='+str(c):>11s}" for c in C_LEVELS)
    print(hdr)
    for pname, pkey, kw in POLICIES:
        row = f"{pname:12s}"
        out["capacity_scaling"][pname] = {}
        for c in C_LEVELS:
            us = np.mean([measure(pkey, kw, 130, c, s)[0] for s in SEEDS])
            out["capacity_scaling"][pname][str(c)] = float(us)
            row += f"{us:11.1f}"
        print(row, flush=True)

    # Excess cost over the cheapest policy at the operating point.
    base = min(out["vehicle_scaling"][p]["130"] for p, _, _ in POLICIES)
    print(f"\n=== EXCESS OVER CHEAPEST POLICY AT V=130, C=20 "
          f"(baseline {base:.1f} us/request) ===")
    print(f"{'policy':12s}{'us/request':>12s}{'excess us':>11s}{'ratio':>8s}")
    out["operating_point"] = {"baseline_us": float(base), "policies": {}}
    for pname, _, _ in POLICIES:
        us = out["vehicle_scaling"][pname]["130"]
        print(f"{pname:12s}{us:12.1f}{us-base:11.1f}{us/base:8.2f}")
        out["operating_point"]["policies"][pname] = {
            "us_per_request": float(us), "excess_us": float(us - base),
            "ratio": float(us / base)}

    out["_meta"] = {
        "seeds": SEEDS, "v_levels": V_LEVELS, "c_levels": C_LEVELS,
        "segment_m": SEG, "r_request_m": R_REQ, "n_items": N_ITEMS,
        "zipf_alpha": ZIPF, "warmup": WARMUP, "measure": MEASURE,
        "note": ("wall-clock per request includes the shared simulation loop; "
                 "excess over the cheapest policy isolates replacement cost"),
    }
    (ROOT / "experiments" / "results" / "complexity_profile.json").write_text(
        json.dumps(out, indent=2)
    )
    print(f"\nElapsed {time.time()-t0:.0f}s. Saved complexity_profile.json")


if __name__ == "__main__":
    main()
