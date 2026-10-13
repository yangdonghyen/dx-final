"""Evaluate the existing scene-image HTTP API; Python standard library only."""

import argparse
import csv
from http.client import HTTPException
import json
import math
import os
from pathlib import Path
import re
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid


ROOT = Path(__file__).resolve().parent
ENDPOINT = "/api/v1/discovery/scene-image"
MIME_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
MAX_BYTES = 10 * 1024 * 1024
FIELDS = [
    "image_id", "image_path", "place_id", "ground_truth_detail", "ground_truth_parent",
    "capture_type", "note", "primary_candidate", "candidate_2", "candidate_3",
    "candidate_4", "ordered_candidates", "top1_correct", "top4_correct", "recognized",
    "confidence", "place_verified", "verified_place", "api_status", "http_status",
    "error_code", "elapsed_seconds", "attempt_count", "retry_count",
]


def normalize_name(value):
    # Only spelling separators; no transliteration, substring, or fuzzy matching.
    return re.sub(r"[\s\-‐‑–—_.,·/\\:;()\[\]{}'\"’]+", "", value.strip().casefold())


def load_dataset(places_path, manifest_path):
    with places_path.open(encoding="utf-8-sig") as source:
        places = json.load(source)
    if not isinstance(places, dict) or not places:
        raise ValueError("places.json must be a nonempty object")
    for place_id, place in places.items():
        if not isinstance(place, dict):
            raise ValueError(f"Invalid place: {place_id}")
        if not isinstance(place.get("detail_name"), str) or not place["detail_name"].strip():
            raise ValueError(f"{place_id}: detail_name must be a nonempty string")
        if place.get("parent_name") is not None and (not isinstance(place["parent_name"], str) or not place["parent_name"].strip()):
            raise ValueError(f"{place_id}: parent_name must be null or a nonempty string")
        names = place.get("accepted_names")
        if not isinstance(names, list) or not names or any(
            not isinstance(name, str) or not normalize_name(name) for name in names
        ):
            raise ValueError(f"{place_id}: accepted_names must contain explicit nonempty names")
    with manifest_path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        required = {"image_id", "image_path", "place_id", "capture_type", "note"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"manifest.csv requires columns: {', '.join(sorted(required))}")
        rows = list(reader)
    if not rows:
        raise ValueError("manifest.csv has no images")
    ids = set()
    for line, row in enumerate(rows, 2):
        if None in row or any(row.get(key) is None for key in required):
            raise ValueError(f"manifest line {line}: malformed CSV row")
        for key in required:
            row[key] = row[key].strip()
        if any(not row[key] for key in required - {"note"}):
            raise ValueError(f"manifest line {line}: required value is empty")
        if row["image_id"] in ids:
            raise ValueError(f"Duplicate image_id: {row['image_id']}")
        ids.add(row["image_id"])
        if row["place_id"] not in places:
            raise ValueError(f"Unknown place_id: {row['place_id']}")
        path = (manifest_path.parent / row["image_path"]).resolve()
        if path.suffix.lower() not in MIME_TYPES:
            raise ValueError(f"Unsupported image extension: {path}")
        if not path.is_file():
            raise ValueError(f"Image does not exist: {path}")
        if not 0 < path.stat().st_size <= MAX_BYTES:
            raise ValueError(f"Image must be nonempty and <= 10 MiB: {path}")
        row["resolved_path"] = path
    return places, rows


def validate_response(data):
    """Reject upload-only/malformed 2xx bodies instead of scoring them as AI misses."""
    if not isinstance(data, dict) or data.get("received") is not True:
        raise ValueError("Missing received=true")
    if type(data.get("recognized")) is not bool:
        raise ValueError("Missing boolean recognized (analyze=true is required)")
    primary = data.get("primary_candidate")
    candidates = data.get("candidates")
    if candidates is None:
        candidates = []
    if not isinstance(candidates, list):
        raise ValueError("candidates is not a list")
    for candidate in ([primary] if primary is not None else []) + candidates:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("place_name"), str):
            raise ValueError("Candidate has no string place_name")
        if not normalize_name(candidate["place_name"]):
            raise ValueError("Candidate has an empty place_name")
    if data["recognized"] and primary is None:
        raise ValueError("Recognized response has no primary_candidate")


