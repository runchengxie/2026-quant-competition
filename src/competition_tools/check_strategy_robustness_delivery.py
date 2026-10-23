"""No-network synthetic installed producer/consumer and accounting check."""

import argparse
import json
import math
import shutil
from pathlib import Path

from .check_study_delivery import synthetic_manifest
from .datasets.binance_daily import PRODUCTS
from .datasets.daily_storage import payload_files, safe_path
from .datasets.storage import digest, write_json, write_manifest
from .evaluation.controls.catalog import ARMS, BUDGET, COSTS
from .evaluation.controls.contracts import read_json
from .evaluation.controls.plan import freeze_controls
from .evaluation.robustness.catalog import CATALOG_SHA256, POOLS, STOCKS, CRYPTO_ARMS
from .evaluation.robustness.contracts import job_hash
from .evaluation.robustness.capacity import capacity_diagnostics
from .evaluation.robustness.verification import verify_robustness_result
from .evaluation.study_identity import source_identity, tree_hash, canonical_hash
from .team.config import load_config
from .team.processes import child_environment, interpreter, run_child


def synthetic_inputs(output: Path) -> dict:
    paths={market:synthetic_manifest(output / market,crypto=market=="crypto") for market in ("US","crypto")}
    for market,path in paths.items():
        manifest=read_json(path)
        products=sorted(STOCKS if market=="US" else PRODUCTS)
        example=path.parent / "normalized" / ("AAPL.csv" if market=="US" else "BTCUSDT.csv")
        for product in products:
            target=path.parent / "normalized" / (product+".csv")
            if not target.exists():
                shutil.copyfile(example,target)
        manifest["spec"]["products"]=products
        if market=="crypto":
            write_manifest(manifest["spec"],path.parent)
        else:
            manifest["files"]=payload_files(path.parent)
            manifest["receipt"]["retained_payload_bytes"]=sum(r["bytes"] for r in manifest["files"])
            write_json(path.parent / "receipt.json",manifest["receipt"])
            write_json(path,manifest)
    return paths


def check_strategy_robustness_delivery(config, output_root: Path) -> dict:
    out=safe_path(output_root)
    out.mkdir(parents=True,exist_ok=False)
    paths=synthetic_inputs(out)
    identity=source_identity(Path(__file__).resolve().parents[2])
    spec=dict(schema="competition.strategy_controls_spec.v1",manifests={m:str(p) for m,p in paths.items()},expected_input_hashes={m:digest(p) for m,p in paths.items()},arms=ARMS,costs=COSTS,role="retrospective",accepted_research=False,budget=BUDGET)
    parent=freeze_controls(spec,out / "parent",code_identity=identity)
    stub=out / "synthetic-baseline.json"
    write_json(stub,dict(synthetic=True,accepted_research=False))
    jobs=[]
    plan_id=canonical_hash(dict(synthetic=True,parent=parent["plan_sha256"]))
    for base in parent["jobs"]:
        if base["market"]=="US" and base["arm_id"]=="ew_monthly":
            choices=[(pool,base["fee_bps"]) for pool in POOLS]
        elif base["market"]=="crypto" and base["arm_id"] in CRYPTO_ARMS and base["fee_bps"]==25:
            choices=[("existing_eight",fee) for fee in (35,50)]
        else:
            continue
        for pool,fee in choices:
            job=dict(schema="competition.strategy_robustness_job.v1",input_job=base,parent_result=str(stub),parent_result_sha256=digest(stub),pool_id=pool,fee_bps=fee,market=base["market"],products=POOLS[pool] if base["market"]=="US" else base["products"],expected_leaf_sha256=tree_hash(Path(identity["source_root"]) / "research" / base["project"] / "src"),catalog_sha256=CATALOG_SHA256,code_commit=identity["commit"],accepted_research=False)
            job["job_id"]=job_hash(job)
            job["plan_sha256"]=plan_id
            jobs.append(job)
    capacity=[]
    for market,project,module in (("US","equity-lab","equity_lab.study.robustness_cli"),("crypto","crypto-mm","crypto_mm.daily.robustness_cli")):
        selected=[j for j in jobs if j["market"]==market]
        batch=out / (market+"-batch.json")
        write_json(batch,dict(schema="competition.strategy_robustness_batch.v1",market=market,plan_sha256=plan_id,jobs=selected))
        child=run_child([str(interpreter(config,project)),"-m",module,"--batch",str(batch),"--output-root",str(out / (market+"-run"))],environment=child_environment(config),timeout=120)
        if child.returncode:
            raise ValueError("SYNTHETIC_ROBUSTNESS_CLI_FAILED")
        for job in selected:
            path=out / (market+"-run") / job["job_id"] / "result.json"
            value=verify_robustness_result(job,path)
            expected=1/(1+job["fee_bps"]/10000)-1 if market=="US" else 0.
            if not math.isclose(value["metrics"]["net_return"],expected,abs_tol=1e-12):
                raise ValueError("SYNTHETIC_ROBUSTNESS_REFERENCE_FAILED")
            if market=="crypto":
                capacity.extend(capacity_diagnostics(job,read_json(path.parent / "periods.json"),None)["checks"])
    report=dict(schema="competition.strategy_robustness_delivery.v1",synthetic=True,completed=len(jobs),capacity_checks=len(capacity),accepted_research=False)
    if report["completed"]!=10 or len(capacity)!=24:
        raise ValueError("SYNTHETIC_ROBUSTNESS_DENOMINATOR")
    write_json(out / "delivery.json",report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",type=Path,required=True)
    parser.add_argument("--output-root",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(check_strategy_robustness_delivery(load_config(args.config),args.output_root)))


if __name__=="__main__":
    main()
