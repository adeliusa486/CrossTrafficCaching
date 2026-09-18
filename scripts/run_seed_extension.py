#!/usr/bin/env python
"""
Seed-count stability of the controlled-tier comparison.

Reviewer concern (Major Comment 5): the experiments use 10 independent seeds,
and some reported differences are below one percentage point. The stability of
those observations with respect to the number of seeds should be demonstrated.

This script extends every controlled-tier cell from 10 to 30 seeds on all three
mobility tiers, using the same scenario, the same demand model and the same
replay logic as run_matched_tiers.py and run_real_ngsim.py. The first 10 seeds
are exactly the published ones, so the 10-seed prefix of each series reproduces
the values in Table 1.

It then reports, for k = 3..30, the running mean of each paired difference
against LFU together with a bootstrap 95 % CI computed from the first k seeds.
That curve shows directly at what point the sign and magnitude of a difference
stop moving.
"""
from __future__ import annotations

import json
import pickle
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

SUMO_BIN = r"C:\Program Files (x86)\Eclipse\Sumo\bin\sumo.exe"
SUMO_DIR = ROOT / "sumo"
NET535B = SUMO_DIR / "highway535b.net.xml"
NGSIM_CSV = ROOT / "data" / "raw" / "ngsim" / "ngsim_i80_win1.csv"

SEG = 535.0
N_ITEMS, CAP, R_REQ, ZIPF = 200, 20, 150.0, 0.8
WARMUP, MEASURE = 150, 600
SUMO_VPH = 15000

PUBLISHED_SEEDS = [84810, 15592, 4278, 98196, 37048,
                   33098, 30256, 19289, 97530, 14434]
# 20 additional seeds drawn once from a fixed generator and then frozen here,
# so that the extended set is reproducible and was not selected post hoc.
EXTRA_SEEDS = [51023, 76418, 12987, 64350, 28761, 93204, 40518, 87632,
               19475, 55840, 71296, 33967, 60482, 25713, 84159, 47026,
               91538, 16704, 38291, 69845]
SEEDS = PUBLISHED_SEEDS + EXTRA_SEEDS

POLICIES = [
    ("LFU", "lfu", {"pop_window": 300.0}),
    ("SU", "trajectory", {"urgency_weight": 0.2}),
    ("EDC", "expected_demand", {"r_req": R_REQ}),
]

RNG = np.random.default_rng(20260918)


# ----------------------------- synthetic ---------------------------------
def synth_job(job):
    pname, pkey, kw, seed = job
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
    mr = compute_metrics(
        SimulationRunner(build_cache(pkey, CAP, **kw), cfg).run()
    ).miss_rate * 100.0
    return "synthetic", pname, seed, mr


# -------------------------------- SUMO -----------------------------------
def gen_fcd_file(seed):
    routes = SUMO_DIR / f"se_routes_{seed}.rou.xml"
    fcd = SUMO_DIR / f"se_fcd_{seed}.xml"
    if fcd.exists():
        return fcd
    routes.write_text(
        '<routes>\n'
        '<vType id="car" carFollowModel="Krauss" maxSpeed="29.06" '
        'speedFactor="normc(1,0.1,0.7,1.3)" minGap="2.5" accel="2.6" '
        'decel="4.5" sigma="0.5"/>\n'
        '<route id="r" edges="AB BC"/>\n'
        f'<flow id="f" type="car" route="r" begin="0" end="900" '
        f'vehsPerHour="{SUMO_VPH}" departSpeed="max" departLane="random"/>\n'
        '</routes>\n')
    subprocess.run([SUMO_BIN, "-n", str(NET535B), "-r", str(routes),
                    "--fcd-output", str(fcd), "--step-length", "1",
                    "--begin", "0", "--end", "900", "--seed", str(seed),
                    "--no-step-log", "true", "--no-warnings", "true"],
                   check=True, capture_output=True)
    routes.unlink()
    return fcd


def _fcd_cache_path(seed):
    return SUMO_DIR / f"se_fcd_{seed}.pkl"


