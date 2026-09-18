#!/usr/bin/env python3
"""Generate the main-text figures directly from the stored per-seed result
JSONs. No numbers are hard-coded: everything is read from experiments/results/
so the figures are reproducible and provably consistent with the tables.

Revision 1 changes, in response to Minor Comment 6:
  * error bars on every paired margin are bootstrap 95 % confidence intervals
    (10 000 resamples) rather than +/- 1 standard deviation, and the captions
    say which is shown;
  * base font size raised from 9 pt to 10.5 pt, with tick and legend text
    scaled to match;
  * exact numeric values are printed on the bars wherever differences are
    small enough that the bar length alone is not readable;
  * axis labels name the quantity and its units in full, and the forward
    request radius is labelled consistently as r_rel throughout.

Figures produced (vector PDF):
  fig_miss_by_tier.pdf        - miss rate of 8 policies x 3 mobility tiers
  fig_ablation_flip.pdf       - SU-LFU margin as one config parameter changes
  fig_signal_correlation.pdf  - Spearman rho of each signal vs realized demand
  fig_freeflow.pdf            - margins vs request radius on free-flow US-101
  fig_radius_continuum.pdf    - margin vs r_rel / lookahead ratio        [new]
  fig_zipf.pdf                - margin vs demand-model skew alpha        [new]
  fig_seed_stability.pdf      - margin and CI as seeds accumulate        [new]
Figures whose input JSON is absent are skipped with a notice.
"""
import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "experiments", "results")
OUT = os.path.join(HERE, "..", "paper_figures")
os.makedirs(OUT, exist_ok=True)

RNG = np.random.default_rng(20260918)


def load(name):
    path = os.path.join(RES, name)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def boot_ci(d, n_boot=10000):
    """Percentile bootstrap 95 % CI on the mean of a paired difference."""
    d = np.asarray(d, float)
    m = np.array([RNG.choice(d, size=d.size, replace=True).mean()
                  for _ in range(n_boot)])
    lo, hi = np.percentile(m, [2.5, 97.5])
    return float(d.mean()), float(lo), float(hi)


# --- shared publication style (colourblind-safe, no chartjunk) ---
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 10.5,
    "axes.labelsize": 10.5,
    "axes.titlesize": 10.5,
    "xtick.labelsize": 9.5,
    "ytick.labelsize": 9.5,
    "legend.fontsize": 9.5,
    "axes.linewidth": 0.9,
    "axes.edgecolor": "#333333",
    "axes.grid": True,
    "grid.color": "#DDDDDD",
    "grid.linewidth": 0.6,
    "axes.axisbelow": True,
    "figure.dpi": 150,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.03,
})
C_SYNTH, C_SUMO, C_REAL = "#4C72B0", "#DD8452", "#55A868"
C_WIN, C_LOSE = "#4C72B0", "#C44E52"
C_POP, C_URG = "#55A868", "#C44E52"
C_EDC = "#8172B3"

POLICY_ORDER = ["EDC", "LFU", "SU", "LRU", "FIFO", "Random", "Proximity", "QLearning"]
JSON_NAME = {"SU": "TC_W0.2"}


def _get(pol_dict, disp):
    for k in (JSON_NAME.get(disp, disp), disp, "SU", "TC_W0.2"):
        if k in pol_dict:
            return pol_dict[k]
    raise KeyError(disp)


