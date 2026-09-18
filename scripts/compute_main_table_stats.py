#!/usr/bin/env python
"""
Significance and interval estimates for every pairwise comparison reported in
the main tables.

Reviewer concern (Major Comment 4): the main tables report means and standard
deviations only. The Wilcoxon tests and bootstrap intervals described in the
protocol are not visible next to the numbers they qualify.

For each table cell this script computes, from the stored per-seed values:
  * the paired mean difference against the LFU reference (negative = better),
  * a two-sided Wilcoxon signed-rank p-value, Holm-corrected within the table,
  * the matched-pairs rank-biserial effect size,
  * a 10 000-resample percentile bootstrap 95 % CI on the paired difference.

No new simulation is performed; every input is an existing per-seed record.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "experiments" / "results"
RNG = np.random.default_rng(20260918)


def rank_biserial(d: np.ndarray) -> float:
    d = d[d != 0]
    if d.size == 0:
        return 0.0
    ranks = np.argsort(np.argsort(np.abs(d))) + 1
    wp, wm = ranks[d > 0].sum(), ranks[d < 0].sum()
    tot = wp + wm
    return float((wp - wm) / tot) if tot else 0.0


def bootstrap_ci(d: np.ndarray, n_boot: int = 10000, alpha: float = 0.05):
    means = np.array([RNG.choice(d, size=d.size, replace=True).mean()
                      for _ in range(n_boot)])
    lo, hi = np.percentile(means, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def compare(a: list[float], b: list[float]) -> dict:
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = a - b
    if np.allclose(d, 0):
        p, stat = 1.0, 0.0
    else:
        r = wilcoxon(a, b, alternative="two-sided", zero_method="wilcox")
        p, stat = float(r.pvalue), float(r.statistic)
    lo, hi = bootstrap_ci(d)
    return {
        "mean_a": float(a.mean()), "mean_b": float(b.mean()),
        "mean_diff": float(d.mean()), "wilcoxon_stat": stat, "p_raw": p,
        "rank_biserial": rank_biserial(d), "ci95_lo": lo, "ci95_hi": hi,
        "n_pairs": int(d.size),
    }


def holm(entries: list[dict]) -> None:
    """Holm-Bonferroni within a family; writes p_holm into each entry."""
    order = sorted(range(len(entries)), key=lambda i: entries[i]["p_raw"])
    m = len(entries)
    running = 0.0
    for rank, i in enumerate(order):
        adj = min(1.0, (m - rank) * entries[i]["p_raw"])
        running = max(running, adj)  # enforce monotonicity
        entries[i]["p_holm"] = running


def fam(name: str, pairs: dict) -> dict:
    """pairs: {label: (series_a, series_b)}; family-wise Holm over labels."""
    ents, labels = [], []
    for label, (a, b) in pairs.items():
        ents.append(compare(a, b))
        labels.append(label)
    holm(ents)
    return {"family": name, "results": dict(zip(labels, ents))}


def show(block: dict, ref: str) -> None:
    print(f"\n=== {block['family']}  (reference = {ref}) ===")
    print(f"{'comparison':28s}{'diff':>8s}{'95% CI':>18s}{'p_raw':>10s}"
          f"{'p_Holm':>10s}{'r_rb':>7s}")
    for label, e in block["results"].items():
        ci = f"[{e['ci95_lo']:+.2f}, {e['ci95_hi']:+.2f}]"
        star = "*" if e["p_holm"] < 0.05 else " "
        print(f"{label:28s}{e['mean_diff']:+8.2f}{ci:>18s}"
              f"{e['p_raw']:10.4f}{e['p_holm']:10.4f}{star}{e['rank_biserial']:+6.2f}")


def main():
    out = {}

    # ---------------- Table 1: controlled mobility tiers ----------------
    mt = json.loads((RES / "matched_tiers_535m.json").read_text())
    rn = json.loads((RES / "real_ngsim_i80.json").read_text())
    tiers = {"synthetic": mt["synthetic"], "sumo": mt["sumo"]}
    # locate the real-tier policy dict
    real = rn.get("policies", rn)
    tiers["real_ngsim"] = real

    alias = {"SU": ["SU", "TC_W0.2", "TC"], "LFU": ["LFU"], "EDC": ["EDC"],
             "LRU": ["LRU"], "FIFO": ["FIFO"], "Random": ["Random"],
             "Proximity": ["Proximity"], "QLearning": ["QLearning"]}

    def series(tier: dict, pol: str):
        for k in alias[pol]:
            if k in tier and isinstance(tier[k], dict) and "per_seed" in tier[k]:
                return tier[k]["per_seed"]
        return None

    t1_blocks = {}
    for tname, tier in tiers.items():
        lfu = series(tier, "LFU")
        if lfu is None:
            print(f"  [skip] {tname}: no LFU per-seed series")
            continue
        pairs = {}
        for pol in ["LRU", "FIFO", "Random", "Proximity", "SU", "EDC", "QLearning"]:
            s = series(tier, pol)
            if s is not None:
                pairs[f"{pol} - LFU"] = (s, lfu)
        t1_blocks[tname] = fam(f"Table 1 / {tname}", pairs)
        show(t1_blocks[tname], "LFU")
    out["table1_controlled_tiers"] = t1_blocks

    # ---------------- Table 2: configuration ablation ----------------
    ab = json.loads((RES / "config_ablation.json").read_text())
    pairs = {}
    for cname in ab["_meta"]["ladder"]:
        pairs[cname] = (ab[cname]["SU"]["per_seed"], ab[cname]["LFU"]["per_seed"])
    out["table2_config_ablation"] = fam("Table 2 / config ablation (SU - LFU)", pairs)
    show(out["table2_config_ablation"], "LFU")

    # ---------------- Table 3: free-flow radius sweep ----------------
    ff = json.loads((RES / "real_freeflow.json").read_text())
    pairs = {}
    for r, cell in ff["by_radius"].items():
        lfu = cell["LFU"]["per_seed"]
        for pol in ["SU", "TC_W0.2", "EDC"]:
            if pol in cell:
                nice = "SU" if pol.startswith(("SU", "TC")) else pol
                pairs[f"{nice} - LFU @ r={r} m"] = (cell[pol]["per_seed"], lfu)
    out["table3_freeflow"] = fam("Table 3 / free-flow US-101", pairs)
    show(out["table3_freeflow"], "LFU")

    (RES / "main_table_statistics.json").write_text(json.dumps(out, indent=2))
    print("\nSaved main_table_statistics.json")


if __name__ == "__main__":
    main()
