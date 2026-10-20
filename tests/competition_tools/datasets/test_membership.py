import pytest
from competition_tools.datasets.membership import load_membership, eligible
from competition_tools.datasets.providers import readiness


def test_historical_membership_requires_known_availability(tmp_path):
    file = tmp_path / "membership.csv"
    file.write_text(
        "stable_id,symbol,valid_from,valid_to,available_at\nold,A,2020-01-01,2020-12-31,2019-12-31\nnew,B,2021-01-01,,\n"
    )
    records = load_membership(file, status="point_in_time")
    assert [r["symbol"] for r in eligible(records, "2020-06-01", "2020-05-31")] == ["A"]
    assert eligible(records, "2021-06-01", "2021-05-31") == []


def test_overlapping_identity_rejected(tmp_path):
    file = tmp_path / "membership.csv"
    file.write_text(
        "stable_id,symbol,valid_from,valid_to,available_at\na,A,2020-01-01,,2019-01-01\na,A,2021-01-01,,2020-01-01\n"
    )
    with pytest.raises(ValueError):
        load_membership(file, status="point_in_time")


def test_unverified_provider_contract_is_not_acquired():
    value = readiness({"source": "algoseek"})
    assert value["status"] == "blocked"
    assert value["reason"] == "PROVIDER_CONTRACT_UNVERIFIED"
