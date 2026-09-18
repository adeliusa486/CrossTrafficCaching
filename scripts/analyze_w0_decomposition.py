#!/usr/bin/env python
"""
Decompose the SU-LFU margin into an admission-control component and a
spatial-term component.

The manuscript states that setting the blend weight W to zero reduces SU
exactly to sliding-window LFU, so that any difference between them is
attributable to the spatial term alone. That is not true of these
implementations, and the parameter sweep made it visible.

LFUCache always admits an incoming item and evicts the least frequently
requested cached item. SU, like EDC, applies admission control: on a miss with
a full cache it evicts the lowest-scoring cached item only when the incoming
item scores strictly higher, and otherwise declines to cache the new item. So
SU at W = 0 is not LFU, it is LFU with admission control.

This script measures both components from the stored per-seed values so that
the manuscript can report the decomposition correctly.
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


def compare(a, b, label):
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = a - b
    lo, hi = boot_ci(d)
    p = 1.0 if np.allclose(d, 0) else float(wilcoxon(a, b).pvalue)
    print(f"{label:46s}{d.mean():+8.2f}  [{lo:+.2f},{hi:+.2f}]  p={p:.4f}")
    return {"mean": float(d.mean()), "ci": [lo, hi], "p": p}


def main():
    sp = json.loads((RES / "su_param_sensitivity.json").read_text())
    lfu = sp["LFU_reference"]["per_seed"]
    w0 = sp["sweeps"]["urgency_weight"]["0.0"]["per_seed"]
    w02 = sp["sweeps"]["urgency_weight"]["0.2"]["per_seed"]

    print("Controlled configuration, 10 seeds, mean miss rate (%)\n")
    print(f"  LFU (always admits)                 "
          f"{np.mean(lfu):6.2f}")
    print(f"  SU at W=0 (admission control only)  {np.mean(w0):6.2f}")
    print(f"  SU at W=0.2 (published setting)     {np.mean(w02):6.2f}")
    print()

    out = {}
    out["admission_control"] = compare(
        w0, lfu, "admission control alone (SU W=0 - LFU)")
    out["spatial_term"] = compare(
        w02, w0, "spatial term alone (SU W=0.2 - SU W=0)")
    out["headline"] = compare(
        w02, lfu, "headline margin (SU W=0.2 - LFU)")

    print()
    print("Reading: admission control is worth a small improvement over LFU, "
          "and the\nspatial term then gives all of that back and more. The "
          "cost of the spatial\nterm is therefore larger than the headline "
          "margin suggests, not smaller.")

    (RES / "w0_decomposition.json").write_text(json.dumps(out, indent=2))
    print("\nSaved w0_decomposition.json")


if __name__ == "__main__":
    main()
