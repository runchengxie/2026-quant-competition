"""Independent piecewise-linear commission solution; no leaf imports."""

import math
import csv
from datetime import date
from pathlib import Path
from statistics import stdev

from ...datasets.daily_storage import safe_path
from ...datasets.quality import validate_bars
from ...datasets.storage import digest


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def reference_account(prices: dict, targets: list[dict], *, fee_bps: int) -> list[dict]:
    dates, close = prices["dates"], prices["close"]
    if not _number(fee_bps) or not 0 <= fee_bps <= 100 or len(targets) != len(dates)-1 or not close or any(len(v)!=len(dates) or any(not _number(p) or p<=0 for p in v) for v in close.values()):
        raise ValueError("INVALID_REFERENCE_INPUT")
    fee, cash, shares, result = fee_bps / 10000, 1., {p:0. for p in close}, []
    for i, target in enumerate(targets):
        if not set(target)<=set(close) or any(not _number(w) or w<0 for w in target.values()) or sum(target.values())>1+1e-12:
            raise ValueError("INVALID_REFERENCE_WEIGHTS")
        values={p:shares[p]*close[p][i] for p in close}
        before=cash+sum(values.values())
        weights={p:target.get(p,0.) for p in close}
        unchanged=sum(abs(weights[p]*before-values[p]) for p in close)<=1e-12*before
        if unchanged:
            traded=cost=0.
        else:
            # Between each held-value / desired-weight breakpoint the absolute
            # commission equation is linear, so solve it without bisection.
            points=sorted({0.,before,*[values[p]/weights[p] for p in close if weights[p]>0 and 0<values[p]/weights[p]<before]})
            after=None
            for lo,hi in zip(points,points[1:]):
                mid=(lo+hi)/2
                signs={p:1 if weights[p]*mid>=values[p] else -1 for p in close}
                candidate=(before+fee*sum(signs[p]*values[p] for p in close))/(1+fee*sum(signs[p]*weights[p] for p in close))
                if lo-1e-12<=candidate<=hi+1e-12:
                    after=candidate
                    break
            if after is None or after<=0:
                raise ValueError("REFERENCE_FUNDING_NOT_SOLVED")
            traded=sum(abs(weights[p]*after-values[p]) for p in close)
            cost=fee*traded
            cash=max(0.,before-cost-sum(weights.values())*after)
            shares={p:weights[p]*after/close[p][i] for p in close}
        marked={p:shares[p]*close[p][i+1] for p in close}
        equity=cash+sum(marked.values())
        result.append(dict(date=dates[i+1],equity=equity,cash=cash,positions=marked,weights={p:v/equity for p,v in marked.items()},turnover=traded/before,cost=cost,net_return=equity/before-1,exposure=sum(marked.values())/equity))
    return result


def compare_periods(expected: list[dict], actual: list[dict]) -> None:
    if len(expected)!=len(actual):
        raise ValueError("REFERENCE_GRID_MISMATCH")
    for left,right in zip(expected,actual,strict=True):
        if left["date"]!=right["date"]:
            raise ValueError("REFERENCE_DATE_MISMATCH")
        for key in ("equity","cash","turnover","cost","net_return","exposure"):
            if not _number(right[key]) or not math.isclose(left[key],right[key],rel_tol=1e-9,abs_tol=1e-10):
                raise ValueError("REFERENCE_ACCOUNTING_MISMATCH")
        for key in ("positions","weights"):
            if set(left[key])!=set(right[key]) or any(not _number(right[key][p]) or not math.isclose(v,right[key][p],rel_tol=1e-9,abs_tol=1e-10) for p,v in left[key].items()):
                raise ValueError("REFERENCE_POSITIONS_MISMATCH")


def input_prices(job: dict, *, benchmark=False) -> dict:
    base=job["input_job"]
    manifest=safe_path(Path(base["manifest"]))
    if digest(manifest)!=base["manifest_sha256"]:
        raise ValueError("REFERENCE_MANIFEST_CHANGED")
    records={r["path"]:r for r in base["input_files"]}
    products=["SPY"] if benchmark else job["products"]
    closes={}
    for product in products:
        relative=f"normalized/{product}.csv"
        record=records[relative]
        path=safe_path(manifest.parent / relative)
        if digest(path)!=record["sha256"] or path.stat().st_size!=record["bytes"]:
            raise ValueError("REFERENCE_INPUT_CHANGED")
        with path.open(encoding="utf-8-sig",newline="") as stream:
            reader=csv.reader(stream)
            if next(reader,None)!=["date","open","high","low","close","volume"]:
                raise ValueError("REFERENCE_INPUT_HEADER")
            rows=list(reader)
        validate_bars(rows)
        values={r[0]:float(r[4]) for r in rows}
        closes[product]=[values[d] for d in base["dates"]]
    return dict(dates=base["dates"],close=closes)


def reference_targets(job: dict, bars: dict) -> list[dict]:
    dates,closes=bars["dates"],bars["close"]
    products=sorted(closes)
    targets,quantities=[],{}
    for decision in range(251,len(dates)-1):
        if job["market"]=="US":
            today,yesterday=date.fromisoformat(dates[decision]),date.fromisoformat(dates[decision-1])
            if decision==251 or (today.year,today.month)!=(yesterday.year,yesterday.month):
                target={p:1/len(products) for p in products}
                quantities={p:target[p]/closes[p][decision] for p in products}
            else:
                marked={p:q*closes[p][decision] for p,q in quantities.items()}
                total=sum(marked.values())
                target={p:v/total for p,v in marked.items()}
        else:
            selected=[p for p in products if closes[p][decision]>sum(closes[p][decision-199:decision+1])/200]
            target={}
            if selected:
                returns=[sum(closes[p][i]/closes[p][i-1]-1 for p in selected)/len(selected) for i in range(decision-19,decision+1)]
                volatility=stdev(returns)*math.sqrt(365)
                if volatility:
                    gross=min(1.,.4/volatility)
                    allocation=products if job["input_job"]["arm_id"]=="ew_trend_gross_matched" else selected
                    target={p:gross/len(allocation) for p in allocation}
        targets.append(target)
    return targets
