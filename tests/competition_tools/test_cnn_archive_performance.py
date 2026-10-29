import csv
import hashlib
import io
import json
import zipfile

import pytest

from competition_tools.cnn_archive_performance import (
    ARCHIVE_PREFIX,
    STRATEGIES,
    load_curves,
    render_svg,
    render_chart_data,
)


def make_archive(path, *, inconsistent=False, fee=0.003):
    with zipfile.ZipFile(path, "w") as archive:
        summaries = io.StringIO(newline="")
        writer = csv.DictWriter(summaries, ["strategy", "total_return", "max_drawdown"])
        writer.writeheader()
        for index, strategy in enumerate(STRATEGIES):
            end = 110 + index * 10
            writer.writerow({"strategy": strategy, "total_return": (end / 100 - 1) + (0.1 if inconsistent else 0), "max_drawdown": -0.2})
            archive.writestr(ARCHIVE_PREFIX + strategy + "/portfolio_daily.csv", f"date,equity\n2020-01-01,100\n2020-01-02,80\n2020-01-03,{end}\n")
            archive.writestr(ARCHIVE_PREFIX + strategy + "/positions_daily.csv", f"turnover,cost\n0.5,{0.5 * fee}\n")
        archive.writestr(ARCHIVE_PREFIX + "summary.csv", summaries.getvalue())
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_curves_validate_and_render_normalized_equity(tmp_path):
    archive = tmp_path / "input.zip"
    checksum = make_archive(archive)
    curves = load_curves(archive, expected_hash=checksum)
    assert [curve["return"] for curve in curves] == pytest.approx([0.1, 0.2, 0.3])
    assert all(curve["drawdown"] == pytest.approx(0.2) for curve in curves)
    svg = render_svg(curves)
    assert svg.startswith('<svg ')
    assert svg.count('class="curve"') == 3
    assert "2020" in svg
    payload = json.loads(render_chart_data(curves))
    assert payload["dates"] == ["2020-01-01", "2020-01-02", "2020-01-03"]
    assert [row["values"] for row in payload["series"]] == [[100, 80, 110], [100, 80, 120], [100, 80, 130]]
    assert [row["strategy"] for row in payload["series"]] == list(STRATEGIES)


@pytest.mark.parametrize("variant", ["hash", "summary", "fee"])
def test_rejects_unverified_archive_or_inconsistent_results(tmp_path, variant):
    archive = tmp_path / "input.zip"
    checksum = make_archive(archive, inconsistent=variant == "summary", fee=0.004 if variant == "fee" else 0.003)
    with pytest.raises(ValueError):
        load_curves(archive, expected_hash="0" * 64 if variant == "hash" else checksum)
