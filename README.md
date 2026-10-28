# Device Log Summarizer CLI

A Python command-line tool that reads device telemetry data from a CSV file,
aggregates statistics per device, filters by a configurable temperature
threshold, exports results to JSON, and generates a Matplotlib bar chart.

Built as a Software Engineering Intern technical assessment for **TestRight Nanosystems**.

---

## Features

- Reads device telemetry from a CSV file (`device_id`, `status`, `temperature`).
- Sanitises and validates sensor readings (Section 1 — independently written).
- Aggregates per-device: total records, average temperature, ERROR count.
- Filters out devices whose average temperature exceeds a configurable threshold (default 80 °C).
- Exports clean, readable JSON output.
- Generates a legible Matplotlib bar chart.
- Handles missing files, malformed rows, empty data, and invalid temperatures gracefully.
- Full `unittest` test suite for all sections.

---

## Python Version

**Python 3.10+** required (uses `list[str]` type hints).  
Tested on Python 3.14.2.

---

## Project Structure

```
device-log-summarizer/
├── main.py                  # Section 2 — CSV processing, aggregation, JSON export
├── sanitizer.py             # Section 1 — sensor data sanitizer (candidate-written)
├── chart.py                 # Section 3 — Matplotlib bar chart generator
├── device_telemetry.csv     # Sample input data
├── output.json              # Generated JSON output (created by main.py)
├── temperature_chart.png    # Generated chart (created by chart.py)
├── sample_output.txt        # Captured terminal output from an actual run
├── PROMPT_LOG.md            # Honest AI-usage log for Section 3
├── README.md                # This file
├── requirements.txt         # External dependencies
├── .gitignore               # Python / venv ignores
└── tests/
    ├── __init__.py
    ├── test_sanitizer.py        # Tests for Section 1
    └── test_main_and_chart.py  # Tests for Sections 2 and 3
```

---

## Installation

```bash
# Clone the repository
git clone https://github.com/Sahil-Singhhh/device-log-summarizer.git
cd device-log-summarizer

# (Recommended) create a virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # macOS / Linux

# Install dependencies
pip install -r requirements.txt
```

---

## Input CSV Format

Expected filename: `device_telemetry.csv`

| Column | Description |
|---|---|
| `device_id` | Unique device identifier (non-empty string) |
| `status` | Operating status — e.g. `ACTIVE`, `WARNING`, `ERROR` (case-insensitive) |
| `temperature` | Numeric temperature reading in °C (invalid values are skipped) |

Example:

```csv
device_id,status,temperature
DEV_A,ACTIVE,35.5
DEV_A,ERROR,48.5
DEV_B,ACTIVE,76.0
DEV_B,ERROR,85.0
```

---

## Running the CLI

### Process CSV and export JSON

```bash
# Using defaults (input: device_telemetry.csv, output: output.json, threshold: 80.0)
python main.py

# Custom paths and threshold
python main.py --input device_telemetry.csv --output output.json --threshold 80
```

### Generate the chart

```bash
# Using defaults (input: output.json, output: temperature_chart.png)
python chart.py

# Custom paths
python chart.py --input output.json --output temperature_chart.png
```

---

## Output JSON Format

```json
{
  "filter_threshold": 80.0,
  "devices": [
    {
      "device_id": "DEV_A",
      "total_records": 3,
      "average_temperature": 42.0,
      "error_count": 1
    }
  ]
}
```

- `filter_threshold`: The temperature threshold used to exclude devices.
- `devices`: Array of devices whose average temperature is ≤ threshold, sorted by `device_id`.
- `total_records`: Count of rows with **valid** `device_id` **and** valid `temperature`.
- `average_temperature`: Mean of valid temperature readings. `null` if no valid temperatures exist.
- `error_count`: Count of included records whose status normalises to `ERROR`.

---

## Aggregation and Filtering Rules

1. **Valid record**: must have a non-empty `device_id` **and** a valid numeric temperature.
2. **Invalid temperatures** (empty, non-numeric, negative after sanitisation): skipped with a warning; do not affect the device average.
3. **ERROR counting**: only counted among valid-temperature records; case-insensitive.
4. **Filter threshold**: devices with `average_temperature > threshold` are excluded. Devices with `null` average are also excluded. Devices with `average_temperature == threshold` are **retained**.
5. **Excluded devices** are reported in the terminal but not written to `output.json`.

---

## Running Tests

```bash
# Run all tests from the project root
python -m unittest discover -s tests -v
```

Tests cover:
- Missing / empty / malformed CSV files.
- Device grouping, record counts, average calculation, ERROR counts.
- The 80 °C threshold boundary (> excluded, == retained, < retained).
- Invalid temperature handling.
- JSON export and reload.
- Chart data extraction (null averages excluded).
- Chart file creation.
- Missing / malformed JSON for chart.

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Input CSV not found | Prints error, exits with code 1 |
| CSV missing required column | Prints error, exits with code 2 |
| Empty CSV (header only) | Processes zero rows, writes empty JSON |
| Malformed row / missing field | Skips row, prints warning, continues |
| Invalid temperature | Skips temperature, prints warning, continues |
| Empty `device_id` | Skips entire row, prints warning |
| JSON not found (chart) | Prints error, exits with code 1 |
| Malformed JSON (chart) | Prints error, exits with code 2 |
| Empty device list (chart) | Prints warning, exits cleanly without crashing |

---

## AI Usage

- **Section 1** (`sanitize_readings` in `sanitizer.py`): written **independently** by the candidate without AI assistance.
- **Section 2** (`main.py`): AI-assisted implementation (Antigravity / Gemini).
- **Section 3** (`chart.py`): AI-assisted implementation with a real formatting bug observed and corrected. See [`PROMPT_LOG.md`](PROMPT_LOG.md) for the full interaction record.

---

## Known Limitations

- Chart uses a single colour for all bars; colour-per-device differentiation would improve readability for large datasets.
- `statistics.mean()` is used for averaging; for very large datasets a streaming approach may be preferable.
- The tool processes only CSV files; JSON or database inputs are not supported.
- If all devices are filtered out, `output.json` contains an empty `devices` array and the chart is not generated.
