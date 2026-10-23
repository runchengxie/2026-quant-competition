"""Installed delivery uses named pools with explicitly synthetic daily prices."""

import subprocess
import sys


def test_delivery_help_is_configuration_free():
    child=subprocess.run([sys.executable,"-m","competition_tools.check_strategy_robustness_delivery","--help"],capture_output=True,timeout=15)
    assert child.returncode==0


def test_synthetic_delivery_inputs_cover_exact_named_products(tmp_path):
    from competition_tools.check_strategy_robustness_delivery import synthetic_inputs
    from competition_tools.evaluation.study_inputs import load_study_input

    paths=synthetic_inputs(tmp_path)
    us=load_study_input(paths["US"])
    crypto=load_study_input(paths["crypto"])
    assert set(us["products"])==set("AAPL MSFT AMZN GOOGL META NVDA JPM JNJ XOM PG".split())
    assert len(crypto["products"])==8
    assert len(us["dates"])==315
    assert len(crypto["dates"])==342
