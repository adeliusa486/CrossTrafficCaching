#!/usr/bin/env python
"""
Download the congested NGSIM I-80 window used for Tier 3 of Table 4 from the
U.S. DOT open-data portal (Socrata dataset 8ect-6jqj) and write it in the exact
7-column schema the project's ngsim_adapter expects.

The window is the first 15-minute I-80 study period (4:00-4:15 pm local,
13 April 2005), bounded by global_time in [1113433135300, 1113434035300]. It
covers 900.0 s, 1972 distinct vehicles and lanes 1 to 7, and averages
27.6 km/h, which is the congested regime reported in Section 4.1 of the paper.

Output: data/raw/ngsim/ngsim_i80_win1.csv

This is the I-80 counterpart of download_us101_freeflow.py. Together the two
scripts make both recorded tiers reproducible from a clean checkout without
manual filtering of the source dataset.

Verify the result with:

    python scripts/adapters/checksums.py --verify
"""
from __future__ import annotations

import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "raw" / "ngsim" / "ngsim_i80_win1.csv"
BASE = "https://data.transportation.gov/resource/8ect-6jqj.json"
UA = {"User-Agent": "ngsim-fetch/1.0 (research)"}
COLS = ["vehicle_id", "frame_id", "global_time", "local_y", "v_vel", "direction", "lane_id"]

# Bounds of I-80 study period 1 (4:00-4:15 pm, 13 April 2005), inclusive.
GT_LO = 1113433135300
GT_HI = 1113434035300
PAGE = 50000


def fetch(offset):
    soql = (
        f"SELECT {','.join(COLS)} "
        f"WHERE location='i-80' "
        f"AND global_time >= {GT_LO} AND global_time <= {GT_HI} "
        f"ORDER BY vehicle_id, global_time "
        f"LIMIT {PAGE} OFFSET {offset}"
    )
    url = BASE + "?" + urllib.parse.urlencode({"$query": soql})
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=UA)
            return json.load(urllib.request.urlopen(req, timeout=120))
        except Exception as e:
            print(f"  retry {attempt+1} (offset {offset}): {e}", flush=True)
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"failed at offset {offset}")


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    n = 0
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(COLS)
        offset = 0
        while True:
            rows = fetch(offset)
            if not rows:
                break
            for r in rows:
                w.writerow([r.get(c, "") for c in COLS])
            n += len(rows)
            print(f"  fetched {n} rows ({time.time()-t0:.0f}s)", flush=True)
            if len(rows) < PAGE:
                break
            offset += PAGE
    print(f"saved {n} rows -> {OUT}  ({time.time()-t0:.0f}s)")
    print("expected: 1173116 rows, 1972 distinct vehicles")
    if n == 0:
        sys.exit("no rows fetched")


if __name__ == "__main__":
    main()
