"""Synthetic delivery has no dependency on private exploration files."""

from competition_tools.check_ablation_delivery import synthetic_spec
from competition_tools.evaluation.ablation_catalog import (
    validate_ablation_spec,
    load_origin_evidence,
)


def test_synthetic_delivery_origin_is_self_contained(tmp_path):
    spec = synthetic_spec(tmp_path / "inputs")
    validate_ablation_spec(spec)
    assert load_origin_evidence(spec["origin"])["stage"] == "retrospective"
    assert len(spec["variants"]["US"]) == 11
    assert len(spec["variants"]["crypto"]) == 6
