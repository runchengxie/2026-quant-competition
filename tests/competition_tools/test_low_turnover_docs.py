"""Published guide numbers must follow the reviewed aggregate in both languages."""

import json
import statistics
from pathlib import Path


def test_bilingual_guides_reconcile_crypto_components_and_holding_medians():
    root = Path(__file__).resolve().parents[2]
    facts = json.loads(
        (root / "site/src/data/low-turnover.v1.json").read_text(encoding="utf-8")
    )
    rows = [
        r
        for r in facts["crypto"]["accounts"]
        if r["arm"] == "trend_weekly" and r["fee_bps"] == 35 and r["delay"] == 0
    ]
    net = statistics.mean(r["net_return"] for r in rows)
    components = sum(
        statistics.mean(r["components"][k] for r in rows)
        for k in ("market", "exposure", "selection", "cost")
    )
    assert abs(components - net) < 1e-10
    for suffix in ("", ".zh-CN"):
        text = (root / f"docs/research/strategy-comparison{suffix}.md").read_text(
            encoding="utf-8"
        )
        assert f"{net * 100:+.4f}%" in text
        for horizon in (5, 20):
            for fee in (20, 40):
                values = [
                    r["metrics"]["net_return"]
                    for r in facts["equity"]["accounts"]
                    if r["horizon"] == horizon
                    and r["fee_bps"] == fee
                    and r["status"] == "completed"
                ]
                expected = f"{statistics.median(values) * 100:+.4f}%".replace("-", "−")
                assert expected in text