# ============================ Figure 1 ============================
def fig_miss_by_tier():
    mt = load("matched_tiers_535m.json")
    real_all = load("real_ngsim_i80.json")
    if mt is None or real_all is None:
        print("skip fig_miss_by_tier (missing input)")
        return
    real = real_all["policies"]
    synth, sumo = mt["synthetic"], mt["sumo"]

    means = {t: [] for t in ("s", "u", "r")}
    stds = {t: [] for t in ("s", "u", "r")}
    for p in POLICY_ORDER:
        for tag, src in (("s", synth), ("u", sumo), ("r", real)):
            d = _get(src, p)
            means[tag].append(d["mean"])
            stds[tag].append(d["std"])

    x = np.arange(len(POLICY_ORDER))
    w = 0.26
    fig, ax = plt.subplots(figsize=(7.4, 3.6))
    for off, tag, col, lab in ((-w, "s", C_SYNTH, "Synthetic"),
                               (0.0, "u", C_SUMO, "SUMO"),
                               (w, "r", C_REAL, "Real (NGSIM I-80)")):
        ax.bar(x + off, means[tag], w, yerr=stds[tag], capsize=2.5,
               color=col, edgecolor="#222222", linewidth=0.4,
               error_kw=dict(elinewidth=0.7, ecolor="#444444"), label=lab)

    # Exact values for the three policies whose differences are small.
    for i, p in enumerate(POLICY_ORDER):
        if p not in ("EDC", "LFU", "SU"):
            continue
        for off, tag in ((-w, "s"), (0.0, "u"), (w, "r")):
            v = means[tag][i]
            ax.text(x[i] + off, v + stds[tag][i] + 0.5, f"{v:.1f}",
                    ha="center", fontsize=7.2, rotation=90, color="#222222")

    lfu_ref = _get(synth, "LFU")["mean"]
    ax.axhline(lfu_ref, ls="--", lw=0.9, color="#888888", zorder=0)
    ax.text(len(x) - 0.4, lfu_ref - 2.4, "LFU (synthetic) reference",
            fontsize=8, color="#666666", ha="right")

    ax.set_xticks(x)
    ax.set_xticklabels(POLICY_ORDER, rotation=20, ha="right")
    ax.set_ylabel("Cache miss rate (%)")
    ax.set_xlabel("Cache replacement policy")
    ax.set_ylim(45, 92)
    ax.set_title("Controlled configuration (535 m segment, forward request\n"
                 "radius $r_{\\mathrm{rel}}=150$ m), 10 seeds; lower is better")
    ax.legend(frameon=False, ncol=3, loc="upper left", handlelength=1.3,
              columnspacing=1.3)
    fig.savefig(os.path.join(OUT, "fig_miss_by_tier.pdf"))
    plt.close(fig)
    print(f"fig_miss_by_tier.pdf  (LFU synth mean = {lfu_ref:.2f})")


# ============================ Figure 2 ============================
def fig_ablation_flip():
    ca = load("config_ablation.json")
    if ca is None:
        print("skip fig_ablation_flip (missing input)")
        return
    rows = [("C0_orig_10km", "Original: 10 km, $r_{\\mathrm{rel}}{=}800$ m"),
            ("C1_unidirectional", "$+$ unidirectional flow"),
            ("C2_dispersed_content", "$+$ content dispersed"),
            ("C3_small_rrel", "$+$ $r_{\\mathrm{rel}}$ $800{\\to}150$ m"),
            ("C4_short_road", "$+$ short road (535 m)"),
            ("C5_realistic_slow", "$+$ realistic congested speed")]
    labels, margins = [], []
    err_lo, err_hi = [], []
    for key, lab in rows:
        su = np.array(ca[key]["SU"]["per_seed"])
        lfu = np.array(ca[key]["LFU"]["per_seed"])
        m, lo, hi = boot_ci(su - lfu)
        labels.append(lab)
        margins.append(m)
        err_lo.append(max(0.0, m - lo))
        err_hi.append(max(0.0, hi - m))

    y = np.arange(len(labels))[::-1]
    colors = [C_LOSE if m > 0 else C_WIN for m in margins]
    fig, ax = plt.subplots(figsize=(6.8, 3.6))
    ax.barh(y, margins, xerr=[err_lo, err_hi], capsize=2.5, color=colors,
            edgecolor="#222222", linewidth=0.4,
            error_kw=dict(elinewidth=0.8, ecolor="#444444"))
    ax.axvline(0, color="#333333", lw=1.1)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("SU $-$ LFU miss-rate margin (percentage points)")

    for i, (yi, m) in enumerate(zip(y, margins)):
        if m >= 0:
            ax.text(m + err_hi[i] + 0.12, yi, f"{m:+.2f}", va="center",
                    ha="left", fontsize=8.5)
        else:
            ax.text(m - err_lo[i] - 0.12, yi, f"{m:+.2f}", va="center",
                    ha="right", fontsize=8.5)

    ax.set_xlim(min(margins) - 1.8, max(margins) + 1.8)
    ax.set_ylim(-0.75, len(labels) - 0.25)
    ax.text(-0.12, -0.60, "$\\leftarrow$ SU better", fontsize=8.5,
            color=C_WIN, ha="right", va="center", style="italic")
    ax.text(0.12, -0.60, "LFU better $\\rightarrow$", fontsize=8.5,
            color=C_LOSE, ha="left", va="center", style="italic")
    ax.set_title("One parameter changed per row (synthetic tier, 10 seeds)\n"
                 "error bars: bootstrap 95 % CI on the paired difference")
    fig.savefig(os.path.join(OUT, "fig_ablation_flip.pdf"))
    plt.close(fig)
    print("fig_ablation_flip.pdf  margins = " +
          ", ".join(f"{m:.2f}" for m in margins))


