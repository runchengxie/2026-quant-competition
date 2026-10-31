"""Offline research intake and blocked future intent; never an acceptance adapter."""

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re

INPUT_SHA256 = '08244582811c67fa2d4263c9b2a7515446f1b69efa4b00ad2b00c8aa155936e6'
SCOPE = {'monthly_candidates': 500, 'universe': 'broad_monthly_causal_candidates',
         'windows': [['2026-05-28', '2026-07-24'], ['2026-07-27', '2026-09-21']]}
BLOCKERS = (
    ('point_in_time_universe', 'dataset_owner', 'Effective-dated membership, inclusion/exclusion and delisting records',
     'Reconstruct each monthly cutoff using records available at that cutoff', 'Current-only or ten-stock substitute'),
    ('security_identity', 'security_master_owner', 'Stable identifiers and effective-dated symbol/security-type mappings',
     'Join every candidate-day to a stable identity and security type', 'Unresolved identities, warrants treated as common stock'),
    ('corporate_actions', 'corporate_actions_owner', 'Complete splits, distributions, reorganizations and delisting cashflows',
     'Reconcile raw-price boundaries, holdings and cashflows across every action', 'Incomplete events or silent adjusted/raw mixing'),
    ('availability', 'publication_owner', 'Timestamped publication and revision history for every consumed field',
     'Compare field availability with decision timestamps including revisions', 'Period-only timestamps or self-declared verified flags'),
    ('owner_provenance', 'trusted_issuer_governance_owner', 'Trusted issuer registry and authenticated immutable asset/version receipts',
     'Independently authenticate issuer and bind consumed bytes to published version', 'Local hashes or caller assertions used as owner authentication'),
    ('holdout_governance', 'independent_research_governance_owner', 'Owner-controlled exposure log, frozen protocol and independent future holdout',
     'Audit exposure history and prospective protocol before observation import', 'Exposed history relabeled unexposed or retrospective selection'),
)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def evidence_worklist():
    return {'schema': 'competition.research_worklist.v1', 'input_sha256': INPUT_SHA256,
            'scope': SCOPE, 'accepted_research': False, 'trusted_owner_adapter': 'unavailable',
            'items': [dict(id=i, owner_role=o, material=m, validation=v, reject=r,
                           status='blocked_external', scope=SCOPE,
                           next_action=f'Request {m.lower()} from {o}; retain and independently review before any acceptance adapter.')
                      for i, o, m, v, r in BLOCKERS]}


def future_intent(frozen_at, sessions, bindings):
    if frozen_at.tzinfo is None or frozen_at.utcoffset() is None:
        raise ValueError('TIMEZONE_REQUIRED')
    if set(bindings) != {'source', 'root_lock', 'equity_lock'} or any(
        not isinstance(v, str) or not re.fullmatch('[0-9a-f]{40}' if k == 'source' else '[0-9a-f]{64}', v)
        for k, v in bindings.items()
    ):
        raise ValueError('INVALID_BINDINGS')
    eligible = []
    previous = None
    for row in sessions:
        if not isinstance(row, dict) or set(row) != {'session', 'open_at'}:
            raise ValueError('INVALID_CALENDAR')
        day = date.fromisoformat(row['session'])
        opened = datetime.fromisoformat(row['open_at'])
        if opened.tzinfo is None or opened.date() != day or (previous and day <= previous):
            raise ValueError('INVALID_CALENDAR')
        previous = day
        if day >= date(2026, 11, 2) and opened > frozen_at:
            eligible.append(day.isoformat())
    if not eligible:
        raise ValueError('NO_FUTURE_SESSION')
    value = {'schema': 'competition.future_study_intent.v1',
             'frozen_at': frozen_at.astimezone(timezone.utc).isoformat(),
             'calendar': 'XNYS', 'calendar_status': 'supplied_schedule_unverified',
             'calendar_sha256': digest(sessions), 'supplied_sessions': sessions, 'source_bindings': bindings,
             'first_eligible_session': eligible[0], 'evaluation_sessions': 120,
             'label_tail_sessions': 20, 'input_sha256': INPUT_SHA256,
             'status': 'frozen_intent_blocked', 'observation_import_enabled': False,
             'future_training_enabled': False, 'future_authorized_fit_cap': 0,
             'accepted_observations': 0, 'unexposed_status': 'not_certified',
             'reason_codes': ['OWNER_UNVERIFIED', 'PIT_UNVERIFIED', 'AVAILABILITY_UNVERIFIED', 'GOVERNANCE_AWAITING'],
             'rules': {'horizons': [5, 20], 'top_n': 50, 'buffers': [0, 20],
                       'one_way_fee_bps': [0, 20, 40], 'delays': [0, 1],
                       'features': ['session_return', 'range_fraction', 'relative_dollar_volume',
                                    'median_spread', 'quote_fraction', 'active_fraction'],
                       'model_catalog': 'research-model-catalog.v1',
                       'grids_sha256': digest(MODEL_GRIDS)},
             'model_grids': MODEL_GRIDS}
    return dict(value, intent_sha256=digest(value))


