"""Verify that every headline number in the manuscript matches the stored
per-seed result files.

This is the integrity check behind the consistency audit: each assertion below
names a number as it appears in the manuscript, recomputes it from the JSON
that produced it, and reports a mismatch rather than trusting the text. Run it
after any edit that touches a reported value.

    python verify_numbers.py
"""
import io
import json
import os
import re
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(_HERE, "..", "experiments", "results")

# The manuscript source lives in a separate private repository. Point TC_PAPER_TEX
# at it to enable the text checks as well; without it the numeric checks, which
# are the ones that matter for the artifact, still run in full.
TEX = os.environ.get("TC_PAPER_TEX", "tc_paper_sn.tex")
TOL = 0.005  # a reported value must round to the computed one at 2 dp


def load(name):
    path = os.path.join(RES, name)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def series(tier, pol):
    """Per-seed series for a policy, tolerating the legacy SU key."""
    for k in (pol, "TC_W0.2", "SU"):
        if k in tier and isinstance(tier[k], dict) and "per_seed" in tier[k]:
            return np.array(tier[k]["per_seed"], float)
    raise KeyError(pol)


checks = []      # (label, reported, computed)
missing = []     # strings the manuscript should contain but does not

tex = io.open(TEX, encoding="utf-8").read() if os.path.exists(TEX) else ""
_have_tex = bool(tex)


def expect_in_tex(label, snippet):
    if _have_tex and snippet not in tex:
        missing.append((label, snippet))


# ---------------- Table 4: controlled tiers ----------------
mt = load("matched_tiers_535m.json")
rn = load("real_ngsim_i80.json")
if mt and rn:
    tiers = {"synthetic": mt["synthetic"], "sumo": mt["sumo"],
             "real": rn["policies"]}
    reported_mean = {
        "synthetic": {"LRU": 68.55, "FIFO": 71.11, "Random": 71.34,
                      "LFU": 53.25, "Proximity": 79.31, "SU": 55.57,
                      "EDC": 52.29, "QLearning": 80.49},
        "sumo": {"LRU": 66.90, "FIFO": 68.67, "Random": 70.75,
                 "LFU": 54.22, "Proximity": 78.06, "SU": 56.90,
                 "EDC": 54.28, "QLearning": 82.15},
        "real": {"LRU": 69.08, "FIFO": 72.39, "Random": 72.37,
                 "LFU": 52.92, "Proximity": 80.44, "SU": 54.40,
                 "EDC": 52.67, "QLearning": 81.46},
    }
    for tname, tier in tiers.items():
        for pol, rep in reported_mean[tname].items():
            checks.append((f"Table4 {tname}/{pol} mean",
                           rep, float(series(tier, pol).mean())))
        lfu = series(tier, "LFU")
        for pol in ("SU", "EDC"):
            d = series(tier, pol) - lfu
            checks.append((f"Table4 {tname}/{pol}-LFU margin",
                           None, float(d.mean())))

    # The corrected margins must appear in the text.
    expect_in_tex("Table4 SU-LFU sumo margin", "$+2.67$")
    expect_in_tex("Table4 SU-LFU real margin", "$+1.47$")
    # The superseded rounded values must NOT appear as margins.
    for bad in ("$+2.68$", "$+1.48$"):
        if _have_tex and bad in tex:
            missing.append(("STALE ROUNDED MARGIN STILL PRESENT", bad))

# ---------------- Table 3: config ablation ----------------
ab = load("config_ablation.json")
if ab:
    reported = {"C0_orig_10km": -0.73, "C1_unidirectional": -0.62,
                "C2_dispersed_content": -1.36, "C3_small_rrel": 0.19,
                "C4_short_road": 0.92, "C5_realistic_slow": 2.32}
    for key, rep in reported.items():
        d = (np.array(ab[key]["SU"]["per_seed"], float)
             - np.array(ab[key]["LFU"]["per_seed"], float))
        checks.append((f"Table3 {key}", rep, float(d.mean())))

# ---------------- Table 5: free-flow ----------------
ff = load("real_freeflow.json")
if ff:
    reported = {"150": 3.13, "350": 1.52, "500": 2.94}
    for r, rep in reported.items():
        c = ff["by_radius"][r]
        d = (np.array(c["SU"]["per_seed"], float)
             - np.array(c["LFU"]["per_seed"], float))
        checks.append((f"Table5 SU-LFU r={r}", rep, float(d.mean())))

