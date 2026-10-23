"""A prospective account extends its original trajectory without resetting cash."""

import pytest
from test_ablation_policies import bars


@pytest.mark.parametrize(
    "arm", ["mom20_monthly", "mom20_monthly_buffer20", "ew_monthly"]
)
@pytest.mark.parametrize("fee", [20, 40])
def test_continuous_replay_keeps_prefix(arm, fee):
    from equity_lab.study.controls import replay_observation

    value = bars()
    prefix = dict(
        dates=value["dates"][:260],
        close={p: v[:260] for p, v in value["close"].items()},
    )
    before = replay_observation(
        prefix, arm, score_start=value["dates"][252], fee_bps=fee, quote_currency="USD"
    )
    after = replay_observation(
        value, arm, score_start=value["dates"][252], fee_bps=fee, quote_currency="USD"
    )
    assert after["net"]["periods"][:8] == before["net"]["periods"]
    assert after["gross"]["periods"][:8] == before["gross"]["periods"]
    with pytest.raises(ValueError):
        replay_observation(
            value,
            arm,
            score_start=value["dates"][253],
            fee_bps=fee,
            quote_currency="USD",
        )


def test_installed_observation_cli(tmp_path):
    import json
    import subprocess
    import sys
    from equity_lab.study.inputs import _source_hash

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
                market="US",
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
            "equity_lab.study.observation_cli",
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
    assert len(result["results"]) == 6
    assert all(len(row["output"]["net"]["periods"]) == 8 for row in result["results"])


def test_continuous_account_can_extend_beyond_512_total_score_dates():
    from datetime import date, timedelta
    from equity_lab.study.controls import replay_observation

    value = dict(
        dates=[(date(2023, 1, 1) + timedelta(days=i)).isoformat() for i in range(765)],
        close={"A": [100.0 + i / 10 for i in range(765)]},
    )
    assert (
        len(
            replay_observation(
                value,
                "ew_monthly",
                score_start=value["dates"][252],
                fee_bps=20,
                quote_currency="USD",
            )["net"]["periods"]
        )
        == 513
    )
