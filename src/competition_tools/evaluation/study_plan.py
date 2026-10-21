"""Freeze fixed assumptions and immutable daily input identities before runs."""

import json
import re
from pathlib import Path

from competition_tools.team.paths import validate_external
from competition_tools.datasets.storage import write_json
from .study_inputs import load_study_input
from .study_identity import canonical_hash, tree_hash

COSTS = {"US": [20, 40], "HK": [30, 60], "crypto": [0, 10, 25]}
STRATEGIES = {
    "US": [
        "buy_hold",
        "equal_weight",
        "momentum_20d",
        "sma_cross",
        "benchmark_buy_hold",
    ],
    "HK": [
        "buy_hold",
        "equal_weight",
        "momentum_20d",
        "sma_cross",
        "benchmark_buy_hold",
    ],
    "crypto": ["equal_weight", "momentum_63d", "trend_200d"],
}
PARAMETERS = {
    "buy_hold": {},
    "equal_weight": {},
    "benchmark_buy_hold": {},
    "momentum_20d": {"lookback_days": 20, "min_momentum": 0},
    "sma_cross": {"short_window": 20, "long_window": 60},
    "momentum_63d": {"lookback_days": 63},
    "trend_200d": {"long_window": 200},
}


def plan_hash(plan):
    value = {k: v for k, v in plan.items() if k != "plan_sha256"}
    value["jobs"] = [
        {k: v for k, v in job.items() if k != "plan_sha256"} for job in plan["jobs"]
    ]
    return canonical_hash(value)


def validate_job(job: dict) -> None:
    try:
        if (
            not isinstance(job, dict)
            or not re.fullmatch(r"[a-f0-9]{64}", job["job_id"])
            or job["market"] not in {*COSTS, "unknown"}
            or job["accepted_research"] is not False
            or job["status"] not in {"planned", "blocked"}
        ):
            raise ValueError
        if job["status"] == "blocked":
            if job["reason"] not in {
                "INSUFFICIENT_HISTORY",
                "MARKET_INPUT_UNAVAILABLE",
                "INVALID_STUDY_INPUT",
            }:
                raise ValueError
            return
        market = job["market"]
        if (
            market not in COSTS
            or job["project"] != ("crypto-mm" if market == "crypto" else "equity-lab")
            or job["strategy"] not in STRATEGIES[market]
            or type(job["fee_bps"]) is not int
            or job["fee_bps"] not in COSTS[market]
            or job["parameters"] != PARAMETERS[job["strategy"]]
        ):
            raise ValueError
        if job["quote_currency"] != {"US": "USD", "HK": "HKD", "crypto": "USDT"}[
            market
        ] or not re.fullmatch(r"[a-f0-9]{64}", job["expected_leaf_sha256"]):
            raise ValueError
        fold, dates = job["fold"], job["dates"]
        score = 90 if market == "crypto" else 63
        if (
            fold["warmup_periods"] != 252
            or fold["scoring_periods"] != score
            or len(dates) != 252 + score
            or dates != sorted(set(dates))
            or (fold["warmup_start"], fold["start"], fold["end"])
            != (dates[0], dates[252], dates[-1])
        ):
            raise ValueError
        if (
            job["accounting_model"] != "self_financing_daily.v1"
            or job["execution_assumption"] != "lagged_close_proxy"
            or job["independent_fold_start"] is not True
            or job["signal_lag_periods"] != 1
        ):
            raise ValueError
    except (KeyError, ValueError, TypeError, IndexError):
        raise ValueError("INVALID_FROZEN_PLAN") from None


