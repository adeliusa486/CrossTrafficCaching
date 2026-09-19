"""Generate the Figure 1 overlay .tex.

The original raster is used exactly as drawn. Only the baked-in lettering is
replaced: each text block is covered with an opaque patch and the same words
are set in LaTeX on top, so every label becomes selectable vector text while
the icons stay untouched.

Boxes below are pixels in the source PNG (2620 x 1384), read off a measured
100 px grid. The generator converts them to mm.
"""
import io

PNG = "fig_system_model.png"
PW, PH = 2620, 1384
WMM = 160.0
K = WMM / PW
HMM = PH * K                     # 84.52 mm

def X(px): return px * K
def Y(py): return HMM - py * K

WHITE = "white"
PANEL_A = "cPanelA"   # the decision rhombus has a soft vertical
PANEL_B = "cPanelB"   # gradient, so each text row gets its own shade
PANEL_C = "cPanelC"

# (x0, y0, x1, y1, anchor, font, fill, body)
#   anchor: l = west at x0, c = center, r = east at x1
T = [
    (20, 0, 2600, 90, "c", "fTitle", WHITE,
     r"System Model and Spatial-Urgency Cache Replacement Pipeline"),

    (238, 155, 420, 203, "c", "fHead", WHITE, r"NETWORK"),
    (893, 155, 1058, 203, "c", "fHead", WHITE, r"DEMAND"),
    (1310, 157, 1985, 206, "c", "fHead", WHITE, r"SPATIAL-URGENCY (SU) COMPUTATION"),
    (2152, 157, 2545, 206, "c", "fHead", WHITE, r"CACHE REPLACEMENT"),

    (218, 243, 508, 298, "l", "fBold", WHITE, r"Content Server"),
    (215, 293, 678, 340, "l", "fBody", WHITE, r"$N=200$ geo-anchored items"),
    (215, 336, 478, 393, "l", "fBody", WHITE, r"$F=\{f_1,\dots,f_N\}$"),
    (308, 418, 620, 462, "c", "fBody", WHITE, r"Backhaul (on miss)"),

    (958, 420, 1215, 466, "l", "fBody", WHITE, r"RSU edge cache"),
    (955, 544, 1132, 592, "l", "fBody", WHITE, r"$C_{\max}=20$"),
    (955, 586, 1204, 633, "l", "fBody", WHITE, r"(10\% of catalog)"),
    (778, 595, 860, 643, "c", "fBody", WHITE, r"RSU"),

    (1370, 277, 1690, 328, "l", "fBold", WHITE, r"Relevant items"),
    (1372, 348, 1478, 400, "l", "fBody", WHITE, r"$A_v(t)$"),
    (1364, 438, 1764, 506, "l", "fBold", WHITE, r"Predicted position"),
    (1372, 508, 1440, 561, "l", "fBody", WHITE, r"$\hat{x}_v$"),
    (1368, 596, 1765, 648, "l", "fBold", WHITE, r"Time-to-encounter"),
    (1362, 656, 1820, 774, "l", "fBody", WHITE,
     r"$\mathrm{TTE}(v,f)=\dfrac{|\ell_f-x_v(t)|}{\max(s_v(t),\varepsilon_s)}$"),
    (1363, 798, 1794, 856, "l", "fBold", WHITE, r"Spatial urgency $U(f)$"),
    (1362, 852, 1762, 908, "l", "fBody", WHITE, r"max-normalized $U_{\mathrm{raw}}(f)$"),
    (1362, 920, 1992, 1048, "l", "fBody", WHITE,
     r"$U_{\mathrm{raw}}(f)=\displaystyle\sum_{v:\,|\hat{x}_v-\ell_f|\le r_{\mathrm{acc}}}"
     r"\dfrac{1}{1+\alpha_d\mathrm{TTE}(v,f)}$"),
    (1776, 750, 2044, 940, "c", "fSmall", WHITE,
     r"\begin{tabular}{@{}c@{}}SU acceptance radius:\\[0.15ex] $r_{\mathrm{acc}}=800$ m\\[0.35ex]"
     r"Forward request radius:\\[0.15ex] $r_{\mathrm{rel}}=150\,/\,800$ m\\[0.35ex]"
     r"$r_{\mathrm{rel}}\neq r_{\mathrm{acc}}$\end{tabular}"),
    (1362, 1100, 1913, 1160, "l", "fBold", WHITE, r"Windowed popularity $P(f)$"),
    (1360, 1158, 1951, 1206, "l", "fSmall", WHITE,
     r"from request counts in the trailing window"),
    (1550, 1303, 1753, 1352, "c", "fBody", WHITE, r"$\Delta T=300$ s"),
    (1514, 1337, 1788, 1384, "c", "fBody", WHITE, r"with time window"),

    (494, 695, 972, 748, "c", "fBody", WHITE, r"Forward request radius $r_{\mathrm{rel}}$"),
    (534, 760, 924, 808, "c", "fBody", WHITE, r"scenario-side relevance"),
    (403, 823, 1070, 886, "c", "fBody", WHITE,
     r"$A_v(t)=\{f\in F: 0<(\ell_f-x_v(t))d_v\le r_{\mathrm{rel}}\}$"),

    (278, 1186, 474, 1239, "c", "fBold", WHITE, r"Vehicle $v$"),
    (238, 1234, 512, 1284, "c", "fBody", WHITE, r"$x_v(t),\,s_v(t),\,d_v(t)$"),
    (295, 1278, 452, 1329, "c", "fBody", WHITE, r"$\Delta t=1$ s"),
    (718, 1190, 1140, 1247, "c", "fBold", WHITE, r"Predicted position $\hat{x}_v$"),
    (708, 1230, 1148, 1314, "c", "fBody", WHITE,
     r"$\hat{x}_v=x_v(t)+s_v(t)\,d_v T_{\mathrm{pred}}$"),
    (766, 1308, 980, 1363, "l", "fBody", WHITE, r"$T_{\mathrm{pred}}=30$ s"),

    (2034, 362, 2620, 418, "r", "fBody", WHITE,
     r"$\mathrm{Score}(f)=W\cdot U(f)+(1-W)\cdot P(f)$"),
    (2465, 410, 2620, 462, "r", "fBody", WHITE, r"$W=0.2$"),
    (2026, 640, 2122, 694, "c", "fBody", WHITE, r"$U(f)$"),
    (2034, 852, 2120, 910, "c", "fBody", WHITE, r"$P(f)$"),

    (2236, 490, 2564, 534, "c", "fBoldS", WHITE, r"CACHE REPLACEMENT"),
    (2324, 526, 2477, 570, "c", "fBoldS", WHITE, r"DECISION"),
    (2263, 568, 2537, 620, "c", "fBody", WHITE, r"RSU Edge Cache"),

    (2098, 818, 2308, 870, "r", "fSmall", WHITE, r"lowest-scoring"),
    (2120, 854, 2308, 906, "r", "fSmall", WHITE, r"cached item"),

    (2406, 921, 2502, 975, "l", "fBody", WHITE, r"Evict"),
    (2263, 961, 2392, 1015, "r", "fBody", WHITE, r"arg\,min"),
    (2406, 957, 2570, 1015, "l", "fBody", WHITE, r"$\mathrm{Score}(f)$"),
    (2485, 1023, 2602, 1076, "c", "fSmall", WHITE, r"Update"),
    (2497, 1058, 2594, 1110, "c", "fSmall", WHITE, r"cache"),

    (2292, 1124, 2522, 1172, "c", "fSmall", PANEL_A, r"evict only if"),
    (2288, 1168, 2532, 1206, "c", "fSmall", PANEL_B, r"incoming score"),
    (2284, 1204, 2536, 1244, "c", "fSmall", PANEL_B, r"$>$ lowest cached"),
    (2330, 1240, 2490, 1282, "c", "fSmall", PANEL_C, r"score?"),
    (2239, 1328, 2570, 1384, "c", "fBody", WHITE, r"(Admission Control)"),
]