def evaluate(data, place):
    primary = (data.get("primary_candidate") or {}).get("place_name", "")
    ordered, seen = [], set()
    for name in [primary] + [item["place_name"] for item in data.get("candidates") or []]:
        normalized = normalize_name(name)
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(name)
    ordered = ordered[:4]
    accepted = {normalize_name(name) for name in place["accepted_names"]}
    recognized = data["recognized"]
    return {
        "primary_candidate": primary,
        **{f"candidate_{index + 1}": ordered[index] if index < len(ordered) else ""
           for index in range(1, 4)},
        "ordered_candidates": json.dumps(ordered, ensure_ascii=False),
        "top1_correct": recognized and normalize_name(primary) in accepted,
        "top4_correct": recognized and any(normalize_name(name) in accepted for name in ordered),
        "recognized": recognized,
        "confidence": data.get("confidence", ""),
        "place_verified": data.get("place_verified", ""),
        "verified_place": json.dumps(data.get("verified_place"), ensure_ascii=False),
    }


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def post_image(url, token, path, timeout):
    boundary = "scene-benchmark-" + uuid.uuid4().hex
    # A simple ASCII upload filename avoids filename/header injection and encoding ambiguity.
    filename = "scene" + path.suffix.lower()
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"analyze\"\r\n\r\ntrue\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
        f"Content-Type: {MIME_TYPES[path.suffix.lower()]}\r\n\r\n"
    ).encode("ascii") + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("ascii")
    request = Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Accept": "application/json",
    })
    try:
        response = build_opener(NoRedirect()).open(request, timeout=timeout)
    except HTTPError as error:
        response = error
    with response:
        return response.code, response.read().decode("utf-8", errors="replace")


def run_image(row, place, url, token, timeout, retries, retry_delay, raw_file,
              rate_limit_backoff=None):
    result = {key: "" for key in FIELDS}
    result.update({key: row[key] for key in ("image_id", "image_path", "place_id", "capture_type", "note")})
    result.update(ground_truth_detail=place["detail_name"], ground_truth_parent=place["parent_name"])
    started = time.monotonic()
    for attempt in range(retries + 1):
        status, text, data, error_code = None, None, None, ""
        try:
            status, text = post_image(url, token, row["resolved_path"], timeout)
            try:
                data = json.loads(text)
            except ValueError:
                pass
            if 200 <= status < 300:
                try:
                    validate_response(data)
                except ValueError:
                    error_code = "INVALID_RESPONSE"
            else:
                error = data.get("error") if isinstance(data, dict) else None
                error_code = (error.get("code") if isinstance(error, dict) else None) or f"HTTP_{status}"
        except (TimeoutError, URLError, OSError, HTTPException) as error:
            # Do not serialize exception text, request headers, or the access token.
            error_code = "REQUEST_TIMEOUT" if isinstance(error, TimeoutError) else "REQUEST_ERROR"
        raw_file.write(json.dumps({
            "image_id": row["image_id"], "attempt": attempt + 1,
            "http_status": status, "error_code": error_code, "response_body": text,
        }, ensure_ascii=False) + "\n")
        raw_file.flush()
        result.update(api_status="failure" if error_code else "success", http_status=status or "",
                      error_code=error_code, attempt_count=attempt + 1, retry_count=attempt)
        if not error_code:
            result.update(evaluate(data, place))
            break
        if status not in {429, 503} or attempt == retries:
            break
        if rate_limit_backoff:
            delay = rate_limit_backoff[min(attempt, len(rate_limit_backoff) - 1)]
        else:
            delay = min(retry_delay * 2 ** attempt, 60)
        print(f"  {row['image_id']}: HTTP {status}, retry {attempt + 1}/{retries} in {delay:g}s", flush=True)
        time.sleep(delay)
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return result


def metrics(rows):
    total = len(rows)
    successful = [row for row in rows if row["api_status"] == "success"]
    count = len(successful)
    top1 = sum(row["top1_correct"] is True for row in successful)
    top4 = sum(row["top4_correct"] is True for row in successful)
    return {
        "total_images": total, "api_success_count": count, "api_failure_count": total - count,
        "api_success_rate": count / total if total else None,
        "evaluable_images": count,
        "top1_correct_count": top1, "top1_accuracy": top1 / count if count else None,
        "top4_correct_count": top4, "top4_hit_rate": top4 / count if count else None,
        "miss_count": count - top4, "miss_rate": (count - top4) / count if count else None,
        "e2e_top1_success_rate": top1 / total if total else None,
        "e2e_top4_success_rate": top4 / total if total else None,
    }


def summarize(rows, places=None):
    summary = metrics(rows)
    for field, key in (("place_id", "by_place"), ("capture_type", "by_capture_type")):
        summary[key] = {value: metrics([row for row in rows if row[field] == value])
                        for value in sorted({row[field] for row in rows})}
    if places:
        for place_field, summary_key in (("category", "by_category"), ("region", "by_region")):
            values = sorted({places.get(row["place_id"], {}).get(place_field, "") for row in rows} - {""})
            if values:
                summary[summary_key] = {
                    value: metrics([row for row in rows if places[row["place_id"]].get(place_field) == value])
                    for value in values
                }
    return summary


