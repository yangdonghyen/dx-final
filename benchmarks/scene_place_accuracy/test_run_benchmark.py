"""Offline tests: python -m unittest discover -s benchmarks/scene_place_accuracy -v"""

import contextlib
import csv
from http.client import IncompleteRead
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import run_benchmark as bench


PLACE = {"detail_name": "근정전", "parent_name": "경복궁",
         "accepted_names": ["근정전", "경복궁", "Gyeongbokgung Palace"]}


def response(primary="근정전", others=(), recognized=True):
    return {"received": True, "filename": "scene.jpg", "content_type": "image/jpeg", "size_bytes": 3,
            "recognized": recognized, "primary_candidate": {"place_name": primary} if primary else None,
            "candidates": [{"place_name": name} for name in others], "confidence": "HIGH",
            "place_verified": False}


class ScoringTests(unittest.TestCase):
    def test_explicit_detail_parent_alias_and_sibling_rules(self):
        for name, correct in [("근정전", True), ("경복궁", True), (" GYEONGBOKGUNG-Palace ", True),
                              ("경회루", False), ("창덕궁", False), ("경복궁역", False),
                              ("Geunjeongjeon", False)]:
            with self.subTest(name=name):
                result = bench.evaluate(response(name), PLACE)
                self.assertEqual(result["top1_correct"], correct)

    def test_deduplication_before_limit_and_fourth_candidate(self):
        result = bench.evaluate(response("Wrong Place", ["wrong-place", "경회루", "다른곳", "경복궁", "근정전"]), PLACE)
        self.assertEqual(json.loads(result["ordered_candidates"]), ["Wrong Place", "경회루", "다른곳", "경복궁"])
        self.assertEqual(result["candidate_4"], "경복궁")
        self.assertFalse(result["top1_correct"])
        self.assertTrue(result["top4_correct"])
        self.assertFalse(bench.evaluate(response("a", ["b", "c", "d", "경복궁"]), PLACE)["top4_correct"])

    def test_unrecognized_always_misses_and_kakao_does_not_replace_primary(self):
        self.assertFalse(bench.evaluate(response("근정전", recognized=False), PLACE)["top4_correct"])
        data = response("경회루")
        data.update(place_verified=True, verified_place={"place_name": "경복궁"})
        self.assertFalse(bench.evaluate(data, PLACE)["top1_correct"])
        self.assertFalse(bench.evaluate(data, PLACE)["top4_correct"])

    def test_invalid_analysis_is_not_evaluable(self):
        for data in [None, [], {"received": True}, {"received": True, "recognized": "false"},
                     response(None), response("---"), dict(response(), candidates=[None])]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                bench.validate_response(data)
        bench.validate_response(response(None, recognized=False))

    def test_denominators_and_zero_success(self):
        rows = [dict(api_status="success", top1_correct=True, top4_correct=True, place_id="a", capture_type="night"),
                dict(api_status="success", top1_correct=False, top4_correct=True, place_id="a", capture_type="detail"),
                dict(api_status="success", top1_correct=False, top4_correct=False, place_id="b", capture_type="night"),
                dict(api_status="failure", top1_correct="", top4_correct="", place_id="b", capture_type="night")]
        summary = bench.summarize(rows)
        self.assertEqual(summary["api_success_rate"], 3 / 4)
        self.assertEqual(summary["top1_accuracy"], 1 / 3)
        self.assertEqual(summary["top4_hit_rate"], 2 / 3)
        self.assertEqual(summary["miss_count"], 1)
        self.assertEqual(summary["e2e_top4_success_rate"], 1 / 2)
        self.assertEqual(summary["by_place"]["a"]["top4_hit_rate"], 1)
        self.assertEqual(summary["by_capture_type"]["night"]["top1_accuracy"], 1 / 2)
        self.assertIsNone(bench.metrics(rows[-1:])["top1_accuracy"])


class HTTPAndDatasetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.places = self.root / "places.json"
        self.places.write_text(json.dumps({"palace": PLACE}), encoding="utf-8")
        self.manifest = self.root / "manifest.csv"

    def make_dataset(self, count=3):
        with self.manifest.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.writer(output)
            writer.writerow(["image_id", "image_path", "place_id", "capture_type", "note"])
            for index in range(count):
                name = f"photo_{index}" + [".jpg", ".png", ".webp"][index % 3]
                (self.root / name).write_bytes(b"test-image-bytes")
                writer.writerow([f"{index:03}", name, "palace", "night", ""])

    def start_server(self, replies):
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                message = BytesParser(policy=policy.default).parsebytes(
                    f"Content-Type: {self.headers['Content-Type']}\r\nMIME-Version: 1.0\r\n\r\n".encode() + body)
                parts = {part.get_param("name", header="content-disposition"): part
                         for part in message.iter_parts()}
                requests.append((self.path, self.headers.get("Authorization"), parts))
                status, payload = replies[min(len(requests) - 1, len(replies) - 1)]
                content = payload.encode() if isinstance(payload, str) else json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def shutdown():
            server.shutdown()
            server.server_close()
            thread.join()

        self.addCleanup(shutdown)
        return f"http://127.0.0.1:{server.server_port}", requests

    def test_120_image_cli_multipart_outputs_and_retries(self):
        self.make_dataset(120)
        base, requests = self.start_server([
            (429, {"error": {"code": "GEMINI_RATE_LIMITED"}}), (200, response()),
            (200, response("경회루", ["경복궁"])), (200, response(None, recognized=False)),
        ])
        output = self.root / "results"
        console = io.StringIO()
        with patch.dict(os.environ, BENCHMARK_API_URL=base, BENCHMARK_ACCESS_TOKEN="test-token"), contextlib.redirect_stdout(console):
            code = bench.main(["--places", str(self.places), "--manifest", str(self.manifest),
                               "--results", str(output), "--retry-delay", "0"])
        self.assertEqual(code, 0)
        summary = json.loads(next(output.glob("*_summary.json")).read_text(encoding="utf-8"))
        self.assertEqual(summary["total_images"], 120)
        self.assertEqual(summary["api_success_count"], 120)
        self.assertEqual(summary["top1_correct_count"], 1)
        self.assertEqual(summary["top4_correct_count"], 2)
        self.assertEqual(summary["miss_count"], 118)
        with next(output.glob("*_details.csv")).open(encoding="utf-8-sig", newline="") as source:
            rows = list(csv.DictReader(source))
        self.assertEqual(len(rows), 120)
        self.assertEqual(rows[0]["image_id"], "000")
        self.assertEqual(rows[0]["retry_count"], "1")
        raw = next(output.glob("*_responses.jsonl")).read_text(encoding="utf-8")
        self.assertEqual(len(raw.splitlines()), 121)
        self.assertNotIn("test-token", raw)
        self.assertIn("[120/120]", console.getvalue())
        for index, (path, auth, parts) in enumerate(requests):
            self.assertEqual(path, bench.ENDPOINT)
            self.assertEqual(auth, "Bearer test-token")
            self.assertEqual(parts["analyze"].get_payload(decode=True), b"true")
            self.assertEqual(parts["file"].get_payload(decode=True), b"test-image-bytes")
        self.assertEqual(requests[1][2]["file"].get_content_type(), "image/jpeg")
        self.assertEqual(requests[2][2]["file"].get_content_type(), "image/png")
        self.assertEqual(requests[3][2]["file"].get_content_type(), "image/webp")

    def test_failure_retry_exhaustion_and_invalid_200(self):
        self.make_dataset(1)
        places, rows = bench.load_dataset(self.places, self.manifest)
        for status, payload, error, attempts in [
            (503, {"error": {"code": "GEMINI_UNAVAILABLE"}}, "GEMINI_UNAVAILABLE", 3),
            (401, {"error": {"code": "UNAUTHORIZED"}}, "UNAUTHORIZED", 1),
            (200, "not-json", "INVALID_RESPONSE", 1),
            (200, {"received": True}, "INVALID_RESPONSE", 1),
        ]:
            with self.subTest(status=status, payload=payload):
                base, requests = self.start_server([(status, payload)])
                with contextlib.redirect_stdout(io.StringIO()):
                    result = bench.run_image(rows[0], places["palace"], base + bench.ENDPOINT,
                                             "token", 2, 2, 0, io.StringIO())
                self.assertEqual(result["error_code"], error)
                self.assertEqual(result["api_status"], "failure")
                self.assertEqual(len(requests), attempts)
                self.assertEqual(result["retry_count"], attempts - 1)
                self.assertEqual(result["top1_correct"], "")

    def test_network_failure_is_excluded(self):
        self.make_dataset(1)
        _, rows = bench.load_dataset(self.places, self.manifest)
        for error, code in [(TimeoutError(), "REQUEST_TIMEOUT"), (IncompleteRead(b"partial"), "REQUEST_ERROR")]:
            with self.subTest(code=code), patch.object(bench, "post_image", side_effect=error):
                result = bench.run_image(rows[0], PLACE, "http://localhost", "token", 1, 2, 0, io.StringIO())
            self.assertEqual(result["error_code"], code)
            self.assertEqual(result["attempt_count"], 1)
            self.assertIsNone(bench.metrics([result])["top4_hit_rate"])

    def test_cli_continues_after_failure_and_writes_mixed_summary(self):
        self.make_dataset(3)
        base, _ = self.start_server([(503, {"error": {"code": "GEMINI_UNAVAILABLE"}}),
                                     (200, response()), (200, response(None, recognized=False))])
        output = self.root / "results"
        with patch.dict(os.environ, BENCHMARK_API_URL=base, BENCHMARK_ACCESS_TOKEN="test-token"), contextlib.redirect_stdout(io.StringIO()):
            code = bench.main(["--places", str(self.places), "--manifest", str(self.manifest),
                               "--results", str(output), "--retries", "0"])
        summary = json.loads(next(output.glob("*_summary.json")).read_text(encoding="utf-8"))
        self.assertEqual(code, 1)
        self.assertEqual(summary["api_failure_count"], 1)
        self.assertEqual(summary["top1_accuracy"], 1 / 2)
        self.assertEqual(summary["miss_rate"], 1 / 2)
        self.assertEqual(summary["e2e_top1_success_rate"], 1 / 3)

    def test_checkpoint_resume_skips_successes_and_stops_on_consecutive_rate_limits(self):
        self.make_dataset(3)
        output = self.root / "results"
        limited_base, limited_requests = self.start_server([
            (429, {"error": {"code": "GEMINI_RATE_LIMITED"}}),
        ])
        with patch.dict(os.environ, BENCHMARK_API_URL=limited_base, BENCHMARK_ACCESS_TOKEN="test-token"), \
             contextlib.redirect_stdout(io.StringIO()):
            code = bench.main(["--places", str(self.places), "--manifest", str(self.manifest),
                               "--results", str(output), "--retries", "0",
                               "--max-consecutive-rate-limits", "2"])
        self.assertEqual(code, 1)
        self.assertEqual(len(limited_requests), 2)
        partial = json.loads(sorted(output.glob("*_summary.json"))[-1].read_text(encoding="utf-8"))
        self.assertFalse(partial["official_results"])
        self.assertEqual(partial["completed_api_successes"], 0)
        self.assertEqual(partial["remaining_count"], 3)
        self.assertEqual(partial["rate_limit_failure_count"], 2)
        checkpoint = output / "benchmark_progress.jsonl"
        self.assertEqual(len(checkpoint.read_text(encoding="utf-8").splitlines()), 2)

        success_base, success_requests = self.start_server([(200, response())])
        with patch.dict(os.environ, BENCHMARK_API_URL=success_base, BENCHMARK_ACCESS_TOKEN="test-token"), \
             contextlib.redirect_stdout(io.StringIO()):
            code = bench.main(["--places", str(self.places), "--manifest", str(self.manifest),
                               "--results", str(output), "--retries", "0"])
        self.assertEqual(code, 0)
        self.assertEqual(len(success_requests), 3)
        final = json.loads(sorted(output.glob("*_summary.json"))[-1].read_text(encoding="utf-8"))
        self.assertTrue(final["official_results"])
        self.assertEqual(final["completed_api_successes"], 3)
        self.assertEqual(final["remaining_count"], 0)

        resume_base, resume_requests = self.start_server([(200, response())])
        with patch.dict(os.environ, BENCHMARK_API_URL=resume_base, BENCHMARK_ACCESS_TOKEN="test-token"), \
             contextlib.redirect_stdout(io.StringIO()):
            code = bench.main(["--places", str(self.places), "--manifest", str(self.manifest),
                               "--results", str(output), "--retries", "0"])
        self.assertEqual(code, 0)
        self.assertEqual(len(resume_requests), 0)

    def test_dataset_errors_prevent_requests(self):
        self.make_dataset(1)
        places, rows = bench.load_dataset(self.places, self.manifest)
        self.assertEqual(rows[0]["image_id"], "000")
        self.assertEqual(places["palace"], PLACE)
        original = self.manifest.read_text(encoding="utf-8-sig")
        for modified in [original + original.splitlines()[1] + "\n",
                         original.replace(",palace,", ",unknown,"),
                         original.replace("photo_0.jpg", "missing.jpg")]:
            self.manifest.write_text(modified, encoding="utf-8")
            with self.assertRaises(ValueError):
                bench.load_dataset(self.places, self.manifest)


if __name__ == "__main__":
    unittest.main()
