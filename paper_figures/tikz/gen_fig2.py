"""Generate the Figure 2 overlay .tex.

Same approach as Figure 1: the original raster is the artwork layer, used
exactly as drawn, and only the baked-in lettering is replaced with live LaTeX
text. Boxes are pixels in the source PNG (2537 x 1324), read off a measured
100 px grid.
"""
import io

PNG = "fig_methodology.png"
PW, PH = 2537, 1324
WMM = 160.0
K = WMM / PW
HMM = PH * K                     # 83.50 mm

def X(px): return px * K
def Y(py): return HMM - py * K

WHITE = "white"
INK = "cInk"
HDR = "cInk"
GREEN = "cGreen"
TEAL = "cTeal"
ORANGE = "cOrange"
GREY = "cGrey"

# (x0, y0, x1, y1, anchor, bold, colour, body)
T = [
    (0, 0, 462, 50, "l", 0, HDR, r"LEFT --- FIXED INPUTS"),
    (610, 0, 1754, 50, "c", 0, HDR, r"MIDDLE --- TWO INDEPENDENT EXPERIMENTAL FACTORS"),
    (1886, 0, 2537, 50, "c", 0, HDR, r"RIGHT --- COMMON EVALUATION"),

    (152, 126, 296, 178, "c", 1, GREEN, r"FIXED"),
    (44, 376, 402, 439, "c", 0, INK, r"Demand model"),
    (112, 440, 334, 497, "c", 0, INK, r"Zipf $\alpha=0.8$"),
    (126, 706, 318, 766, "c", 0, INK, r"Per-seed"),
    (56, 756, 386, 818, "c", 0, INK, r"request stream"),
    (132, 818, 306, 873, "c", 0, INK, r"identical"),
    (104, 1050, 334, 1113, "c", 0, INK, r"Held fixed"),

    (906, 124, 1472, 182, "c", 0, TEAL, r"MOBILITY SOURCE VARIED"),
    (620, 445, 1016, 508, "c", 0, INK, r"Synthetic platoon"),
    (1109, 445, 1264, 508, "c", 0, INK, r"SUMO"),
    (1370, 448, 1739, 511, "c", 0, INK, r"Recorded NGSIM"),

    (1002, 606, 1473, 662, "c", 0, GREY, r"INDEPENDENTLY VARIED"),

    (808, 754, 1575, 813, "c", 0, ORANGE, r"SCENARIO CONFIGURATION VARIED"),
    (954, 888, 1463, 951, "c", 0, INK, r"Forward request radius"),
    (1156, 956, 1252, 1014, "c", 0, INK, r"$r_{\mathrm{rel}}$"),
    (1027, 1052, 1378, 1113, "c", 0, INK, r"$150$ m $\leftrightarrow$ $800$ m"),
    (1388, 1020, 1590, 1072, "l", 0, ORANGE, r"scenario"),
    (1382, 1072, 1604, 1122, "l", 0, ORANGE, r"parameter"),

    (2000, 604, 2140, 668, "c", 0, INK, r"Same"),
    (1898, 658, 2208, 730, "c", 0, INK, r"cache-policy"),
    (1950, 711, 2196, 776, "c", 0, INK, r"evaluation"),
    (1893, 778, 2249, 835, "c", 0, INK, r"paired across seeds"),
    (2320, 604, 2537, 668, "c", 0, INK, r"Compare"),
    (2316, 654, 2537, 721, "c", 0, INK, r"outcomes"),

    (100, 1264, 2438, 1324, "c", 0, INK,
     r"Demand and per-seed request streams are held fixed while mobility "
     r"source and scenario configuration are varied independently."),
]

ANCH = {"l": "west", "c": "center", "r": "east"}

HEADER = r"""%% ===================================================================
%% Figure 2 - The two-factor experimental design.
%%
%% The artwork is the original raster, used exactly as drawn. Only the
%% lettering is replaced: each block of baked-in text is covered with an
%% opaque patch and the same words are set in LaTeX on top, so the labels
%% are live vector text while every icon stays as it was.
%%
%% Point sizes are measured, not guessed: calibrate.py reads the ink box of
%% each original label and solves for the size that reproduces its width.
%%
%%   python calibrate.py gen_fig2 && python gen_fig2.py
%%   pdflatex fig_methodology_tikz.tex
%%
%% Canvas is 160 x 83.50 mm, the source PNG at \textwidth of sn-jnl.
%% Generated file - edit gen_fig2.py, not this.
%% ===================================================================
\documentclass[border=0pt,varwidth=false]{standalone}

\usepackage[T1]{fontenc}
\usepackage{amsmath,amssymb}
\usepackage[scaled=0.95]{helvet}
\renewcommand{\familydefault}{\sfdefault}
\usepackage{newtxsf}
\usepackage{anyfontsize}
\usepackage{xcolor}
\usepackage{graphicx}
\usepackage{tikz}

\definecolor{cInk}{HTML}{111111}
\definecolor{cGreen}{HTML}{4F9A48}
\definecolor{cTeal}{HTML}{1A7B7C}
\definecolor{cOrange}{HTML}{D4832F}
\definecolor{cGrey}{HTML}{47494C}

\begin{document}
\begin{tikzpicture}[x=1mm,y=1mm]
\useasboundingbox (0,0) rectangle (160,83.50);
\node[anchor=south west,inner sep=0pt] at (0,0)
  {\includegraphics[width=160mm]{fig_methodology.png}};

"""

MINPT = 4.6


def main():
    import json
    import os

    SZ = json.load(open("sizes2.json")) if os.path.exists("sizes2.json") else None
    sizes = SZ["sizes"] if SZ else [None] * len(T)
    inks = SZ["ink"] if SZ else [None] * len(T)

    out = [HEADER, "% --- cover the baked-in lettering ---\n"]
    for x0, y0, x1, y1, a, b, col, body in T:
        out.append("\\fill[white] (%.2f,%.2f) rectangle (%.2f,%.2f);\n"
                   % (X(x0), Y(y1), X(x1), Y(y0)))

    out.append("\n% --- the same words, set in LaTeX at the original size ---\n")
    for i, (x0, y0, x1, y1, a, b, col, body) in enumerate(T):
        bx = inks[i] if inks[i] else (x0, y0, x1, y1)
        ax = {"l": X(bx[0]), "c": (X(bx[0]) + X(bx[2])) / 2.0, "r": X(bx[2])}[a]
        ay = (Y(bx[1]) + Y(bx[3])) / 2.0
        pt = max(sizes[i] if sizes[i] else 8.0, MINPT)
        bold = "\\bfseries" if b else ""
        out.append("\\node[anchor=%s,inner sep=0pt,outer sep=0pt,text=%s] "
                   "at (%.2f,%.2f) {\\fontsize{%.2f}{%.2f}\\selectfont%s %s};\n"
                   % (ANCH[a], col, ax, ay, pt, pt * 1.18, bold, body))

    out.append("\n\\end{tikzpicture}\n\\end{document}\n")
    io.open("fig_methodology_tikz.tex", "w", encoding="utf-8").write("".join(out))
    print("wrote fig_methodology_tikz.tex  (%d text blocks)" % len(T))
    print("canvas %.2f x %.2f mm" % (WMM, HMM))


if __name__ == "__main__":
    main()
