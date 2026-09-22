#!/usr/bin/env python3
"""Colector RÁPIDO de contactos públicos de Google Maps (qwen/).

En lugar de cargar la UI de Maps por ficha, consume el endpoint interno de
búsqueda de Maps (`/search?tbm=map&pb=...`) directamente por HTTP: una petición
por consulta devuelve ~20 fichas completas (nombre, categoría, dirección,
teléfono internacional, sitio web, cid). Sin navegador, sin Lupa, sin token,
librería estándar.

El parámetro pb se captura una vez de la petición real que hace la SPA de Maps
y se conserva como plantilla en qwen/maps_pb.txt (sólo se sustituye el
segmento `!1s<consulta>`). Si Google cambia la estructura de la respuesta, el
colector falla de forma explícita y hay que recapturar la plantilla (ver
qwen/cdp_net.js) — ese es el punto donde entra la reparación asistida por LLM.

Reutiliza la capa de datos del repositorio (lead_data.py) sin modificarla y
conserva el mismo esquema de state.json que integrations/browser-use/leads.py,
así que la carpeta de salida es interoperable con --resume y export_leads.py.

Uso:
  python3 qwen/qwen_leads_fast.py \
    --query 'veterinarias en Zapopan' \
    --municipality Zapopan --limit 100 --category veterin \
    --output /root/lupa/downloads/leads-fast-zapopan-AAAAMMDD
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'integrations' / 'browser-use'))
from lead_data import duplicate_of, export, lead_from_detail, normalized, write_json  # noqa: E402

HERE = Path(__file__).resolve().parent
ENDPOINT = 'https://www.google.com/search?tbm=map&authuser=0&hl={hl}&gl={gl}&q={q}&pb={pb}'
UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/147.0.0.0 Safari/537.36')
PHONE = re.compile(r'^\+?[\d][\d\s\-.()]{7,17}$')


def safe_get(node, *indexes):
    for index in indexes:
        if not isinstance(node, list) or index >= len(node):
            return None
        node = node[index]
    return node


def pb_for(template, query, count):
    # La plantilla empieza con `!1s<consulta-antes>`; se sustituyen ese segmento
    # y el tamaño de página (`!7i<N>`).
    tail = re.sub(r'!7i\d+', '!7i' + str(count), template[template.index('!7i'):], count=1)
    return '!1s' + query + tail


def fetch_results(query, template, hl, gl, count):
    url = ENDPOINT.format(hl=hl, gl=gl,
                          q=urllib.parse.quote(query, safe=''),
                          pb=urllib.parse.quote(pb_for(template, query, count), safe=''))
    request = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(request, timeout=45) as response:
        body = response.read().decode('utf-8', 'replace')
    payload = body[body.index('\n') + 1:]
    data = json.loads(payload)
    results = data[64] if len(data) > 64 and isinstance(data[64], list) else None
    if not results:
        raise RuntimeError('Estructura de respuesta cambiada o respuesta bloqueada; recapturar plantilla')
    return results


def phone_from(payload):
    direct = safe_get(payload, 178, 0, 1, 1, 0)
    if isinstance(direct, str) and PHONE.match(direct.strip()):
        return direct.strip()
    local = safe_get(payload, 178, 0, 0, 0)
    if isinstance(local, str) and PHONE.match(local.strip()):
        return local.strip()
    found = []

    def scan(node):
        if isinstance(node, str):
            if PHONE.match(node.strip()) and len(node.strip()) >= 8:
                found.append(node.strip())
        elif isinstance(node, list):
            for item in node:
                scan(item)
    scan(safe_get(payload, 178) or [])
    return found[0] if found else ''


def to_detail(payload, query):
    name = safe_get(payload, 11)
    if not isinstance(name, str) or not name.strip():
        return None
    category = safe_get(payload, 13, 0)
    cid = safe_get(payload, 10)
    address = safe_get(payload, 39) or safe_get(payload, 2, 2) or ''
    website = safe_get(payload, 7, 0)
    phone = phone_from(payload)
    source = ''
    if isinstance(cid, str) and ':0x' in cid:
        source = 'https://www.google.com/maps?cid=' + str(int(cid.rsplit(':0x', 1)[1], 16))
    if not source:
        return None
    details = [
        {'id': 'address', 'text': address, 'href': ''},
        {'id': 'authority', 'text': '', 'href': website if isinstance(website, str) else ''},
    ]
    if phone:
        details.append({'id': 'phone:tel:' + phone, 'text': phone, 'href': ''})
    return {
        'name': name.strip(), 'url': source,
        'category': category if isinstance(category, str) else '',
        # El feed de búsqueda no expone el estado de cierre; la variante UI sí lo verifica.
        'permanently_closed': False, 'details': details, 'query': query,
    }


def discover(queries, state, template, hl, gl, count):
    for query in queries:
        print('Buscando: ' + query, flush=True)
        started = time.monotonic()
        results = fetch_results(query, template, hl, gl, count)
        added = 0
        known = {card['url'] for card in state['candidates']}
        for item in results:
            if not (isinstance(item, list) and len(item) >= 2 and isinstance(item[1], list)):
                continue
            detail = to_detail(item[1], query)
            if not detail or detail['url'] in known:
                continue
            known.add(detail['url'])
            state['candidates'].append({'name': detail['name'], 'url': detail['url'],
                                        'query': query, 'detail': detail})
            added += 1
        print(f'  +{added} fichas en {time.monotonic() - started:.1f}s '
              f'(acumuladas {len(state["candidates"])})', flush=True)
        time.sleep(0.5)
    valid = [card for card in state['candidates'] if card.get('detail')]
    if len(valid) < 3:
        raise RuntimeError('Pocas fichas válidas; posible bloqueo o estructura cambiada')
    state['discovery_complete'] = True


def collect(args, template):
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    config = dict(queries=args.query, municipality=args.municipality, limit=args.limit, categories=args.category)
    path = output / 'state.json'
    if path.exists():
        if not args.resume:
            raise SystemExit('Ya existe la carpeta de salida; usa --resume o una carpeta nueva')
        state = json.loads(path.read_text())
        old = state['config']
        if old['municipality'] != config['municipality'] or old['categories'] != config['categories'] \
                or args.limit < len(state['accepted']):
            raise SystemExit('Resume requiere el mismo municipio/categorías y un límite >= contactos guardados')
        if old != config:
            state['discovery_complete'] = False
            state['config'] = config
    else:
        state = dict(config=config, accepted=[], rejected=[], errors=[], candidates=[],
                     completed=[], discovery_complete=False)

    def save():
        state['updated_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
        state['complete'] = len(state['accepted']) >= args.limit
        write_json(path, state)
        export(state, output)

    started = time.monotonic()
    if not state['discovery_complete']:
        discover(args.query, state, template, args.hl, args.gl, args.count)
        save()

    failures = 0
    for card in state['candidates']:
        if len(state['accepted']) >= args.limit:
            break
        if card['url'] in state['completed']:
            continue
        print(f"Validando ({len(state['accepted'])}/{args.limit}): {card['name']}", flush=True)
        try:
            detail = card['detail']
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
            failures += 1
            if failures >= 5:
                raise RuntimeError('Fallas repetidas al validar; resultados parciales guardados') from None
        save()
    print(json.dumps(dict(contacts=len(state['accepted']), requested=args.limit,
                          complete=state['complete'], output=str(output),
                          seconds=round(time.monotonic() - started, 1)), ensure_ascii=False), flush=True)
    if not state['complete']:
        raise SystemExit('Contactos verificados insuficientes; revisa state.json y reanuda con --resume')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--query', action='append', required=True, help='Consulta de Maps; repítela para ampliar candidatos')
    parser.add_argument('--municipality', required=True, help='Municipio que debe confirmar la dirección')
    parser.add_argument('--limit', type=int, default=15, help='Total de contactos objetivo (1-200)')
    parser.add_argument('--category', action='append', default=[], help='Fragmento de categoría aceptado; repítelo')
    parser.add_argument('--output', required=True, help='Carpeta de salida (state.json, leads.csv/json/html)')
    parser.add_argument('--resume', action='store_true', help='Reanuda la carpeta de salida existente')
    parser.add_argument('--hl', default='es', help='Idioma (predeterminado es)')
    parser.add_argument('--gl', default='mx', help='País (predeterminado mx)')
    parser.add_argument('--count', type=int, default=50, help='Fichas por consulta (20-100; predeterminado 50)')
    args = parser.parse_args()
    if not 1 <= args.limit <= 200:
        raise SystemExit('El límite debe estar entre 1 y 200')
    if not 20 <= args.count <= 100:
        raise SystemExit('El tamaño de página debe estar entre 20 y 100')
    template = (HERE / 'maps_pb.txt').read_text().strip()
    if not template.startswith('!1s') or '!7i' not in template:
        raise SystemExit('Plantilla maps_pb.txt inválida; recaptúrala con qwen/cdp_net.js')
    collect(args, template)


if __name__ == '__main__':
    main()
