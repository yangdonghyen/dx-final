"""Benchmark Gemini location inference from travel photos only.

This script intentionally uses Gemini's REST API and the Python standard
library, matching the project's existing Gemini integration style.
"""

from __future__ import annotations

import argparse
import base64
import csv
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import math
import mimetypes
import os
from pathlib import Path
import random
import re
import socket
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
GROUND_TRUTH_PATH = ROOT / "ground_truth.csv"
RESULTS_PATH = ROOT / "results.csv"
ATTEMPTS_PATH = ROOT / "attempts.csv"
PROJECT_DOTENV_PATH = ROOT.parents[1] / "backend" / ".env"

# Model configuration is deliberately separate from the request logic. The
# existing project setting is reused; no key or model is created by this script.
MODEL_NAME = os.environ.get("GEMINI_MODEL", "").strip()
FALLBACK_MODEL_NAME = os.environ.get("GEMINI_FALLBACK_MODEL", "").strip()
API_KEY_ENV_NAME = "GEMINI_API_KEY"

PROMPT = """이 사진만 보고 촬영 장소를 추정해줘.

사진에 보이는 시각적 정보만 사용하고,
확실하지 않은 장소를 만들어내지 마.

반드시 JSON 형식으로만 답해줘.

{
  "country": null,
  "region": null,
  "city": null,
  "place_name": null,
  "confidence": 0.0,
  "reason": ""
}

규칙:
- 특정 장소까지 판단하기 어렵다면 place_name은 null
- 도시를 판단하기 어렵다면 city는 null
- 지역을 판단하기 어렵다면 region은 null
- confidence는 0.0 ~ 1.0
- 사진 파일명이나 정답 정보는 사용하지 말 것"""

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
DIFFICULTIES = {"landmark", "general", "hard"}
TRUTH_FIELDS = ("image_id", "image_path", "true_country", "true_region", "true_city", "true_place", "difficulty")
RESULT_FIELDS = [
    "image_id", "image_path", "difficulty",
    "true_country", "true_region", "true_city", "true_place",
    "pred_country", "pred_region", "pred_city", "pred_place", "confidence", "reason",
    "country_match", "region_match", "city_match", "exact_place_match",
    "status", "error", "model_used",
]
ATTEMPT_FIELDS = [
    "image_id", "attempt_no", "timestamp", "model_used", "http_status", "status",
    "error_code", "error_status", "error_message", "quota_metric", "quota_limit",
    "quota_dimension", "retry_after", "request_duration_sec", "backoff_sec",
    "fallback_reason", "pred_region", "pred_city", "pred_place", "confidence", "error",
]
GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def load_dotenv_if_needed() -> None:
    """Load only the project's existing Gemini settings, without printing values."""
    if not PROJECT_DOTENV_PATH.is_file():
        return
    try:
        lines = PROJECT_DOTENV_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    wanted = {API_KEY_ENV_NAME, "GEMINI_MODEL", "GEMINI_FALLBACK_MODEL"}
    for line in lines:
        match = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$", line)
        if not match or match.group(1) not in wanted or os.environ.get(match.group(1)):
            continue
        value = match.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if value:
            os.environ[match.group(1)] = value


def configure_models_from_environment() -> tuple[str, str]:
    return os.environ.get("GEMINI_MODEL", MODEL_NAME).strip(), os.environ.get(
        "GEMINI_FALLBACK_MODEL", FALLBACK_MODEL_NAME
    ).strip()


