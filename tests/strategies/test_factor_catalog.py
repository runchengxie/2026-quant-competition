import pytest

from strategies.international_lite.factors import FactorDefinition, factor_eligibility


def definition(**overrides: object) -> FactorDefinition:
    values: dict[str, object] = {
        "provider": "quantzone",
        "factor_id": "alpha_momentum",
        "name": "Momentum",
        "formula_version": "v1",
        "asset_scope": "equity",
        "market_scope": "CN",
        "license_status": "confirmed_research_and_publication",
        "validated_markets": ("CN",),
    }
    values.update(overrides)
    return FactorDefinition(**values)  # type: ignore[arg-type]


def test_unverified_formula_market_or_license_fails_closed() -> None:
    item = definition(formula_version="", market_scope="", license_status="unverified")

    eligible, reasons = factor_eligibility(item, market="CN", purpose="research")

    assert not eligible
    assert reasons == ("missing_formula_version", "missing_market_scope", "license_unverified")


@pytest.mark.parametrize("market", ["US", "JP", "HK"])
def test_a_share_factor_is_not_eligible_for_other_markets(market: str) -> None:
    eligible, reasons = factor_eligibility(definition(), market=market, purpose="research")

    assert not eligible
    assert reasons == ("market_scope_mismatch",)


def test_declared_cross_market_scope_requires_market_specific_validation() -> None:
    candidate = definition(market_scope="CN,US")

    eligible, reasons = factor_eligibility(candidate, market="US", purpose="research")

    assert not eligible
    assert reasons == ("market_not_validated",)


def test_delimiter_only_market_scope_is_rejected() -> None:
    candidate = definition(market_scope=" , , ", validated_markets=("US",))

    eligible, reasons = factor_eligibility(candidate, market="US", purpose="research")

    assert not eligible
    assert reasons == ("invalid_market_scope",)


def test_validated_cross_market_definition_is_eligible_for_research() -> None:
    candidate = definition(market_scope="CN,US", validated_markets=("CN", "US"))

    assert factor_eligibility(candidate, market="US", purpose="research") == (True, ())


def test_research_only_license_cannot_be_used_for_public_summary() -> None:
    candidate = definition(license_status="confirmed_research")

    assert factor_eligibility(candidate, market="CN", purpose="research") == (True, ())
    assert factor_eligibility(candidate, market="CN", purpose="public_summary") == (
        False,
        ("publication_rights_unconfirmed",),
    )


def test_unknown_purpose_fails_closed() -> None:
    with pytest.raises(ValueError, match="unknown factor purpose"):
        factor_eligibility(definition(), market="CN", purpose="backtest")  # type: ignore[arg-type]
