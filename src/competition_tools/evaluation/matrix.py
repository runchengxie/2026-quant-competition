"""Deterministic retrospective job planning without research imports."""

from pathlib import Path

from competition_tools.datasets.storage import verify_manifest, digest


def equity_folds(dates: list[str]) -> list[dict]:
    if dates != sorted(set(dates)):
        raise ValueError("INVALID_SESSION_GRID")
    return [
        {
            "warmup_start": dates[start - 252],
            "start": dates[start],
            "end": dates[start + 62],
        }
        for start in range(252, len(dates) - 62, 63)
    ][:32]


def build_matrix(manifests: list[Path]) -> list[dict]:
    jobs = []
    for path in manifests:
        value = verify_manifest(path)
        spec = value["spec"]
        if spec["source"] != "binance_spot" or spec["market"] != "crypto":
            raise ValueError("UNSUPPORTED_EVALUATION_INPUT_KIND")
        for strategy in ("equal_weight", "momentum_63d"):
            for fee in (0, 10):
                jobs.append(
                    {
                        "manifest": str(path),
                        "manifest_sha256": digest(path),
                        "strategy": strategy,
                        "fee_bps": fee,
                        "project": "crypto-mm",
                    }
                )
    if len(jobs) > 32:
        raise ValueError("JOB_BUDGET")
    return jobs
