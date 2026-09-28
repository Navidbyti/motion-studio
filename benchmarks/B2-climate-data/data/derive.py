"""Derive the B2 chart tables and answer key from the frozen raw snapshots.

Uses only the files in data/raw/. Never refetch the sources during a
benchmark run: the upstream files are revised monthly and later numbers
would not be comparable with earlier runs.

    python benchmarks/B2-climate-data/data/derive.py

Rounding: decimal arithmetic, ROUND_HALF_UP, to the precision stated per
column. Temperature values are GISTEMP v4 annual (J-D) land-ocean
anomalies in degrees Celsius relative to the 1951-1980 mean.
"""

from __future__ import annotations

import csv
import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
DERIVED = HERE / "derived"
TEMP_FILE = RAW / "GLB.Ts+dSST.csv"
CO2_FILE = RAW / "co2_annmean_mlo.csv"


def q(value: Decimal, places: str) -> str:
    return str(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_temperature() -> dict[int, tuple[Decimal, int]]:
    """Return {year: (anomaly, csv line number)} for complete years only."""
    out: dict[int, tuple[Decimal, int]] = {}
    with TEMP_FILE.open(newline="", encoding="utf-8") as fh:
        for line_no, row in enumerate(csv.reader(fh), start=1):
            if not row or not row[0].isdigit():
                continue
            if row[13] != "***":
                out[int(row[0])] = (Decimal(row[13]), line_no)
    return out


def load_co2() -> dict[int, tuple[Decimal, int]]:
    out: dict[int, tuple[Decimal, int]] = {}
    with CO2_FILE.open(newline="", encoding="utf-8") as fh:
        for line_no, row in enumerate(csv.reader(fh), start=1):
            if row and row[0].isdigit():
                out[int(row[0])] = (Decimal(row[1]), line_no)
    return out


def write_csv(name: str, header: list[str], rows: list[list[object]]) -> None:
    DERIVED.mkdir(exist_ok=True)
    with (DERIVED / name).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def main() -> None:
    temp = load_temperature()
    co2 = load_co2()

    write_csv("co2_ppm_annual.csv", ["year", "co2_ppm"], [[y, str(v)] for y, (v, _) in sorted(co2.items())])
    write_csv(
        "temp_anomaly_c_annual.csv",
        ["year", "anomaly_c"],
        [[y, str(v)] for y, (v, _) in sorted(temp.items()) if y >= 1880],
    )

    decades = []
    for start in range(1960, 2030, 10):
        years = [y for y in range(start, start + 10) if y in temp]
        mean = sum(temp[y][0] for y in years) / Decimal(len(years))
        label = f"{start}s" if len(years) == 10 else f"{start}-{years[-1]}"
        decades.append({"label": label, "first_year": years[0], "last_year": years[-1],
                        "years": len(years), "mean_exact": str(mean), "mean_c": q(mean, "0.01")})
    write_csv("temp_decade_means_c.csv", ["label", "first_year", "last_year", "years", "mean_c"],
              [[d["label"], d["first_year"], d["last_year"], d["years"], d["mean_c"]] for d in decades])

    ranked = sorted(temp, key=lambda y: (-temp[y][0], y))[:5]
    write_csv("warmest_years_top5.csv", ["rank", "year", "anomaly_c"],
              [[i + 1, y, str(temp[y][0])] for i, y in enumerate(ranked)])

    co2_1960, co2_2025 = co2[1960][0], co2[2025][0]
    first_350 = min(y for y in co2 if co2[y][0] >= 350)
    first_400 = min(y for y in co2 if co2[y][0] >= 400)
    key = {
        "suite": "benchmarks v1",
        "rounding": "Decimal ROUND_HALF_UP",
        "sources": {
            "temperature": {"file": "raw/GLB.Ts+dSST.csv", "sha256": sha256(TEMP_FILE)},
            "co2": {"file": "raw/co2_annmean_mlo.csv", "sha256": sha256(CO2_FILE)},
        },
        "values": {
            "co2_1960_ppm": {"value": str(co2_1960), "source": "co2", "line": co2[1960][1]},
            "co2_2025_ppm": {"value": str(co2_2025), "source": "co2", "line": co2[2025][1]},
            "co2_change_1960_2025_ppm": {"value": q(co2_2025 - co2_1960, "0.01"), "source": "co2", "derived": "2025 minus 1960"},
            "co2_change_1960_2025_pct": {"value": q((co2_2025 / co2_1960 - 1) * 100, "0.1"), "source": "co2", "derived": "(2025 / 1960 - 1) x 100"},
            "co2_first_year_at_or_above_350": {"value": first_350, "ppm": str(co2[first_350][0]), "source": "co2", "line": co2[first_350][1]},
            "co2_first_year_at_or_above_400": {"value": first_400, "ppm": str(co2[first_400][0]), "source": "co2", "line": co2[first_400][1]},
            "temp_1960_c": {"value": str(temp[1960][0]), "source": "temperature", "line": temp[1960][1]},
            "temp_2025_c": {"value": str(temp[2025][0]), "source": "temperature", "line": temp[2025][1]},
            "temp_decade_means_c": decades,
            "warmest_years_top3": [{"rank": i + 1, "year": y, "anomaly_c": str(temp[y][0]), "line": temp[y][1]}
                                   for i, y in enumerate(ranked[:3])],
            "temp_record_first_year": min(temp),
            "temp_record_last_complete_year": max(temp),
            "temp_baseline": "1951-1980 mean",
        },
    }
    (HERE / "expected-values.json").write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(key["values"], indent=2))


if __name__ == "__main__":
    main()