def freeze_study(spec: dict, output_root: Path, *, code_identity: dict) -> dict:
    if (
        not isinstance(spec, dict)
        or set(spec) != {"schema", "manifests", "costs"}
        or spec["schema"] != "competition.evaluation_spec.v2"
        or spec["costs"] != COSTS
        or any(type(n) is not int for values in spec["costs"].values() for n in values)
        or not isinstance(spec["manifests"], list)
        or not 1 <= len(spec["manifests"]) <= 3
        or not all(isinstance(p, str) for p in spec["manifests"])
        or len(set(spec["manifests"])) != len(spec["manifests"])
    ):
        raise ValueError("INVALID_STUDY_SPEC")
    if (
        not isinstance(code_identity, dict)
        or set(code_identity) != {"commit", "source_root", "source_sha256"}
        or not re.fullmatch(r"[a-f0-9]{40}", code_identity["commit"])
        or not re.fullmatch(r"[a-f0-9]{64}", code_identity["source_sha256"])
        or not Path(code_identity["source_root"]).is_absolute()
    ):
        raise ValueError("INVALID_CODE_IDENTITY")
    output_root = validate_external(output_root)
    if output_root.exists():
        raise FileExistsError("STUDY_OUTPUT_EXISTS")
    jobs, inputs, seen = [], [], set()

    def blocked(market, reason):
        jobs.append(
            {
                "job_id": canonical_hash([market, reason]),
                "market": market,
                "status": "blocked",
                "reason": reason,
                "accepted_research": False,
            }
        )

    for name in spec["manifests"]:
        try:
            data = load_study_input(Path(name))
        except (ValueError, OSError, KeyError, TypeError):
            market = "unknown"
            try:
                candidate = json.loads(Path(name).read_text(encoding="utf-8"))["spec"][
                    "market"
                ]
                if candidate in COSTS:
                    market = candidate
            except (ValueError, OSError, KeyError, TypeError):
                pass
            blocked(market, "INVALID_STUDY_INPUT")
            seen.add(market)
            continue
        market = data["market"]
        if market in seen:
            raise ValueError("DUPLICATE_MARKET")
        seen.add(market)
        inputs.append(data)
        dates = data["dates"]
        score = 90 if market == "crypto" else 63
        if len(dates) < 252 + score:
            blocked(market, "INSUFFICIENT_HISTORY")
            continue
        project = "crypto-mm" if market == "crypto" else "equity-lab"
        leaf_hash = tree_hash(
            Path(code_identity["source_root"]) / "research" / project / "src"
        )
        for first in range(252, len(dates) - score + 1, score):
            fold = {
                "warmup_start": dates[first - 252],
                "start": dates[first],
                "end": dates[first + score - 1],
                "warmup_periods": 252,
                "scoring_periods": score,
            }
            for strategy in STRATEGIES[market]:
                for fee in COSTS[market]:
                    job = {
                        "schema": "competition.daily_study_job.v1",
                        "market": market,
                        "project": project,
                        "status": "planned",
                        "manifest": data["manifest"],
                        "manifest_sha256": data["manifest_sha256"],
                        "input_files": data["input_files"],
                        "input_slice": data["slice"],
                        "products": [data["benchmark"]]
                        if strategy == "benchmark_buy_hold"
                        else data["products"],
                        "benchmark": data["benchmark"],
                        "quote_currency": data["quote_currency"],
                        "strategy": strategy,
                        "parameters": PARAMETERS[strategy],
                        "fee_bps": fee,
                        "fold": fold,
                        "dates": dates[first - 252 : first + score],
                        "accounting_model": "self_financing_daily.v1",
                        "execution_assumption": "lagged_close_proxy",
                        "independent_fold_start": True,
                        "max_positions": 10 if market != "crypto" else 20,
                        "max_gross_exposure": 1,
                        "signal_lag_periods": 1,
                        "expected_leaf_sha256": leaf_hash,
                        "accepted_research": False,
                    }
                    job["job_id"] = canonical_hash(
                        {
                            k: job[k]
                            for k in (
                                "market",
                                "manifest_sha256",
                                "strategy",
                                "fold",
                                "fee_bps",
                            )
                        }
                    )
                    job["code_commit"] = code_identity["commit"]
                    jobs.append(job)
    for market in COSTS.keys() - seen:
        blocked(market, "MARKET_INPUT_UNAVAILABLE")
    jobs.sort(key=lambda j: j["job_id"])
    if len(jobs) > 384 or len({j["job_id"] for j in jobs}) != len(jobs):
        raise ValueError("STUDY_JOB_BUDGET_OR_DUPLICATE")
    plan = {
        "schema": "competition.study_plan.v1",
        "code_identity": code_identity,
        "costs": COSTS,
        "inputs": inputs,
        "jobs": jobs,
        "retrospective": True,
        "selection": "fixed_current_from_2023",
        "budget": {"jobs": 384, "seconds": 3600},
        "accepted_research": False,
    }
    plan["plan_sha256"] = plan_hash(plan)
    for job in jobs:
        job["plan_sha256"] = plan["plan_sha256"]
    output_root.mkdir(parents=True, exist_ok=False)
    (output_root / "jobs").mkdir()
    for job in jobs:
        write_json(output_root / "jobs" / (job["job_id"] + ".json"), job)
    write_json(output_root / "plan.json", plan)
    return plan
