"""Metadata-only relevance rules for Wikimedia collection."""
import sys
from pathlib import Path
import tempfile
from unittest.mock import patch
import csv
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect_dataset as collector


class RelevanceTests(unittest.TestCase):
    def setUp(self):
        self.place = collector.build_places("diversity")["pohang_space_walk"]

    def test_foreign_homonym_is_rejected(self):
        verdict, _ = collector.assess_place({"title": "Somerset Space Walk Earth", "description": "United Kingdom", "categories": [], "depicts": []}, self.place)
        self.assertEqual(verdict, "REJECT")

    def test_required_landmark_evidence_and_korea_pass(self):
        verdict, _ = collector.assess_place({"title": "Pohang Space Walk", "description": "Pohang, South Korea", "categories": [], "depicts": []}, self.place)
        self.assertEqual(verdict, "PASS")

    def test_squirrel_is_rejected_even_with_place_tag(self):
        place = collector.build_places("diversity")["seoraksan"]
        verdict, _ = collector.assess_place({"title": "Squirrel in Seoraksan", "description": "South Korea", "categories": [], "depicts": []}, place)
        self.assertEqual(verdict, "REJECT")

    def test_word_boundaries_do_not_treat_gyeongbuk_as_uk(self):
        place = collector.build_places("diversity")["bulguksa"]
        verdict, _ = collector.assess_place({"title": "Bulguksa", "description": "Gyeongbuk, Korea", "categories": [], "depicts": []}, place)
        self.assertEqual(verdict, "PASS")

    def test_missing_place_records_failure_and_continues(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(collector, "ROOT", Path(temp)), \
             patch.object(collector, "DIVERSITY", [("missing", "Missing", ["Missing"], "Missing", "park", "Seoul")]), \
             patch.object(collector, "candidates", return_value=iter(())):
            collector.collect("diversity")
            lines=(Path(temp)/"diversity"/"collection_failures.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            self.assertIn('"place_id": "missing"', lines[0])
            self.assertFalse((Path(temp)/"diversity"/"dataset_lock.json").exists())

    def test_write_csv_normalizes_commons_title_and_ignores_extra_metadata(self):
        fields=["file_title", "license"]
        rows=[
            {"file_title":"existing", "license":"A"},
            {"title":"fallback", "license":"B"},
            {"file_title":"preferred", "title":"discarded", "license":"C"},
            {"title":"with-extra", "license":"D", "unexpected":"value"},
        ]
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/"sources.csv"
            collector.write_csv(output, rows, fields)
            with output.open(encoding="utf-8-sig", newline="") as source:
                actual=list(csv.DictReader(source))
        self.assertEqual([row["file_title"] for row in actual], ["existing","fallback","preferred","with-extra"])
        self.assertEqual([row["license"] for row in actual], ["A","B","C","D"])


if __name__ == "__main__":
    unittest.main()
