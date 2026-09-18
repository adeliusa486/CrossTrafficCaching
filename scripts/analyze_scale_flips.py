#!/usr/bin/env python
"""
Are the sign reversals in the capacity and catalog-size sweeps real?

Both sweeps show the SU-LFU margin changing sign at the small end: SU is ahead
of LFU at the smallest cache and the smallest catalog, and behind it everywhere
else. Because that qualifies the paper's headline claim, the reversals are
tested rather than read off the means.

Paired Wilcoxon signed-rank tests with Holm correction within each sweep, and
bootstrap 95 % confidence intervals on each paired difference.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "experiments" / "results"
RNG = np.random.default_rng(20260918)


def boot_ci(d, n_boot=10000):
    m = np.array([RNG.choice(d, size=d.size, replace=True).mean()
                  for _ in range(n_boot)])
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    run, out = 0.0, [0.0] * len(ps)
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        out[i] = run
    return out


def family(cells, label, xname):
    """cells: list of (x, lfu_series, su_series, edc_series)."""
    print(f"\n=== {label} ===")
    rows, ps_su, ps_edc = [], [], []
    for x, lfu, su, edc in cells:
        lfu, su, edc = map(lambda a: np.asarray(a, float), (lfu, su, edc))
        ds, de = su - lfu, edc - lfu
        rows.append({
            "x": x, "lfu": float(lfu.mean()),
            "su_margin": float(ds.mean()), "su_ci": boot_ci(ds),
            "edc_margin": float(de.mean()), "edc_ci": boot_ci(de)})
        ps_su.append(float(wilcoxon(su, lfu).pvalue))
        ps_edc.append(float(wilcoxon(edc, lfu).pvalue))
    for r, a, b in zip(rows, holm(ps_su), holm(ps_edc)):
        r["su_p"], r["edc_p"] = a, b

    print(f"{xname:>10s}{'LFU':>8s} | {'SU-LFU':>8s}{'95% CI':>18s}{'p':>8s}"
          f" | {'EDC-LFU':>8s}{'95% CI':>18s}{'p':>8s}")
    for r in rows:
        s_ci = f"[{r['su_ci'][0]:+.2f},{r['su_ci'][1]:+.2f}]"
        e_ci = f"[{r['edc_ci'][0]:+.2f},{r['edc_ci'][1]:+.2f}]"
        s_m = "*" if r["su_p"] < 0.05 else " "
        e_m = "*" if r["edc_p"] < 0.05 else " "
        print(f"{r['x']:>10}{r['lfu']:8.2f} | {r['su_margin']:+8.2f}"
              f"{s_ci:>18s}{r['su_p']:8.4f}{s_m}| {r['edc_margin']:+8.2f}"
              f"{e_ci:>18s}{r['edc_p']:8.4f}{e_m}")
    return rows


def main():
    out = {}

    cap = json.loads((RES / "capacity_sweep.json").read_text())
    cells = []
    for c in cap["_meta"]["capacities"]:
        k = f"cap_{c}"
        cells.append((f"{c} ({100*c/200:.1f}%)",
                      cap[k]["LFU"]["per_seed"],
                      cap[k]["SU"]["per_seed"],
                      cap[k]["EDC"]["per_seed"]))
    out["capacity"] = family(cells, "CACHE CAPACITY (catalog fixed at 200)",
                             "C_max")

    cat = json.loads((RES / "catalog_scope.json").read_text())
    cells = []
    for n in cat["_meta"]["catalog_sizes"]:
        k = str(n)
        cells.append((f"N={n}",
                      cat["catalog"][k]["LFU"]["per_seed"],
                      cat["catalog"][k]["SU"]["per_seed"],
                      cat["catalog"][k]["EDC"]["per_seed"]))
    out["catalog"] = family(cells, "CATALOG SIZE (cache held at 10 % of N)",
                            "catalog")

    cells = []
    for z in cat["_meta"]["zones_m"]:
        k = str(z)
        cells.append((f"{z:.0f} m",
                      cat["zone"][k]["LFU"]["per_seed"],
                      cat["zone"][k]["SU"]["per_seed"],
                      cat["zone"][k]["EDC"]["per_seed"]))
    out["dispersion"] = family(cells, "CONTENT DISPERSION (active zone width)",
                               "zone")

    (RES / "scale_flip_stats.json").write_text(json.dumps(out, indent=2))
    print("\nSaved scale_flip_stats.json")


if __name__ == "__main__":
    main()