# ============================ Figure 3 ============================
def fig_signal_correlation():
    sc = load("ngsim_signal_correlation.json")
    if sc is None:
        print("skip fig_signal_correlation (missing input)")
        return
    order = [("popularity", "Popularity\n(LFU signal)"),
             ("pop_x_exposure", "Pop. $\\times$ exposure\n(EDC signal)"),
             ("urgency_SU", "Urgency\n(SU signal)"),
             ("exposure", "Exposure")]
    labels = [lab for _, lab in order]
    means = [sc[k]["mean"] for k, _ in order]
    stds = [sc[k]["std"] for k, _ in order]
    cols = [C_POP, C_POP, C_URG, C_URG]

    x = np.arange(len(order))
    fig, ax = plt.subplots(figsize=(5.2, 3.5))
    ax.bar(x, means, 0.62, yerr=stds, capsize=3, color=cols,
           edgecolor="#222222", linewidth=0.4,
           error_kw=dict(elinewidth=0.8, ecolor="#444444"))
    for xi, m, s in zip(x, means, stds):
        ax.text(xi, m + s + 0.03, f"{m:.2f}", ha="center", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8.5)
    ax.set_ylabel("Spearman $\\rho$ with realized demand\nover the next 30 s")
    ax.set_xlabel("Scoring signal")
    ax.set_ylim(0, 1.05)
    ax.set_title("Real NGSIM I-80, 5 seeds: urgency is informative\n"
                 "but weaker than popularity")
    leg = [Patch(facecolor=C_POP, edgecolor="#222", label="popularity-based"),
           Patch(facecolor=C_URG, edgecolor="#222", label="spatial / urgency")]
    ax.legend(handles=leg, frameon=False, loc="upper right")
    fig.savefig(os.path.join(OUT, "fig_signal_correlation.pdf"))
    plt.close(fig)
    print("fig_signal_correlation.pdf  rho = " +
          ", ".join(f"{m:.3f}" for m in means))


# ============================ Figure 4 ============================
def fig_freeflow():
    d = load("real_freeflow.json")
    if d is None:
        print("skip fig_freeflow (missing input)")
        return
    radii = sorted(d["by_radius"], key=lambda s: int(s))
    su_m, edc_m = [], []
    su_lo, su_hi, edc_lo, edc_hi = [], [], [], []
    for r in radii:
        p = d["by_radius"][r]
        lfu = np.array(p["LFU"]["per_seed"])
        m, lo, hi = boot_ci(np.array(p["SU"]["per_seed"]) - lfu)
        su_m.append(m); su_lo.append(max(0.0, m - lo)); su_hi.append(max(0.0, hi - m))
        m, lo, hi = boot_ci(np.array(p["EDC"]["per_seed"]) - lfu)
        edc_m.append(m); edc_lo.append(max(0.0, m - lo)); edc_hi.append(max(0.0, hi - m))

    x = np.arange(len(radii))
    w = 0.36
    fig, ax = plt.subplots(figsize=(5.4, 3.5))
    ax.bar(x - w / 2, su_m, w, yerr=[su_lo, su_hi], capsize=3, color=C_LOSE,
           edgecolor="#222", linewidth=0.4,
           error_kw=dict(elinewidth=0.8, ecolor="#444"), label="SU $-$ LFU")
    ax.bar(x + w / 2, edc_m, w, yerr=[edc_lo, edc_hi], capsize=3, color=C_EDC,
           edgecolor="#222", linewidth=0.4,
           error_kw=dict(elinewidth=0.8, ecolor="#444"), label="EDC $-$ LFU")
    for xi, m, e in zip(x - w / 2, su_m, su_hi):
        ax.text(xi, m + e + 0.12, f"{m:+.2f}", ha="center", fontsize=8.5)
    for xi, m, e in zip(x + w / 2, edc_m, edc_hi):
        ax.text(xi, m + e + 0.12, f"{m:+.2f}", ha="center", fontsize=8.5)
    ax.axhline(0, color="#333", lw=1.1)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r} m" for r in radii])
    ax.set_xlabel("Forward request radius $r_{\\mathrm{rel}}$ (m)")
    ax.set_ylabel("Miss-rate margin vs LFU\n(percentage points)")
    ax.set_ylim(min(0, min(edc_m)) - 0.6, max(su_m) + 1.5)
    ax.text(0.02, 0.96, "above 0 = worse than LFU", transform=ax.transAxes,
            fontsize=8.5, color="#C44E52", va="top", style="italic")
    ax.set_title("Free-flow real traffic (US-101, 41 km/h, 10 seeds)\n"
                 "error bars: bootstrap 95 % CI")
    ax.legend(frameon=False, loc="upper right")
    fig.savefig(os.path.join(OUT, "fig_freeflow.pdf"))
    plt.close(fig)
    print("fig_freeflow.pdf  SU-LFU = " + ", ".join(f"{m:.2f}" for m in su_m))


