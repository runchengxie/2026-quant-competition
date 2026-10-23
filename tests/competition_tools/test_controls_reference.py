"""Independent piecewise fee algebra must not reuse leaf accounting."""

import pytest


def test_piecewise_post_fee_cash_has_known_buy_and_rebalance_solutions():
    from competition_tools.check_controls_reference import post_fee_nav

    assert post_fee_nav(1.0, [0.0, 0.0], 0.002) == pytest.approx(1 / 1.002)
    assert post_fee_nav(1.0, [0.8, 0.2], 0.01) == pytest.approx(0.994)
    assert post_fee_nav(1.0, [0.8, 0.2], 0.0) == 1.0
    with pytest.raises(ValueError):
        post_fee_nav(1.0, [-0.1, 0.2], 0.01)
