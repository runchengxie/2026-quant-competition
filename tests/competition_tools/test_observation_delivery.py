"""Installed synthetic delivery remains distinct from real observation."""


def test_delivery_fixture_has_an_explicit_synthetic_clock():
    from competition_tools.check_observation_delivery import synthetic_clock
    from datetime import datetime, timezone

    freeze = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    import pytest

    assert synthetic_clock(freeze) > freeze
    with pytest.raises(ValueError):
        synthetic_clock(datetime(2026, 1, 1))
