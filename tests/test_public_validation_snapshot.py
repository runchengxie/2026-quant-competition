"""Contracts for the reviewed, aggregate-only public validation snapshot."""

import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_public_snapshot_has_only_reviewed_aggregate_fields():
    snapshot = json.loads(
        (ROOT / "site/src/data/strategy-validation.json").read_text(encoding="utf-8")
    )
    assert set(snapshot) == {
        "schema_version",
        "as_of",
        "code_revision",
        "providers",
        "results",
        "blocked",
    }
    assert snapshot["schema_version"] == 1
    assert re.fullmatch(r"[a-f0-9]{40}", snapshot["code_revision"])
    assert {p["id"] for p in snapshot["providers"]} == {
        "aivix",
        "index_one",
        "algoseek",
        "coinpaprika",
        "ib_gateway",
    }
    for provider in snapshot["providers"]:
        assert set(provider) == {"id", "status", "history_observations"}
        assert (
            provider["history_observations"] is None
            or provider["history_observations"] >= 0
        )
    ids = [row["id"] for row in snapshot["results"]]
    assert len(ids) == len(set(ids)) == 24
    for row in snapshot["results"]:
        assert set(row) == {
            "id",
            "strategy",
            "market",
            "start",
            "end",
            "observations",
            "universe_count",
            "evidence",
            "cost_bps",
            "metrics",
            "input_fingerprint",
            "config_fingerprint",
        }
        assert row["market"] in {"HK", "US", "CRYPTO", "MULTI"}
        assert row["evidence"] in {
            "limited_universe",
            "no_trades",
            "no_eligible_folds",
            "in_sample_diagnostic",
            "archived_diagnostic",
            "native_currency_proxy",
        }
        assert set(row["metrics"]) == {
            "total_return",
            "sharpe",
            "max_drawdown",
            "total_pnl",
            "fill_count",
            "max_absolute_inventory",
        }
        for value in row["metrics"].values():
            assert value is None or (
                type(value) in {int, float} and math.isfinite(value)
            )
        for field in ("input_fingerprint", "config_fingerprint"):
            assert re.fullmatch(r"[a-f0-9]{64}", row[field])
        if row["evidence"] == "no_eligible_folds":
            assert all(value is None for value in row["metrics"].values())


def test_validation_translations_cover_same_machine_facts():
    en = json.loads((ROOT / "site/src/i18n/en.json").read_text(encoding="utf-8"))[
        "validation"
    ]
    zh = json.loads((ROOT / "site/src/i18n/zh-CN.json").read_text(encoding="utf-8"))[
        "validation"
    ]
    assert set(en) == set(zh)
    for key in ("evidence", "providers", "blocked"):
        assert set(en[key]) == set(zh[key])
