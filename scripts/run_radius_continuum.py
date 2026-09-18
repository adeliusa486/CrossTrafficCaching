#!/usr/bin/env python
"""
Continuous validation of the lookahead--request-radius coincidence hypothesis.

Reviewer concern (Major Comment 3): the coincidence diagnosis rests on a few
discrete configurations. The relationship should be characterised continuously.

Design. The hypothesis states that the SU-LFU margin is governed by how the
demand-side forward request radius r_req compares with SU's physical lookahead
distance D_look = T_pred * v_bar. We therefore sweep BOTH quantities
independently -- nine request radii crossed with six prediction horizons -- and
express every cell by the dimensionless ratio

    rho = r_req / (T_pred * v_bar).

If the coincidence hypothesis holds, cells sharing a value of rho should share
a margin regardless of which of the two parameters produced it, and the margin
should be most favourable to SU near rho = 1.

Two SU variants are run, because the policy has an internal acceptance radius
r_rel^SU that is distinct from the demand-side request radius despite sharing a
symbol in the original manuscript:
  * "published"  -- r_rel^SU held at its default 800 m, exactly as in Tables 1-2.
  * "aligned"    -- r_rel^SU set equal to r_req, the choice a careful
                    implementer would make. Reported as a robustness check.

Long-road geometry (10 km, dispersed catalog, 25 m/s) is used so that radii up
to 1250 m are physically meaningful on the segment.
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

ROAD = 10000.0
N_ITEMS, CAP = 200, 20
N_VEH, MEAN_SPEED, SPEED_STD = 200, 25.0, 3.0
WARMUP, MEASURE = 150, 600
SEEDS = [84810, 15592, 4278, 98196, 37048, 33098, 30256, 19289, 97530, 14434]

RADII = [50.0, 100.0, 150.0, 250.0, 400.0, 550.0, 750.0, 1000.0, 1250.0]
TPREDS = [10.0, 20.0, 30.0, 45.0, 60.0, 90.0]
TPRED_DEFAULT = 30.0


def _cfg(r_req, seed):
    from trajectorycache.simulation.runner import SimulationConfig
    return SimulationConfig(
        road_length=ROAD, active_zone_length=ROAD, r_rel=r_req,
        n_vehicles=N_VEH, mean_speed=MEAN_SPEED, speed_std=SPEED_STD,
        platoon_size=10, unidirectional=True, n_items=N_ITEMS,
        zipf_alpha=0.8, cache_capacity=CAP, n_steps=MEASURE,
        warmup_steps=WARMUP, seed=seed,
    )


def job(args):
    kind, r_req, t_pred, seed = args
    sys.path.insert(0, str(ROOT / "src"))
    from trajectorycache.cache import build_cache
    from trajectorycache.evaluation.metrics import compute_metrics
    from trajectorycache.simulation.runner import SimulationRunner

    if kind == "LFU":
        cache = build_cache("lfu", CAP, pop_window=300.0)
    elif kind == "EDC":
        cache = build_cache("expected_demand", CAP, r_req=r_req)
    elif kind == "SU_published":
        cache = build_cache("trajectory", CAP, urgency_weight=0.2, t_pred=t_pred)
    elif kind == "SU_aligned":
        cache = build_cache("trajectory", CAP, urgency_weight=0.2,
                            t_pred=t_pred, r_rel=r_req)
    else:
        raise ValueError(kind)

    mr = compute_metrics(
        SimulationRunner(cache, _cfg(r_req, seed)).run()
    ).miss_rate * 100.0
    return kind, r_req, t_pred, seed, mr


def agg(raw, kind, r, t):
    vals = [raw[(kind, r, t)][s] for s in SEEDS]
    return {"mean": float(np.mean(vals)), "std": float(np.std(vals)),
            "per_seed": [round(v, 4) for v in vals]}


def main():
    t0 = time.time()
    jobs = []
    # LFU and EDC depend only on the demand radius.
    for r in RADII:
        for s in SEEDS:
            jobs.append(("LFU", r, TPRED_DEFAULT, s))
            jobs.append(("EDC", r, TPRED_DEFAULT, s))
    # SU across the full radius x horizon grid.
    for r in RADII:
        for t in TPREDS:
            for s in SEEDS:
                jobs.append(("SU_published", r, t, s))
    # Aligned-variant robustness check at the default horizon.
    for r in RADII:
        for s in SEEDS:
            jobs.append(("SU_aligned", r, TPRED_DEFAULT, s))

    raw: dict = {}
    done = 0
    with Pool(processes=12) as pool:
        for kind, r, t, seed, mr in pool.imap_unordered(job, jobs):
            raw.setdefault((kind, r, t), {})[seed] = mr
            done += 1
            if done % 100 == 0:
                print(f"  {done}/{len(jobs)} runs ({time.time()-t0:.0f}s)", flush=True)

    out = {"lfu": {}, "edc": {}, "su_published": {}, "su_aligned": {}, "grid": []}
    for r in RADII:
        out["lfu"][str(r)] = agg(raw, "LFU", r, TPRED_DEFAULT)
        out["edc"][str(r)] = agg(raw, "EDC", r, TPRED_DEFAULT)
        out["su_aligned"][str(r)] = agg(raw, "SU_aligned", r, TPRED_DEFAULT)
        for t in TPREDS:
            out["su_published"][f"{r}|{t}"] = agg(raw, "SU_published", r, t)
            out["grid"].append({
                "r_req_m": r, "t_pred_s": t,
                "lookahead_m": t * MEAN_SPEED,
                "rho": r / (t * MEAN_SPEED),
                "su": out["su_published"][f"{r}|{t}"]["mean"],
                "lfu": out["lfu"][str(r)]["mean"],
                "margin": out["su_published"][f"{r}|{t}"]["mean"]
                          - out["lfu"][str(r)]["mean"],
            })

    out["_meta"] = {
        "seeds": SEEDS, "radii_m": RADII, "t_preds_s": TPREDS,
        "road_m": ROAD, "n_vehicles": N_VEH, "mean_speed_mps": MEAN_SPEED,
        "n_items": N_ITEMS, "capacity": CAP, "zipf_alpha": 0.8,
        "warmup": WARMUP, "measure": MEASURE,
        "rho": "r_req / (t_pred * mean_speed)",
    }
    (ROOT / "experiments" / "results" / "radius_continuum.json").write_text(
        json.dumps(out, indent=2)
    )

    print("\n=== SU-LFU MARGIN vs REQUEST RADIUS (T_pred = 30 s, lookahead 750 m) ===")
    print(f"{'r_req':>8s}{'rho':>7s}{'LFU':>8s}{'SU':>8s}{'SU-LFU':>9s}{'EDC-LFU':>9s}")
    for r in RADII:
        g = next(x for x in out["grid"] if x["r_req_m"] == r and x["t_pred_s"] == 30.0)
        edc_m = out["edc"][str(r)]["mean"] - out["lfu"][str(r)]["mean"]
        print(f"{r:8.0f}{g['rho']:7.2f}{g['lfu']:8.2f}{g['su']:8.2f}"
              f"{g['margin']:+9.2f}{edc_m:+9.2f}")

    print("\n=== MARGIN COLLAPSE ONTO rho (all 54 grid cells, binned) ===")
    bins = [(0.0, 0.25), (0.25, 0.5), (0.5, 0.8), (0.8, 1.25),
            (1.25, 2.0), (2.0, 4.0), (4.0, 99.0)]
    print(f"{'rho bin':>14s}{'n':>4s}{'mean margin':>13s}{'min':>8s}{'max':>8s}")
    for lo, hi in bins:
        sel = [g["margin"] for g in out["grid"] if lo <= g["rho"] < hi]
        if sel:
            print(f"{f'[{lo:.2f},{hi:.2f})':>14s}{len(sel):4d}"
                  f"{np.mean(sel):+13.2f}{min(sel):+8.2f}{max(sel):+8.2f}")

    print(f"\nElapsed {time.time()-t0:.0f}s. Saved radius_continuum.json")


if __name__ == "__main__":
    main()
