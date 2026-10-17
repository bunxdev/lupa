#!/usr/bin/env python3
"""Opt-in, sequential Maps smoke matrix; private datasets stay in --output.

Requires a dedicated Lupa instance for UI. Never run against a working profile.
The aggregate report contains counts only; raw collector logs remain private.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

CASES = [
    ('farmacias-guadalajara', 'farmacias en Guadalajara', 'Guadalajara', 'farmac', False),
    ('ferreterias-monterrey', 'ferreterías en Monterrey', 'Monterrey', 'ferreter', False),
    ('panaderias-merida', 'panaderías en Mérida Yucatán', 'Mérida', 'panader', False),
    ('empty', 'zzlupafixture005xqvkt', 'Guadalajara', '', True),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-live', action='store_true', help='Explicitly enable requests to Google and navigation in Lupa')
    parser.add_argument('--output', required=True)
    parser.add_argument('--method', choices=['http', 'ui', 'both'], default='both')
    parser.add_argument('--case', choices=[c[0] for c in CASES], action='append')
    args = parser.parse_args()
    if not args.run_live:
        parser.error('--run-live is required; this navigates the configured dedicated instance')
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    if any(output.iterdir()):
        parser.error('use an empty output directory; this matrix does not overwrite previous runs')
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'results': [], 'comparisons': []}
    methods = ['http', 'ui'] if args.method == 'both' else [args.method]

    def save():
        (output / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    for name, query, municipality, category, empty in CASES:
        if args.case and name not in args.case:
            continue
        contacts = {}
        for method in methods:
            folder = output / f'{name}-{method}'
            script = 'qwen_leads_fast.py' if method == 'http' else 'qwen_leads.py'
            command = [sys.executable, str(Path(__file__).with_name(script)), '--query', query,
                       '--municipality', municipality, '--output', str(folder)]
            if category:
                command += ['--category', category]
            if method == 'http':
                command += ['--count', '20']
            for limit in ([1] if empty else [3, 5]):
                invocation = command + ['--limit', str(limit)] + (['--resume'] if limit == 5 else [])
                with (output / f'{name}-{method}-{limit}.log').open('w') as log:
                    try:
                        result = subprocess.run(invocation, stdout=log, stderr=subprocess.STDOUT, timeout=360)
                        code = result.returncode
                    except subprocess.TimeoutExpired:
                        code = 124
                state_path = folder / 'state.json'
                state = json.loads(state_path.read_text()) if state_path.exists() else {}
                accepted = state.get('accepted', [])
                errors = sorted(set(e['error'] for e in state.get('errors', [])))
                ok = (code != 0 and not accepted and state.get('discovery_complete') and not errors) if empty else (code == 0 and len(accepted) == limit)
                row = dict(case=name, method=method, requested=limit, contacts=len(accepted),
                           unique_phones=len({r['phone'] for r in accepted}),
                           exit_code=code, errors=errors, discovery_complete=state.get('discovery_complete', False),
                           ok=bool(ok))
                report['results'].append(row)
                contacts[method] = {r['maps']: r for r in accepted}
                save()
                print(json.dumps(row), flush=True)
                if 'BlockedError' in errors:
                    report['stopped'] = 'Google block or consent; remaining requests were not attempted'
                    save()
                    return 1
                if not ok:
                    break
        if len(contacts) == 2 and not empty:
            common = contacts['http'].keys() & contacts['ui'].keys()
            row = dict(case=name, shared_maps_ids=len(common),
                       matching_phone=sum(contacts['http'][k]['phone'] == contacts['ui'][k]['phone'] for k in common),
                       matching_address=sum(contacts['http'][k]['address'] == contacts['ui'][k]['address'] for k in common))
            report['comparisons'].append(row)
            save()
    report['completed_at'] = datetime.now(timezone.utc).isoformat()
    report['ok'] = bool(report['results']) and all(row['ok'] for row in report['results'])
    save()
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
