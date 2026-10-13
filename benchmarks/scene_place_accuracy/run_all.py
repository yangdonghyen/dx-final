"""Validate and run the two fixed scene-place benchmarks."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys

import run_benchmark

ROOT = Path(__file__).resolve().parent
SPECS = {"diversity": ("Benchmark A - 100 Different Places", "DIV"),
         "gyeongbokgung": ("Benchmark B - Gyeongbokgung 100", "ROB")}

def sha256(path):
    digest=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): digest.update(chunk)
    return digest.hexdigest()

def validate(kind):
    base=ROOT/kind; places_path=base/"places.json"; manifest_path=base/"manifest.csv"
    places, rows=run_benchmark.load_dataset(places_path,manifest_path)
    if len(rows)!=100: raise ValueError(f"{kind}: manifest must have exactly 100 rows; found {len(rows)}")
    expected_prefix=SPECS[kind][1]
    if any(not row["image_id"].startswith(expected_prefix) for row in rows): raise ValueError(f"{kind}: invalid image ID prefix")
    if kind=="diversity" and (len(places)!=100 or len({r['place_id'] for r in rows})!=100):
        raise ValueError("diversity: requires 100 defined, unique places")
    if kind=="gyeongbokgung":
        if any(p.get("parent_name") not in {None,"경복궁"} for p in places.values()): raise ValueError("gyeongbokgung: non-Gyeongbokgung hierarchy")
        if any("경복궁" not in p["accepted_names"] for p in places.values()): raise ValueError("gyeongbokgung: parent acceptance missing")
    sources={r["image_id"]:r for r in csv.DictReader((base/"sources.csv").open(encoding="utf-8-sig",newline=""))}
    lock=json.loads((base/"dataset_lock.json").read_text(encoding="utf-8"))
    if lock.get("places_sha256") != sha256(places_path):
        raise ValueError(f"{kind}: places.json differs from dataset lock")
    if lock.get("audit_status_counts") != {"PASS": 100, "REVIEW": 0, "REJECT": 0} or lock.get("active_collection_failures") != 0:
        raise ValueError(f"{kind}: dataset lock does not certify 100 PASS images")
    if len(sources)!=100 or lock.get("image_count")!=100: raise ValueError(f"{kind}: incomplete sources or lock")
    hashes=[]
    for row in rows:
        source=sources.get(row["image_id"])
        if not source: raise ValueError(f"{kind}: source missing for {row['image_id']}")
        actual=sha256(row["resolved_path"]); hashes.append(actual)
        if source.get("sha256")!=actual or lock.get("sha256",{}).get(row["image_id"])!=actual:
            raise ValueError(f"{kind}: dataset lock mismatch for {row['image_id']}")
    if len(set(hashes))!=100: raise ValueError(f"{kind}: SHA256 duplicate image")
    return rows, places

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("--benchmark",choices=SPECS); p.add_argument("--validate-only",action="store_true")
    p.add_argument("--request-delay", type=float, help="Delay before each new API image request")
    p.add_argument("--rate-limit-backoff", type=float, nargs="+", help="429/503 retry delays, e.g. 10 30 60")
    p.add_argument("--max-consecutive-rate-limits", type=int, help="Checkpoint and stop after this many terminal 429s")
    args=p.parse_args(argv); kinds=[args.benchmark] if args.benchmark else list(SPECS)
    for kind in kinds:
        rows,_=validate(kind); print(f"{kind}: validation passed ({len(rows)} images)")
    if args.validate_only: return 0
    if not os.environ.get("BENCHMARK_ACCESS_TOKEN","").strip():
        print("BENCHMARK_ACCESS_TOKEN is not set. Collection and validation completed; evaluation was not run.")
        print("Set BENCHMARK_API_URL (optional) and BENCHMARK_ACCESS_TOKEN, then run this command again.")
        return 0
    code=0
    for kind in kinds:
        title,_=SPECS[kind]; base=ROOT/kind
        print("\n"+"="*36+f"\n{title}\n"+"="*36)
        run_args=["--places",str(base/"places.json"),"--manifest",str(base/"manifest.csv"),"--results-dir",str(base/"results")]
        if args.request_delay is not None: run_args += ["--request-delay",str(args.request_delay)]
        if args.rate_limit_backoff is not None: run_args += ["--rate-limit-backoff",*(str(x) for x in args.rate_limit_backoff)]
        if args.max_consecutive_rate_limits is not None: run_args += ["--max-consecutive-rate-limits",str(args.max_consecutive_rate_limits)]
        code=max(code,run_benchmark.main(run_args))
    return code
if __name__=="__main__": raise SystemExit(main())
