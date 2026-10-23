"""Independent continuous observation producer with no provider dependencies."""

import argparse
import hashlib
import json
from pathlib import Path

from .controls import replay_observation
from .study_inputs import _external, _source_hash

MARKET = "crypto"
QUOTE = "USDT"
CANDIDATES = ("trend200_vol40_strict", "ew_trend_gross_matched", "ew_legacy")
FEES = (0, 10, 25)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        source = _external(args.request)
        raw = source.read_bytes()
        value = json.loads(
            raw,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ValueError("NONFINITE_INPUT")
            ),
        )
        if (
            not isinstance(value, dict)
            or set(value)
            != {
                "schema",
                "protocol_id",
                "market",
                "bars",
                "score_start",
                "expected_leaf_sha256",
            }
            or value["schema"] != "competition.observation_replay_request.v1"
            or value["market"] != MARKET
            or not isinstance(value["protocol_id"], str)
            or len(value["protocol_id"]) != 64
            or _source_hash() != value["expected_leaf_sha256"]
        ):
            raise ValueError("INVALID_OBSERVATION_REQUEST")
        rows = [
            dict(
                arm_id=arm,
                fee_bps=fee,
                output=replay_observation(
                    value["bars"],
                    arm,
                    score_start=value["score_start"],
                    fee_bps=fee,
                    quote_currency=QUOTE,
                ),
            )
            for arm in CANDIDATES
            for fee in FEES
        ]
        if (
            source.read_bytes() != raw
            or _source_hash() != value["expected_leaf_sha256"]
        ):
            raise ValueError("OBSERVATION_SOURCE_CHANGED")
        result = dict(
            schema="competition.observation_replay_result.v1",
            protocol_id=value["protocol_id"],
            request_sha256=hashlib.sha256(raw).hexdigest(),
            expected_leaf_sha256=value["expected_leaf_sha256"],
            market=MARKET,
            results=rows,
        )
        target = _external(args.output)
        with target.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, sort_keys=True, allow_nan=False)
    except (ValueError, OSError, TypeError, KeyError, IndexError):
        print(
            json.dumps(
                dict(status="blocked", issue_codes=["INVALID_OBSERVATION_REPLAY"])
            )
        )
        return 2
    print(json.dumps(dict(status="completed", results=len(rows))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