def print_summary(summary):
    def display(label, numerator, denominator, rate):
        percentage = "N/A" if rate is None else f"{rate:.1%}"
        print(f"{label:<20}: {numerator} / {denominator} ({percentage})")

    print("=================================\nScene Place Accuracy Benchmark\n=================================")
    total, count = summary["total_images"], summary["api_success_count"]
    print(f"{'Images':<20}: {total}")
    display("API success", count, total, summary["api_success_rate"])
    if not summary.get("official_results", True):
        print("Partial results only — not official accuracy.")
        print(f"{'Completed API successes':<25}: {count}")
        print(f"{'Remaining':<25}: {summary.get('remaining_count', total - count)}")
        print(f"{'429 failures':<25}: {summary.get('rate_limit_failure_count', 0)}")
        print(f"{'503 failures':<25}: {summary.get('service_unavailable_failure_count', 0)}")
        print("=================================")
        return
    display("Top-1 Accuracy", summary["top1_correct_count"], count, summary["top1_accuracy"])
    display("Top-4 Hit Rate", summary["top4_correct_count"], count, summary["top4_hit_rate"])
    display("Miss Rate", summary["miss_count"], count, summary["miss_rate"])
    print()
    display("E2E Top-1", summary["top1_correct_count"], total, summary["e2e_top1_success_rate"])
    display("E2E Top-4", summary["top4_correct_count"], total, summary["e2e_top4_success_rate"])
    print("=================================")


def load_checkpoint(path, dataset_ids):
    """Return the latest checkpoint row per current image ID.

    JSONL is append-only so a process interruption cannot corrupt already
    completed work.  Malformed trailing lines are ignored deliberately.
    """
    latest = {}
    if not path.exists():
        return latest
    with path.open(encoding="utf-8") as source:
        for line in source:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            image_id = record.get("image_id") if isinstance(record, dict) else None
            if image_id in dataset_ids and record.get("api_status") in {"success", "failure"}:
                latest[image_id] = record
    return latest


def write_checkpoint(output, result):
    output.write(json.dumps(result, ensure_ascii=False) + "\n")
    output.flush()
    os.fsync(output.fileno())


