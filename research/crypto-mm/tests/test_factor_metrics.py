import pytest

from crypto_mm.factors.metrics import rank_ic, cross_section, selected_hour


def test_rank_ic_and_insufficient_sample_are_distinct():
    values = list(range(30))
    assert rank_ic(values, values, minimum=30)["value"] == pytest.approx(1)
    assert rank_ic(values, values[::-1], minimum=30)["value"] == pytest.approx(-1)
    assert rank_ic(values[:29], values[:29], minimum=30) == dict(
        value=None, n=29, reason="INSUFFICIENT_OBSERVATIONS"
    )
    assert rank_ic([1] * 30, values, minimum=30)["reason"] == "CONSTANT_SIGNAL"
    assert rank_ic(values, [1] * 30, minimum=30)["reason"] == "CONSTANT_TARGET"
    assert rank_ic([1, 1, 3], [1, 2, 3], minimum=3)["value"] == pytest.approx(
        0.8660254037844386
    )


def test_three_groups_require_nine_and_never_split_ties():
    result = cross_section(list(range(9)), list(range(9)))
    assert result["group_mean_forward_returns"] == [1, 4, 7]
    assert result["top_minus_bottom"] == 6
    assert (
        cross_section(list(range(8)), list(range(8)))["reason"]
        == "INSUFFICIENT_UNDERLYINGS"
    )
    assert (
        cross_section([1] * 5 + [2] * 4, list(range(9)))["reason"]
        == "INSUFFICIENT_GROUP_SIZE"
    )


def test_nonoverlap_uses_utc_offset_not_position():
    start = "2025-01-01T00:00:00Z"
    assert selected_hour("2025-01-01T06:00:00Z", start, 6, "non_overlapping")
    assert not selected_hour("2025-01-01T07:00:00Z", start, 6, "non_overlapping")


@pytest.mark.parametrize("bad", [True, float("inf"), float("nan")])
def test_metrics_reject_invalid_numbers(bad):
    with pytest.raises(ValueError):
        rank_ic([bad], [1], minimum=1)
