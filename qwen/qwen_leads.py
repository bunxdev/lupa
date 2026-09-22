#!/usr/bin/env python3
"""Colector de contactos públicos de Google Maps para Lupa.

Variante propia (qwen/): conduce la sesión /live únicamente con la API HTTP de
Lupa (POST /live y /live/eval), sin cliente CDP ni contenedor intermedio.
Reutiliza la capa de datos del repositorio (lead_data.py) sin modificarla y
conserva el mismo esquema de state.json que integrations/browser-use/leads.py,
por lo que la carpeta de salida es interoperable con --resume y export_leads.py.

Uso:
  python3 qwen/qwen_leads.py \
    --query 'veterinarias en Zapopan' \
    --municipality Zapopan --limit 100 --category veterin \
    --output /root/lupa/downloads/leads-veterinarias-zapopan-20260921

Token: LUPA_API_TOKEN_FILE o LUPA_API_TOKEN en el entorno. Sin ambos, si se da
LUPA_CONTAINER (nombre del contenedor de Lupa), se obtiene desde el contenedor.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'integrations' / 'browser-use'))
from lead_data import duplicate_of, export, lead_from_detail, normalized, write_json  # noqa: E402

BATCH_JS = (
    "return JSON.stringify([...document.querySelectorAll('[role=feed] a[href*=\"/maps/place/\"]')]"
    ".map(a=>({name:a.getAttribute('aria-label'),url:a.href})).filter(a=>a.name))"
)
DETAIL_JS = (
    "return JSON.stringify({name:[...document.querySelectorAll('h1')].find(h=>h.innerText.trim())?.innerText.trim(),"
    "url:location.href,"
    "category:document.querySelector('button[jsaction*=\"category\"]')?.innerText||'',"
    "permanently_closed:/Cerrado permanentemente|Permanently closed/i.test(document.querySelector('[role=main]')?.innerText||''),"
    "details:[...document.querySelectorAll('[data-item-id]')].filter(e=>/^(address|authority|phone:tel:)/.test(e.getAttribute('data-item-id')))"
    ".map(e=>({id:e.getAttribute('data-item-id'),text:e.innerText,href:e.getAttribute('href')}))})"
)
BLOCK_JS = (
    "return /captcha|recaptcha|unusual traffic|ante del tráfico|antes de continuar/i.test((document.body&&document.body.innerText)||'')"
)


def token_from_container(container):
    script = (
        'import {readFileSync} from "node:fs"; const t=process.env.LUPA_API_TOKEN_FILE?'
        'readFileSync(process.env.LUPA_API_TOKEN_FILE,"utf8").trim():process.env.LUPA_API_TOKEN;'
        'if(!t)process.exit(1);process.stdout.write(t);'
    )
    return subprocess.check_output([
        'docker', 'exec', container, 'sh', '-c',
        'if command -v bun >/dev/null 2>&1; then exec bun "$@"; else exec /config/.bun/bin/bun "$@"; fi',
        'lupa-bun', '-e', script,
    ]).decode().strip()


def resolve_token():
    path = os.environ.get('LUPA_API_TOKEN_FILE')
    if path:
        return Path(path).read_text().strip()
    token = os.environ.get('LUPA_API_TOKEN', '')
    if token:
        return token
    container = os.environ.get('LUPA_CONTAINER')
    if container:
        return token_from_container(container)
    sys.exit('Configura LUPA_API_TOKEN_FILE, LUPA_API_TOKEN o LUPA_CONTAINER')


class Lupa:
    def __init__(self, url, token):
        self.url = url.rstrip('/')
        self.headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}

    def request(self, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.url + path, data=data, headers=self.headers)
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.load(response)

    def eval(self, script):
        response = self.request('/live/eval', {'script': script})
        if 'result' not in response:
            raise RuntimeError('eval sin resultado: ' + json.dumps(response, ensure_ascii=False)[:200])
        return response['result']

    def wait(self, script, timeout=30, interval=0.25):
        end = time.monotonic() + timeout
        while True:
            try:
                if self.eval(script) is True:
                    return
            except Exception:
                pass  # La navegación reemplaza el contexto de ejecución.
            if time.monotonic() >= end:
                raise TimeoutError('La página no alcanzó el estado esperado')
            time.sleep(interval)

    def goto(self, url, timeout=45):
        try:
            previous = self.eval('return location.href')
        except Exception:
            previous = None
        for attempt in (1, 2):
            try:
                self.request('/live', {'url': url})
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(1.5)
        target = json.dumps(url)
        if previous is None:
            script = f'return document.readyState === "complete" && location.href === {target}'
        else:
            script = (f'return document.readyState === "complete" && '
                      f'(location.href === {target} || location.href !== {json.dumps(previous)})')
        self.wait(script, timeout=timeout)

    def blocked(self):
        try:
            return self.eval(BLOCK_JS) is True
        except Exception:
            return False


def discover(lupa, queries, limit, state):
    """Recorre el feed de cada consulta hasta el fondo con paciencia por lotes."""
    cap = max(20, min(50, limit * 2))
    groups = []
    for query in queries:
        print('Buscando: ' + query, flush=True)
        url = 'https://www.google.com/maps/search/' + urllib.parse.quote(query, safe='') + '?hl=es'
        lupa.goto(url)
        lupa.wait('return !!document.querySelector("[role=feed]")', timeout=40)
        if lupa.blocked():
            raise RuntimeError('Bloqueo/CAPTCHA de Google Maps; se conservó el avance')
        cards = {}
        stalled = 0
        while len(cards) < cap:
            before = len(cards)
            batch = json.loads(lupa.eval(BATCH_JS) or '[]')
            for card in batch:
                cards[card['url']] = dict(card, query=query)
            if len(cards) >= cap:
                break
            stalled = 0 if len(cards) > before else stalled + 1
            if stalled >= 3:  # Los lotes pueden tardar un scroll extra.
                break
            lupa.eval('const f=document.querySelector("[role=feed]"); f.scrollTop=f.scrollHeight; return true')
            time.sleep(2.5)
        print(f'  {len(cards)} tarjetas para: {query}', flush=True)
        groups.append(list(cards.values()))
    seen = {card['url'] for card in state['candidates']}
    for index in range(max((len(group) for group in groups), default=0)):
        for group in groups:
            if index < len(group) and group[index]['url'] not in seen:
                state['candidates'].append(group[index])
                seen.add(group[index]['url'])
    state['discovery_complete'] = True


def collect(lupa, args):
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

    if not state['discovery_complete']:
        discover(lupa, args.query, args.limit, state)
        save()

    failures = 0
    for card in state['candidates']:
        if len(state['accepted']) >= args.limit:
            break
        if card['url'] in state['completed']:
            continue
        print(f"Revisando ({len(state['accepted'])}/{args.limit}): {card['name']}", flush=True)
        try:
            lupa.goto(card['url'])
            if lupa.blocked():
                raise RuntimeError('Bloqueo/CAPTCHA de Google Maps')
            name = json.dumps(card['name'])
            lupa.wait(f'return [...document.querySelectorAll("h1")].some(h=>h.innerText.trim()==={name})', timeout=30)
            time.sleep(1.2)
            detail = json.loads(lupa.eval(DETAIL_JS) or 'null')
            if detail is None:
                raise RuntimeError('Detalle no disponible')
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
            # La ficha queda pendiente para que --resume la reintente.
            state['errors'].append(dict(name=card['name'], url=card['url'], error=type(error).__name__))
            failures += 1
            if failures >= 5:
                raise RuntimeError('Fallas repetidas del navegador; resultados parciales guardados') from None
        save()
    print(json.dumps(dict(contacts=len(state['accepted']), requested=args.limit,
                          complete=state['complete'], output=str(output)), ensure_ascii=False), flush=True)
    if not state['complete']:
        raise SystemExit('Contactos verificados insuficientes; revisa state.json y reanuda con --resume')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--query', action='append', required=True, help='Consulta de Maps; repítela para alternar candidatos')
    parser.add_argument('--municipality', required=True, help='Municipio que debe confirmar la dirección')
    parser.add_argument('--limit', type=int, default=15, help='Total de contactos objetivo (1-200)')
    parser.add_argument('--category', action='append', default=[], help='Fragmento de categoría aceptado; repítelo')
    parser.add_argument('--output', required=True, help='Carpeta de salida en el host (state.json, leads.csv/json/html)')
    parser.add_argument('--resume', action='store_true', help='Reanuda la carpeta de salida existente')
    parser.add_argument('--url', default=os.environ.get('LUPA_URL', 'http://127.0.0.1:3136'),
                        help='Raíz de la API de Lupa (predeterminada: env LUPA_URL o http://127.0.0.1:3136)')
    args = parser.parse_args()
    if not 1 <= args.limit <= 200:
        raise SystemExit('El límite debe estar entre 1 y 200')
    lupa = Lupa(args.url, resolve_token())
    lupa.request('/cdp/json/version')  # Verifica autenticación antes de trabajar.
    collect(lupa, args)


if __name__ == '__main__':
    main()
