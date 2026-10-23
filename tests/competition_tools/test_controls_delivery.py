"""Independent constant-price accounting vectors for installed delivery checks."""

import pytest


def test_controls_reference_keeps_cash_and_fractional_fee_algebra():
    from competition_tools.check_controls_delivery import reference_return

    assert reference_return("US", "mom20_monthly_buffer20", 40) == 0
    assert reference_return("crypto", "trend200_vol40_strict", 25) == 0
    assert reference_return("US", "ew_monthly_buffer20", 20) == pytest.approx(
        1 / 1.002 - 1
    )
    assert reference_return("crypto", "ew_fixed60", 25) == pytest.approx(1 / 1.0015 - 1)
    assert reference_return("crypto", "ew_legacy", 10) == pytest.approx(1 / 1.001 - 1)
