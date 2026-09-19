"""Measure the original lettering and size the LaTeX replacements to match.

For each text block: find the real ink bounding box inside its declared
rectangle, typeset the same string at a reference size, and solve for the point
size that reproduces the original width. The result is written to sizes.json
and consumed by gen_fig1.py, so the replacement text occupies the same space on
the page as the lettering it replaces.
"""
import io
import json
import re
import subprocess
import sys

import numpy as np
from PIL import Image

REF = 10.0  # reference point size for the probe


def ink_boxes(png, blocks):
    im = Image.open(png).convert("RGB")
    a = np.asarray(im).astype(int)
    ink = a.max(axis=2) < 250
    out = []
    for (x0, y0, x1, y1) in blocks:
        sub = ink[y0:y1, x0:x1]
        ys, xs = np.nonzero(sub)
        if len(xs) == 0:
            out.append(None)
            continue
        out.append((x0 + int(xs.min()), y0 + int(ys.min()),
                    x0 + int(xs.max()) + 1, y0 + int(ys.max()) + 1))
    return out


def probe_widths(bodies, fonts, workdir="."):
    src = [
        r"\documentclass{article}",
        r"\usepackage[T1]{fontenc}",
        r"\usepackage{amsmath,amssymb}",
        r"\usepackage[scaled=0.95]{helvet}",
        r"\renewcommand{\familydefault}{\sfdefault}",
        r"\usepackage{newtxsf}",
        r"\usepackage{anyfontsize}",
        r"\makeatletter",
        r"\newcommand{\W}[2]{\setbox0\hbox{#2}\typeout{PROBE #1 "
        r"\strip@pt\dimexpr\wd0*1000/2845\relax|"
        r"\strip@pt\dimexpr\ht0*1000/2845\relax}}",
        r"\makeatother",
        r"\begin{document}",
    ]
    for i, (body, bold) in enumerate(zip(bodies, fonts)):
        wt = r"\bfseries" if bold else ""
        src.append(r"\W{%d}{\fontsize{%s}{%s}\selectfont%s %s}"
                   % (i, REF, REF * 1.2, wt, body))
    src.append(r"\end{document}")
    io.open("_probe.tex", "w", encoding="utf-8").write("\n".join(src))
    subprocess.run(["pdflatex", "-interaction=nonstopmode", "_probe.tex"],
                   capture_output=True, text=True, cwd=workdir)
    log = io.open("_probe.log", encoding="utf-8", errors="replace").read()
    res = {}
    for m in re.finditer(r"PROBE (\d+) ([\d.-]+)\|([\d.-]+)", log):
        res[int(m.group(1))] = (float(m.group(2)), float(m.group(3)))
    return res


if __name__ == "__main__":
    import importlib
    mod = sys.argv[1] if len(sys.argv) > 1 else "gen_fig1"
    G = importlib.import_module(mod)
    OUT = "sizes.json" if mod == "gen_fig1" else "sizes2.json"

    blocks = [(t[0], t[1], t[2], t[3]) for t in G.T]
    bodies = [t[7] for t in G.T]
    if mod == "gen_fig1":
        bolds = ["fBold" in t[5] or "fTitle" in t[5] for t in G.T]
    else:
        bolds = [bool(t[5]) for t in G.T]

    boxes = ink_boxes(G.PNG, blocks)
    probe = probe_widths(bodies, bolds)

    sizes, anchors = [], []
    for i, (t, ib) in enumerate(zip(G.T, boxes)):
        if ib is None or i not in probe:
            sizes.append(None)
            anchors.append(None)
            print(f"  block {i}: no ink or no probe, keeping default")
            continue
        target_mm = (ib[2] - ib[0]) * G.K
        w10 = probe[i][0]
        pt = REF * target_mm / w10 if w10 > 0 else REF
        pt = max(4.2, min(pt, 20.0))
        sizes.append(round(pt, 2))
        anchors.append(ib)
        print(f"  block {i:2d}: target {target_mm:6.2f} mm  "
              f"w@10pt {w10:6.2f} mm  -> {pt:5.2f} pt   {bodies[i][:38]}")

    json.dump({"sizes": sizes, "ink": anchors}, open(OUT, "w"), indent=1)
    print("\nwrote sizes.json")
