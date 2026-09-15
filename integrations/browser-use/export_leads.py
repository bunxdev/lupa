"""Re-export saved leads, optionally adding public facts with explicit sources."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from lead_data import enrich, export, write_json

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--enrichment', type=Path)
    parser.add_argument('--exclude-maps', action='append', default=[], help='Exclude a Maps URL after manual relevance review')
    parser.add_argument('--reason', help='Required explanation for manual exclusions')
    parser.add_argument('--review-source', help='Source supporting the manual review')
    args = parser.parse_args()
    if args.exclude_maps and not args.reason:
        parser.error('--exclude-maps requiere --reason')
    path = args.directory / 'state.json'
    state = json.loads(path.read_text())
    known = {row['maps'] for row in state['accepted']}
    if not set(args.exclude_maps) <= known:
        parser.error('Una URL excluida no coincide con los contactos guardados')
    for row in list(state['accepted']):
        if row['maps'] in args.exclude_maps:
            state['accepted'].remove(row)
            state['rejected'].append(dict(detail=row, reason=args.reason, review_source=args.review_source or row['maps']))
    state['complete'] = len(state['accepted']) >= state['config']['limit']
    state['updated_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    if args.enrichment:
        enrich(state['accepted'], json.loads(args.enrichment.read_text()))
    write_json(path, state)
    export(state, args.directory)
    print(f"Exportados {len(state['accepted'])} contactos en {args.directory}")
