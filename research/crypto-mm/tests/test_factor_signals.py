from datetime import datetime, timedelta, timezone

import pytest

from crypto_mm.factors.signals import build_signals, forward_returns


def rows(count=220):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    result = []
    for i in range(count):
        result.append(
            dict(
                asset_id="sample",
                time_open=(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                interval_end=(start + timedelta(hours=i + 1)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                open=i + 10,
                high=i + 11,
                low=i + 9,
                close=i + 10,
                volume=10 if i < 192 else 20,
            )
        )
    return result


def test_exact_windows_and_future_invariance():
    values = rows()
    result = build_signals(values, "momentum_24h")
    assert result[23]["value"] is None
    assert result[24]["value"] == pytest.approx(34 / 10 - 1)
    later = [r.copy() for r in values]
    later[-1].update(close=1000, high=1001)
    assert build_signals(later, "momentum_24h")[:-1] == result[:-1]
    assert build_signals(values[:200], "volume_ratio_24h_7d")[-1][
        "value"
    ] == pytest.approx((16 * 10 + 8 * 20) / (168 * 10 / 7))


def test_missing_grid_and_zero_volume_baseline_are_null():
    values = rows()
    del values[100]
    assert build_signals(values, "momentum_168h")[168]["value"] is None
    values = rows()
    for row in values:
        row["volume"] = 0
    assert (
        build_signals(values, "volume_ratio_24h_7d")[-1]["reason"]
        == "ZERO_VOLUME_BASELINE"
    )


def test_confirmation_and_complete_forward_target():
    values = rows()
    signal = build_signals(values, "momentum_volume_24h")
    assert signal[191]["value"] == 0
    assert signal[215]["value"] > 0
    targets = forward_returns(values, 6)
    assert targets[0]["value"] == pytest.approx(16 / 10 - 1)
    assert targets[-6]["value"] is None
    del values[3]
    assert forward_returns(values, 6)[0]["value"] is None


@pytest.mark.parametrize(
    "change",
    [{"close": True}, {"close": 0}, {"volume": float("inf")}, {"open": float("nan")}],
)
def test_invalid_input_numbers_rejected(change):
    values = rows()
    values[0].update(change)
    with pytest.raises(ValueError):
        build_signals(values, "momentum_24h")
