import pytest

from apps.execution_runner.safety import KillSwitch


def test_kill_switch_blocks_when_marker_exists(tmp_path):
    switch = KillSwitch(tmp_path / "STOP")
    switch.assert_clear()
    switch.trigger("manual stop")
    assert switch.is_triggered
    with pytest.raises(RuntimeError, match="kill switch"):
        switch.assert_clear()
