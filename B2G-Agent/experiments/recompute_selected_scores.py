"""Offline promotion of the selected goal metric, using retained physical evidence.

F/A/V and non-quality diagnostics retain their audited definitions and values.
Acquisition records are immutable; selected scores live in current_scores.
No API or simulator is called. All cohorts are validated before publication.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket
import statistics
from types import SimpleNamespace

from retained_paths import ROOT, resolve_recorded_path
from b2g_agent.publication import recorded_hash_matches
from b2g_agent.evaluation.goal_attainment import QUALITY_PROTOCOL, EVIDENCE_INPUT_HASHES, validated_goal
from b2g_agent.evaluation.scoring import InteractionScore
from b2g_agent.evaluation.reviewer_feedback_metrics import REVIEWER_METRICS, reviewer_feedback_metrics
from finalize_selected_reports import SOURCES, COMPARISON, main as finalize
from reassess_reviewer_feedback_harms import summarize

AUDIT = ROOT / 'outputs/analysis/goal-attainment'
CASE = ROOT / 'cases/ieee33_10bem_15min'
RAW_HASHES = {}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_raw(path, expected=None):
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if expected and not recorded_hash_matches(path, expected, actual_sha256=actual):
        raise ValueError(f'Acquisition hash mismatch: {path}')
    RAW_HASHES[str(path.resolve())] = actual
    return json.loads(data)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def write_lines(path, rows):
    with path.open('w', encoding='utf-8', newline='\n') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')


def candidate(record, manifests):
    path = resolve_recorded_path(record['manifest'])
    if not path.is_file():
        path = manifests[record['run_id']]
    manifest = read_raw(path)
    root = path.parent.parent
    result = root / 'results' / f"{record['run_id']}.json"
    if result.is_file():
        return read_raw(result, manifest['output_hashes']['result']), result
    result = root / 'errors' / f"{record['run_id']}.candidate.json"
    return read_raw(result), result


def group_summary(rows):
    result = {'attempts': len(rows)}
    for key in ('F', 'A', 'V', 'G', 'quality', 'success'):
        values = [r[key] for r in rows if r[key] is not None]
        result[key] = statistics.mean(values) if values else None
    result['success_count'] = sum(r['success'] for r in rows)
    return result


def update_indexes():
    selected = {(r['method'], r['run_id']): r for r in map(json.loads, (AUDIT / 'per_run.jsonl').read_text(encoding='utf-8').splitlines())}
    for method, suite in SOURCES.items():
        path = suite / 'interaction_records/INDEX.md'
        source_lines = path.read_text(encoding='utf-8').splitlines()
        lines = ['# Current interaction index', '',
                 'Selected scoring: F>=0.85, A=V=1, G>=0.90 where applicable. Clarification G is N/A.',
                 'Acquisition transcripts retain original events; this table and current_scores use the selected offline protocol.', '',
                 '| Run | Workflow | Success | Q |', '| --- | --- | --- | ---: |']
        for line in source_lines:
            if not (line.startswith('| [ep-') or line.startswith('- [ep-')):
                continue
            run_id = line.split('[')[1].split(']')[0]
            row = selected[(method, run_id)]
            if line.startswith('|'):
                workflow = line.split('|')[2].strip()
            else:
                record = json.loads((suite / 'interaction_records' / run_id / 'record.json').read_text(encoding='utf-8'))
                workflow = record['index_row'].get('workflow_status') or 'unavailable'
            lines.append(f"| [{run_id}]({run_id}/transcript.md) | {workflow} | {row['success']} | {row['quality']:.2f} |")
        assert len(lines) == 607, (method, len(lines))
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    def offline(*args, **kwargs):
        raise AssertionError('Network is forbidden during retained-record rescoring')
    socket.socket.connect = socket.socket.connect_ex = socket.create_connection = offline
    truth_path = CASE / 'groundtruth/contract_oracles.jsonl'
    RAW_HASHES[str(truth_path.resolve())] = digest(truth_path)
    truths = {x['episode_id']: x for x in map(json.loads, truth_path.read_text(encoding='utf-8').splitlines())}
    matrix = json.loads((COMPARISON / 'metrics.json').read_text(encoding='utf-8'))
    protocol = json.loads((CASE / 'evaluation/scoring.json').read_text(encoding='utf-8'))
    staged, rows, cohorts = {}, [], {}
    expected = json.loads((AUDIT / 'adopted_expected.json').read_text(encoding='utf-8'))
    for method, suite in SOURCES.items():
        lookup = {p.stem: p for p in suite.glob('remaining150/w*/*/manifests/*.json')}
        selected = []
        for path in sorted((suite / 'interaction_records').glob('*/record.json')):
            record = json.loads(path.read_text(encoding='utf-8'))
            run_id, episode_id = record['run_id'], record['index_row']['episode_id']
            truth = truths[episode_id]
            applicable = truth['perfect_execution']['route'] != 'clarify_sender'
            current = suite / 'current_scores' / f'{run_id}.json'
            old = json.loads(current.read_text(encoding='utf-8')) if current.is_file() else record.get('score')
            scored = old is not None and old.get('scored_candidate', True)
            goal, goals, result_path = (0.0 if applicable else None), {}, None
            if applicable and scored:
                result, result_path = candidate(record, lookup)
                evidence = result.get('physics_evidence')
                goal, goals = validated_goal(truth['task_specification'], SimpleNamespace(**evidence) if evidence else None)
            if old is None:
                old = dict(episode_id=episode_id, semantic_fidelity=0.0, actionability=0.0,
                           physical_feasibility=0.0, first_transfer={}, second_transfer={},
                           actionability_checks={}, agent_metrics={})
            f, a, v = [old[k] for k in ('semantic_fidelity', 'actionability', 'physical_feasibility')]
            components = [f, a, v] + ([goal] if applicable else [])
            quality = 100 * sum(components) / len(components)
            success = f >= protocol['semantic_success_threshold'] and a == 1 and v == 1 and (goal is None or goal >= protocol['goal_success_threshold'])
            score = {**old, 'schema_version': '2.0', 'scoring_protocol_id': QUALITY_PROTOCOL,
                     'scored_candidate': scored, 'goal_applicable': applicable, 'goal_achievement': goal,
                     'goal_scores': goals, 'interaction_quality': quality, 'task_success': success}
            InteractionScore.model_validate(score)
            row = dict(method=method, run_id=run_id, episode_id=episode_id, goal_applicable=applicable,
                       scored_candidate=scored, F=f, A=a, V=v, G=goal, quality=quality, success=success,
                       family_scores=goals, result_path=str(result_path.relative_to(ROOT)) if result_path else None)
            selected.append(row)
            staged[(method, run_id)] = (path, score)
        required = {f'ep-{i:03d}-r{j:02d}' for i in range(1, 201) for j in range(1, 4)}
        assert len(selected) == 600 and {r['run_id'] for r in selected} == required
        executable = [r for r in selected if r['goal_applicable']]
        clarification = [r for r in selected if not r['goal_applicable']]
        assert len(executable) == len(clarification) == 300
        groups = {name: group_summary(group) for name, group in
                  [('all', selected), ('executable', executable), ('clarification', clarification)]}
        for field in ('F', 'A', 'V'):
            assert abs(groups['all'][field] - matrix['methods'][method]['Q_' + field]) < 1e-12
        values = {'Q_G': groups['executable']['G'], 'Q_qua': groups['all']['quality'], 'Q_tsr': groups['all']['success']}
        for name, value in values.items():
            assert abs(value - expected[suite.name][name]) < 1e-10, (method, name, value)
        matrix['methods'][method].update(values)
        cohorts[method] = groups
        rows.extend(selected)
        print(json.dumps({'method': method, **values, 'checked_attempts': len(selected)}), flush=True)
    # Retain independent first-review evidence labels; refresh all score-dependent fields.
    reviewer_dir = ROOT / 'outputs/analysis/reviewer-feedback'
    outcomes = [json.loads(s) for s in (reviewer_dir / 'run_outcomes.jsonl').read_text(encoding='utf-8').splitlines()]
    for row in outcomes:
        score = staged[(row['method'], row['run_id'])][1]
        row.update(task_success=score['task_success'], final_quality=score['interaction_quality'])
        row['appropriate_handling'] = bool(
            (row['reference_label'] == 'clarification' and row['first_forward_route'] == 'clarify_sender' and row['task_success'])
            or (row['reference_label'] == 'clean' and row['first_forward_route'] == 'actor' and row['reached_reverse_review'])
            or (row['reference_label'] in {'semantic', 'evidence'} and row['error_eliminated']))
    reviewer_counts = {}
    for method in ('proposed', 'reviewer_v4'):
        subset = [r for r in outcomes if r['method'] == method]
        metrics = reviewer_feedback_metrics(subset)
        reviewer_counts[method] = {}
        for i, name in enumerate(REVIEWER_METRICS, 1):
            key = f'F_rew_{i}'
            matrix['methods'][method][key] = metrics[name]['value']
            reviewer_counts[method][key] = metrics[name]['numerator']
    print(json.dumps({'reviewer_counts': reviewer_counts}), flush=True)
    # Publication begins only after every run and the adopted aggregate have passed.
    for (method, run_id), (path, score) in staged.items():
        write_json(SOURCES[method] / 'current_scores' / f'{run_id}.json', score)
        record = json.loads(path.read_text(encoding='utf-8'))
        record['score'] = score
        record['scoring_configuration'] = protocol
        record['score_scope'] = 'selected_post_acquisition_protocol; source journal and physical evidence unchanged'
        record['index_row'].update(interaction_quality=score['interaction_quality'], task_success=score['task_success'])
        write_json(path, record)
    write_lines(AUDIT / 'per_run.jsonl', rows)
    with (AUDIT / 'per_run.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader(); writer.writerows(rows)
    write_json(AUDIT / 'cohorts.json', cohorts)
    write_json(AUDIT / 'protocol.json', protocol)
    write_lines(reviewer_dir / 'run_outcomes.jsonl', outcomes)
    review = json.loads((reviewer_dir / 'comparison.json').read_text(encoding='utf-8'))
    review['generated_at'] = datetime.now(timezone.utc).isoformat()
    review['protocol']['score_policy'] = QUALITY_PROTOCOL
    review['protocol']['status'] = 'selected_post_acquisition_protocol'
    review['protocol'].pop('analysis_script_sha256', None)
    review['protocol'].update(scoring_script_sha256=digest(Path(__file__)), reference_labels_reused=True)
    review['protocol']['indicators'] = {k: v.replace('unchanged original task_success', 'selected-protocol task_success').replace('original task_success', 'selected-protocol task_success') for k,v in review['protocol']['indicators'].items()}
    for method in review['methods']:
        subset = [r for r in outcomes if r['method'] == method]
        review['methods'][method] = {
            'all_runs': summarize(subset),
            'executable_runs': summarize([r for r in subset if r['source_executable']]),
            'natural_affected_runs': summarize([r for r in subset if r['affected']]),
            'matched_affected_runs': summarize([r for r in subset if r['matched_affected']])}
    write_json(reviewer_dir / 'comparison.json', review)
    write_json(reviewer_dir / 'protocol.json', review['protocol'])
    write_json(COMPARISON / 'metrics.json', matrix)
    methods = list(SOURCES)
    with (COMPARISON / 'metrics.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['metric', *methods])
        writer.writeheader()
        writer.writerows({'metric': key, **{m: matrix['methods'][m].get(key, '') for m in methods}} for key in matrix['rows'])
    provenance = json.loads((COMPARISON / 'provenance.json').read_text(encoding='utf-8'))
    provenance.update(generated_at=datetime.now(timezone.utc).isoformat(), quality_protocol=QUALITY_PROTOCOL,
                      quality_cohorts=cohorts, reviewer_numerators=reviewer_counts,
                      goal_denominator_per_method=300, quality_and_success_denominator_per_method=600,
                      notes=['Post-acquisition metric revision; no new API or physics runs.',
                             'G describes the validated simulated plan, not external service delivery.',
                             'Source-required clarification has G=N/A; quality averages F/A/V.',
                             'Non-target agent indicators are unreported, not zero.',
                             'Immutable acquisition artifacts may contain historical score fields; only current_scores and final reports are current.'])
    write_json(COMPARISON / 'provenance.json', provenance)
    for path, expected_hash in (RAW_HASHES | EVIDENCE_INPUT_HASHES).items():
        assert digest(Path(path)) == expected_hash, path
    write_json(AUDIT / 'source_hashes.json', {str(Path(p).relative_to(ROOT)): h for p,h in (RAW_HASHES | EVIDENCE_INPUT_HASHES).items()})
    write_json(AUDIT / 'verification.json', {'runs': len(rows), 'raw_input_hashes_verified': len(RAW_HASHES | EVIDENCE_INPUT_HASHES), 'F_A_V_unchanged': True, 'adopted_results_reproduced': True, 'api_calls': 0, 'physics_runs': 0})
    finalize()
    update_indexes()
    lines = ['# Selected five-method comparison', '', '200 tasks x 3 repeats per method. Post-acquisition scoring revision; no API calls or physics reruns.', '',
             'G: validated-plan original-goal attainment, averaged over 300 source-executable runs. All other quality aggregates use 600 runs.',
             'Executable quality: 25(F+A+V+G). Source-required clarification: G=N/A and quality=100(F+A+V)/3.',
             'Success: F>=0.85, A=V=1, and G>=0.90 where applicable.', '',
             '| Metric | ' + ' | '.join(methods) + ' |', '|---|' + '---:|' * len(methods)]
    for key in matrix['rows']:
        lines.append('| ' + key + ' | ' + ' | '.join(f"{matrix['methods'][m][key]:.6f}" if key in matrix['methods'][m] else 'N/A' for m in methods) + ' |')
    (COMPARISON / 'COMPARISON.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (reviewer_dir / 'COMPARISON.md').write_text('# Reviewer feedback impact\n\nCurrent definitions and all three values are in ../../comparison/final/COMPARISON.md.\nThe first-stage evidence labels are retained; success and quality use the selected goal-attainment protocol.\n', encoding='utf-8')
    print('Published 3,000 selected scores and five final reports.', flush=True)


if __name__ == '__main__':
    main()
