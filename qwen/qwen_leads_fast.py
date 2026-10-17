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
colector falla de forma explícita: revisa qwen/README.md antes de actualizar
la plantilla y el mapa de campos.

Reutiliza la capa de datos del repositorio (lead_data.py) sin modificarla y
usa un checkpoint versionado para este método. --resume exige el mismo
colector; las exportaciones conservan el esquema de contactos compartido.

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
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'integrations' / 'browser-use'))
from collector_state import (BlockedError, CollectionError, SchemaError, accept_detail,
                             finish, open_state, output_lock, record_error, save)

HERE = Path(__file__).resolve().parent
ENDPOINT = 'https://www.google.com/search?tbm=map&authuser=0&hl={hl}&gl={gl}&q={q}&pb={pb}'
UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/147.0.0.0 Safari/537.36')
PHONE = re.compile(r'^\+?[\d][\d\s\-.()]{7,17}$')


def safe_get(node, *indexes):
    for index in indexes:
        if not isinstance(node, list) or index < 0 or index >= len(node):
            return None
        node = node[index]
    return node


def pb_for(template, query, count):
    # La plantilla empieza con `!1s<consulta-antes>`; se sustituyen ese segmento
    # y el tamaño de página (`!7i<N>`).
    tail = re.sub(r'!7i\d+', '!7i' + str(count), template[template.index('!7i'):], count=1)
    return '!1s' + query + tail


def parse_response(body):
    if not body.lstrip().startswith(")]}'"):
        if '<html' in body.lower() or any(word in body.lower() for word in ('captcha', 'unusual traffic', 'consent.google')):
            raise BlockedError('Respuesta HTML, consentimiento o bloqueo de Maps; no se reintenta automáticamente')
        raise SchemaError('Respuesta de Maps sin el prefijo JSON esperado')
    try:
        data = json.loads(body.lstrip()[4:].lstrip())
    except (ValueError, TypeError):
        raise SchemaError('JSON de Maps inválido') from None
    results = safe_get(data, 64)
    # Observed no-result envelope: only the search header, with an explicit
    # empty result marker at [18]. A missing [64] alone is never enough.
    table = safe_get(data, 0, 1)
    header = safe_get(table, 0)
    if (isinstance(data, list) and len(data) > 64 and results is None
            and isinstance(safe_get(data, 0, 0), str)
            and isinstance(table, list) and len(table) == 1
            and isinstance(header, list) and len(header) == 19
            and header[:8] == [None] * 8 and header[18] == []
            and isinstance(safe_get(header, 12, 1), str)
            and safe_get(header, 12, 1).startswith('/search?q=')):
        return []
    if not isinstance(results, list):
        raise SchemaError('La respuesta de Maps cambió: falta la lista de resultados')
    return results


def fetch_results(query, template, hl, gl, count):
    url = ENDPOINT.format(hl=urllib.parse.quote(hl, safe=''), gl=urllib.parse.quote(gl, safe=''),
                          q=urllib.parse.quote(query, safe=''),
                          pb=urllib.parse.quote(pb_for(template, query, count), safe=''))
    request = urllib.request.Request(url, headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read(8 * 1024 * 1024 + 1)
    except urllib.error.HTTPError as error:
        if error.code in (403, 429):
            raise BlockedError('Maps rechazó o limitó la solicitud; no se reintenta automáticamente') from None
        raise
    if len(raw) > 8 * 1024 * 1024:
        raise SchemaError('Respuesta de Maps demasiado grande')
    return parse_response(raw.decode('utf-8', 'replace'))


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
    if isinstance(cid, str) and re.fullmatch(r'0x[0-9a-fA-F]+:0x[0-9a-fA-F]{1,16}', cid):
        source = 'https://www.google.com/maps?cid=' + str(int(cid.rsplit(':0x', 1)[1], 16))
    if not source or not isinstance(address, str):
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
        'permanently_closed': None, 'details': details, 'query': query,
        'retrieved_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
    }


def discover(queries, state, template, hl, gl, count, checkpoint=lambda: None):
    for query in queries:
        if query in state['completed_queries']:
            continue
        print('Buscando: ' + query, flush=True)
        results = fetch_results(query, template, hl, gl, count)
        recognized = 0
        known = {card['url'] for card in state['candidates']}
        for item in results:
            if not (isinstance(item, list) and len(item) >= 2 and isinstance(item[1], list)):
                continue
            detail = to_detail(item[1], query)
            if not detail:
                continue
            recognized += 1
            if detail['url'] not in known:
                known.add(detail['url'])
                state['candidates'].append({'name': detail['name'], 'url': detail['url'],
                                            'query': query, 'detail': detail})
        if results and not recognized:
            raise SchemaError('Ninguna ficha reconocible; posible cambio en el formato de Maps')
        state['completed_queries'].append(query)
        checkpoint()
        print(f'  {recognized} fichas reconocidas; {len(state["candidates"])} candidatas acumuladas', flush=True)
        time.sleep(0.5)
    state['discovery_complete'] = True


def collect(args, template):
    with output_lock(args.output):
        return _collect(args, template)


def _collect(args, template):
    state = open_state(args, 'maps-http', dict(hl=args.hl, gl=args.gl, count=args.count))
    checkpoint = lambda: save(state, args.output)
    checkpoint()  # A resumable checkpoint exists before the first network request.
    try:
        if not state['complete'] and not state['discovery_complete']:
            discover(state['config']['queries'], state, template, args.hl, args.gl, args.count, checkpoint)
            checkpoint()
        failures = 0
        for card in state['candidates']:
            if len(state['accepted']) >= args.limit:
                break
            if card['url'] in state['completed']:
                continue
            try:
                accept_detail(state, card['detail'])
                state['completed'].append(card['url'])
                failures = 0
            except Exception as error:
                record_error(state, 'detail', error, url=card['url'])
                failures += 1
                if failures >= 5:
                    raise CollectionError('Cinco fallas consecutivas; resultados parciales guardados') from None
            finally:
                checkpoint()
    except (Exception, KeyboardInterrupt) as error:
        record_error(state, 'collection', error)
        checkpoint()
        raise
    finish(state, args)


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
        raise SystemExit('Plantilla maps_pb.txt inválida; revisa qwen/README.md')
    try:
        collect(args, template)
    except CollectionError as error:
        raise SystemExit(str(error)) from None
    except KeyboardInterrupt:
        raise SystemExit("Interrumpido; avance guardado para --resume") from None
    except (OSError, ValueError) as error:
        raise SystemExit(f"{type(error).__name__}; revisa state.json antes de reanudar") from None


if __name__ == '__main__':
    main()
