#!/usr/bin/env python3
"""Colector de contactos públicos de Google Maps para Lupa.

Variante propia (qwen/): conduce la sesión /live únicamente con la API HTTP de
Lupa (POST /live y /live/eval), sin cliente CDP ni contenedor intermedio.
Reutiliza la capa de datos del repositorio (lead_data.py) sin modificarla y
usa un checkpoint versionado para este método. --resume exige el mismo
colector; las exportaciones conservan el esquema de contactos compartido.

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
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'integrations' / 'browser-use'))
from collector_state import (BlockedError, CollectionError, accept_detail, finish,
                             open_state, record_error, save)

BATCH_JS = (
    "return JSON.stringify([...document.querySelectorAll('[role=feed] a[href*=\"/maps/place/\"]')]"
    ".map(a=>({name:a.getAttribute('aria-label'),url:a.href})).filter(a=>a.name))"
)
DETAIL_JS = (
    "return JSON.stringify({name:[...document.querySelectorAll('h1')].find(h=>h.innerText.trim())?.innerText.trim(),"
    "url:location.href,"
    "category:document.querySelector('button[jsaction*=\"category\"]')?.innerText||'',"
    "permanently_closed:/Cerrado permanentemente|Permanentemente cerrado|Permanently closed/i.test(document.querySelector('[role=main]')?.innerText||''),"
    "details:[...document.querySelectorAll('[data-item-id]')].filter(e=>/^(address|authority|phone:tel:)/.test(e.getAttribute('data-item-id')))"
    ".map(e=>({id:e.getAttribute('data-item-id'),text:e.innerText,href:e.getAttribute('href')}))})"
)
BLOCK_JS = (
    "return /captcha|recaptcha|unusual traffic|tráfico inusual|trafico inusual|antes de continuar/i.test((document.body&&document.body.innerText)||'')"
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


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CollectionError('La API redirigió la solicitud; revisa LUPA_URL')


class Lupa:
    def __init__(self, url, token):
        self.url = url.rstrip('/')
        self.headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}
        self.opener = urllib.request.build_opener(NoRedirect)

    def request(self, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.url + path, data=data, headers=self.headers)
        with self.opener.open(request, timeout=90) as response:
            return json.load(response)

    def eval(self, script):
        response = self.request('/live/eval', {'script': script})
        if 'result' not in response:
            raise CollectionError('La API devolvió un resultado inesperado')
        return response['result']

    def wait(self, script, timeout=30, interval=0.25):
        end = time.monotonic() + timeout
        while True:
            if self.blocked():
                raise BlockedError('Bloqueo o consentimiento de Google Maps; avance guardado')
            try:
                if self.eval(script) is True:
                    return
            except CollectionError:
                raise
            except RuntimeError:
                pass  # La navegación puede reemplazar el contexto de ejecución.
            if time.monotonic() >= end:
                raise TimeoutError('La página no alcanzó el estado esperado')
            time.sleep(interval)

    def goto(self, url, timeout=45):
        self.request('/live', {'url': url})
        self.wait('return document.readyState !== "loading"', timeout=timeout)

    def blocked(self):
        return self.eval(BLOCK_JS) is True


def discover(lupa, queries, limit, state, checkpoint=lambda: None):
    """Checkpoint every batch; bounded scrolling tolerates three empty polls."""
    cap = max(20, min(50, limit * 2))
    known = {card['url'] for card in state['candidates']}
    for query in queries:
        if query in state['completed_queries']:
            continue
        print('Buscando: ' + query, flush=True)
        url = 'https://www.google.com/maps/search/' + urllib.parse.quote(query, safe='') + '?hl=es'
        lupa.goto(url)
        if lupa.blocked():
            raise BlockedError('Bloqueo o consentimiento de Maps; avance guardado')
        lupa.wait('return !!document.querySelector("[role=feed]")', timeout=40)
        cards = set()
        stalled = 0
        for _ in range(30):
            if lupa.blocked():
                raise BlockedError('Bloqueo o consentimiento de Maps; avance guardado')
            before = len(cards)
            batch = json.loads(lupa.eval(BATCH_JS) or '[]')
            if not isinstance(batch, list):
                raise CollectionError('Feed inesperado de Maps')
            for card in batch:
                if not isinstance(card, dict) or not isinstance(card.get('url'), str) or not card.get('name'):
                    continue
                cards.add(card['url'])
                if card['url'] not in known:
                    state['candidates'].append(dict(card, query=query))
                    known.add(card['url'])
            checkpoint()
            if len(cards) >= cap:
                break
            stalled = 0 if len(cards) > before else stalled + 1
            if stalled >= 3:
                break
            lupa.eval('const f=document.querySelector("[role=feed]"); if(f) f.scrollTop=f.scrollHeight; return true')
            time.sleep(2.5)
        state['completed_queries'].append(query)
        checkpoint()
        print(f'  {len(cards)} tarjetas para: {query}', flush=True)
    state['discovery_complete'] = True


def collect(lupa, args):
    state = open_state(args, 'maps-ui')
    checkpoint = lambda: save(state, args.output)
    checkpoint()
    try:
        if not state['complete'] and not state['discovery_complete']:
            discover(lupa, state['config']['queries'], args.limit, state, checkpoint)
            checkpoint()
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
                    raise BlockedError('Bloqueo o consentimiento de Maps; avance guardado')
                name = json.dumps(card['name'])
                lupa.wait(f'return [...document.querySelectorAll("h1")].some(h=>h.innerText.trim()==={name})', timeout=30)
                time.sleep(1.2)
                detail = json.loads(lupa.eval(DETAIL_JS) or 'null')
                if not isinstance(detail, dict):
                    raise CollectionError('Detalle no disponible')
                detail['query'] = card['query']
                accept_detail(state, detail)
                state['completed'].append(card['url'])
                failures = 0
            except BlockedError:
                raise
            except Exception as error:
                record_error(state, 'detail', error, name=card['name'], url=card['url'])
                failures += 1
                if failures >= 5:
                    raise CollectionError('Cinco fallas consecutivas del navegador; resultados parciales guardados') from None
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
    parser.add_argument('--output', required=True, help='Carpeta de salida en el host (state.json, leads.csv/json/html)')
    parser.add_argument('--resume', action='store_true', help='Reanuda la carpeta de salida existente')
    parser.add_argument('--url', default=os.environ.get('LUPA_URL', 'http://127.0.0.1:3136'),
                        help='Raíz de la API de Lupa (predeterminada: env LUPA_URL o http://127.0.0.1:3136)')
    args = parser.parse_args()
    if not 1 <= args.limit <= 200:
        raise SystemExit('El límite debe estar entre 1 y 200')
    lupa = Lupa(args.url, resolve_token())
    try:
        lupa.request('/live')  # Read-only authenticated status, no CDP connection needed.
        collect(lupa, args)
    except CollectionError as error:
        raise SystemExit(str(error)) from None
    except KeyboardInterrupt:
        raise SystemExit('Interrumpido; avance guardado para --resume') from None
    except (OSError, ValueError) as error:
        raise SystemExit(f'{type(error).__name__}; revisa state.json antes de reanudar') from None


if __name__ == '__main__':
    main()