# ======================= Figure 5 (new) ==========================
def fig_radius_continuum():
    d = load("radius_continuum.json")
    if d is None:
        print("skip fig_radius_continuum (missing input)")
        return
    grid = d["grid"]
    tpreds = sorted({g["t_pred_s"] for g in grid})
    cmap = plt.get_cmap("viridis")

    fig, axes = plt.subplots(1, 2, figsize=(9.4, 3.7))

    ax = axes[0]
    for i, tp in enumerate(tpreds):
        pts = sorted([g for g in grid if g["t_pred_s"] == tp],
                     key=lambda g: g["r_req_m"])
        ax.plot([g["r_req_m"] for g in pts], [g["margin"] for g in pts],
                marker="o", ms=3.5, lw=1.2,
                color=cmap(i / max(1, len(tpreds) - 1)),
                label=f"$T_{{\\mathrm{{pred}}}}={tp:.0f}$ s")
    ax.axhline(0, color="#333", lw=1.1)
    ax.set_xlabel("Forward request radius $r_{\\mathrm{rel}}$ (m)")
    ax.set_ylabel("SU $-$ LFU margin\n(percentage points)")
    ax.set_title("(a) Margin against the request radius")
    ax.legend(frameon=False, ncol=2, fontsize=8.2)

    ax = axes[1]
    for i, tp in enumerate(tpreds):
        pts = sorted([g for g in grid if g["t_pred_s"] == tp],
                     key=lambda g: g["rho"])
        ax.plot([g["rho"] for g in pts], [g["margin"] for g in pts],
                marker="o", ms=3.5, lw=1.2, alpha=0.9,
                color=cmap(i / max(1, len(tpreds) - 1)),
                label=f"$T_{{\\mathrm{{pred}}}}={tp:.0f}$ s")
    ax.axhline(0, color="#333", lw=1.1)
    ax.axvline(1.0, ls="--", lw=1.0, color="#888")
    ylim = ax.get_ylim()
    ax.text(1.12, ylim[1] - 0.10 * (ylim[1] - ylim[0]),
            "$r_{\\mathrm{rel}}=D_{\\mathrm{look}}$", fontsize=8.5,
            color="#666")
    ax.set_xscale("log")
    ax.set_xlabel("Ratio $\\rho = r_{\\mathrm{rel}} / "
                  "(T_{\\mathrm{pred}}\\,\\bar{s})$")
    ax.set_ylabel("SU $-$ LFU margin\n(percentage points)")
    ax.set_title("(b) The same cells against the ratio")

    fig.suptitle("Request radius crossed with prediction horizon "
                 "(10 km road, 10 seeds)", fontsize=10.5, y=1.03)
    fig.savefig(os.path.join(OUT, "fig_radius_continuum.pdf"))
    plt.close(fig)
    print(f"fig_radius_continuum.pdf  ({len(grid)} grid cells)")


