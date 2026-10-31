from datetime import datetime, timezone
import copy
import json
from pathlib import Path
import pytest

from competition_tools import research_governance as g


def test_six_work_items_bind_broad_input_and_cannot_accept():
    work = g.evidence_worklist()
    assert len(work['items']) == 6
    assert work['input_sha256'] == g.INPUT_SHA256
    assert work['scope']['monthly_candidates'] == 500
    for item in work['items']:
        assert all(item[k] for k in ('owner_role', 'material', 'validation', 'reject', 'next_action'))
        assert item['status'] == 'blocked_external'
    assert work['accepted_research'] is False


def test_future_intent_boundary_and_immutable_registration(tmp_path):
    intent = g.future_intent(datetime(2026, 11, 2, 15, tzinfo=timezone.utc),
                             [{'session': '2026-11-02', 'open_at': '2026-11-02T14:30:00+00:00'},
                              {'session': '2026-11-03', 'open_at': '2026-11-03T14:30:00+00:00'}],
                             {'source': 'a'*40, 'root_lock': 'b'*64, 'equity_lock': 'c'*64})
    assert intent['first_eligible_session'] == '2026-11-03'
    assert intent['future_authorized_fit_cap'] == 0
    assert intent['evaluation_sessions'] == 120 and intent['label_tail_sessions'] == 20
    target = tmp_path / 'intent.json'
    g.register_intent(target, intent)
    original = target.read_bytes()
    with pytest.raises(FileExistsError):
        g.register_intent(target, intent)
    assert target.read_bytes() == original
    forged = copy.deepcopy(intent)
    forged['observation_import_enabled'] = True
    with pytest.raises(ValueError):
        g.register_intent(tmp_path / 'forged.json', forged)
    forged = copy.deepcopy(intent)
    forged['evaluation_sessions'] = 2
    forged['intent_sha256'] = g.digest({k:v for k,v in forged.items() if k != 'intent_sha256'})
    with pytest.raises(ValueError):
        g.register_intent(tmp_path / 'short.json', forged)


def test_execution_self_certification_never_lifts_gate():
    intake = g.execution_template()
    assert g.validate_execution(intake)['status'] == 'blocked_external'
    intake['synthetic'] = True
    assert g.validate_execution(intake)['status'] == 'diagnostic_only'
    intake['verified'] = True
    with pytest.raises(ValueError):
        g.validate_execution(intake)


def test_public_status_closed_and_bound_to_reviewed_facts():
    payload = g.public_status()
    g.validate_public_status(payload)
    payload['forest_status'] = 'completed'
    with pytest.raises(ValueError):
        g.validate_public_status(payload)


def test_public_status_source_provenance_is_canonical():
    root = Path(__file__).resolve().parents[1]
    tree = json.loads((root / 'site/src/data/tree-study.v1.json').read_text())
    assert g.digest(tree) == g.public_status()['source_facts']['tree_study_canonical_sha256']


def test_pages_checker_accepts_new_closed_status_sources():
    from competition_tools.check_pages_content import _allowed_source
    from pathlib import PurePosixPath
    assert _allowed_source(PurePosixPath('src/data/research-progress.v1.json'))
    assert _allowed_source(PurePosixPath('src/i18n/progress-en.json'))
    assert not _allowed_source(PurePosixPath('src/data/arbitrary-private.json'))


def test_intent_rejects_source_output_and_naive_calendars(tmp_path):
    with pytest.raises(ValueError, match='TIMEZONE'):
        g.future_intent(datetime(2026, 11, 1), [], {})
    with pytest.raises(ValueError, match='INVALID_CALENDAR'):
        g.future_intent(datetime(2026, 11, 1, tzinfo=timezone.utc),
                        [{'session': '2026-11-02', 'open_at': '2026-11-02T14:30:00'}],
                        {'source': 'a'*40, 'root_lock': 'b'*64, 'equity_lock': 'c'*64})
    root = tmp_path / 'source'
    root.mkdir()
    (root / '.git').write_text('gitdir: elsewhere')
    with pytest.raises(ValueError, match='OUTPUT_IN_SOURCE'):
        g._exclusive_json(root / 'out.json', {})


def test_all_material_references_still_require_real_owner_review():
    intake = g.execution_template()
    for group in ('cost_material', 'paper_material'):
        intake[group] = dict.fromkeys(intake[group], 'self-certified-receipt')
    result = g.validate_execution(intake)
    assert result['missing'] == []
    assert result['status'] == 'blocked_external'
    assert result['broker_authorized'] is False
