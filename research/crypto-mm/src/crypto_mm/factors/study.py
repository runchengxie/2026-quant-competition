"""Fixed retrospective diagnostics with separate temporal and cross-sectional evidence."""

import json
from collections import Counter
from statistics import fmean

from .inputs import external, verify_inputs
from .signals import build_signals, forward_returns, hour
from .metrics import rank_ic, cross_section, selected_hour


def run_factor_study(protocol, output_root):
    inputs = verify_inputs(protocol)
    dataset = protocol["dataset"]
    start = dataset["start"]
    assets = [a["stable_id"] for a in dataset["assets"]]
    temporal, cross = [], []
    for signal_id in protocol["signals"]:
        signals = {
            asset: build_signals(inputs["rows"][asset], signal_id) for asset in assets
        }
        for horizon in protocol["horizons"]:
            targets = {
                asset: forward_returns(inputs["rows"][asset], horizon)
                for asset in assets
            }
            for sampling in protocol["sampling"]:
                by_time = {}
                for asset in assets:
                    pairs = []
                    for feature, target in zip(
                        signals[asset], targets[asset], strict=True
                    ):
                        time = feature["timestamp"]
                        if (
                            feature["value"] is None
                            or target["value"] is None
                            or not selected_hour(time, start, horizon, sampling)
                        ):
                            continue
                        pairs.append((time, feature["value"], target["value"]))
                        by_time.setdefault(time, []).append(
                            (feature["value"], target["value"])
                        )
                    slices = []
                    for index in range(3):
                        subset = [
                            p
                            for p in pairs
                            if index * 720
                            <= (hour(p[0]) - hour(start)).total_seconds() / 3600
                            < (index + 1) * 720
                        ]
                        slices.append(
                            {
                                "index": index,
                                **rank_ic(
                                    [p[1] for p in subset],
                                    [p[2] for p in subset],
                                    minimum=20,
                                ),
                            }
                        )
                    temporal.append(
                        {
                            "asset_id": asset,
                            "signal_id": signal_id,
                            "horizon": horizon,
                            "sampling": sampling,
                            "overall": rank_ic(
                                [p[1] for p in pairs], [p[2] for p in pairs], minimum=30
                            ),
                            "slices": slices,
                        }
                    )
                frames, excluded = [], Counter()
                for values in by_time.values():
                    result = cross_section(
                        [v[0] for v in values], [v[1] for v in values]
                    )
                    if result["reason"]:
                        excluded[result["reason"]] += 1
                    else:
                        frames.append(result)
                reason = (
                    None
                    if frames
                    else "INSUFFICIENT_UNDERLYINGS"
                    if len(assets) < 9
                    else "NO_VALID_GROUPS"
                )
                ic_frames = [r for r in frames if r["rank_ic"] is not None]
                ic_excluded = Counter(
                    r["ic_reason"] for r in frames if r["rank_ic"] is None
                )
                cross.append(
                    {
                        "signal_id": signal_id,
                        "horizon": horizon,
                        "sampling": sampling,
                        "candidate_timestamps": len(by_time),
                        "valid_timestamps": len(frames),
                        "ic_valid_timestamps": len(ic_frames),
                        "ic_excluded_reasons": dict(sorted(ic_excluded.items())),
                        "ic_reason": None if ic_frames else reason or "CONSTANT_TARGET",
                        "mean_rank_ic": fmean(r["rank_ic"] for r in ic_frames)
                        if ic_frames
                        else None,
                        "group_mean_forward_returns": [
                            fmean(r["group_mean_forward_returns"][i] for r in frames)
                            for i in range(3)
                        ]
                        if frames
                        else None,
                        "top_minus_bottom": fmean(r["top_minus_bottom"] for r in frames)
                        if frames
                        else None,
                        "reason": reason,
                        "excluded_reasons": dict(sorted(excluded.items())),
                    }
                )
    after = verify_inputs(protocol)
    if any(
        inputs[k] != after[k]
        for k in ("manifest_sha256", "protocol_sha256", "input_hashes", "code_hashes")
    ):
        raise ValueError("FACTOR_INPUT_HASH_MISMATCH")
    result = {
        "schema": "competition.dex_factor_result.v1",
        "status": "completed",
        "dataset": dataset,
        "source_commit": protocol["source_commit"],
        "protocol_sha256": inputs["protocol_sha256"],
        "manifest_sha256": inputs["manifest_sha256"],
        "input_hashes": inputs["input_hashes"],
        "source_files": protocol["source_files"],
        "role": "retrospective",
        "coverage": [
            {
                "asset_id": a,
                "observed_intervals": len(inputs["rows"][a]),
                "expected_intervals": 2160,
            }
            for a in assets
        ],
        "time_series": temporal,
        "cross_sectional": cross,
        "restrictions": [
            "fixed_current_selection",
            "bar_close_proxy_unverified",
            "gross_descriptive_forward_returns",
            "not_portfolio_pnl",
            "no_cost_or_execution_model",
            "no_out_of_sample_or_significance_claim",
        ],
    }
    body = json.dumps(result, indent=2, allow_nan=False) + "\n"
    output = external(output_root)
    output.mkdir(parents=True, exist_ok=False)
    with (output / "result.json").open("x", encoding="utf-8") as stream:
        stream.write(body)
    return result
