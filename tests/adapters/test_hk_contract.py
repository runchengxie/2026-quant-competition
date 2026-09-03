from adapters.ibkr.events import contract_for_symbol


def test_hong_kong_symbol_maps_to_sehk_contract():
    contract = contract_for_symbol("0700.HK")

    assert contract.symbol == "0700"
    assert contract.exchange == "SMART"
    assert contract.primaryExchange == "SEHK"
    assert contract.currency == "HKD"