MODEL_GRIDS = {
    'ridge': {'alpha': [0.1, 1, 10]},
    'elastic_net': {'alpha': [0.0001, 0.001, 0.01], 'l1_ratio': [0.1, 0.5, 0.9],
                    'max_iter': 2000, 'tol': 0.0001, 'selection': 'cyclic'},
    'hist_gradient_boosting': {'max_depth': [2, 3], 'max_iter': 100, 'learning_rate': 0.05,
                               'max_leaf_nodes': 7, 'min_samples_leaf': 100,
                               'l2_regularization': 1.0, 'max_bins': 63,
                               'random_state': 42, 'early_stopping': False},
    'forest_planned': {'models': ['RandomForestRegressor', 'ExtraTreesRegressor'],
                       'n_estimators': 100, 'max_depth': [3, 5], 'min_samples_leaf': 100,
                       'max_features': 1.0, 'criterion': 'squared_error', 'random_state': 42,
                       'n_jobs': 2, 'rf_bootstrap': True, 'extra_trees_bootstrap': False},
}


def register_intent(path, intent):
    try:
        expected = future_intent(datetime.fromisoformat(intent['frozen_at']),
                                 intent['supplied_sessions'], intent['source_bindings'])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('INVALID_BLOCKED_INTENT') from error
    if intent != expected:
        raise ValueError('INVALID_BLOCKED_INTENT')
    value = {k: v for k, v in intent.items() if k != 'intent_sha256'}
    if (digest(value) != intent.get('intent_sha256') or
        value.get('status') != 'frozen_intent_blocked' or
        value.get('observation_import_enabled') is not False or
        value.get('future_training_enabled') is not False or
        type(value.get('future_authorized_fit_cap')) is not int or
        value['future_authorized_fit_cap'] != 0 or value.get('accepted_observations') != 0):
        raise ValueError('INVALID_BLOCKED_INTENT')
    _exclusive_json(path, intent)


def execution_template():
    return {'schema': 'competition.execution_intake.v1', 'synthetic': False,
            'scope': SCOPE, 'input_sha256': INPUT_SHA256,
            'cost_material': {'venue': None, 'product': None, 'currency': None,
                              'effective_dates': None, 'fee_schedule': None,
                              'bid_ask_timestamps': None, 'spread_samples': None,
                              'liquidity_depth': None, 'participation_capacity': None,
                              'provider_receipt': None},
            'paper_material': {k: None for k in ['supervisor_role', 'account_authorization',
                 'contract_qualification', 'submission', 'cancellation', 'fills',
                 'restart_recovery', 'reconciliation', 'kill_switch', 'audit_receipt']}}


def validate_execution(value):
    template = execution_template()
    if (not isinstance(value, dict) or set(value) != set(template) or
        value['schema'] != template['schema'] or type(value['synthetic']) is not bool or
        value['scope'] != SCOPE or value['input_sha256'] != INPUT_SHA256):
        raise ValueError('INVALID_INTAKE')
    missing = []
    for group in ('cost_material', 'paper_material'):
        if not isinstance(value[group], dict) or set(value[group]) != set(template[group]):
            raise ValueError('INVALID_INTAKE_FIELDS')
        for key, material in value[group].items():
            if material is not None and (not isinstance(material, str) or not material.strip()):
                raise ValueError('INVALID_MATERIAL_REFERENCE')
            if material is None:
                missing.append(f'{group}.{key}')
    return {'schema': 'competition.execution_intake_result.v1',
            'status': 'diagnostic_only' if value['synthetic'] else 'blocked_external',
            'missing': missing, 'accepted_research': False, 'broker_authorized': False,
            'issue_codes': ['SYNTHETIC_FORMAT_ONLY'] if value['synthetic'] else
                           ['OWNER_VALIDATION_UNAVAILABLE', 'SUPERVISED_PAPER_REVIEW_REQUIRED']}


def public_status():
    return {'schema': 'competition.research_progress.v1', 'as_of': '2026-10-31',
            'retrospective_model_blocks': 16, 'external_blockers': [r[0] for r in BLOCKERS],
            'future_status': 'frozen_intent_blocked', 'accepted_observations': 0,
            'future_authorized_fit_cap': 0, 'forest_status': 'planned_not_yet_run',
            'risk_filter_status': 'design_preregistered_not_trained',
            'diagnostics_status': 'planned_post_hoc', 'accepted_research': False,
            'source_facts': {'tree_study_canonical_sha256': 'cd5bff08818a3eca86d68a21b2a0bb8c67330ef6227792c87e0788f291631c28',
                             'input_sha256': INPUT_SHA256}}


def validate_public_status(value):
    if value != public_status():
        raise ValueError('UNREVIEWED_PUBLIC_STATUS')
    return value


def _exclusive_json(path, value):
    path = Path(path)
    resolved = path.resolve()
    if any((parent / '.git').exists() for parent in (resolved.parent, *resolved.parents)):
        raise ValueError('OUTPUT_IN_SOURCE_CHECKOUT')
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=['worklist', 'execution-template', 'future-intent'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--calendar', type=Path)
    parser.add_argument('--bindings', type=Path)
    args = parser.parse_args()
    if args.kind == 'future-intent':
        if not args.calendar or not args.bindings:
            parser.error('future-intent requires --calendar and --bindings')
        value = future_intent(datetime.now(timezone.utc), json.loads(args.calendar.read_text()),
                              json.loads(args.bindings.read_text()))
        register_intent(args.output, value)
    else:
        _exclusive_json(args.output, evidence_worklist() if args.kind == 'worklist' else execution_template())
    print(json.dumps({'status': 'blocked_external', 'accepted_research': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
