"""Recovery keeps spent attempts immutable and never trusts partial pairs."""

import hashlib
import pytest

from competition_tools.datasets.daily_recovery import inspect_cached_pairs, BUDGET


def test_partial_pair_is_not_reused(tmp_path):
    resource = dict(
        product="BTCUSDT",
        day="2026-10-01",
        url="https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1d/BTCUSDT-1d-2026-10-01.zip",
    )
    (tmp_path / "BTCUSDT-1d-2026-10-01.zip").write_bytes(b"unverified")
    assert (
        inspect_cached_pairs(
            tmp_path, [resource, resource | {"url": resource["url"] + ".CHECKSUM"}]
        )
        == []
    )
    assert BUDGET == dict(
        attempts=64,
        seconds=300,
        transferred_bytes=4 * 1024**2,
        per_response_bytes=32768,
    )


def test_corrupt_complete_pair_stops_instead_of_redownloading(tmp_path):
    resource = dict(
        product="BTCUSDT",
        day="2026-10-01",
        url="https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1d/BTCUSDT-1d-2026-10-01.zip",
    )
    name = resource["url"].rsplit("/", 1)[-1]
    (tmp_path / name).write_bytes(b"broken")
    (tmp_path / (name + ".CHECKSUM")).write_text(
        hashlib.sha256(b"different").hexdigest() + "  " + name
    )
    with pytest.raises(ValueError, match="CHECKSUM"):
        inspect_cached_pairs(
            tmp_path, [resource, resource | {"url": resource["url"] + ".CHECKSUM"}]
        )


def test_unlisted_response_cannot_enter_recovery_inventory(tmp_path):
    (tmp_path / "unexpected.txt").write_text("unlisted")
    with pytest.raises(ValueError, match="UNLISTED"):
        inspect_cached_pairs(tmp_path, [])


def prepared_recovery(tmp_path):
    from datetime import datetime, timezone
    from test_binance_daily_acquisition import prepared, ArchiveTransport
    from competition_tools.datasets.binance_daily_acquisition import (
        acquire_daily_extension,
    )
    from competition_tools.datasets.daily_recovery import freeze_recovery

    config, plan = prepared(tmp_path)

    class Partial(ArchiveTransport):
        count = 0

        def fetch(self, *args, **kwargs):
            self.count += 1
            if self.count == 5:
                raise TimeoutError("SYNTHETIC_UNKNOWN_SPEND")
            return super().fetch(*args, **kwargs)

    acquire_daily_extension(config, plan, tmp_path / "partial", transport=Partial())
    receipt = tmp_path / "partial/receipt.json"
    old = receipt.read_bytes()
    frozen = freeze_recovery(
        receipt,
        tmp_path / "recovery-plan",
        now=datetime(2025, 1, 3, tzinfo=timezone.utc),
    )
    assert len(frozen["cached"]) == 4
    assert frozen["previous_attempts"] == 5
    assert frozen["previous_spend_uncertain"] is True
    return config, receipt, old


def test_separate_recovery_preserves_old_ledger_and_reuses_only_checked_pairs(tmp_path):
    from test_binance_daily_acquisition import ArchiveTransport
    from competition_tools.datasets.daily_recovery import (
        acquire_recovery,
        inspect_recovery,
    )

    config, receipt, old = prepared_recovery(tmp_path)
    plan = tmp_path / "recovery-plan/plan.json"
    result = acquire_recovery(
        config, plan, tmp_path / "recovered", transport=ArchiveTransport()
    )
    assert result["status"] == "acquired" and result["attempts"] == 12
    assert result["reused_responses"] == 4
    assert result["previous_spend_uncertain"] is True
    assert receipt.read_bytes() == old
    inspected = inspect_recovery(tmp_path / "recovered/manifest.json")
    assert inspected["coverage"]["BTCUSDT"]["end"] == "2025-01-02"
    with pytest.raises(ValueError, match="ALREADY_SPENT"):
        acquire_recovery(config, plan, tmp_path / "other", transport=ArchiveTransport())
    from datetime import datetime, timezone
    from competition_tools.datasets.daily_recovery import freeze_recovery

    freeze_recovery(
        receipt, tmp_path / "refrozen", now=datetime(2025, 1, 4, tzinfo=timezone.utc)
    )
    with pytest.raises(ValueError, match="ALREADY_SPENT"):
        acquire_recovery(
            config,
            tmp_path / "refrozen/plan.json",
            tmp_path / "other",
            transport=ArchiveTransport(),
        )


def test_unknown_recovery_transfer_blocks_without_automatic_retry(tmp_path):
    from competition_tools.datasets.daily_recovery import acquire_recovery

    config, _, _ = prepared_recovery(tmp_path)

    class Unknown:
        count = 0

        def fetch(self, *args, **kwargs):
            self.count += 1
            raise TimeoutError("SYNTHETIC_UNKNOWN_SPEND")

    client = Unknown()
    result = acquire_recovery(
        config,
        tmp_path / "recovery-plan/plan.json",
        tmp_path / "recovered",
        transport=client,
    )
    assert result["status"] == "blocked" and result["spend_uncertain"] is True
    assert client.count == 1 and not (tmp_path / "recovered/manifest.json").exists()


def test_cache_change_after_freeze_is_rejected_before_any_request(tmp_path):
    from test_binance_daily_acquisition import ArchiveTransport
    from competition_tools.datasets.daily_recovery import acquire_recovery

    config, receipt, _ = prepared_recovery(tmp_path)
    file = next((receipt.parent / "raw").glob("*.zip"))
    file.write_bytes(b"changed")
    with pytest.raises(ValueError):
        acquire_recovery(
            config,
            tmp_path / "recovery-plan/plan.json",
            tmp_path / "recovered",
            transport=ArchiveTransport(),
        )