# ======================= Figure 6 (new) ==========================
def fig_zipf():
    d = load("zipf_sensitivity.json")
    if d is None:
        print("skip fig_zipf (missing input)")
        return
    alphas = d["_meta"]["alphas"]
    su_m, edc_m = [], []
    su_lo, su_hi, edc_lo, edc_hi = [], [], [], []
    for a in alphas:
        c = d[f"alpha_{a}"]
        lfu = np.array(c["LFU"]["per_seed"])
        m, lo, hi = boot_ci(np.array(c["SU"]["per_seed"]) - lfu)
        su_m.append(m); su_lo.append(max(0.0, m - lo)); su_hi.append(max(0.0, hi - m))
        m, lo, hi = boot_ci(np.array(c["EDC"]["per_seed"]) - lfu)
        edc_m.append(m); edc_lo.append(max(0.0, m - lo)); edc_hi.append(max(0.0, hi - m))

    fig, ax = plt.subplots(figsize=(5.8, 3.6))
    ax.errorbar(alphas, su_m, yerr=[su_lo, su_hi], marker="o", ms=5, lw=1.4,
                capsize=3, color=C_LOSE, label="SU $-$ LFU")
    ax.errorbar(alphas, edc_m, yerr=[edc_lo, edc_hi], marker="s", ms=5, lw=1.4,
                capsize=3, color=C_EDC, label="EDC $-$ LFU")
    ax.axhline(0, color="#333", lw=1.1)
    ax.axvline(0.8, ls="--", lw=1.0, color="#888")
    for a, m in zip(alphas, su_m):
        ax.text(a, m + 0.55, f"{m:+.2f}", ha="center", fontsize=8.2,
                color=C_LOSE)
    ax.set_ylim(min(edc_m) - 1.1, max(su_m) + 1.6)
    ax.text(0.78, min(edc_m) - 0.75, "value used in the main text",
            fontsize=8.2, color="#666", ha="right")
    ax.set_xlabel("Zipf skew $\\alpha$ of the content popularity law")
    ax.set_ylabel("Miss-rate margin vs LFU\n(percentage points)")
    ax.set_title("Demand-model sensitivity (synthetic tier, 10 seeds)\n"
                 "at $\\alpha=0$ popularity carries no rank information")
    ax.legend(frameon=False, loc="upper left")
    fig.savefig(os.path.join(OUT, "fig_zipf.pdf"))
    plt.close(fig)
    print("fig_zipf.pdf  SU-LFU = " + ", ".join(f"{m:.2f}" for m in su_m))


# ======================= Figure 7 (new) ==========================
def fig_seed_stability():
    d = load("seed_extension.json")
    if d is None:
        print("skip fig_seed_stability (missing input)")
        return
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 3.6), sharex=True)
    for ax, suffix, title in ((axes[0], "SU-LFU", "(a) SU $-$ LFU"),
                              (axes[1], "EDC-LFU", "(b) EDC $-$ LFU")):
        for tier, col in (("synthetic", C_SYNTH), ("sumo", C_SUMO),
                          ("real_ngsim", C_REAL)):
            key = f"{tier}/{suffix}"
            if key not in d["stability"]:
                continue
            c = d["stability"][key]
            ks = [p["k"] for p in c]
            ms = [p["mean"] for p in c]
            lo = [p["ci_lo"] for p in c]
            hi = [p["ci_hi"] for p in c]
            ax.plot(ks, ms, lw=1.4, color=col, label=tier.replace("_", " "))
            ax.fill_between(ks, lo, hi, color=col, alpha=0.16, linewidth=0)
        ax.axhline(0, color="#333", lw=1.1)
        ax.axvline(10, ls="--", lw=1.0, color="#888")
        ax.set_xlabel("Number of seeds $k$")
        ax.set_ylabel("Paired margin\n(percentage points)")
        ax.set_title(title)
    ylim = axes[0].get_ylim()
    axes[0].text(10.5, ylim[0] + 0.06 * (ylim[1] - ylim[0]),
                 "published $k=10$", fontsize=8.2, color="#666")
    axes[0].legend(frameon=False, loc="best", fontsize=8.5)
    fig.suptitle("Stability of each paired difference as seeds accumulate "
                 "(shaded band: bootstrap 95 % CI)", fontsize=10.5, y=1.03)
    fig.savefig(os.path.join(OUT, "fig_seed_stability.pdf"))
    plt.close(fig)
    print("fig_seed_stability.pdf")


if __name__ == "__main__":
    fig_miss_by_tier()
    fig_ablation_flip()
    fig_signal_correlation()
    fig_freeflow()
    fig_radius_continuum()
    fig_zipf()
    fig_seed_stability()
    print("done ->", os.path.normpath(OUT))