def prepare_fcd_cache(seed):
    """Parse one FCD trace once and cache the replay window.

    Each trace is consumed by three policy jobs; parsing the XML inside every
    job would triple the cost for no benefit.
    """
    cache = _fcd_cache_path(seed)
    if cache.exists():
        return
    fcd = SUMO_DIR / f"se_fcd_{seed}.xml"
    steps = []
    for ts in ET.parse(fcd).getroot():
        vehs = [{"x": float(v.get("x")), "speed": float(v.get("speed")),
                 "direction": 1} for v in ts if float(v.get("x")) <= SEG]
        steps.append((float(ts.get("time")), vehs))
    with open(cache, "wb") as fh:
        pickle.dump(steps[: WARMUP + MEASURE], fh, protocol=4)


def sumo_job(job):
    pname, pkey, kw, seed = job
    sys.path.insert(0, str(ROOT / "src"))
    from trajectorycache.cache import build_cache
    from trajectorycache.content.catalog import ContentCatalog

    with open(_fcd_cache_path(seed), "rb") as fh:
        window = pickle.load(fh)

    cat = ContentCatalog(n_items=N_ITEMS, road_length=SEG,
                         active_zone_length=SEG, zipf_alpha=ZIPF, seed=seed)
    loc_map = cat.location_map()
    cache = build_cache(pkey, CAP, **kw)
    cache.clear()
    for i, (t, vehs) in enumerate(window):
        if i == WARMUP:
            cache.reset_stats()
        for item in cat.generate_vehicle_requests(vehicles=vehs, r_request=R_REQ):
            cache.request(item_id=item.item_id, item_location=item.location,
                          current_time=t, vehicles=vehs, catalog=loc_map)
    return "sumo", pname, seed, cache.summary()["miss_rate"]


# -------------------------------- real -----------------------------------
NGSIM_CACHE = ROOT / "experiments" / "results" / "_ngsim_i80_window.pkl"


def prepare_ngsim_cache():
    """Parse the 62 MB NGSIM CSV once and cache the replay window.

    Every real-tier job replays the same recorded trajectory, so parsing the
    CSV inside each job would repeat that work 90 times.
    """
    if NGSIM_CACHE.exists():
        return
    sys.path.insert(0, str(ROOT / "scripts"))
    from adapters.ngsim_adapter import load_ngsim_steps
    steps, meta = load_ngsim_steps(NGSIM_CSV)
    with open(NGSIM_CACHE, "wb") as fh:
        pickle.dump({"window": steps[: WARMUP + MEASURE],
                     "segment_m": meta["segment_length_m"]}, fh, protocol=4)


def real_job(job):
    pname, pkey, kw, seed = job
    sys.path.insert(0, str(ROOT / "src"))
    from trajectorycache.cache import build_cache
    from trajectorycache.content.catalog import ContentCatalog

    with open(NGSIM_CACHE, "rb") as fh:
        cached = pickle.load(fh)
    window, seg = cached["window"], cached["segment_m"]
    cat = ContentCatalog(n_items=N_ITEMS, road_length=seg,
                         active_zone_length=seg, zipf_alpha=ZIPF, seed=seed)
    loc_map = cat.location_map()
    cache = build_cache(pkey, CAP, **kw)
    cache.clear()
    for i, (t, vehs) in enumerate(window):
        if i == WARMUP:
            cache.reset_stats()
        for item in cat.generate_vehicle_requests(vehicles=vehs, r_request=R_REQ):
            cache.request(item_id=item.item_id, item_location=item.location,
                          current_time=t, vehicles=vehs, catalog=loc_map)
    return "real_ngsim", pname, seed, cache.summary()["miss_rate"]


