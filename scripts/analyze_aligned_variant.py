#!/usr/bin/env python
"""
Statistics for the aligned-implementation variant of the radius sweep.

In the aligned variant the policy's urgency acceptance radius tracks the
scenario's forward request radius, which is the choice a careful implementer
would make and which removes the confound present when the acceptance radius
is held at a fixed 800 m while the horizon varies.

Under that variant the coincidence hypothesis makes a sharp prediction: the
SU-LFU margin should be most favourable to SU when the request radius equals
the lookahead distance D_look = T_pred * v_bar = 750 m, and should worsen in
both directions away from that point. This script tests that prediction with
paired statistics rather than by eye.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.stats import wilcoxon

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "experiments" / "results"
RNG = np.random.default_rng(20260918)

D_LOOK = 750.0  # T_pred = 30 s at v_bar = 25 m/s


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


def main():
    d = json.loads((RES / "radius_continuum.json").read_text())
    radii = d["_meta"]["radii_m"]

    rows, ps = [], []
    for r in radii:
        lfu = np.array(d["lfu"][str(r)]["per_seed"], float)
        al = np.array(d["su_aligned"][str(r)]["per_seed"], float)
        diff = al - lfu
        lo, hi = boot_ci(diff)
        p = float(wilcoxon(al, lfu).pvalue)
        ps.append(p)
        rows.append({"r": r, "rho": r / D_LOOK, "lfu": float(lfu.mean()),
                     "su": float(al.mean()), "margin": float(diff.mean()),
                     "lo": lo, "hi": hi, "p_raw": p})
    for row, ph in zip(rows, holm(ps)):
        row["p_holm"] = ph

    print("=== ALIGNED VARIANT: SU vs LFU across the request radius ===")
    print("(SU acceptance radius tracks the request radius; "
          f"lookahead D_look = {D_LOOK:.0f} m)\n")
    print(f"{'r_req':>7s}{'rho':>7s}{'LFU':>8s}{'SU':>8s}{'SU-LFU':>9s}"
          f"{'95% CI':>18s}{'p_Holm':>9s}")
    for row in rows:
        ci = f"[{row['lo']:+.2f},{row['hi']:+.2f}]"
        star = "*" if row["p_holm"] < 0.05 else " "
        print(f"{row['r']:7.0f}{row['rho']:7.2f}{row['lfu']:8.2f}"
              f"{row['su']:8.2f}{row['margin']:+9.2f}{ci:>18s}"
              f"{row['p_holm']:9.4f}{star}")

    best = min(rows, key=lambda x: x["margin"])
    print(f"\nMargin is minimised at r_req = {best['r']:.0f} m "
          f"(rho = {best['rho']:.2f}), margin {best['margin']:+.2f} pp")
    print(f"Lookahead distance D_look = {D_LOOK:.0f} m, so the minimum sits at "
          f"rho = {best['rho']:.2f}")

    # Monotone on each side of the minimum?
    i = rows.index(best)
    left = [rows[k]["margin"] for k in range(i + 1)]
    right = [rows[k]["margin"] for k in range(i, len(rows))]
    dec = all(left[k] >= left[k + 1] for k in range(len(left) - 1))
    inc = all(right[k] <= right[k + 1] for k in range(len(right) - 1))
    print(f"monotone decreasing up to the minimum: {dec}")
    print(f"monotone increasing after the minimum: {inc}")

    # Sign change
    sign_change = None
    for a, b in zip(rows, rows[1:]):
        if a["margin"] > 0 >= b["margin"]:
            sign_change = (a["r"], b["r"], a["rho"], b["rho"])
    print(f"sign change between r_req = {sign_change[0]:.0f} and "
          f"{sign_change[1]:.0f} m (rho {sign_change[2]:.2f} to "
          f"{sign_change[3]:.2f})")

    out = {"d_look_m": D_LOOK, "rows": rows,
           "minimum": {"r_req_m": best["r"], "rho": best["rho"],
                       "margin": best["margin"]},
           "monotone_before_min": dec, "monotone_after_min": inc,
           "sign_change_bracket_m": [sign_change[0], sign_change[1]]}
    (RES / "aligned_variant_stats.json").write_text(json.dumps(out, indent=2))
    print("\nSaved aligned_variant_stats.json")


if __name__ == "__main__":
    main()