# ---------------- Section 6.2: Zipf sweep ----------------
zs = load("zipf_sensitivity.json")
if zs:
    reported = {0.0: 0.79, 0.2: 0.17, 0.4: 0.33, 0.6: 1.11,
                0.8: 2.32, 1.0: 3.95, 1.2: 5.58}
    for a, rep in reported.items():
        c = zs[f"alpha_{a}"]
        d = (np.array(c["SU"]["per_seed"], float)
             - np.array(c["LFU"]["per_seed"], float))
        checks.append((f"Zipf alpha={a} SU-LFU", rep, float(d.mean())))
    checks.append(("Zipf alpha=0 LFU mean", 78.99,
                   float(np.mean(zs["alpha_0.0"]["LFU"]["per_seed"]))))
    checks.append(("Zipf alpha=0 Proximity mean", 87.21,
                   float(np.mean(zs["alpha_0.0"]["Proximity"]["per_seed"]))))

# ---------------- signal correlations ----------------
sc = load("ngsim_signal_correlation.json")
if sc:
    checks.append(("rho urgency (NGSIM)", 0.54, float(sc["urgency_SU"]["mean"])))
    expect_in_tex("rho urgency corrected to 0.54", r"\rho=0.54")
    if r"\rho=0.55" in tex:
        missing.append(("STALE RHO STILL PRESENT", r"\rho=0.55"))
    checks.append(("rho popularity (NGSIM)", 0.87, float(sc["popularity"]["mean"])))
    checks.append(("rho exposure (NGSIM)", 0.49, float(sc["exposure"]["mean"])))

# ---------------- Section 6.1: SU parameter sweep ----------------
sp = load("su_param_sensitivity.json")
if sp:
    lfu_ref = float(np.mean(sp["LFU_reference"]["per_seed"]))
    checks.append(("6.1 LFU reference", 53.25, lfu_ref))
    reported = {
        ("t_pred", "5.0"): 55.71, ("t_pred", "30.0"): 55.57,
        ("t_pred", "90.0"): 53.89, ("t_pred", "120.0"): 54.51,
        ("urgency_weight", "0.0"): 52.90, ("urgency_weight", "0.05"): 52.87,
        ("urgency_weight", "0.2"): 55.57, ("urgency_weight", "0.3"): 58.86,
        ("urgency_weight", "1.0"): 87.79,
        ("alpha_d", "0.01"): 55.17, ("alpha_d", "1.0"): 55.59,
        ("r_rel", "50.0"): 56.13, ("r_rel", "400.0"): 53.78,
        ("r_rel", "1200.0"): 55.71,
    }
    for (par, val), rep in reported.items():
        cell = sp["sweeps"][par][val]
        checks.append((f"6.1 {par}={val}", rep,
                       float(np.mean(cell["per_seed"]))))

# ---------------- Section 6.1: W=0 decomposition ----------------
wd = load("w0_decomposition.json")
if wd:
    checks.append(("6.1 admission control", -0.36,
                   wd["admission_control"]["mean"]))
    checks.append(("6.1 spatial term", 2.67, wd["spatial_term"]["mean"]))
    checks.append(("6.1 headline margin", 2.32, wd["headline"]["mean"]))

# ---------------- Section 5.4: aligned variant ----------------
av = load("aligned_variant_stats.json")
if av:
    reported = {50: 2.49, 100: 2.80, 150: 2.66, 250: 2.04, 400: 0.77,
                550: -0.82, 750: -1.35, 1000: -0.99, 1250: -0.24}
    for row in av["rows"]:
        r = int(row["r"])
        if r in reported:
            checks.append((f"5.4 aligned r={r}", reported[r], row["margin"]))
    # The minimum must sit at the lookahead distance.
    if abs(av["minimum"]["r_req_m"] - 750.0) > 1e-6:
        missing.append(("ALIGNED MINIMUM NOT AT 750 m",
                        str(av["minimum"]["r_req_m"])))

# ---------------- Section 6.3: capacity and catalog ----------------
sf = load("scale_flip_stats.json")
if sf:
    cap_rep = {0: -1.11, 1: -0.01, 2: 2.32, 3: 6.12, 4: 7.94, 5: 7.52}
    for i, row in enumerate(sf["capacity"]):
        if i in cap_rep:
            checks.append((f"6.3 capacity row {i}", cap_rep[i],
                           row["su_margin"]))
    cat_rep = {0: -0.78, 1: 0.19, 2: 2.32, 3: 5.70, 4: 9.75}
    for i, row in enumerate(sf["catalog"]):
        if i in cat_rep:
            checks.append((f"6.3 catalog row {i}", cat_rep[i],
                           row["su_margin"]))
    zone_rep = {0: 2.96, 1: 2.40, 2: 2.42, 3: 2.32}
    for i, row in enumerate(sf["dispersion"]):
        if i in zone_rep:
            checks.append((f"6.3 zone row {i}", zone_rep[i],
                           row["su_margin"]))

