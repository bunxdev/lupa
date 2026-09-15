"""Collect public Maps contact cards in the user's visible Lupa session."""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import quote
from lead_data import duplicate_of, export, lead_from_detail, normalized, write_json


def arguments(commands):
    parser = commands.add_parser('leads', help=__doc__)
    parser.add_argument('--query', action='append', required=True)
    parser.add_argument('--municipality', required=True)
    parser.add_argument('--limit', type=int, default=15)
    parser.add_argument('--output', required=True, help='Directory under /output (host downloads/)')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--category', action='append', default=[], help='Accepted category substring; repeat for alternatives')


async def collect(lupa, args):
    if not 1 <= args.limit <= 200:
        raise ValueError('limit must be between 1 and 200')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    config = dict(queries=args.query, municipality=args.municipality, limit=args.limit, categories=args.category)
    path = output / 'state.json'
    if path.exists():
        if not args.resume:
            raise ValueError('Output exists; use --resume or a new directory')
        state = json.loads(path.read_text())
        old = state['config']
        if old['municipality'] != config['municipality'] or old['categories'] != config['categories'] or args.limit < len(state['accepted']):
            raise ValueError('Resume requires the same municipality/categories and a limit >= saved contacts')
        if old != config:
            state['discovery_complete'] = False
            state['config'] = config
    else:
        state = dict(config=config, accepted=[], rejected=[], errors=[], candidates=[], completed=[], discovery_complete=False)
    def save():
        state['updated_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
        state['complete'] = len(state['accepted']) >= args.limit
        write_json(path, state)
        export(state, output)
    async def evaluate(script, *values):
        return await asyncio.wait_for(lupa.page.evaluate(script, *values), 25)
    failures = 0
    try:
        if not state['discovery_complete']:
            groups = []
            for query in args.query:
                print('Buscando: ' + query, flush=True)
                await lupa.page.goto('https://www.google.com/maps/search/' + quote(query, safe='') + '?hl=es')
                await lupa.wait('() => !!document.querySelector("[role=feed]")', timeout=35)
                cards = {}
                for _ in range(20):
                    batch = json.loads(await evaluate('''() => [...document.querySelectorAll('[role=feed] a[href*="/maps/place/"]')].map(a=>({name:a.getAttribute('aria-label'),url:a.href})).filter(a=>a.name)'''))
                    before = len(cards)
                    for card in batch:
                        cards[card['url']] = dict(card, query=query)
                    if len(cards) >= max(20, min(50, args.limit * 2)):
                        break
                    await evaluate('() => {document.querySelector("[role=feed]").scrollBy(0,1100); return true}')
                    await asyncio.sleep(1.5)
                    if len(cards) == before and len(cards) > 10:
                        break
                groups.append(list(cards.values()))
            seen = {c['url'] for c in state['candidates']}
            for index in range(max((len(g) for g in groups), default=0)):
                for group in groups:
                    if index < len(group) and group[index]['url'] not in seen:
                        state['candidates'].append(group[index]); seen.add(group[index]['url'])
            state['discovery_complete'] = True
            save()
        for card in state['candidates']:
            if len(state['accepted']) >= args.limit:
                break
            if card['url'] in state['completed']:
                continue
            print(f"Revisando ({len(state['accepted'])}/{args.limit}): {card['name']}", flush=True)
            try:
                await lupa.page.goto(card['url'])
                await lupa.wait('(name) => [...document.querySelectorAll("h1")].some(h=>h.innerText.trim()===name)', card['name'], timeout=30)
                await asyncio.sleep(1.5)
                detail = json.loads(await evaluate('''() => ({name:[...document.querySelectorAll('h1')].find(h=>h.innerText.trim())?.innerText.trim(),url:location.href,category:document.querySelector('button[jsaction*="category"]')?.innerText||'',permanently_closed:/Cerrado permanentemente|Permanently closed/i.test(document.querySelector('[role=main]')?.innerText||''),details:[...document.querySelectorAll('[data-item-id]')].filter(e=>/^(address|authority|phone:tel:)/.test(e.getAttribute('data-item-id'))).map(e=>({id:e.getAttribute('data-item-id'),text:e.innerText,href:e.getAttribute('href')}))})'''))
                detail['query'] = card['query']
                row, reason = lead_from_detail(detail, args.municipality)
                if row and args.category and not any(normalized(term) in normalized(row['category']) for term in args.category):
                    row, reason = None, 'category_mismatch'
                duplicate = duplicate_of(row, state['accepted']) if row else None
                if duplicate:
                    row, reason = None, 'duplicate: ' + duplicate
                if row:
                    state['accepted'].append(row)
                else:
                    state['rejected'].append(dict(detail=detail, reason=reason))
                state['completed'].append(card['url'])
            except Exception as error:
                state['errors'].append(dict(name=card['name'], url=card['url'], error=type(error).__name__))
                # Leave failed cards pending so --resume retries them.
                failures += 1
                if failures >= 5:
                    raise RuntimeError('Repeated browser failures; partial results saved') from None
            save()
    finally:
        save()
    print(json.dumps(dict(contacts=len(state['accepted']), requested=args.limit, complete=state['complete'], output=str(output)), ensure_ascii=False), flush=True)
    if not state['complete']:
        raise RuntimeError('Insufficient verified contacts; inspect state.json')
