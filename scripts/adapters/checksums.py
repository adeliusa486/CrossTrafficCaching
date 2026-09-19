#!/usr/bin/env python
"""
Provenance and integrity record for the recorded-trajectory inputs.

The raw NGSIM CSV files are too large to commit, so this file records what they
must contain: the source dataset, the exact extraction bounds, the row and
vehicle counts, and a SHA-256 checksum of each extracted window. A reviewer who
runs the two download scripts can confirm they obtained the same data we did.

    python scripts/adapters/checksums.py --verify     # check local files
    python scripts/adapters/checksums.py --write      # regenerate this record

Section 4.1 of the manuscript refers to this file.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "ngsim"
RECORD = Path(__file__).resolve().parent / "ngsim_provenance.json"

WINDOWS = {
    "ngsim_i80_win1.csv": {
        "source_dataset": "https://data.transportation.gov/d/8ect-6jqj",
        "location": "i-80",
        "study_period": "1 (16:00-16:15 local, 13 April 2005)",
        "global_time_lo": 1113433135300,
        "global_time_hi": 1113434035300,
        "span_s": 900.0,
        "expected_rows": 1173116,
        "expected_vehicles": 1972,
        "segment_m": 535.2102072,
        "mean_speed_kmh": 27.636188597695508,
        "download_script": "scripts/adapters/download_i80_window.py",
        "used_for": "Table 4, Tier 3 (recorded NGSIM)",
    },
    "ngsim_us101_freeflow.csv": {
        "source_dataset": "https://data.transportation.gov/d/8ect-6jqj",
        "location": "us-101",
        "study_period": "0 (07:50-08:05 local, 15 June 2005, free-flow onset)",
        "global_time_lo": 1118846979700,
        "global_time_hi": 1118847903800,
        "span_s": 924.1,
        "expected_rows": 1188679,
        "expected_vehicles": 2196,
        "segment_m": 669.1768176,
        "mean_speed_kmh": 40.86641509880778,
        "download_script": "scripts/adapters/download_us101_freeflow.py",
        "used_for": "Table 7, free-flow robustness",
    },
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def summarize(path: Path) -> dict:
    rows = 0
    vids = set()
    gts = []
    with open(path) as f:
        for r in csv.DictReader(f):
            rows += 1
            vids.add(r["vehicle_id"])
            gts.append(int(r["global_time"]))
    return {"rows": rows, "vehicles": len(vids),
            "global_time_lo": min(gts), "global_time_hi": max(gts),
            "sha256": sha256(path)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    if not (a.write or a.verify):
        ap.error("pass --write or --verify")

    if a.write:
        out = {}
        for name, meta in WINDOWS.items():
            p = RAW / name
            if not p.exists():
                sys.exit(f"missing {p}; run {meta['download_script']} first")
            out[name] = {**meta, **summarize(p)}
            print(f"  {name}: sha256={out[name]['sha256']}")
        RECORD.write_text(json.dumps(out, indent=2))
        print(f"wrote {RECORD}")
        return

    if not RECORD.exists():
        sys.exit(f"no provenance record at {RECORD}; run with --write first")
    rec = json.loads(RECORD.read_text())
    bad = 0
    for name, want in rec.items():
        p = RAW / name
        if not p.exists():
            print(f"  {name}: MISSING (run {want['download_script']})")
            bad += 1
            continue
        got = summarize(p)
        for k in ("rows", "vehicles", "global_time_lo", "global_time_hi", "sha256"):
            if got[k] != want[k]:
                print(f"  {name}: {k} differs\n      expected {want[k]}\n      got      {got[k]}")
                bad += 1
                break
        else:
            print(f"  {name}: OK ({got['rows']} rows, {got['vehicles']} vehicles, sha256 matches)")
    if bad:
        sys.exit(f"{bad} window(s) did not match the recorded provenance")
    print("all recorded windows match")


if __name__ == "__main__":
    main()
