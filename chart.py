"""
Device Log Summarizer — Chart Generator (Section 3)
=====================================================
Reads output.json produced by main.py and generates a bar chart of
average temperature per device, saved as temperature_chart.png.

AI-assisted initial version — see PROMPT_LOG.md for review notes.
"""

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt


def load_json(filepath: Path) -> dict:
    """Load and parse the JSON file. Raises on missing or malformed file."""
    if not filepath.exists():
        raise FileNotFoundError(f"Input JSON not found: {filepath}")
    with filepath.open(encoding="utf-8") as fh:
        return json.load(fh)


def extract_chart_data(data: dict) -> tuple[list[str], list[float]]:
    """
    Extract device IDs and average temperatures from the JSON payload.
    Devices with null average temperatures are excluded from the chart
    (no misleading bar for unavailable data).
    """
    devices = data.get("devices", [])
    labels = []
    values = []
    for d in devices:
        avg = d.get("average_temperature")
        if avg is not None:
            labels.append(d["device_id"])
            values.append(avg)
    return labels, values


def generate_chart(labels: list[str], values: list[float], output_path: Path) -> None:
    """
    Build and save the bar chart.
    NOTE (initial version): x-axis labels are not rotated, which can cause
    overlap when many devices are present. See PROMPT_LOG.md for the fix.
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    bars = ax.bar(labels, values, color="steelblue", edgecolor="black", width=0.5)

    ax.set_title("Average Temperature per Device", fontsize=14, fontweight="bold")
    ax.set_xlabel("Device ID", fontsize=12)
    ax.set_ylabel("Average Temperature (°C)", fontsize=12)

    # Add value labels on top of each bar
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.5,
            f"{val:.1f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    ax.yaxis.grid(True, linestyle="--", alpha=0.7)
    ax.set_axisbelow(True)

    # FIX (after follow-up prompt): rotate labels 45° so they don't overlap.
    # This was absent in the initial version, causing label overlap with 5+ devices.
    plt.xticks(rotation=45, ha="right")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"Chart saved to: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate average-temperature bar chart from device log JSON."
    )
    parser.add_argument(
        "--input",
        default="output.json",
        help="Path to JSON file produced by main.py (default: output.json)",
    )
    parser.add_argument(
        "--output",
        default="temperature_chart.png",
        help="Path for the output chart image (default: temperature_chart.png)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    try:
        data = load_json(input_path)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"ERROR: Malformed JSON — {exc}", file=sys.stderr)
        sys.exit(2)

    labels, values = extract_chart_data(data)

    if not labels:
        print("WARNING: No devices with valid average temperatures found. Chart not generated.")
        sys.exit(0)

    generate_chart(labels, values, output_path)


if __name__ == "__main__":
    main()
