"""Closed sklearn 1.7.2 forest parameters; no automatic grid expansion."""

import numpy as np

MODELS = ("random_forest", "extra_trees")
DEPTHS = (3, 5)
EXPECTED_INPUT_SHA256 = (
    "08244582811c67fa2d4263c9b2a7515446f1b69efa4b00ad2b00c8aa155936e6"
)


def require_real_input(binding):
    if binding.get("input_sha256") != EXPECTED_INPUT_SHA256:
        raise ValueError("FOREST_RETAINED_INPUT_REQUIRED")


def parameters(kind, depth):
    if kind not in MODELS or type(depth) is not int or depth not in DEPTHS:
        raise ValueError("INVALID_FOREST_SETTING")
    return dict(
        n_estimators=100,
        criterion="squared_error",
        max_depth=depth,
        min_samples_split=2,
        min_samples_leaf=100,
        min_weight_fraction_leaf=0.0,
        max_features=1.0,
        max_leaf_nodes=None,
        min_impurity_decrease=0.0,
        bootstrap=kind == "random_forest",
        oob_score=False,
        n_jobs=2,
        random_state=42,
        verbose=0,
        warm_start=False,
        ccp_alpha=0.0,
        max_samples=None,
        monotonic_cst=None,
    )


def build_model(kind, params):
    import sklearn
    from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline

    if sklearn.__version__ != "1.7.2" or set(params) != {"max_depth"}:
        raise ValueError("FOREST_PINNED_PROFILE_REQUIRED")
    estimator = (
        RandomForestRegressor if kind == "random_forest" else ExtraTreesRegressor
    )
    return Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("model", estimator(**parameters(kind, params["max_depth"]))),
        ]
    )


def _fit_forest(kind, params, x, y):
    """Internal fitter: supported real entry point validates owner claims first."""
    from threadpoolctl import threadpool_limits

    if not len(y) or not np.isfinite(y).all() or np.ptp(y) == 0:
        raise ValueError("INVALID_FOREST_TRAINING_LABELS")
    model = build_model(kind, params)
    with threadpool_limits(limits=2):
        model.fit(x, y)
    return model
