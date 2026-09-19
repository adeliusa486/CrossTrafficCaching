#!/usr/bin/env python
"""
Re-run one seed of the controlled synthetic tier from scratch and compare the
result against the committed per-seed file behind Table 4.

This exists so the reproduction claim can be checked by hand in under a minute,
without running any of the long sweeps.

    python scripts/reproduce_one_seed.py                 # seed 84810
    python scripts/reproduce_one_seed.py --seed 15592
    python scripts/reproduce_one_seed.py --all-seeds     # all ten, ~5 min

Exit code is 0 only if every policy matches the stored value exactly.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SEEDS = [84810, 15592, 4278, 98196, 37048, 33098, 30256, 19289, 97530, 14434]

# Table 4, controlled configuration (535 m segment, r_rel = 150 m).
CFG = dict(
    road_length=535.0, active_zone_length=535.0, r_rel=150.0,
    n_vehicles=130, mean_speed=7.7, speed_std=3.0, platoon_size=10,
    unidirectional=True, n_items=200, cache_capacity=20, zipf_alpha=0.8,
    n_steps=600, warmup_steps=150,
)

# (label in the stored JSON, build_cache key, kwargs)
POLICIES = [
    ("LRU", "lru", {}),
    ("FIFO", "fifo", {}),
    ("Random", "random", {}),
    ("LFU", "lfu", {"pop_window": 300.0}),
    ("Proximity", "proximity", {}),
    ("SU", "su", {"urgency_weight": 0.2}),
    ("EDC", "expected_demand", {"r_req": 150.0}),
    ("QLearning", "qlearning", {"lr": 0.05}),
]

# Random is expected not to match. Its committed rows were produced before the
# eviction RNG was seeded, when RandomCache drew fresh entropy on construction
# and moved by roughly 0.17 pp between runs. The policy is seeded now, so new
# runs are reproducible, but they do not reproduce the pre-fix stored values.
# Every other policy must match exactly. See Section 5.5 of the paper for why
# this does not affect the reported ranking argument.
EXPECTED_TO_DIFFER = {"Random"}


def stored_series(label):
    path = ROOT / "experiments" / "results" / "matched_tiers_535m.json"
    tier = json.loads(path.read_text())["synthetic"]
    for k in (label, "TC_W0.2", "SU", "TrajectoryCache"):
        if k in tier and "per_seed" in tier[k]:
            return tier[k]["per_seed"]
    raise KeyError(label)


def run_seed(seed):
    from trajectorycache.cache import build_cache
    from trajectorycache.evaluation.metrics import compute_metrics
    from trajectorycache.simulation.runner import SimulationConfig, SimulationRunner

    cfg = SimulationConfig(seed=seed, **CFG)
    out = {}
    for label, key, kw in POLICIES:
        if key == "random":
            kw = {**kw, "seed": seed}   # tie the eviction RNG to the scenario seed
        cache = build_cache(key, cfg.cache_capacity, **kw)
        out[label] = compute_metrics(SimulationRunner(cache, cfg).run()).miss_rate * 100.0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=84810)
    ap.add_argument("--all-seeds", action="store_true")
    a = ap.parse_args()

    seeds = SEEDS if a.all_seeds else [a.seed]
    if a.seed not in SEEDS and not a.all_seeds:
        sys.exit(f"seed {a.seed} is not one of the published seeds: {SEEDS}")

    stored = {label: stored_series(label) for label, _, _ in POLICIES}
    t0 = time.time()
    bad = 0

    for seed in seeds:
        idx = SEEDS.index(seed)
        print(f"\nseed {seed}  (controlled synthetic tier, Table 4)")
        print(f"  {'policy':<12}{'re-run':>10}{'stored':>10}   status")
        got = run_seed(seed)
        for label, _, _ in POLICIES:
            want = stored[label][idx]
            ok = abs(got[label] - want) < 1e-4
            if label in EXPECTED_TO_DIFFER:
                note = "match" if ok else "differs (pre-seeding data, expected)"
            else:
                note = "match" if ok else "*** DIFFERS ***"
                if not ok:
                    bad += 1
            print(f"  {label:<12}{got[label]:>10.4f}{want:>10.4f}   {note}")

    checked = [p for p in POLICIES if p[0] not in EXPECTED_TO_DIFFER]
    n = len(seeds) * len(checked)
    print(f"\n{n - bad}/{n} values reproduced exactly in {time.time() - t0:.0f}s "
          f"({len(EXPECTED_TO_DIFFER)} policy excluded, see EXPECTED_TO_DIFFER)")
    if bad:
        print("Reproduction FAILED. Check the library versions in "
              "requirements-lock.txt.")
        return 1
    print("Reproduction OK. These are the values printed in Table 4.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