def normalize(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    # Deliberately limited to spelling separators, never transliteration or fuzzy matching.
    return re.sub(r"[\s\-‐‑‒–—―.,/\\:;!?()\[\]{}'\"“”‘’]", "", value.strip().casefold())


def match(prediction: Any, truth: str) -> bool:
    return bool(normalize(prediction)) and normalize(prediction) == normalize(truth)


# These are spelling variants for the same top-level Korean municipality only.
# Do not add districts (for example, Jongno-gu) here: a district and its parent
# city are different administrative levels and must not be scored as identical.
ADMINISTRATIVE_ALIASES = {
    "서울": "서울특별시",
    "서울특별시": "서울특별시",
    "부산": "부산광역시",
    "부산광역시": "부산광역시",
    "경주": "경주시",
    "경주시": "경주시",
    "강릉": "강릉시",
    "강릉시": "강릉시",
}


def normalize_administrative(value: Any) -> str:
    """Normalize only approved equivalent city/region spellings."""
    normalized = normalize(value)
    for alias, canonical in ADMINISTRATIVE_ALIASES.items():
        if normalized == normalize(alias):
            return normalize(canonical)
    return normalized


def match_administrative(prediction: Any, truth: str) -> bool:
    return bool(normalize_administrative(prediction)) and (
        normalize_administrative(prediction) == normalize_administrative(truth)
    )


def is_abstention(row: dict[str, Any]) -> bool:
    """Only a successful Gemini response with place_name=null counts as abstention."""
    return row.get("status") == "success" and not str(row.get("pred_place") or "").strip()


def score_result(result: dict[str, Any], row: dict[str, str]) -> None:
    """Recalculate evaluation fields without changing the recorded Gemini response."""
    result.update(
        country_match=match(result.get("pred_country"), row["true_country"]),
        region_match=match_administrative(result.get("pred_region"), row["true_region"]),
        city_match=match_administrative(result.get("pred_city"), row["true_city"]),
        exact_place_match=match(result.get("pred_place"), row["true_place"]),
    )


def parse_truth(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"Missing ground truth file: {path}")
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not set(TRUTH_FIELDS).issubset(reader.fieldnames or []):
            raise ValueError("ground_truth.csv requires: " + ", ".join(TRUTH_FIELDS))
        rows = list(reader)
    if not rows:
        raise ValueError("ground_truth.csv has no image rows")
    seen: set[str] = set()
    root_resolved = ROOT.resolve()
    for line_number, row in enumerate(rows, start=2):
        for field in TRUTH_FIELDS:
            row[field] = (row.get(field) or "").strip()
        if not all(row[field] for field in TRUTH_FIELDS):
            raise ValueError(f"ground_truth.csv line {line_number}: required value is empty")
        if row["image_id"] in seen:
            raise ValueError(f"Duplicate image_id: {row['image_id']}")
        seen.add(row["image_id"])
        if row["difficulty"] not in DIFFICULTIES:
            raise ValueError(f"{row['image_id']}: difficulty must be landmark, general, or hard")
        image_path = (ROOT / row["image_path"]).resolve()
        if root_resolved not in image_path.parents or image_path.suffix.lower() not in IMAGE_SUFFIXES:
            raise ValueError(f"{row['image_id']}: image_path must be a supported file inside this benchmark folder")
        if not image_path.is_file() or image_path.stat().st_size == 0:
            raise ValueError(f"{row['image_id']}: image is missing or empty: {row['image_path']}")
        row["_resolved_image_path"] = str(image_path)
    return rows


def request_bytes(url: str, body: bytes | None, timeout: float) -> tuple[int, bytes, str, float]:
    """Return only diagnostic-safe response metadata; never log request URLs or keys."""
    request = Request(url, data=body, method="POST" if body is not None else "GET", headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, response.read(), response.headers.get("Retry-After", ""), time.perf_counter() - started
    except HTTPError as error:
        return error.code, error.read(), error.headers.get("Retry-After", ""), time.perf_counter() - started


def available_models(api_key: str, timeout: float) -> set[str]:
    """Verify configured candidates against Google's current model list."""
    status, body, _, _ = request_bytes(MODELS_URL + "?key=" + quote(api_key, safe=""), None, timeout)
    if not 200 <= status < 300:
        raise RuntimeError(f"model list request failed (HTTP {status})")
    payload = json.loads(body.decode("utf-8"))
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        raise RuntimeError("model list response is malformed")
    available = set()
    for item in models:
        name = item.get("name") if isinstance(item, dict) else None
        methods = item.get("supportedGenerationMethods") if isinstance(item, dict) else None
        if isinstance(name, str) and isinstance(methods, list) and "generateContent" in methods:
            available.add(name.removeprefix("models/"))
    return available


def select_model(api_key: str, configured: str, fallback: str, timeout: float) -> tuple[str, str]:
    if not configured:
        raise RuntimeError("GEMINI_MODEL is not configured; refusing to guess a model name")
    available = available_models(api_key, timeout)
    primary = configured.removeprefix("models/")
    if primary in available:
        return primary, ""
    if fallback and fallback.removeprefix("models/") in available:
        return fallback.removeprefix("models/"), "primary unavailable"
    raise RuntimeError("Configured Gemini model is unavailable or does not support generateContent")


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("response did not contain JSON")
    parsed = json.loads(text[start:end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("response JSON must be an object")
    return parsed


def validate_prediction(data: dict[str, Any]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for source, target in (("country", "pred_country"), ("region", "pred_region"), ("city", "pred_city"), ("place_name", "pred_place")):
        item = data.get(source)
        if item is not None and not isinstance(item, str):
            raise ValueError(f"{source} must be a string or null")
        value[target] = item.strip() if isinstance(item, str) else ""
    confidence = data.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError("confidence must be a number from 0.0 to 1.0")
    reason = data.get("reason")
    if not isinstance(reason, str):
        raise ValueError("reason must be a string")
    value["confidence"] = confidence
    value["reason"] = reason.strip()
    return value


def safe_text(value: Any, limit: int = 500) -> str:
    """Keep diagnostic strings bounded and avoid storing arbitrary response bodies."""
    return value.strip()[:limit] if isinstance(value, str) else ""


def quota_dimension(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return ";".join(
        f"{safe_text(str(key), 80)}={safe_text(str(item), 120)}"
        for key, item in sorted(value.items())
        if isinstance(key, str) and isinstance(item, (str, int, float, bool))
    )[:500]


def parse_error_diagnostic(body: bytes) -> dict[str, str]:
    """Extract only stable Gemini error and quota fields, never the full body."""
    diagnostic = {
        "error_code": "", "error_status": "", "error_message": "",
        "quota_metric": "", "quota_limit": "", "quota_dimension": "",
    }
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return diagnostic
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return diagnostic
    code = error.get("code")
    if isinstance(code, (int, str)) and not isinstance(code, bool):
        diagnostic["error_code"] = str(code)
    diagnostic["error_status"] = safe_text(error.get("status"), 120)
    diagnostic["error_message"] = safe_text(error.get("message"))
    details = error.get("details")
    if not isinstance(details, list):
        return diagnostic
    for detail in details:
        if not isinstance(detail, dict):
            continue
        violations = detail.get("violations")
        if not isinstance(violations, list) or not violations:
            continue
        violation = violations[0]
        if not isinstance(violation, dict):
            continue
        diagnostic["quota_metric"] = safe_text(violation.get("quotaMetric") or violation.get("quota_metric"), 300)
        limit = violation.get("quotaLimit") or violation.get("quotaValue") or violation.get("limit")
        if isinstance(limit, (str, int, float)) and not isinstance(limit, bool):
            diagnostic["quota_limit"] = str(limit)[:120]
        diagnostic["quota_dimension"] = quota_dimension(
            violation.get("quotaDimensions") or violation.get("quota_dimensions")
        )
        break
    return diagnostic


def retry_after_seconds(value: str) -> float | None:
    value = value.strip()
    if not value:
        return None
    try:
        seconds = float(value)
        return seconds if seconds >= 0 else None
    except ValueError:
        try:
            target = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            return None
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        return max(0.0, (target - datetime.now(timezone.utc)).total_seconds())


def next_backoff(attempt_index: int, retry_after: str) -> float:
    """Prefer server guidance; otherwise use capped exponential backoff with jitter."""
    server_delay = retry_after_seconds(retry_after)
    if server_delay is not None:
        return server_delay
    return min(2 ** attempt_index, 30) + random.uniform(0, 0.5)


def call_gemini(
    row: dict[str, str], api_key: str, model: str, timeout: float, max_attempts: int,
    fallback_reason: str, record_attempt: Any,
) -> dict[str, Any]:
    image = Path(row["_resolved_image_path"])
    mime_type = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
    # Only bytes and the identical prompt are sent: never the filename or ground truth.
    payload = {"contents": [{"parts": [
        {"text": PROMPT},
        {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(image.read_bytes()).decode("ascii")}},
    ]}], "generationConfig": {"responseMimeType": "application/json"}}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    url = GENERATE_URL.format(model=quote(model, safe="")) + "?key=" + quote(api_key, safe="")
    last_error = ""
    for attempt in range(max_attempts):
        timestamp = datetime.now(timezone.utc).isoformat()
        status, retry_after, duration = "", "", 0.0
        diagnostic = {
            "error_code": "", "error_status": "", "error_message": "",
            "quota_metric": "", "quota_limit": "", "quota_dimension": "",
        }
        try:
            status, response, retry_after, duration = request_bytes(url, body, timeout)
            if 200 <= status < 300:
                raw = json.loads(response.decode("utf-8"))
                candidates = raw.get("candidates") if isinstance(raw, dict) else None
                parts = candidates[0].get("content", {}).get("parts", []) if isinstance(candidates, list) and candidates else []
                text = next((part.get("text") for part in parts if isinstance(part, dict) and isinstance(part.get("text"), str)), None)
                if text is None:
                    raise ValueError("response contained no text candidate")
                prediction = validate_prediction(extract_json(text))
                record_attempt({
                    "timestamp": timestamp, "model_used": model, "http_status": str(status), "status": "success",
                    "retry_after": retry_after, "request_duration_sec": f"{duration:.3f}",
                    "fallback_reason": fallback_reason, **prediction,
                })
                return prediction
            last_error = f"HTTP_{status}"
            retryable = status == 429 or 500 <= status <= 599
            diagnostic = parse_error_diagnostic(response)
        except (TimeoutError, socket.timeout):
            last_error, retryable = "TIMEOUT", True
        except (URLError, OSError):
            last_error, retryable = "NETWORK_ERROR", True
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, KeyError, IndexError, TypeError):
            last_error, retryable = "INVALID_RESPONSE", False
        should_retry = retryable and attempt + 1 < max_attempts
        backoff = next_backoff(attempt, retry_after) if should_retry else 0.0
        record_attempt({
            "timestamp": timestamp, "model_used": model, "http_status": str(status), "status": "failure",
            "retry_after": retry_after, "request_duration_sec": f"{duration:.3f}",
            "backoff_sec": f"{backoff:.3f}" if should_retry else "",
            "fallback_reason": fallback_reason, "error": last_error, **diagnostic,
        })
        if not should_retry:
            break
        print(f"  {row['image_id']}: {last_error}; retrying in {backoff:.3f}s ({attempt + 1}/{max_attempts - 1})", flush=True)
        time.sleep(backoff)
    raise RuntimeError(last_error or "REQUEST_FAILED")


def blank_result(row: dict[str, str], model: str) -> dict[str, Any]:
    result = {field: "" for field in RESULT_FIELDS}
    result.update({field: row[field] for field in ("image_id", "image_path", "difficulty")})
    result.update(true_country=row["true_country"], true_region=row["true_region"], true_city=row["true_city"], true_place=row["true_place"], model_used=model)
    return result


def write_results(rows: list[dict[str, Any]]) -> None:
    temporary = RESULTS_PATH.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=RESULT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(RESULTS_PATH)


def load_attempts() -> list[dict[str, str]]:
    if not ATTEMPTS_PATH.is_file():
        return []
    with ATTEMPTS_PATH.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        rows = list(reader)
        fields = set(reader.fieldnames or [])
        if set(ATTEMPT_FIELDS).issubset(fields):
            return rows
        legacy_fields = {"image_id", "attempt_no", "status", "pred_region", "pred_city", "pred_place", "confidence", "error", "model_used"}
        if legacy_fields.issubset(fields):
            # Preserve every legacy value while leaving new diagnostics explicitly unknown.
            return [{field: row.get(field, "") for field in ATTEMPT_FIELDS} for row in rows]
        raise ValueError("attempts.csv requires: " + ", ".join(ATTEMPT_FIELDS))


def write_attempts(attempts: list[dict[str, Any]]) -> None:
    temporary = ATTEMPTS_PATH.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=ATTEMPT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(attempts)
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(ATTEMPTS_PATH)


def attempt_record(image_id: str, attempt_no: int, values: dict[str, Any]) -> dict[str, Any]:
    record = {field: "" for field in ATTEMPT_FIELDS}
    record.update({field: values.get(field, "") for field in ATTEMPT_FIELDS})
    record["image_id"] = image_id
    record["attempt_no"] = attempt_no
    return record


def bootstrap_initial_attempts(previous: dict[str, dict[str, str]], rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Snapshot pre-attempts.csv results as attempt 1 without changing results.csv."""
    attempts: list[dict[str, Any]] = []
    for row in rows:
        result = previous.get(row["image_id"])
        if result:
            attempts.append(attempt_record(row["image_id"], 1, result))
    if attempts:
        write_attempts(attempts)
    return attempts


def append_attempt(attempts: list[dict[str, Any]], image_id: str, values: dict[str, Any]) -> None:
    attempt_no = 1 + max(
        (int(item["attempt_no"]) for item in attempts if item["image_id"] == image_id),
        default=0,
    )
    attempts.append(attempt_record(image_id, attempt_no, values))
    write_attempts(attempts)


def load_completed() -> dict[str, dict[str, str]]:
    if not RESULTS_PATH.is_file():
        return {}
    with RESULTS_PATH.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not set(RESULT_FIELDS).issubset(reader.fieldnames or []):
            return {}
        return {row["image_id"]: row for row in reader if row.get("image_id") and row.get("status") in {"success", "failure"}}


def metrics(rows: list[dict[str, Any]]) -> None:
    successful = [row for row in rows if row["status"] == "success"]
    api_failures = [row for row in rows if row["status"] != "success"]
    abstentions = [row for row in successful if is_abstention(row)]
    def rate(field: str, subset: list[dict[str, Any]] = successful) -> str:
        if not subset:
            return "N/A"
        return f"{sum(str(row[field]).lower() == 'true' for row in subset) / len(subset):.1%}"
    confidence_values = [float(row["confidence"]) for row in successful if str(row["confidence"]).strip()]
    print(f"Total: {len(rows)}")
    print(f"Successful: {len(successful)}")
    print(f"API Success Rate: {len(successful) / len(rows):.1%}" if rows else "API Success Rate: N/A")
    print(f"API Failure Count: {len(api_failures)}")
    print(f"Abstention Count: {len(abstentions)}")
    print()
    print(f"Country Accuracy: {rate('country_match')}")
    print(f"Region Accuracy: {rate('region_match')}")
    print(f"City Accuracy: {rate('city_match')}")
    print(f"Exact Place Accuracy: {rate('exact_place_match')}")
    print()
    for difficulty in ("landmark", "general", "hard"):
        subset = [row for row in successful if row["difficulty"] == difficulty]
        print(f"{difficulty}: {rate('exact_place_match', subset)}")
    print(f"Average Confidence: {sum(confidence_values) / len(confidence_values):.3f}" if confidence_values else "Average Confidence: N/A")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--max-attempts", type=int, default=3, help="Maximum generateContent requests per image, including the first request")
    parser.add_argument("--request-interval", type=float, default=0.0, help="Seconds to wait before each subsequent image request")
    parser.add_argument("--retry-failed", action="store_true", help="Retry rows previously recorded as failure")
    parser.add_argument("--force", action="store_true", help="Ignore all existing results.csv rows")
    parser.add_argument("--migrate-attempts", action="store_true", help="Expand a legacy attempts.csv schema without API access")
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0 or not 1 <= args.max_attempts <= 10:
        parser.error("--timeout must be positive and --max-attempts must be between 1 and 10")
    if not math.isfinite(args.request_interval) or args.request_interval < 0:
        parser.error("--request-interval must be zero or greater")
    if args.migrate_attempts:
        try:
            attempts = load_attempts()
            write_attempts(attempts)
        except (OSError, csv.Error, ValueError) as error:
            print(f"Attempt history error: {error}", file=sys.stderr)
            return 2
        print(f"Attempt history migrated: {ATTEMPTS_PATH}")
        return 0
    try:
        rows = parse_truth(GROUND_TRUTH_PATH)
    except (OSError, csv.Error, ValueError) as error:
        print(f"Input error: {error}", file=sys.stderr)
        return 2
    load_dotenv_if_needed()
    api_key = os.environ.get(API_KEY_ENV_NAME, "").strip()
    if not api_key:
        print("Configuration error: GEMINI_API_KEY is not set. Set the existing GEMINI_API_KEY environment variable and retry.", file=sys.stderr)
        return 2
    configured, fallback = configure_models_from_environment()
    try:
        model, fallback_reason = select_model(api_key, configured, fallback, args.timeout)
    except (RuntimeError, TimeoutError, socket.timeout, URLError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        print(f"Configuration error: unable to select an available image-capable Gemini model ({error}).", file=sys.stderr)
        return 2
    previous = {} if args.force else load_completed()
    try:
        attempts = load_attempts()
    except (OSError, csv.Error, ValueError) as error:
        print(f"Attempt history error: {error}", file=sys.stderr)
        return 2
    if not attempts and previous:
        attempts = bootstrap_initial_attempts(previous, rows)
    results: list[dict[str, Any]] = []
    prior_image_request_finished: float | None = None
    for index, row in enumerate(rows, start=1):
        old = previous.get(row["image_id"])
        if old and (old["status"] == "success" or not args.retry_failed):
            results.append(old)
            print(f"[{index}/{len(rows)}] {row['image_id']}: skipped existing {old['status']}", flush=True)
            continue
        if prior_image_request_finished is not None and args.request_interval:
            elapsed = time.monotonic() - prior_image_request_finished
            if elapsed < args.request_interval:
                time.sleep(args.request_interval - elapsed)
        result = blank_result(row, model)
        try:
            prediction = call_gemini(
                row, api_key, model, args.timeout, args.max_attempts, fallback_reason,
                lambda values: append_attempt(attempts, row["image_id"], values),
            )
            result.update(prediction, status="success")
            score_result(result, row)
            print(f"[{index}/{len(rows)}] {row['image_id']}: success", flush=True)
        except RuntimeError as error:
            result.update(status="failure", error=str(error))
            print(f"[{index}/{len(rows)}] {row['image_id']}: failure ({result['error']})", flush=True)
        prior_image_request_finished = time.monotonic()
        results.append(result)
        # Atomic rewrite after every image provides a durable resume checkpoint.
        write_results(results)
    write_results(results)
    metrics(results)
    print(f"Results: {RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
