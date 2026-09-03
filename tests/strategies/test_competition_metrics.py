import pytest

from strategies.international_lite.evaluation import evaluate_competition_metrics


def test_metrics_prioritize_risk_adjusted_and_stable_returns():
    metrics = evaluate_competition_metrics([0.01, 0.01, -0.005, 0.01])
    assert metrics.cumulative_return > 0
    assert metrics.sharpe > 0
    assert 0 < metrics.positive_period_fraction < 1
    assert metrics.max_drawdown > 0


def test_empty_or_invalid_returns_are_rejected():
    with pytest.raises(ValueError):
        evaluate_competition_metrics([])
    with pytest.raises(ValueError):
        evaluate_competition_metrics([float("nan")])
