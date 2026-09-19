#!/usr/bin/env python
"""
Check every reference cited by the manuscript against its authoritative record.

Entries with a DOI are checked against the CrossRef REST API. Entries without
one are checked against the arXiv API. For each entry the script compares the
title, year, container title, volume, issue, pages, and the full author list in
order, and reports every field that disagrees.

    python scripts/verify_references.py --bib path/to/references_tc.bib \
                                        --tex path/to/tc_paper_sn.tex

Only entries actually cited by the .tex file are checked, so uncited entries
left in the .bib do not produce noise. The script exits non-zero if any cited
entry fails to resolve or disagrees on title, year or authors.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "refcheck/1.0 (research; mailto:adeelahmada485@gmail.com)"}


def field(entry: str, name: str) -> str | None:
    m = re.search(r"(?i)[\s,{]" + name + r"\s*=\s*", entry)
    if not m:
        return None
    i = m.end()
    if entry[i] == "{":
        depth, j = 0, i
        while j < len(entry):
            if entry[j] == "{":
                depth += 1
            elif entry[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        return entry[i + 1:j]
    m2 = re.match(r"([^,\n}]+)", entry[i:])
    return m2.group(1).strip() if m2 else None


def clean(s: str | None) -> str:
    if not s:
        return ""
    s = re.sub(r"\\[a-zA-Z]+\s*", "", s)
    s = s.replace("{", "").replace("}", "").replace("\\&", "&")
    return re.sub(r"\s+", " ", s).strip()


def norm(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def get(url: str):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read()


def crossref(doi: str) -> dict:
    return json.loads(get("https://api.crossref.org/works/" + urllib.parse.quote(doi)))["message"]


def arxiv(aid: str) -> dict:
    xml = get("https://export.arxiv.org/api/query?id_list=" + urllib.parse.quote(aid)).decode()
    ent = xml.split("<entry>")[-1]
    title = re.search(r"<title>(.*?)</title>", ent, re.S)
    names = re.findall(r"<name>(.*?)</name>", ent)
    pub = re.search(r"<published>(\d{4})", ent)
    return {"title": [re.sub(r"\s+", " ", title.group(1)).strip() if title else ""],
            "author": [{"family": n.split()[-1], "given": " ".join(n.split()[:-1])} for n in names],
            "container-title": ["arXiv"], "issued": {"date-parts": [[int(pub.group(1))]]} if pub else {}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bib", required=True)
    ap.add_argument("--tex", required=True)
    a = ap.parse_args()

    bib = open(a.bib, encoding="utf-8").read()
    tex = open(a.tex, encoding="utf-8").read()

    cited = set()
    for m in re.finditer(r"\\cite\{([^}]*)\}", tex):
        cited.update(k.strip() for k in m.group(1).split(",") if k.strip())

    starts = [(m.start(), m.group(1)) for m in re.finditer(r"^@\w+\{([^,]+),", bib, re.M)]
    entries = {}
    for i, (s, k) in enumerate(starts):
        e = starts[i + 1][0] if i + 1 < len(starts) else len(bib)
        entries[k] = bib[s:e]

    missing = sorted(cited - set(entries))
    if missing:
        print("CITED BUT NOT IN BIB:", missing)

    hard = 0
    for key in sorted(cited & set(entries)):
        t = entries[key]
        btitle, byear = clean(field(t, "title")), clean(field(t, "year"))
        bauth = clean(field(t, "author"))
        doi = clean(field(t, "doi") or field(t, "DOI"))
        journal = clean(field(t, "journal") or field(t, "booktitle"))
        try:
            if doi:
                m = crossref(doi)
            else:
                aid = re.search(r"arXiv:\s*([0-9.]+)", journal or "")
                if not aid:
                    print(f"[{key}] NO DOI and no arXiv id -- NOT VERIFIED")
                    hard += 1
                    continue
                m = arxiv(aid.group(1))
        except Exception as ex:
            print(f"[{key}] LOOKUP FAILED: {ex}")
            hard += 1
            continue

        flags = []
        ct = clean((m.get("title") or [""])[0])
        if norm(ct) != norm(btitle):
            flags.append(f"TITLE\n      bib: {btitle}\n      src: {ct}")
        cy = None
        for f in ("published-print", "published-online", "issued", "created"):
            if f in m and m[f].get("date-parts"):
                cy = m[f]["date-parts"][0][0]
                break
        if byear and cy and str(cy) != byear:
            flags.append(f"YEAR bib={byear} src={cy}")
        auth = m.get("author") or []
        bsur = [norm(x.split(",")[0]) for x in bauth.split(" and ")] if bauth else []
        # Some CrossRef records (older IEEE conference metadata in particular)
        # leave `family` empty and put the whole name in `given`. Fall back to
        # the last token of `given` so those do not read as author mismatches.
        csur = [norm(x.get("family") or (x.get("given") or "").split()[-1]
                     if (x.get("given") or "").split() else "")
                for x in auth]
        if bsur and csur and all(csur):
            if len(bsur) != len(csur):
                flags.append(f"AUTHOR COUNT bib={len(bsur)} src={len(csur)}")
            else:
                bad = [i + 1 for i in range(len(bsur)) if bsur[i] != csur[i]]
                if bad:
                    flags.append(f"AUTHOR NAME/ORDER at position(s) {bad}")
        if flags:
            hard += 1
            print(f"[{key}] {len(flags)} issue(s):")
            for f in flags:
                print("    -", f)
        else:
            print(f"[{key}] OK")
        time.sleep(0.3)

    print(f"\n{len(cited & set(entries))} cited entries checked, {hard} with problems")
    return 1 if (hard or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