def failure_count(rows, status):
    return sum(row.get("api_status") == "failure" and str(row.get("http_status", "")) == str(status)
               for row in rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--places", type=Path, default=ROOT / "places.json")
    parser.add_argument("--manifest", type=Path, default=ROOT / "manifest.csv")
    parser.add_argument("--results", type=Path, default=ROOT / "results",
                        help="Legacy results directory (uses *_details.csv naming)")
    parser.add_argument("--results-dir", type=Path,
                        help="Results directory for dataset runners (uses *_detail.csv naming)")
    parser.add_argument("--timeout", type=float, default=240, help="Socket timeout in seconds (default: 240)")
    parser.add_argument("--retries", type=int, default=2, help="Extra HTTP attempts on 429/503, 0-5 (default: 2)")
    parser.add_argument("--retry-delay", type=float, default=2, help="Initial retry delay; exponential, capped at 30s")
    parser.add_argument("--rate-limit-backoff", type=float, nargs="+", default=None,
                        help="Explicit 429/503 retry delays, e.g. --rate-limit-backoff 10 30 60")
    parser.add_argument("--request-delay", type=float, default=0,
                        help="Wait this many seconds before each new image API request")
    parser.add_argument("--max-consecutive-rate-limits", type=int, default=5,
                        help="Checkpoint and stop after this many terminal consecutive 429 failures (default: 5)")
    parser.add_argument("--validate-only", action="store_true", help="Check labels and image files without API calls")
    args = parser.parse_args(argv)
    if not 0 <= args.retries <= 5 or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--retries must be 0-5 and --timeout must be positive and finite")
    if not math.isfinite(args.retry_delay) or args.retry_delay < 0:
        parser.error("--retry-delay must be nonnegative and finite")
    if (not math.isfinite(args.request_delay) or args.request_delay < 0 or
            args.max_consecutive_rate_limits < 1 or
            args.rate_limit_backoff is not None and any(not math.isfinite(x) or x < 0 for x in args.rate_limit_backoff)):
        parser.error("--request-delay/backoff values must be nonnegative and finite; rate-limit threshold must be positive")
    try:
        places, dataset = load_dataset(args.places.resolve(), args.manifest.resolve())
    except (OSError, ValueError, csv.Error) as error:
        parser.error(str(error))
    print(f"Validated {len(dataset)} images", flush=True)
    if args.validate_only:
        return 0
    token = os.environ.get("BENCHMARK_ACCESS_TOKEN", "").strip()
    if not token or "\n" in token or "\r" in token:
        parser.error("Set BENCHMARK_ACCESS_TOKEN to a valid backend access token (without 'Bearer ')")
    base_url = os.environ.get("BENCHMARK_API_URL", "http://127.0.0.1:8000").rstrip("/")
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        parser.error("BENCHMARK_API_URL must be an HTTP(S) base URL without credentials/query/fragment")
    url = base_url + ENDPOINT
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    results_dir = args.results_dir or args.results
    results_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = results_dir / "benchmark_progress.jsonl"
    # Keep the old plural name for callers/tests using --results, while the new
    # benchmark contract uses the requested singular timestamp_detail.csv.
    detail_suffix = "detail" if args.results_dir else "details"
    csv_path = results_dir / f"{stamp}_{detail_suffix}.csv"
    raw_path = results_dir / f"{stamp}_raw_responses.jsonl"
    summary_path = results_dir / f"{stamp}_summary.json"
    checkpoint = load_checkpoint(checkpoint_path, {row["image_id"] for row in dataset})
    completed = {image_id: result for image_id, result in checkpoint.items()
                 if result.get("api_status") == "success"}
    results_by_id = dict(checkpoint)
    consecutive_rate_limits = 0
    stopped_for_rate_limit = False
    with checkpoint_path.open("a", encoding="utf-8") as checkpoint_output, raw_path.open("x", encoding="utf-8") as raw:
        for index, row in enumerate(dataset, 1):
            image_id = row["image_id"]
            if image_id in completed:
                print(f"[{index}/{len(dataset)}] {row['resolved_path'].name} -> reused successful checkpoint", flush=True)
                continue
            if args.request_delay:
                print(f"  {image_id}: waiting {args.request_delay:g}s before request", flush=True)
                time.sleep(args.request_delay)
            result = run_image(row, places[row["place_id"]], url, token, args.timeout,
                               args.retries, args.retry_delay, raw, args.rate_limit_backoff)
            # Save every finished image before printing or deciding whether to stop.
            write_checkpoint(checkpoint_output, result)
            results_by_id[image_id] = result
            status = (f"Top1 {'PASS' if result['top1_correct'] else 'FAIL'} / "
                      f"Top4 {'PASS' if result['top4_correct'] else 'FAIL'}")
            if result["api_status"] == "failure":
                status = f"API FAIL ({result['error_code']}) / accuracy excluded"
            print(f"[{index}/{len(dataset)}] {row['resolved_path'].name} -> {status}", flush=True)
            if result["api_status"] == "failure" and str(result["http_status"]) == "429":
                consecutive_rate_limits += 1
                if consecutive_rate_limits >= args.max_consecutive_rate_limits:
                    stopped_for_rate_limit = True
                    print("Too many consecutive rate limits. Progress saved. Resume later.", flush=True)
                    break
            else:
                consecutive_rate_limits = 0
    results = [results_by_id[row["image_id"]] for row in dataset if row["image_id"] in results_by_id]
    with csv_path.open("x", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        writer.writeheader(); writer.writerows(results)
    summary = summarize(results, places)
    completed_count = sum(row.get("api_status") == "success" for row in results)
    summary.update(dataset_image_count=len(dataset), completed_api_successes=completed_count,
                   remaining_count=len(dataset) - completed_count,
                   rate_limit_failure_count=failure_count(results, 429),
                   service_unavailable_failure_count=failure_count(results, 503),
                   official_results=completed_count == len(dataset),
                   progress_file=checkpoint_path.name,
                   stopped_for_rate_limit=stopped_for_rate_limit)
    # The checkpoint may represent only a partial run.  Keep success-rate
    # accounting tied to the full requested dataset, never to a smaller slice.
    summary["observed_result_count"] = len(results)
    summary["total_images"] = len(dataset)
    summary["api_failure_count"] = len(dataset) - completed_count
    summary["api_success_rate"] = completed_count / len(dataset) if dataset else None
    summary.update(timestamp_utc=stamp, endpoint=url, retries=args.retries, timeout_seconds=args.timeout,
                   retry_delay_seconds=args.retry_delay, places=places,
                   manifest=[{key: value for key, value in row.items() if key != "resolved_path"} for row in dataset],
                   details_file=csv_path.name, responses_file=raw_path.name,
                   accuracy_denominator="Valid analyzed API responses, including recognized=false")
    with summary_path.open("x", encoding="utf-8") as output:
        json.dump(summary, output, ensure_ascii=False, indent=2)
    print_summary(summary)
    print(f"Results: {csv_path.resolve()}\nSummary: {summary_path.resolve()}\nResponses: {raw_path.resolve()}")
    return 0 if summary["official_results"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
