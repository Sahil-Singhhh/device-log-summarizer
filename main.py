"""
Device Log Summarizer CLI — Section 2
======================================
Reads device_telemetry.csv, aggregates stats per device,
filters by a configurable temperature threshold, and exports to JSON.

Aggregation rules (documented per assessment requirement):
- A record must have a non-empty device_id to be included at all.
- temperature is passed through sanitize_readings(); invalid or missing
  temperatures are skipped and a warning is printed.
- total_records = number of rows with valid device_id AND valid temperature.
- average_temperature = arithmetic mean of valid temperature readings.
- error_count = rows (among valid-temperature rows) whose status normalises to ERROR.
- Devices with no valid temperature readings get average_temperature: null
  in JSON and are NOT classified as overheating.
- Devices whose average_temperature > threshold are excluded from output.
- Devices with null average_temperature are also excluded from output
  (cannot confirm they are within threshold).
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from statistics import mean

from sanitizer import sanitize_readings


REQUIRED_COLUMNS = {"device_id", "status", "temperature"}


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def load_csv(filepath: Path) -> list[dict]:
    """
    Read the CSV file and return a list of raw row dicts.
    Raises FileNotFoundError or ValueError for unrecoverable problems.
    """
    if not filepath.exists():
        raise FileNotFoundError(f"Input file not found: {filepath}")

    rows = []
    with filepath.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)

        # Validate required columns exist
        if reader.fieldnames is None:
            raise ValueError("CSV file is empty or has no header row.")

        actual = {col.strip() for col in reader.fieldnames}
        missing = REQUIRED_COLUMNS - actual
        if missing:
            raise ValueError(
                f"CSV is missing required column(s): {', '.join(sorted(missing))}"
            )

        for line_num, row in enumerate(reader, start=2):
            rows.append((line_num, row))

    return rows


def parse_row(line_num: int, row: dict) -> tuple[str | None, str | None, float | None]:
    """
    Extract and normalise device_id, status, and temperature from a raw CSV row.
    Returns (device_id, status, temperature). Any field may be None if invalid.
    Prints a warning for each skipped or problematic field.
    """
    device_id = row.get("device_id", "").strip()
    if not device_id:
        print(f"  [WARN] Line {line_num}: missing device_id — row skipped entirely.")
        return None, None, None

    status_raw = row.get("status", "").strip().upper()

    temp_raw = row.get("temperature", "").strip()
    clean = sanitize_readings([temp_raw])
    if not clean:
        print(
            f"  [WARN] Line {line_num}: device '{device_id}' has invalid/missing "
            f"temperature ({temp_raw!r}) — temperature record skipped."
        )
        return device_id, status_raw, None

    return device_id, status_raw, clean[0]


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate(rows: list[tuple]) -> dict[str, dict]:
    """
    Build per-device aggregation from parsed CSV rows.
    Returns a dict keyed by device_id.
    """
    devices: dict[str, dict] = {}

    for line_num, row in rows:
        device_id, status, temperature = parse_row(line_num, row)

        if device_id is None:
            continue  # row skipped entirely

        if device_id not in devices:
            devices[device_id] = {"temperatures": [], "error_count": 0, "total_records": 0}

        if temperature is not None:
            devices[device_id]["temperatures"].append(temperature)
            devices[device_id]["total_records"] += 1
            if status == "ERROR":
                devices[device_id]["error_count"] += 1

    result = {}
    for device_id, data in devices.items():
        temps = data["temperatures"]
        avg = round(mean(temps), 4) if temps else None
        result[device_id] = {
            "device_id": device_id,
            "total_records": data["total_records"],
            "average_temperature": avg,
            "error_count": data["error_count"],
        }

    return result


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def filter_devices(aggregated: dict, threshold: float) -> tuple[list[dict], list[str]]:
    """
    Exclude devices whose average_temperature is strictly > threshold,
    or whose average_temperature is None (cannot confirm within threshold).

    Returns (kept_devices, excluded_device_ids).
    """
    kept = []
    excluded = []

    for device_id, stats in sorted(aggregated.items()):
        avg = stats["average_temperature"]
        if avg is None:
            print(
                f"  [INFO] Device '{device_id}' excluded: no valid temperature readings."
            )
            excluded.append(device_id)
        elif avg > threshold:
            print(
                f"  [INFO] Device '{device_id}' excluded: avg {avg:.2f}°C > threshold {threshold}°C."
            )
            excluded.append(device_id)
        else:
            kept.append(stats)

    return kept, excluded


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------

def export_json(devices: list[dict], threshold: float, output_path: Path) -> None:
    """Write the filtered aggregation to a JSON file."""
    payload = {
        "filter_threshold": threshold,
        "devices": devices,
    }
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {output_path}")


# ---------------------------------------------------------------------------
# Terminal summary
# ---------------------------------------------------------------------------

def print_summary(devices: list[dict], excluded: list[str], threshold: float) -> None:
    """Print a readable table of results to stdout."""
    print("\n" + "=" * 62)
    print("  DEVICE LOG SUMMARY")
    print("=" * 62)

    if not devices:
        print("  No devices remain after filtering.")
    else:
        header = f"  {'Device':<10} {'Records':>8} {'Avg Temp (°C)':>15} {'Errors':>8}"
        print(header)
        print("  " + "-" * 58)
        for d in devices:
            avg = f"{d['average_temperature']:.2f}" if d["average_temperature"] is not None else "N/A"
            print(
                f"  {d['device_id']:<10} {d['total_records']:>8} {avg:>15} {d['error_count']:>8}"
            )

    print("=" * 62)
    print(f"  Threshold applied : avg_temperature <= {threshold}°C")
    print(f"  Devices included  : {len(devices)}")
    print(f"  Devices excluded  : {len(excluded)} {('(' + ', '.join(excluded) + ')') if excluded else ''}")
    print("=" * 62)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Device Log Summarizer — aggregate device telemetry and export to JSON."
    )
    parser.add_argument(
        "--input",
        default="device_telemetry.csv",
        help="Path to input CSV file (default: device_telemetry.csv)",
    )
    parser.add_argument(
        "--output",
        default="output.json",
        help="Path to output JSON file (default: output.json)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=80.0,
        help="Exclude devices with avg temperature STRICTLY above this value (default: 80.0)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    threshold = args.threshold

    print(f"Reading: {input_path}")

    try:
        raw_rows = load_csv(input_path)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)

    if not raw_rows:
        print("WARNING: CSV file contains no data rows.")
        export_json([], threshold, output_path)
        print_summary([], [], threshold)
        return

    print(f"Processing {len(raw_rows)} row(s)...\n")
    aggregated = aggregate(raw_rows)

    kept, excluded = filter_devices(aggregated, threshold)

    print_summary(kept, excluded, threshold)
    export_json(kept, threshold, output_path)


if __name__ == "__main__":
    main()
