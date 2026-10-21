"""Independent frozen-job input checks and private study artifact writing."""

import csv
import hashlib
import json
import math
import re
from datetime import date
from pathlib import Path, PurePosixPath

from .study import evaluate_study

PROJECT = "crypto-mm"
MARKETS = {"crypto"}
PARAMETERS = {
    "buy_hold": {},
    "benchmark_buy_hold": {},
    "equal_weight": {},
    "momentum_20d": {"lookback_days": 20, "min_momentum": 0},
    "sma_cross": {"short_window": 20, "long_window": 60},
    "momentum_63d": {"lookback_days": 63},
    "trend_200d": {"long_window": 200},
}
JOB_KEYS = set(
    "schema market project status manifest manifest_sha256 input_files input_slice products benchmark quote_currency strategy parameters fee_bps fold dates accounting_model execution_assumption independent_fold_start max_positions max_gross_exposure signal_lag_periods expected_leaf_sha256 accepted_research job_id code_commit plan_sha256".split()
)


def _hash(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _external(path):
    path = Path(path).expanduser()
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("INVALID_EXTERNAL_PATH")
    for part in (path, *path.parents):
        if (
            part.is_symlink()
            or (hasattr(part, "is_junction") and part.is_junction())
            or (part / ".git").exists()
            or part.name == ".git"
        ):
            raise ValueError("INVALID_EXTERNAL_PATH")
    return path.resolve()


def _source_hash():
    root = Path(__file__).resolve().parents[2]
    paths = sorted(root.rglob("*.py"))
    if any(p.is_symlink() for p in paths):
        raise ValueError("INVALID_SOURCE_PATH")
    return _hash([(p.relative_to(root).as_posix(), _digest(p)) for p in paths])


def _validate_job(job):
    try:
        if (
            not isinstance(job, dict)
            or set(job) != JOB_KEYS
            or job["schema"] != "competition.daily_study_job.v1"
            or job["project"] != PROJECT
            or job["market"] not in MARKETS
            or job["status"] != "planned"
            or job["accepted_research"] is not False
        ):
            raise ValueError
        crypto = job["market"] == "crypto"
        strategies = (
            {"equal_weight", "momentum_63d", "trend_200d"}
            if crypto
            else {
                "buy_hold",
                "benchmark_buy_hold",
                "equal_weight",
                "momentum_20d",
                "sma_cross",
            }
        )
        if (
            job["strategy"] not in strategies
            or job["parameters"] != PARAMETERS[job["strategy"]]
            or type(job["fee_bps"]) is not int
            or job["fee_bps"]
            not in {"US": [20, 40], "HK": [30, 60], "crypto": [0, 10, 25]}[
                job["market"]
            ]
        ):
            raise ValueError
        if any(
            not isinstance(job[k], str) or not re.fullmatch(r"[a-f0-9]{64}", job[k])
            for k in (
                "job_id",
                "plan_sha256",
                "manifest_sha256",
                "expected_leaf_sha256",
            )
        ) or not re.fullmatch(r"[a-f0-9]{40}", job["code_commit"]):
            raise ValueError
        if job["job_id"] != _hash(
            {
                k: job[k]
                for k in ("market", "manifest_sha256", "strategy", "fold", "fee_bps")
            }
        ):
            raise ValueError
        if (
            job["quote_currency"]
            != {"US": "USD", "HK": "HKD", "crypto": "USDT"}[job["market"]]
            or job["accounting_model"] != "self_financing_daily.v1"
            or job["execution_assumption"] != "lagged_close_proxy"
            or job["signal_lag_periods"] != 1
            or job["independent_fold_start"] is not True
            or job["max_gross_exposure"] != 1
            or job["max_positions"] != (20 if crypto else 10)
        ):
            raise ValueError
        dates, fold = job["dates"], job["fold"]
        score = 90 if crypto else 63
        if (
            len(dates) != 252 + score
            or dates != sorted(set(dates))
            or fold
            != {
                "warmup_start": dates[0],
                "start": dates[252],
                "end": dates[-1],
                "warmup_periods": 252,
                "scoring_periods": score,
            }
            or any(date.fromisoformat(d).isoformat() != d for d in dates)
        ):
            raise ValueError
        products = job["products"]
        if (
            not isinstance(products, list)
            or not 1 <= len(products) <= 20
            or len(set(products)) != len(products)
            or any(
                not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", p) for p in products
            )
        ):
            raise ValueError
        if crypto and any(
            (date.fromisoformat(b) - date.fromisoformat(a)).days != 1
            for a, b in zip(dates, dates[1:])
        ):
            raise ValueError
    except (ValueError, TypeError, KeyError, IndexError):
        raise ValueError("INVALID_STUDY_JOB") from None


def _load_prices(job):
    path = _external(job["manifest"])
    if _digest(path) != job["manifest_sha256"]:
        raise ValueError("DATASET_HASH_MISMATCH")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    spec = manifest["spec"]
    crypto = job["market"] == "crypto"
    expected = (
        ("binance_spot", "365", "UTC", "raw")
        if crypto
        else (
            "ibkr_daily",
            "XNYS" if job["market"] == "US" else "XHKG",
            "America/New_York" if job["market"] == "US" else "Asia/Hong_Kong",
            "split_adjusted",
        )
    )
    if (
        manifest["schema"]
        != (
            "competition.dataset_manifest.v1"
            if crypto
            else "competition.dataset_manifest.v2"
        )
        or tuple(spec[k] for k in ("source", "calendar", "timezone", "price_basis"))
        != expected
        or spec["market"] != job["market"]
        or spec["quote_currency"] != job["quote_currency"]
        or spec["universe_status"] != "fixed_current"
        or manifest["status"]
        not in ({"partial", "acquired"} if crypto else {"acquired"})
    ):
        raise ValueError("INCOMPATIBLE_STUDY_MANIFEST")
    owner = _external(path.parent / ".dataset-owner").read_text()
    if owner != ("competition.dataset.v1" if crypto else "competition.dataset.v2"):
        raise ValueError("UNOWNED_STUDY_INPUT")
    slice_receipt = job["input_slice"]
    if (
        slice_receipt["schema"] != "competition.study_input_slice.v1"
        or slice_receipt["parent_sha256"] != job["manifest_sha256"]
        or slice_receipt["parent_status"] != manifest["status"]
        or slice_receipt["products"] != spec["products"]
        or slice_receipt["accepted_research"] is not False
        or not slice_receipt["start"]
        <= job["dates"][0]
        <= job["dates"][-1]
        <= slice_receipt["end"]
    ):
        raise ValueError("INVALID_STUDY_SLICE")
    known = {r["path"]: r for r in manifest["files"]}
    records = {}
    for record in job["input_files"]:
        relative = PurePosixPath(record["path"])
        if (
            len(relative.parts) != 2
            or relative.parts[0] != "normalized"
            or ".." in relative.parts
            or "\\" in record["path"]
            or ":" in record["path"]
            or known.get(record["path"]) != record
            or record["path"] in records
        ):
            raise ValueError("INVALID_STUDY_INPUT_PATH")
        target = _external(path.parent / relative)
        if (
            target.stat().st_size != record["bytes"]
            or _digest(target) != record["sha256"]
        ):
            raise ValueError("DATASET_HASH_MISMATCH")
        records[relative.as_posix()] = target
    if not crypto:
        schedule = manifest["receipt"]["calendar"]["sessions"]
        if [d for d in schedule if job["dates"][0] <= d <= job["dates"][-1]] != job[
            "dates"
        ] or spec["benchmark"] != job["benchmark"]:
            raise ValueError("INVALID_STUDY_GRID")
    elif job["benchmark"] != "equal_weight":
        raise ValueError("INVALID_STUDY_BENCHMARK")
    permitted = set(spec["products"]) | ({spec["benchmark"]} if not crypto else set())
    if not set(job["products"]) <= permitted:
        raise ValueError("UNKNOWN_STUDY_PRODUCT")
    expected_products = (
        [spec["benchmark"]]
        if not crypto and job["strategy"] == "benchmark_buy_hold"
        else slice_receipt["products"]
    )
    if job["products"] != expected_products:
        raise ValueError("INVALID_STUDY_PRODUCTS")
    closes = {}
    for product in job["products"]:
        with records[f"normalized/{product}.csv"].open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            reader = csv.reader(stream)
            if next(reader, None) != ["date", "open", "high", "low", "close", "volume"]:
                raise ValueError("INVALID_STUDY_HEADER")
            table = {}
            previous = None
            for row in reader:
                if (
                    len(row) != 6
                    or date.fromisoformat(row[0]).isoformat() != row[0]
                    or (previous is not None and row[0] <= previous)
                ):
                    raise ValueError("INVALID_STUDY_GRID")
                opening, high, low, close, volume = map(float, row[1:])
                if (
                    not all(
                        math.isfinite(v) for v in (opening, high, low, close, volume)
                    )
                    or min(opening, high, low, close) <= 0
                    or volume < 0
                    or not low <= min(opening, close) <= max(opening, close) <= high
                ):
                    raise ValueError("INVALID_STUDY_BAR")
                table[row[0]] = close
                previous = row[0]
        if [d for d in table if job["dates"][0] <= d <= job["dates"][-1]] != job[
            "dates"
        ]:
            raise ValueError("INCOMPLETE_STUDY_GRID")
        closes[product] = [table[d] for d in job["dates"]]
    return {"dates": job["dates"], "close": closes}


def _write(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def run_job(job_path: Path, output_root: Path) -> dict:
    job = json.loads(_external(job_path).read_text(encoding="utf-8-sig"))
    _validate_job(job)
    code_hash = _source_hash()
    if code_hash != job["expected_leaf_sha256"]:
        raise ValueError("CODE_CHANGED")
    output = _external(output_root)
    if output.exists():
        raise FileExistsError("STUDY_OUTPUT_EXISTS")
    bars = _load_prices(job)
    computation = evaluate_study(
        bars,
        job["strategy"],
        fee_bps=job["fee_bps"],
        quote_currency=job["quote_currency"],
    )
    output.mkdir(parents=True, exist_ok=False)
    periods = output / "periods.json"
    _write(
        periods,
        {
            "schema": "competition.daily_study_periods.v1",
            "job_id": job["job_id"],
            "net": computation["net"]["periods"],
            "gross": computation["gross"]["periods"],
        },
    )
    hold = job["strategy"] in {"buy_hold", "benchmark_buy_hold"} or (
        job["market"] == "crypto" and job["strategy"] == "equal_weight"
    )
    methods = {
        "method_id": job["market"].lower()
        + "."
        + job["strategy"]
        + ".self_financing_daily.v1",
        "strategy": job["strategy"],
        "signal_parameters": PARAMETERS[job["strategy"]],
        "signal_lag_periods": 1,
        "rebalance": "buy_hold" if hold else "daily_target_weights",
        "execution_assumption": "lagged_close_proxy",
        "warmup_periods": 252,
        "scoring_periods": job["fold"]["scoring_periods"],
        "fold_initialization": "independent_cash",
        "cost_model": "self_financing_oneway_bps",
        "terminal_liquidation": False,
        "retrospective": True,
    }
    result = {
        "schema": "competition.daily_study_result.v1",
        "job_id": job["job_id"],
        "plan_sha256": job["plan_sha256"],
        "manifest_sha256": job["manifest_sha256"],
        "code_sha256": code_hash,
        "code_commit": job["code_commit"],
        "market": job["market"],
        "quote_currency": job["quote_currency"],
        "strategy": job["strategy"],
        "parameters": PARAMETERS[job["strategy"]],
        "fee_bps": job["fee_bps"],
        "start": job["fold"]["start"],
        "end": job["fold"]["end"],
        "products": job["products"],
        "fold": job["fold"],
        "methods": methods,
        "metrics": computation["metrics"],
        "benchmark": job["benchmark"],
        "accepted_research": False,
        "artifacts": [
            {
                "path": "periods.json",
                "sha256": _digest(periods),
                "bytes": periods.stat().st_size,
            }
        ],
    }
    _write(output / "result.json", result)
    return result
