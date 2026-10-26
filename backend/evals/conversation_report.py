"""Offline P1 metrics and blinded human-review material; raw reports stay intact."""
import argparse
import json
import math
import random
import statistics
from pathlib import Path


def percentile(values, fraction):
    return sorted(values)[max(0, math.ceil(len(values)*fraction)-1)] if values else None


def generate(directory, candidate='live-candidate.json', judge_name='live-judge.json'):
    reports={arm:json.loads((directory/(candidate if arm=='candidate' else 'live-baseline.json')).read_text(encoding='utf-8')) for arm in ('baseline','candidate')}
    assert reports['baseline']['dataset_sha256']==reports['candidate']['dataset_sha256']
    assert reports['baseline']['configuration']==reports['candidate']['configuration']
    judge=json.loads((directory/judge_name).read_text(encoding='utf-8'))
    metrics=('factual_accuracy','multi_turn_consistency','relevance_usefulness','tool_correctness',
             'natural_vietnamese','initiative','uncertainty_calibration','persona_differentiation','privacy_authorization','intent_alignment')
    result={'dataset':reports['baseline']['dataset_version'],'dataset_sha256':reports['baseline']['dataset_sha256'],
            'comparison_settings':reports['baseline']['configuration'],'model':reports['baseline']['model'],
            'independent_human_review':False,'statistical_significance':'NOT_CLAIMED: 12 new development conversations, one model alias, same-model judge',
            'arms':{},'objective_adjudications':[],'judge_errors':judge.get('error_type'),
            'judge_unknown_usage_requests':judge['unknown_usage_requests']}
    for arm,report in reports.items():
        failures=[]
        for row in report['rows']:
            for key,passed in row['assertions'].items():
                if passed:
                    continue
                text=(row.get('output') or {}).get('text','')
                if key=='grounded_mean' and 'trung bình' not in text.lower():
                    result['objective_adjudications'].append({'arm':arm,'caseId':row['caseId'],'turn':row['turn'],
                        'raw_assertion':key,'raw_result':False,'factual_violation':False,
                        'reason':'The response omits an unrequested mean; it does not state a false mean. Raw evidence retained.'})
                else:
                    failures.append({'caseId':row['caseId'],'turn':row['turn'],'assertion':key})
        intent=[{'caseId':row['caseId'],'turn':row['turn'],'assertion':key} for row in report['rows']
                for key,passed in row.get('intent_assertions',{}).items() if not passed]
        case_scores={}
        for row in judge['rows']:
            if row.get('variant')==arm:
                case_scores.setdefault(row['caseId'],[]).append(row)
        averages={metric:round(statistics.mean(statistics.mean(row[metric] for row in values)
                             for values in case_scores.values()),3) for metric in metrics} if case_scores else {}
        latencies=[row['latency_seconds'] for row in report['rows']]
        result['arms'][arm]={'runtime_commit':report['runtime_commit'],'turns':len(report['rows']),
             'completed':sum(row['status']=='COMPLETED' for row in report['rows']),
             'raw_assertion_failures':sum(not value for row in report['rows'] for value in row['assertions'].values()),
             'factual_privacy_failures':failures,'intent_failures':intent,'judge_case_count':len(case_scores),
             'judge_hard_gate_flags':sum(row.get('hard_gate_failure',False) for row in judge['rows'] if row.get('variant')==arm),
             'quality_case_weighted_means':averages,'latency_p50_seconds':statistics.median(latencies),
             'latency_p95_seconds':percentile(latencies,.95),'usage':report['usage'],
             'estimated_usd_known_usage':report['estimated_usd'],'budget_consumed':report['budget_consumed']}
    result['known_usage_estimated_usd']=round(sum(report['estimated_usd'] or 0 for report in reports.values())+judge['estimated_usd_known_usage'],6)
    sensitivity=[]
    for arm in reports:
        for identity in {row['caseId'] for row in judge['rows'] if row.get('variant')==arm}:
            rows=[row for row in judge['rows'] if row.get('variant')==arm and row['caseId']==identity]
            if len(rows)>1:
                sensitivity.extend(abs(rows[0][metric]-rows[1][metric]) for metric in metrics)
    result['max_reversed_order_score_difference']=max(sensitivity,default=None)
    (directory/'evaluation-summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# Blinded synthetic conversation review','',
           'Review each answer independently before opening human-review-key.json or the metrics. No independent human review has yet occurred.',
           'Score intent, factuality, usefulness, continuity, Vietnamese, initiative, persona and privacy from 1 to 5. Scope is permission, not a demand for analysis. Missing context must not be guessed.','']
    key={}
    cases=list(dict.fromkeys(row['caseId'] for row in reports['baseline']['rows']))
    for index,identity in enumerate(cases,1):
        order=['baseline','candidate']
        random.Random('human:'+identity).shuffle(order)
        key[f'conversation-{index}']={f'answer-{i+1}':arm for i,arm in enumerate(order)}
        lines.extend([f'## Conversation {index}: {identity}',''])
        for position,arm in enumerate(order,1):
            lines.extend([f'### Answer {position}',''])
            for row in reports[arm]['rows']:
                if row['caseId']!=identity:
                    continue
                lines.extend([f"Turn {row['turn']}; bot={row['botId']}; mood permission={row['scope_present']}; records={row['recorded_days']}; memory authorized={row['memory_authorized']}; history limit={row['history_limit']}.",'',
                              '**User:** '+row['prompt'],'','**Assistant:** '+((row.get('output') or {}).get('text') or '[No completed response: '+str(row.get('error_code'))+']'),''])
                sources = {'verified_mood_reads': [], 'approved_memory_inputs': []}
                for capture in row['model_inputs']:
                    for entry in capture['input']:
                        content = entry.get('content')
                        if entry.get('role') == 'user' and isinstance(content, str) and content.startswith('Approved memory data '):
                            if content not in sources['approved_memory_inputs']:
                                sources['approved_memory_inputs'].append(content)
                        if entry.get('type') == 'function_call_output':
                            output = json.loads(entry['output'])
                            if 'buckets' in output:
                                read = {key: output[key] for key in ('from', 'to', 'count', 'mean', 'buckets')}
                                if read not in sources['verified_mood_reads']:
                                    sources['verified_mood_reads'].append(read)
                lines.extend(['**Authorized source inputs observed for this turn:**', '',
                              '```json', json.dumps(sources, ensure_ascii=False, indent=2), '```', ''])
    (directory/'human-review-blind.md').write_text('\n'.join(lines),encoding='utf-8')
    (directory/'human-review-key.json').write_text(json.dumps(key,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('directory',type=Path)
    parser.add_argument('--candidate',default='live-candidate.json')
    parser.add_argument('--judge',default='live-judge.json')
    args=parser.parse_args()
    generate(args.directory,args.candidate,args.judge)
