"""Reproduce a normalized performance chart from the public research archive."""

import argparse
import csv
import hashlib
import io
import math
import zipfile
from datetime import date
from pathlib import Path

ARCHIVE_PREFIX = "chi-futu-quant-lab-bundle-20260616_124229/artifacts/reports/backtests/image_cnn_mvp/"
RELEASE_SHA256 = "418ad65ffe059fc723d3f57b4668abc195bb5c63fdab5d6ff02ed7b320fe79a8"
STRATEGIES = ("image_cnn_top5", "sma_cross_same_universe", "momentum_20d_same_universe")


def load_curves(archive_path, *, expected_hash=RELEASE_SHA256):
    """Check source identity, report metrics, common dates, and modeled costs."""
    archive_path = Path(archive_path)
    if hashlib.sha256(archive_path.read_bytes()).hexdigest() != expected_hash:
        raise ValueError("Archive checksum does not match")
    with zipfile.ZipFile(archive_path) as archive:
        def rows(name):
            return list(csv.DictReader(io.StringIO(archive.read(ARCHIVE_PREFIX + name).decode("utf-8-sig"))))

        summaries = {row["strategy"]: row for row in rows("summary.csv")}
        curves = []
        common_dates = None
        initial = None
        for strategy in STRATEGIES:
            daily = rows(strategy + "/portfolio_daily.csv")
            dates = [date.fromisoformat(row["date"]) for row in daily]
            values = [float(row["equity"]) for row in daily]
            if not values or dates != sorted(set(dates)) or any(not math.isfinite(v) or v <= 0 for v in values):
                raise ValueError("Invalid daily equity series")
            if common_dates is not None and dates != common_dates:
                raise ValueError("Strategy dates do not match")
            if initial is not None and not math.isclose(values[0], initial, rel_tol=1e-10):
                raise ValueError("Starting equity does not match")
            common_dates, initial = dates, values[0]
            peak = values[0]
            drawdown = 0.0
            for value in values:
                peak = max(peak, value)
                drawdown = max(drawdown, 1 - value / peak)
            result = values[-1] / values[0] - 1
            summary = summaries[strategy]
            if not math.isclose(result, float(summary["total_return"]), abs_tol=1e-8) or not math.isclose(
                drawdown, -float(summary["max_drawdown"]), abs_tol=1e-8
            ):
                raise ValueError("Daily values do not match summary")
            trades = 0
            for row in rows(strategy + "/positions_daily.csv"):
                turnover, cost = float(row["turnover"]), float(row["cost"])
                if not math.isfinite(turnover) or not math.isfinite(cost) or turnover < 0:
                    raise ValueError("Invalid modeled cost")
                if not math.isclose(cost, turnover * 0.003, abs_tol=1e-10):
                    raise ValueError("Unexpected modeled cost")
                trades += turnover > 0
            if not trades:
                raise ValueError("No recorded turnover")
            curves.append({"strategy": strategy, "dates": dates, "equity": [v / initial * 100 for v in values],
                           "return": result, "drawdown": drawdown})
        return curves


def render_svg(curves):
    """Draw all recorded daily values with a common starting value of 100."""
    width, height = 800, 400
    left, right, top, bottom = 60, 775, 20, 350
    dates = curves[0]["dates"]
    span = max((dates[-1] - dates[0]).days, 1)
    ymax = max(150, math.ceil(max(max(c["equity"]) for c in curves) / 50) * 50)
    ymin = min(0, math.floor(min(min(c["equity"]) for c in curves) / 50) * 50)
    def y(value):
        return bottom - (value - ymin) / (ymax - ymin) * (bottom - top)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">',
             '<rect width="800" height="400" fill="white"/>',
             '<g font-family="system-ui,sans-serif" font-size="14" fill="#334155">']
    for tick in range(int(ymin), int(ymax) + 1, 50):
        py = y(tick)
        parts.append(f'<line x1="{left}" y1="{py:.2f}" x2="{right}" y2="{py:.2f}" stroke="#d8dee9"/>')
        parts.append(f'<text x="{left - 10}" y="{py + 5:.2f}" text-anchor="end">{tick}</text>')
    for year in range(dates[0].year, dates[-1].year + 1, 2):
        day = max(date(year, 1, 1), dates[0])
        x = left + (day - dates[0]).days / span * (right - left)
        parts.append(f'<text x="{x:.2f}" y="380" text-anchor="middle">{year}</text>')
    styles = (("#6d28d9", ""), ("#087f73", ' stroke-dasharray="9 5"'), ("#b45309", ' stroke-dasharray="2 5"'))
    for curve, (color, dash) in zip(curves, styles, strict=True):
        points = " ".join(f'{left + (day - dates[0]).days / span * (right-left):.2f},{y(value):.2f}'
                          for day, value in zip(curve["dates"], curve["equity"], strict=True))
        parts.append(f'<polyline class="curve" fill="none" stroke="{color}" stroke-width="2.5"{dash} points="{points}"/>')
    parts.append("</g></svg>")
    return "\n".join(parts) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(render_svg(load_curves(args.archive)), encoding="utf-8")


if __name__ == "__main__":
    main()
