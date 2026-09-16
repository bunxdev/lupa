"""Browser Use Actor client for Lupa's shared, visible Chromium session."""
import argparse
import asyncio
import base64
import json
import os
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request
import uuid

os.environ.setdefault('ANONYMIZED_TELEMETRY', 'false')
os.environ.setdefault('BROWSER_USE_CLOUD_SYNC', 'false')
os.environ.setdefault('BROWSER_USE_LOGGING_LEVEL', 'error')

from browser_use import BrowserSession


class Lupa:
    def __init__(self, url, token):
        self.url = url.rstrip('/')
        self.headers = {'Authorization': 'Bearer ' + token}
        self.browser = None
        self.page = None
        self.cursor_script = None
        self.position = (30, 30)

    def api(self, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.url + path, data=data, headers={
            **self.headers, 'Content-Type': 'application/json',
        })
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    async def connect(self):
        # Check authentication before handing credentials to a client library.
        await asyncio.to_thread(self.api, '/cdp/json/version')
        ws = urllib.parse.urlsplit(self.url)
        endpoint = urllib.parse.urlunsplit(('wss' if ws.scheme == 'https' else 'ws', ws.netloc, '/cdp', '', ''))
        geometry = (await asyncio.to_thread(self.api, '/live/eval', {
            'script': 'return {width:Math.min(outerWidth,screen.availWidth),height:Math.min(outerHeight,screen.availHeight)}',
        }))['result']
        self.browser = BrowserSession(
            cdp_url=endpoint, headers=self.headers, is_local=False, keep_alive=True,
            enable_default_extensions=False, headless=False, no_viewport=True, window_size=geometry,
            downloads_path='/config/Downloads',
            highlight_elements=False, auto_download_pdfs=False,
        )
        await asyncio.wait_for(self.browser.start(), timeout=45)
        # URLs can be duplicated across tabs. Mark the exact page owned by /live.
        marker = '__lupa_actor_' + uuid.uuid4().hex
        await asyncio.to_thread(self.api, '/live/eval', {'script': f'window[{json.dumps(marker)}]=true; return true'})
        for page in await self.browser.get_pages():
            try:
                if await page.evaluate('(key) => window[key] === true', marker) == 'True':
                    self.page = page
                    await page.evaluate('(key) => { delete window[key]; }', marker)
                    break
            except Exception:
                continue
        if self.page is None:
            raise RuntimeError('No se encontró la pestaña /live de Lupa')
        await self.browser.cdp_client.send.Page.bringToFront(session_id=await self.page.session_id)

    async def cursor(self):
        script = Path(__file__).with_name('cursor.js').read_text()
        response = await self.browser.cdp_client.send.Page.addScriptToEvaluateOnNewDocument(
            {'source': script}, session_id=await self.page.session_id,
        )
        self.cursor_script = response['identifier']
        await self.page.evaluate('() => {' + script + '}')

    async def disconnect(self):
        if not self.browser:
            return
        try:
            if self.page and self.cursor_script:
                await self.browser.cdp_client.send.Page.removeScriptToEvaluateOnNewDocument(
                    {'identifier': self.cursor_script}, session_id=await self.page.session_id,
                )
                await self.page.evaluate('() => window.__lupaCursor?.()')
        except Exception:
            pass  # A closed/navigating tab must not prevent transport cleanup.
        finally:
            await self.browser.stop()  # Release the client, keep Lupa running.

    async def wait(self, script, *args, timeout=20):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                value = await self.page.evaluate(script, *args)
                if value in ('True', 'true'):
                    return
            except Exception:
                pass  # Navigation can replace the execution context.
            await asyncio.sleep(.15)
        raise TimeoutError('La página no alcanzó el estado esperado')

    async def open(self, url):
        previous = await self.page.get_url()
        await self.page.goto(url)
        await self.wait('(url, previous) => document.readyState === "complete" && (location.href === url || location.href !== previous)', url, previous)

    async def element(self, selector):
        await self.wait('(s) => !!document.querySelector(s)', selector)
        elements = await self.page.get_elements_by_css_selector(selector)
        if len(elements) != 1:
            raise ValueError(f'El selector debe identificar un elemento, encontró {len(elements)}')
        return elements[0]

    async def move_to(self, selector):
        # Scrolling and geometry only; clicks and typing use Actor input actions.
        await self.page.evaluate('(s) => document.querySelector(s).scrollIntoView({block:"center", behavior:"instant"})', selector)
        bounds = json.loads(await self.page.evaluate('(s) => {const b=document.querySelector(s).getBoundingClientRect(); return {x:b.x+b.width/2,y:b.y+b.height/2}}', selector))
        mouse = await self.page.mouse
        start_x, start_y = self.position
        for step in range(1, 21):
            x = round(start_x + (bounds['x'] - start_x) * step / 20)
            y = round(start_y + (bounds['y'] - start_y) * step / 20)
            await mouse.move(x, y)
            await asyncio.sleep(.025)
        self.position = (bounds['x'], bounds['y'])

    async def click(self, selector):
        element = await self.element(selector)
        await self.move_to(selector)
        await element.click()

    async def fill(self, selector, text):
        element = await self.element(selector)
        await self.move_to(selector)
        await element.fill(text)

    async def inspect(self):
        expression = '''() => ({
            title:document.title,
            url:location.protocol==='data:' ? 'data: (demostración local)' : location.href,
            text:document.body.innerText.slice(0,12000),
            controls:[...document.querySelectorAll('a,button,input,select,textarea')].filter(e=>e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden').slice(0,60).map(e=>({
                tag:e.tagName.toLowerCase(),id:e.id,text:(e.innerText||e.getAttribute('aria-label')||e.getAttribute('placeholder')||'').slice(0,160),href:e.getAttribute('href')
            }))
        })'''
        for attempt in range(5):
            try:
                await self.wait('() => document.readyState === "complete"', timeout=5)
                return json.loads(await self.page.evaluate(expression))
            except (RuntimeError, TimeoutError):
                if attempt == 4:
                    raise
                await asyncio.sleep(.15)

    async def demo(self, pause):
        html = Path(__file__).with_name('demo.html').read_text()
        await self.browser.cdp_client.send.Emulation.clearDeviceMetricsOverride(session_id=await self.page.session_id)
        print('1/6 Abriendo la demostración en tu sesión /live', flush=True)
        await self.open('data:text/html;charset=utf-8,' + urllib.parse.quote(html))
        await asyncio.sleep(pause)
        print('2/6 Moviendo el puntero y escribiendo Lupa', flush=True)
        await self.fill('#name', 'Lupa')
        await asyncio.sleep(pause)
        print('3/6 Haciendo clic en Saludar', flush=True)
        await self.click('#greet')
        await self.wait('() => document.querySelector("#greeting").textContent === "Hola Lupa"')
        await asyncio.sleep(pause)
        print('4/6 Marcando la casilla', flush=True)
        await self.click('#confirmed')
        await self.wait('() => document.querySelector("#confirmed").checked')
        await asyncio.sleep(pause)
        print('5/6 Siguiendo el enlace y desplazando la página', flush=True)
        await self.click('#more')
        await asyncio.sleep(pause)
        print('6/6 Finalizando con otro clic', flush=True)
        await self.click('#finish')
        await self.wait('() => document.querySelector("#result").textContent.includes("Conexión comprobada")')
        evidence = json.loads(await self.page.evaluate('() => ({greeting:document.querySelector("#greeting").textContent,checked:document.querySelector("#confirmed").checked,result:document.querySelector("#result").textContent,events:window.demoEvents})'))
        clicks = [e for e in evidence['events'] if e['type'] == 'click']
        typed = [e for e in evidence['events'] if e['type'] == 'input' and e['trusted']]
        # Actor.fill emits a synthetic input while clearing, then real key events.
        if len(clicks) < 4 or not all(e['trusted'] for e in clicks) or len(typed) < 4:
            raise RuntimeError('La demo no recibió los eventos de teclado y clic esperados')
        print(json.dumps(evidence, ensure_ascii=False), flush=True)
        await asyncio.sleep(pause)


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', dest='api_url', default=os.environ.get('LUPA_URL', 'http://127.0.0.1:3036'))
    parser.add_argument('--token-stdin', action='store_true')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('inspect')
    commands.add_parser('report', help='Show a saved HTML report in Lupa').add_argument('path')
    commands.add_parser('open').add_argument('url')
    commands.add_parser('click').add_argument('selector')
    fill = commands.add_parser('fill'); fill.add_argument('selector'); fill.add_argument('text')
    commands.add_parser('press').add_argument('key')
    commands.add_parser('scroll').add_argument('pixels', type=int)
    commands.add_parser('screenshot').add_argument('path')
    commands.add_parser('demo').add_argument('--pause', type=float, default=4)
    from leads import arguments, collect
    arguments(commands)
    args = parser.parse_args()
    if args.token_stdin:
        token = sys.stdin.readline().strip()
    elif os.environ.get('LUPA_API_TOKEN_FILE'):
        token = Path(os.environ['LUPA_API_TOKEN_FILE']).read_text().strip()
    else:
        token = os.environ.get('LUPA_API_TOKEN', '')
    if not token:
        parser.error('Se necesita LUPA_API_TOKEN o LUPA_API_TOKEN_FILE')
    lupa = Lupa(args.api_url, token)
    if args.command == 'report':
        report = Path(args.path).resolve()
        relative = report.relative_to(Path('/output'))
        if report.suffix != '.html' or not report.is_file():
            parser.error('report requiere un archivo HTML existente bajo /output')
        await asyncio.to_thread(lupa.api, '/live', {'url': 'file:///config/Downloads/' + urllib.parse.quote(relative.as_posix(), safe='/')})
        print('Informe abierto en Lupa', flush=True)
        return
    try:
        await lupa.connect()
        if args.command in ('demo', 'click', 'fill', 'scroll'):
            await lupa.cursor()
        if args.command == 'demo':
            if not 0 <= args.pause <= 30:
                parser.error('--pause debe estar entre 0 y 30 segundos')
            await lupa.demo(args.pause)
        elif args.command == 'leads':
            await collect(lupa, args)
        elif args.command == 'open':
            await lupa.open(args.url)
        elif args.command == 'click':
            await lupa.click(args.selector)
        elif args.command == 'fill':
            await lupa.fill(args.selector, args.text)
        elif args.command == 'press':
            await lupa.page.press(args.key)
        elif args.command == 'scroll':
            mouse = await lupa.page.mouse
            await mouse.scroll(x=200, y=200, delta_y=args.pixels)
            await asyncio.sleep(.5)
        elif args.command == 'screenshot':
            Path(args.path).write_bytes(base64.b64decode(await lupa.page.screenshot()))
            print('Captura guardada', flush=True)
        if args.command not in ('demo', 'screenshot', 'leads'):
            print(json.dumps(await lupa.inspect(), ensure_ascii=False, indent=2), flush=True)
    finally:
        await asyncio.wait_for(lupa.disconnect(), timeout=15)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as error:
        # Third-party exception messages may contain connection headers.
        print(f'Falló la acción Browser Use: {type(error).__name__}', file=sys.stderr)
        sys.exit(1)