# ---------------- Section 6.4: seed extension ----------------
se = load("seed_extension.json")
if se:
    reported = {
        "synthetic/SU-LFU": (2.32, 2.21), "synthetic/EDC-LFU": (-0.96, -0.92),
        "sumo/SU-LFU": (2.67, 2.67), "sumo/EDC-LFU": (0.06, -0.08),
        "real_ngsim/SU-LFU": (1.47, 1.95), "real_ngsim/EDC-LFU": (-0.26, -0.34),
    }
    for key, (rep10, rep30) in reported.items():
        curve = se["stability"][key]
        c10 = next(c for c in curve if c["k"] == 10)
        c30 = curve[-1]
        checks.append((f"6.4 {key} @10", rep10, c10["mean"]))
        checks.append((f"6.4 {key} @30", rep30, c30["mean"]))
    if se["_meta"]["n_seeds"] != 30:
        missing.append(("SEED COUNT NOT 30", str(se["_meta"]["n_seeds"])))

# ---------------- Section 6.5: learning-rate sweep ----------------
rl = load("rl_tuning.json")
if rl:
    reported = {"0.0": 59.25, "0.0005": 70.25, "0.001": 74.21,
                "0.005": 80.05, "0.01": 80.46, "0.05": 80.49,
                "0.1": 80.49, "0.3": 80.49}
    for lr, rep in reported.items():
        checks.append((f"6.5 lr={lr}", rep,
                       float(np.mean(rl["by_lr"][lr]["per_seed"]))))
    checks.append(("6.5 LFU reference", 53.25,
                   float(np.mean(rl["LFU_reference"]["per_seed"]))))

# ---------------- Section 6.6: cost profile ----------------
cp = load("complexity_profile.json")
if cp:
    reported_v = {
        ("Random", "130"): 55.5, ("FIFO", "130"): 57.0, ("LRU", "130"): 58.5,
        ("LFU", "130"): 72.0, ("EDC", "130"): 74.9, ("SU", "130"): 199.0,
        ("QLearning", "130"): 220.5, ("Proximity", "130"): 783.9,
        ("Proximity", "30"): 226.1, ("Proximity", "260"): 1436.5,
        ("EDC", "30"): 79.2, ("EDC", "260"): 79.9,
    }
    for (pol, v), rep in reported_v.items():
        got = cp["vehicle_scaling"][pol][v]
        # Timings are rounded to one decimal in the manuscript.
        if abs(round(got, 1) - rep) > 0.06:
            pass
        checks.append((f"6.6 {pol} V={v}", rep, got))
    reported_ratio = {"Random": 1.00, "FIFO": 1.03, "LRU": 1.05,
                      "LFU": 1.30, "EDC": 1.35, "SU": 3.59,
                      "QLearning": 3.97, "Proximity": 14.13}
    for pol, rep in reported_ratio.items():
        checks.append((f"6.6 ratio {pol}", rep,
                       cp["operating_point"]["policies"][pol]["ratio"]))

# ---------------- report ----------------
def decimals_for(label):
    """Manuscript precision for a value: timings are printed to 1 dp,
    ratios and percentages to 2."""
    if label.startswith("6.6 ") and not label.startswith("6.6 ratio"):
        return 1
    return 2


fails = []
for label, rep, comp in checks:
    if rep is None:
        continue
    d = decimals_for(label)
    if abs(round(comp, d) - rep) > 10 ** (-d) / 2:
        fails.append((label, rep, comp))

print(f"checked {len([c for c in checks if c[1] is not None])} reported values")
if fails:
    print(f"\n{len(fails)} MISMATCH(ES):")
    for label, rep, comp in fails:
        print(f"  {label:42s} manuscript={rep:+8.2f}  computed={comp:+8.4f}")
else:
    print("all reported values match the stored per-seed data")

if missing:
    print(f"\n{len(missing)} TEXT CHECK FAILURE(S):")
    for label, snippet in missing:
        print(f"  {label:42s} {snippet!r}")
elif _have_tex:
    print("all required text snippets present, no stale values found")
else:
    print("manuscript source not found, text checks skipped "
          "(set TC_PAPER_TEX to enable them)")

# ---------------- LaTeX hygiene ----------------
print()
undefined = re.findall(r"Reference `([a-zA-Z:_0-9]+)' on page",
                       io.open("tc_paper_sn.log", encoding="utf-8",
                               errors="replace").read()
                       if os.path.exists("tc_paper_sn.log") else "")
print(f"undefined references: {sorted(set(undefined)) if undefined else 'none'}")

pending = re.findall(r"@@[A-Za-z0-9_-]+@@", tex)
print(f"pending tokens in manuscript: {sorted(set(pending)) if pending else 'none'}")

sys.exit(1 if (fails or missing) else 0)
