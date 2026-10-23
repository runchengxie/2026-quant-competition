"""Forward replay preserves the original self-financing account prefix."""

import pytest
from test_daily_ablation import bars


@pytest.mark.parametrize(
    "arm", ["trend200_vol40_strict", "ew_trend_gross_matched", "ew_legacy"]
)
@pytest.mark.parametrize("fee", [0, 10, 25])
def test_continuous_replay_keeps_prefix(arm, fee):
    from crypto_mm.daily.controls import replay_observation

    value = bars()
    prefix = dict(
        dates=value["dates"][:260],
        close={p: v[:260] for p, v in value["close"].items()},
    )
    before = replay_observation(
        prefix, arm, score_start=value["dates"][252], fee_bps=fee, quote_currency="USDT"
    )
    after = replay_observation(
        value, arm, score_start=value["dates"][252], fee_bps=fee, quote_currency="USDT"
    )
    assert after["net"]["periods"][:8] == before["net"]["periods"]
    assert after["gross"]["periods"][:8] == before["gross"]["periods"]
    with pytest.raises(ValueError):
        replay_observation(
            value,
            arm,
            score_start=value["dates"][253],
            fee_bps=fee,
            quote_currency="USDT",
        )


def test_installed_observation_cli(tmp_path):
    import json
    import subprocess
    import sys
    from crypto_mm.daily.study_inputs import _source_hash

    value = bars()
    value = dict(
        dates=value["dates"][:260],
        close={p: v[:260] for p, v in value["close"].items()},
    )
    request = tmp_path / "request.json"
    request.write_text(
        json.dumps(
            dict(
                schema="competition.observation_replay_request.v1",
                protocol_id="a" * 64,
                market="crypto",
                bars=value,
                score_start=value["dates"][252],
                expected_leaf_sha256=_source_hash(),
            )
        )
    )
    output = tmp_path / "result.json"
    child = subprocess.run(
        [
            sys.executable,
            "-m",
            "crypto_mm.daily.observation_cli",
            "--request",
            str(request),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert child.returncode == 0, child.stderr
    result = json.loads(output.read_text())
    assert len(result["results"]) == 9
    assert all(len(row["output"]["net"]["periods"]) == 8 for row in result["results"])


def test_continuous_account_can_extend_beyond_512_total_score_dates():
    from datetime import date, timedelta
    from crypto_mm.daily.controls import replay_observation

    value = dict(
        dates=[(date(2023, 1, 1) + timedelta(days=i)).isoformat() for i in range(765)],
        close={"A": [100.0 + i / 10 for i in range(765)]},
    )
    assert (
        len(
            replay_observation(
                value,
                "ew_legacy",
                score_start=value["dates"][252],
                fee_bps=10,
                quote_currency="USDT",
            )["net"]["periods"]
        )
        == 513
    )