ANCH = {"l": "west", "c": "center", "r": "east"}

HEADER = r"""%% ===================================================================
%% Figure 1 - System model and the SU cache replacement pipeline.
%%
%% The artwork is the original raster, used exactly as drawn. Only the
%% lettering is replaced: each block of baked-in text is covered with an
%% opaque patch and the same words are set in LaTeX on top, so the labels
%% are live vector text (selectable, searchable, sharp at any zoom) while
%% every icon stays exactly as it was.
%%
%% Point sizes are measured, not guessed: calibrate.py reads the ink box of
%% each original label and solves for the size that reproduces its width.
%%
%%   python calibrate.py && python gen_fig1.py && pdflatex fig_system_model_tikz
%%
%% Canvas is 160 x 84.52 mm, the source PNG at \textwidth of sn-jnl, so
%% \includegraphics[width=\textwidth]{...} places it 1:1.
%% Generated file - edit gen_fig1.py, not this.
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

\definecolor{cInk}{HTML}{16202E}
\definecolor{cGreyD}{HTML}{5F676D}
\definecolor{cPanelA}{HTML}{F0F1F3}
\definecolor{cPanelB}{HTML}{E9EAEC}
\definecolor{cPanelC}{HTML}{EAEBED}

\begin{document}
\begin{tikzpicture}[x=1mm,y=1mm]
\useasboundingbox (0,0) rectangle (160,84.52);
\node[anchor=south west,inner sep=0pt] at (0,0)
  {\includegraphics[width=160mm]{fig_system_model.png}};

"""

