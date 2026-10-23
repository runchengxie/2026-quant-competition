import copy
import pytest

from competition_tools.datasets.databento_spec import plan, validate_spec, pilot_spec


def test_fixed_pilot_rejects_scope_expansion(tmp_path):
    spec = pilot_spec(tmp_path / "databento.env")
    validate_spec(spec)
    assert plan(spec)["download_parameters"]["limit"] == 4000
    assert plan(spec)["accepted_research"] is False
    for key, value in [
        ("dataset", "EQUS.MINI"),
        ("symbols", ["ALL_SYMBOLS"]),
        ("price_basis", "split_adjusted"),
        ("end", "2027-01-01"),
    ]:
        altered = copy.deepcopy(spec)
        altered[key] = value
        with pytest.raises(ValueError):
            validate_spec(altered)
    spec["unexpected"] = True
    with pytest.raises(ValueError):
        validate_spec(spec)


def test_plan_is_offline_without_a_credential_file(tmp_path):
    result = plan(pilot_spec(tmp_path / "missing.env"))
    assert result["source"] == "databento"
    assert result["price_basis"] == "raw"
