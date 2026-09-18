#!/usr/bin/env python
"""
Does the SU-LFU margin depend on the ratio of request radius to lookahead
distance, or on either quantity by itself?

The coincidence hypothesis says the margin is governed by
rho = r_req / (T_pred * v_bar), not by r_req alone and not by T_pred alone.
That is a testable claim about which predictor organises the 54-cell grid, so
this script compares the three candidates directly:

  * Spearman rank correlation of the margin against each predictor;
  * the spread of margins among cells that share a predictor value, which is
    what "collapses onto" means operationally: if rho is the right variable,
    cells with similar rho should have similar margins even when they were
    produced by different (r_req, T_pred) pairs.

It also reports the crossover point, that is the value of rho at which the
margin changes sign, and a per-horizon breakdown so that a reader can see the
relationship is not an artifact of one horizon.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "experiments" / "results"


def main():
    d = json.loads((RES / "radius_continuum.json").read_text())
    grid = d["grid"]

    margin = np.array([g["margin"] for g in grid])
    rho = np.array([g["rho"] for g in grid])
    r_req = np.array([g["r_req_m"] for g in grid])
    t_pred = np.array([g["t_pred_s"] for g in grid])
    look = np.array([g["lookahead_m"] for g in grid])

    print("=== WHICH VARIABLE ORGANISES THE GRID? "
          f"({len(grid)} cells) ===")
    print(f"{'predictor':28s}{'Spearman rho':>14s}{'p':>12s}")
    for name, v in (("ratio r_req/(T_pred*v)", rho),
                    ("request radius r_req", r_req),
                    ("prediction horizon T_pred", t_pred),
                    ("lookahead distance T_pred*v", look)):
        r, p = spearmanr(v, margin)
        print(f"{name:28s}{r:14.3f}{p:12.2e}")

    # Operational test of "collapse": group cells by a predictor and measure
    # how much margin varies WITHIN groups. Lower is better.
    print("\n=== WITHIN-GROUP SPREAD OF THE MARGIN (lower = better collapse) ===")
    print(f"{'grouping':28s}{'groups':>8s}{'mean within-group SD':>23s}")

    def within_sd(values, n_bins=7, log=False):
        v = np.log10(values) if log else values.astype(float)
        edges = np.quantile(v, np.linspace(0, 1, n_bins + 1))
        edges[-1] += 1e-9
        sds, n_used = [], 0
        for k in range(n_bins):
            sel = (v >= edges[k]) & (v < edges[k + 1])
            if sel.sum() >= 2:
                sds.append(margin[sel].std(ddof=1))
                n_used += 1
        return n_used, float(np.mean(sds))

    for name, v, log in (("ratio rho", rho, True),
                         ("request radius r_req", r_req, True),
                         ("prediction horizon T_pred", t_pred, True)):
        n, sd = within_sd(v, log=log)
        print(f"{name:28s}{n:8d}{sd:23.3f}")
    print(f"{'(overall SD of margin)':28s}{'':8s}{margin.std(ddof=1):23.3f}")

    # Crossover: where does the margin change sign as rho grows?
    order = np.argsort(rho)
    rs, ms = rho[order], margin[order]
    cross = None
    for i in range(len(rs) - 1):
        if ms[i] > 0 >= ms[i + 1]:
            cross = (rs[i], rs[i + 1])
    print(f"\ncrossover bracket in rho: {cross}")

    print("\n=== PER-HORIZON: rho at which the margin turns negative ===")
    print(f"{'T_pred (s)':>11s}{'lookahead (m)':>15s}"
          f"{'r_req at sign change':>22s}{'rho there':>11s}")
    for tp in sorted(set(t_pred)):
        pts = sorted([g for g in grid if g["t_pred_s"] == tp],
                     key=lambda g: g["r_req_m"])
        turn = None
        for a, b in zip(pts, pts[1:]):
            if a["margin"] > 0 >= b["margin"]:
                turn = b
        if turn:
            print(f"{tp:11.0f}{tp*25.0:15.0f}{turn['r_req_m']:22.0f}"
                  f"{turn['rho']:11.2f}")
        else:
            best = min(pts, key=lambda g: g["margin"])
            print(f"{tp:11.0f}{tp*25.0:15.0f}"
                  f"{'no sign change':>22s}{best['rho']:11.2f}")

    print("\n=== ALIGNED-VARIANT CHECK (policy acceptance radius = r_req) ===")
    print(f"{'r_req':>8s}{'LFU':>9s}{'SU aligned':>12s}{'margin':>9s}")
    for r in d["_meta"]["radii_m"]:
        lfu = d["lfu"][str(r)]["mean"]
        al = d["su_aligned"][str(r)]["mean"]
        print(f"{r:8.0f}{lfu:9.2f}{al:12.2f}{al-lfu:+9.2f}")


if __name__ == "__main__":
    main()