MINPT = 4.6


def main():
    import json
    import os

    SZ = json.load(open("sizes.json")) if os.path.exists("sizes.json") else None
    sizes = SZ["sizes"] if SZ else [None] * len(T)
    inks = SZ["ink"] if SZ else [None] * len(T)

    out = [HEADER, "% --- cover the baked-in lettering ---\n"]

    for x0, y0, x1, y1, a, f, fill, body in T:
        if fill.startswith("cPanel"):
            continue
        out.append("\\fill[%s] (%.2f,%.2f) rectangle (%.2f,%.2f);\n"
                   % (fill, X(x0), Y(y1), X(x1), Y(y0)))

    # patches inside the decision rhombus are clipped to its outline,
    # otherwise the rectangle corners show against the white background
    out.append("\\begin{scope}\n\\clip (%.2f,%.2f) -- (%.2f,%.2f) -- "
               "(%.2f,%.2f) -- (%.2f,%.2f) -- cycle;\n"
               % (X(2264), Y(1200), X(2410), Y(1078),
                  X(2557), Y(1200), X(2410), Y(1322)))
    for x0, y0, x1, y1, a, f, fill, body in T:
        if not fill.startswith("cPanel"):
            continue
        out.append("\\fill[%s] (%.2f,%.2f) rectangle (%.2f,%.2f);\n"
                   % (fill, X(x0), Y(y1), X(x1), Y(y0)))
    out.append("\\end{scope}\n")

    panel_pt = [sizes[i] for i, t in enumerate(T)
                if t[6].startswith("cPanel") and sizes[i]]
    panel_pt = min(panel_pt) if panel_pt else None

    out.append("\n% --- the same words, set in LaTeX at the original size ---\n")
    for i, (x0, y0, x1, y1, a, f, fill, body) in enumerate(T):
        if fill.startswith("cPanel"):
            bx = (x0, y0, x1, y1)
            if panel_pt:
                sizes[i] = panel_pt
        else:
            bx = inks[i] if inks[i] else (x0, y0, x1, y1)
        ax = {"l": X(bx[0]), "c": (X(bx[0]) + X(bx[2])) / 2.0, "r": X(bx[2])}[a]
        ay = (Y(bx[1]) + Y(bx[3])) / 2.0
        pt = max(sizes[i] if sizes[i] else 8.0, MINPT)
        bold = "\\bfseries" if ("fBold" in f or "fTitle" in f) else ""
        col = "cGreyD" if f == "fHead" else "cInk"
        out.append("\\node[anchor=%s,inner sep=0pt,outer sep=0pt,text=%s] "
                   "at (%.2f,%.2f) {\\fontsize{%.2f}{%.2f}\\selectfont%s %s};\n"
                   % (ANCH[a], col, ax, ay, pt, pt * 1.18, bold, body))

    out.append("\n\\end{tikzpicture}\n\\end{document}\n")
    io.open("fig_system_model_tikz.tex", "w", encoding="utf-8").write("".join(out))
    print("wrote fig_system_model_tikz.tex  (%d text blocks)" % len(T))
    print("canvas %.2f x %.2f mm" % (WMM, HMM))


if __name__ == "__main__":
    main()
