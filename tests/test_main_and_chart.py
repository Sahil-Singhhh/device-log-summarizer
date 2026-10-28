"""
Tests for Section 2 — CSV processing, aggregation, filtering, and JSON export.
Tests for Section 3 — chart generation.

These tests patch sanitize_readings() with a correct reference implementation
so they can run independently of the Section 1 candidate implementation.
The Section 1 tests in test_sanitizer.py test the real implementation separately.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Project root on path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Reference implementation of sanitize_readings used only for mocking.
# This is NOT the Section 1 candidate implementation.
# ---------------------------------------------------------------------------
def _reference_sanitize(readings):
    result = []
    for r in readings:
        if r is None:
            continue
        try:
            val = float(r)
        except (ValueError, TypeError):
            continue
        if val < 0:
            continue
        result.append(min(val, 500.0))
    return result


# ---------------------------------------------------------------------------
# Helper — write a temporary CSV
# ---------------------------------------------------------------------------
def write_temp_csv(content: str) -> Path:
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    return Path(path)


# ---------------------------------------------------------------------------
# Section 2: load_csv
# ---------------------------------------------------------------------------
class TestLoadCSV(unittest.TestCase):

    def test_missing_file_raises(self):
        from main import load_csv
        with self.assertRaises(FileNotFoundError):
            load_csv(Path("non_existent_file_xyz.csv"))

    def test_empty_file_raises(self):
        from main import load_csv
        p = write_temp_csv("")
        try:
            with self.assertRaises(ValueError):
                load_csv(p)
        finally:
            p.unlink()

    def test_missing_column_raises(self):
        from main import load_csv
        p = write_temp_csv("device_id,temperature\nDEV_A,35.5\n")
        try:
            with self.assertRaises(ValueError):
                load_csv(p)
        finally:
            p.unlink()

    def test_valid_csv_loads(self):
        from main import load_csv
        p = write_temp_csv("device_id,status,temperature\nDEV_A,ACTIVE,35.5\n")
        try:
            rows = load_csv(p)
            self.assertEqual(len(rows), 1)
        finally:
            p.unlink()

    def test_header_only_returns_empty(self):
        from main import load_csv
        p = write_temp_csv("device_id,status,temperature\n")
        try:
            rows = load_csv(p)
            self.assertEqual(rows, [])
        finally:
            p.unlink()


# ---------------------------------------------------------------------------
# Section 2: aggregate
# ---------------------------------------------------------------------------
def make_rows(content: str) -> list:
    from main import load_csv
    p = write_temp_csv(content)
    try:
        rows = load_csv(p)
    finally:
        p.unlink()
    return rows


@patch("main.sanitize_readings", side_effect=_reference_sanitize)
class TestAggregate(unittest.TestCase):

    def test_single_device_grouping(self, _mock):
        from main import aggregate
        rows = make_rows(
            "device_id,status,temperature\n"
            "DEV_A,ACTIVE,35.5\nDEV_A,WARNING,42.0\nDEV_A,ERROR,48.5\n"
        )
        result = aggregate(rows)
        self.assertIn("DEV_A", result)

    def test_total_records_count(self, _mock):
        from main import aggregate
        rows = make_rows(
            "device_id,status,temperature\n"
            "DEV_A,ACTIVE,35.5\nDEV_A,WARNING,42.0\nDEV_A,ERROR,48.5\n"
        )
        result = aggregate(rows)
        self.assertEqual(result["DEV_A"]["total_records"], 3)

    def test_average_temperature(self, _mock):
        from main import aggregate
        rows = make_rows(
            "device_id,status,temperature\n"
            "DEV_A,ACTIVE,35.5\nDEV_A,WARNING,42.0\nDEV_A,ERROR,48.5\n"
        )
        result = aggregate(rows)
        expected = round((35.5 + 42.0 + 48.5) / 3, 4)
        self.assertAlmostEqual(result["DEV_A"]["average_temperature"], expected, places=4)

    def test_error_count(self, _mock):
        from main import aggregate
        rows = make_rows(
            "device_id,status,temperature\n"
            "DEV_A,ACTIVE,35.5\nDEV_A,WARNING,42.0\nDEV_A,ERROR,48.5\n"
        )
        result = aggregate(rows)
        self.assertEqual(result["DEV_A"]["error_count"], 1)

    def test_multiple_devices(self, _mock):
        from main import aggregate
        rows = make_rows(
            "device_id,status,temperature\n"
            "DEV_A,ACTIVE,35.5\nDEV_B,ERROR,90.0\n"
        )
        result = aggregate(rows)
        self.assertEqual(len(result), 2)

    def test_invalid_temperature_excluded_from_average(self, _mock):
        from main import aggregate
        rows = make_rows(
            "device_id,status,temperature\n"
            "DEV_A,ACTIVE,35.5\nDEV_A,WARNING,bad_temp\n"
        )
        result = aggregate(rows)
        self.assertEqual(result["DEV_A"]["total_records"], 1)
        self.assertAlmostEqual(result["DEV_A"]["average_temperature"], 35.5, places=4)

    def test_missing_device_id_skipped(self, _mock):
        from main import aggregate
        rows = make_rows(
            "device_id,status,temperature\n"
            ",ACTIVE,50.0\nDEV_A,ACTIVE,35.0\n"
        )
        result = aggregate(rows)
        self.assertNotIn("", result)
        self.assertIn("DEV_A", result)

    def test_device_with_no_valid_temps_has_null_average(self, _mock):
        from main import aggregate
        rows = make_rows(
            "device_id,status,temperature\nDEV_X,ACTIVE,invalid\n"
        )
        result = aggregate(rows)
        self.assertIn("DEV_X", result)
        self.assertIsNone(result["DEV_X"]["average_temperature"])
        self.assertEqual(result["DEV_X"]["total_records"], 0)

    def test_status_normalised_to_uppercase(self, _mock):
        from main import aggregate
        rows = make_rows(
            "device_id,status,temperature\n"
            "DEV_A,error,35.5\nDEV_A,Error,40.0\n"
        )
        result = aggregate(rows)
        self.assertEqual(result["DEV_A"]["error_count"], 2)

    def test_empty_data_rows(self, _mock):
        from main import aggregate
        rows = make_rows("device_id,status,temperature\n")
        result = aggregate(rows)
        self.assertEqual(result, {})


# ---------------------------------------------------------------------------
# Section 2: filter_devices
# ---------------------------------------------------------------------------
class TestFilterDevices(unittest.TestCase):

    def _make_agg(self, entries):
        return {
            dev: {"device_id": dev, "total_records": 1,
                  "average_temperature": avg, "error_count": 0}
            for dev, avg in entries
        }

    def test_above_threshold_excluded(self):
        from main import filter_devices
        kept, excluded = filter_devices(self._make_agg([("DEV_A", 81.0)]), 80.0)
        self.assertEqual(kept, [])
        self.assertIn("DEV_A", excluded)

    def test_at_threshold_retained(self):
        from main import filter_devices
        kept, _ = filter_devices(self._make_agg([("DEV_A", 80.0)]), 80.0)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["device_id"], "DEV_A")

    def test_below_threshold_retained(self):
        from main import filter_devices
        kept, _ = filter_devices(self._make_agg([("DEV_A", 42.0)]), 80.0)
        self.assertEqual(len(kept), 1)

    def test_none_average_excluded(self):
        from main import filter_devices
        kept, excluded = filter_devices(self._make_agg([("DEV_X", None)]), 80.0)
        self.assertEqual(kept, [])
        self.assertIn("DEV_X", excluded)

    def test_output_sorted_by_device_id(self):
        from main import filter_devices
        agg = self._make_agg([("DEV_C", 30.0), ("DEV_A", 20.0), ("DEV_B", 50.0)])
        kept, _ = filter_devices(agg, 80.0)
        ids = [d["device_id"] for d in kept]
        self.assertEqual(ids, sorted(ids))

    def test_empty_input(self):
        from main import filter_devices
        kept, excluded = filter_devices({}, 80.0)
        self.assertEqual(kept, [])
        self.assertEqual(excluded, [])


# ---------------------------------------------------------------------------
# Section 2: export_json
# ---------------------------------------------------------------------------
class TestExportJSON(unittest.TestCase):

    def test_valid_json_written(self):
        from main import export_json
        devices = [{"device_id": "DEV_A", "total_records": 3,
                    "average_temperature": 42.0, "error_count": 1}]
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)
        try:
            export_json(devices, 80.0, path)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["filter_threshold"], 80.0)
            self.assertEqual(data["devices"][0]["device_id"], "DEV_A")
        finally:
            path.unlink()

    def test_empty_devices_written(self):
        from main import export_json
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)
        try:
            export_json([], 80.0, path)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["devices"], [])
        finally:
            path.unlink()


# ---------------------------------------------------------------------------
# Section 3: chart helpers
# ---------------------------------------------------------------------------
class TestExtractChartData(unittest.TestCase):

    def test_valid_data_extracted(self):
        from chart import extract_chart_data
        data = {"devices": [
            {"device_id": "DEV_A", "average_temperature": 42.0},
            {"device_id": "DEV_B", "average_temperature": 78.5},
        ]}
        labels, values = extract_chart_data(data)
        self.assertEqual(labels, ["DEV_A", "DEV_B"])
        self.assertEqual(values, [42.0, 78.5])

    def test_null_average_excluded(self):
        from chart import extract_chart_data
        data = {"devices": [
            {"device_id": "DEV_A", "average_temperature": 42.0},
            {"device_id": "DEV_X", "average_temperature": None},
        ]}
        labels, values = extract_chart_data(data)
        self.assertNotIn("DEV_X", labels)

    def test_empty_devices_returns_empty(self):
        from chart import extract_chart_data
        labels, values = extract_chart_data({"devices": []})
        self.assertEqual(labels, [])
        self.assertEqual(values, [])

    def test_missing_devices_key(self):
        from chart import extract_chart_data
        labels, values = extract_chart_data({})
        self.assertEqual(labels, [])
        self.assertEqual(values, [])


class TestChartLoadJSON(unittest.TestCase):

    def test_missing_file_raises(self):
        from chart import load_json as chart_load_json
        with self.assertRaises(FileNotFoundError):
            chart_load_json(Path("non_existent_xyz.json"))

    def test_malformed_json_raises(self):
        from chart import load_json as chart_load_json
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write("{this is not valid json")
            path = Path(f.name)
        try:
            with self.assertRaises(json.JSONDecodeError):
                chart_load_json(path)
        finally:
            path.unlink()


class TestChartGeneration(unittest.TestCase):

    def test_chart_file_created(self):
        from chart import generate_chart
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = Path(f.name)
        path.unlink()
        try:
            generate_chart(["DEV_A", "DEV_B"], [35.5, 76.0], path)
            self.assertTrue(path.exists())
        finally:
            if path.exists():
                path.unlink()


if __name__ == "__main__":
    unittest.main()