def boot_ci(d, n_boot=5000):
    m = np.array([RNG.choice(d, size=d.size, replace=True).mean()
                  for _ in range(n_boot)])
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def main():
    t0 = time.time()

    print(f"Generating {len(SEEDS)} SUMO FCD traces (sequential)...", flush=True)
    for i, s in enumerate(SEEDS, 1):
        gen_fcd_file(s)
        prepare_fcd_cache(s)
        if i % 5 == 0:
            print(f"  {i}/{len(SEEDS)} traces ({time.time()-t0:.0f}s)",
                  flush=True)
    print(f"  traces ready ({time.time()-t0:.0f}s)", flush=True)

    print("Caching the NGSIM replay window...", flush=True)
    prepare_ngsim_cache()
    print(f"  NGSIM ready ({time.time()-t0:.0f}s)", flush=True)

    jobs = []
    for pn, pk, kw in POLICIES:
        for s in SEEDS:
            jobs.append((synth_job, (pn, pk, kw, s)))
            jobs.append((sumo_job, (pn, pk, kw, s)))
            jobs.append((real_job, (pn, pk, kw, s)))

    raw: dict = {}
    done = 0
    with Pool(processes=18) as pool:
        results = [pool.apply_async(fn, (arg,)) for fn, arg in jobs]
        for r in results:
            tier, pn, seed, mr = r.get()
            raw.setdefault(tier, {}).setdefault(pn, {})[seed] = mr
            done += 1
            if done % 60 == 0:
                print(f"  {done}/{len(jobs)} runs ({time.time()-t0:.0f}s)",
                      flush=True)

    out: dict = {"tiers": {}, "stability": {}}
    for tier in ["synthetic", "sumo", "real_ngsim"]:
        out["tiers"][tier] = {
            pn: {"mean": float(np.mean([raw[tier][pn][s] for s in SEEDS])),
                 "std": float(np.std([raw[tier][pn][s] for s in SEEDS])),
                 "per_seed": [round(raw[tier][pn][s], 4) for s in SEEDS]}
            for pn, _, _ in POLICIES
        }
        lfu = np.array([raw[tier]["LFU"][s] for s in SEEDS])
        for pol in ["SU", "EDC"]:
            arr = np.array([raw[tier][pol][s] for s in SEEDS])
            d = arr - lfu
            curve = []
            for k in range(3, len(SEEDS) + 1):
                dk = d[:k]
                lo, hi = boot_ci(dk)
                try:
                    p = float(wilcoxon(arr[:k], lfu[:k]).pvalue)
                except ValueError:
                    p = 1.0
                curve.append({"k": k, "mean": float(dk.mean()),
                              "ci_lo": lo, "ci_hi": hi, "p": p})
            out["stability"][f"{tier}/{pol}-LFU"] = curve

    out["_meta"] = {
        "published_seeds": PUBLISHED_SEEDS, "extra_seeds": EXTRA_SEEDS,
        "n_seeds": len(SEEDS), "segment_m": SEG, "r_request_m": R_REQ,
        "n_items": N_ITEMS, "capacity": CAP, "zipf_alpha": ZIPF,
        "warmup": WARMUP, "measure": MEASURE,
    }
    (ROOT / "experiments" / "results" / "seed_extension.json").write_text(
        json.dumps(out, indent=2)
    )

    print("\n=== 30-SEED CONTROLLED TIERS (mean miss %, first 10 = published) ===")
    print(f"{'tier':12s}{'policy':8s}{'10-seed':>9s}{'30-seed':>9s}{'shift':>8s}")
    for tier in ["synthetic", "sumo", "real_ngsim"]:
        for pn, _, _ in POLICIES:
            ps = out["tiers"][tier][pn]["per_seed"]
            m10, m30 = np.mean(ps[:10]), np.mean(ps)
            print(f"{tier:12s}{pn:8s}{m10:9.2f}{m30:9.2f}{m30-m10:+8.2f}")

    print("\n=== PAIRED DIFFERENCE vs LFU: 10 seeds vs 30 seeds ===")
    print(f"{'comparison':22s}{'10-seed':>9s}{'30-seed':>9s}"
          f"{'30-seed 95% CI':>20s}{'p':>9s}")
    for key, curve in out["stability"].items():
        c10 = next(c for c in curve if c["k"] == 10)
        c30 = curve[-1]
        ci = f"[{c30['ci_lo']:+.2f},{c30['ci_hi']:+.2f}]"
        print(f"{key:22s}{c10['mean']:+9.2f}{c30['mean']:+9.2f}"
              f"{ci:>20s}{c30['p']:9.4f}")

    print(f"\nElapsed {time.time()-t0:.0f}s. Saved seed_extension.json")


if __name__ == "__main__":
    main()
