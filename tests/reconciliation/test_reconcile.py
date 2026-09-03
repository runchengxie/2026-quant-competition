from packages.reconciliation import reconcile_orders


def test_submit_without_terminal_event_is_unknown():
    report = reconcile_orders(
        [{"event_id": "1", "kind": "order_submitted", "order_id": "o1"}],
        broker_orders=[],
    )
    assert report.unknown_order_ids == ("o1",)
    assert report.missing_broker_order_ids == ("o1",)


def test_reconnect_report_finds_missing_and_unjournaled_broker_orders():
    report = reconcile_orders(
        [{"event_id": "1", "kind": "order_submitted", "order_id": "o1"}],
        broker_orders=[{"order_id": "o2", "status": "Submitted"}],
    )
    assert report.missing_broker_order_ids == ("o1",)
    assert report.unjournaled_broker_order_ids == ("o2",)
