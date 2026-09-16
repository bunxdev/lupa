import { withPage, liveOpen, liveStatus, liveClose, liveEval, liveClick, liveMouseClick, liveMouseMove, liveType, liveKey, liveScreenshot, liveAddCookies, liveGetCookies, getExtContext, closeExtContext, type Viewport } from './browser';
import { authorized } from './auth';

const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json' },
  });

const err = (message: string, status = 400) => json({ error: message }, status);
const binary = (data: Uint8Array, contentType: string) =>
  new Response(Uint8Array.from(data).buffer, { headers: { 'content-type': contentType } });

type JsonResult = { body: Record<string, unknown> } | { response: Response };

const safeJson = async (req: Request, maxBodyBytes: number): Promise<JsonResult> => {
  const contentType = req.headers.get('content-type')?.split(';', 1)[0].trim().toLowerCase();
  if (contentType !== 'application/json') return { response: err('content-type must be application/json', 415) };

  const declaredLength = Number(req.headers.get('content-length'));
  if (Number.isFinite(declaredLength) && declaredLength > maxBodyBytes) {
    return { response: err('request body too large', 413) };
  }

  try {
    const bytes = await req.arrayBuffer();
    if (bytes.byteLength > maxBodyBytes) return { response: err('request body too large', 413) };
    const body = JSON.parse(new TextDecoder().decode(bytes));
    if (!body || typeof body !== 'object' || Array.isArray(body)) {
      return { response: err('json body must be an object') };
    }
    return { body: body as Record<string, unknown> };
  } catch {
    return { response: err('invalid json body') };
  }
};

const str = (v: unknown): string | null => (typeof v === 'string' ? v : null);
const bool = (v: unknown, def = false): boolean => (typeof v === 'boolean' ? v : def);
const obj = (v: unknown): Record<string, unknown> | null =>
  v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null;

const VALID_WAIT = ['load', 'domcontentloaded', 'networkidle'] as const;
type WaitUntil = (typeof VALID_WAIT)[number];
const wait = (v: unknown): WaitUntil =>
  (VALID_WAIT as readonly string[]).includes(str(v) ?? '')
    ? (v as WaitUntil)
    : 'networkidle';

const viewport = (v: unknown): Viewport | undefined => {
  const o = obj(v);
  if (!o) return undefined;
  const w = Number(o.width);
  const h = Number(o.height);
  return Number.isInteger(w) && Number.isInteger(h) && w >= 64 && w <= 7680 && h >= 64 && h <= 4320
    ? { width: w, height: h }
    : undefined;
};

const validViewport = (v: unknown): boolean => v === undefined || viewport(v) !== undefined;
const validUrl = (v: unknown): v is string => typeof v === 'string' && v.length > 0 && v.length <= 8192;
const validScript = (v: unknown): v is string => typeof v === 'string' && v.length > 0 && v.length <= 262144;

const evalScript = (script: string) => `(async () => { ${script} })()`;

type Body = Record<string, unknown>;

type HandlerOptions = { apiToken: string; maxBodyBytes: number };


export function createHandler({ apiToken, maxBodyBytes }: HandlerOptions) {
  return async function handle(req: Request): Promise<Response> {
    try {
      const { pathname } = new URL(req.url);
      const method = req.method;

      if (method === 'GET' && pathname === '/health') return json({ ok: true });
      if (method === 'GET' && pathname === '/selftest') return new Response(SELFTEST_HTML, { headers: { 'content-type': 'text/html; charset=utf-8' } });

      if (!authorized(req, apiToken)) {
        return new Response(JSON.stringify({ error: 'unauthorized' }), {
          status: 401,
          headers: { 'content-type': 'application/json', 'www-authenticate': 'Bearer' },
        });
      }

      if (method === 'GET' && pathname === '/live') return json(liveStatus());
      if (method === 'GET' && pathname === '/live/cookies') return await liveGetCookiesRoute();

      if (method !== 'POST') return new Response('not found', { status: 404 });

      // Endpoints que no requieren body
      if (pathname === '/live/close') return await liveCloseRoute();
      if (pathname === '/live/screenshot') return await liveScreenshotRoute();

      const parsed = await safeJson(req, maxBodyBytes);
      if ('response' in parsed) return parsed.response;
      const body = parsed.body;

      switch (pathname) {
        case '/screenshot':     return await screenshot(body);
        case '/render':         return await render(body);
        case '/pdf':            return await pdf(body);
        case '/eval':           return await evaluate(body);
        case '/content':        return await content(body);
        case '/extension/run':  return await runExtension(body);
        case '/live':           return await live(body);
        case '/live/eval':      return await liveEvalRoute(body);
        case '/live/click':     return await liveClickRoute(body);
        case '/live/mouse-click': return await liveMouseClickRoute(body);
        case '/live/mouse-move':  return await liveMouseMoveRoute(body);
        case '/live/type':        return await liveTypeRoute(body);
        case '/live/key':         return await liveKeyRoute(body);
        case '/live/cookies/add': return await liveAddCookiesRoute(body);
        default: return new Response('not found', { status: 404 });
      }
    } catch (e) {
      console.error('[lupa] request failed:', e instanceof Error ? e.name : 'unknown error');
      return err('request failed', 500);
    }
  };
}

async function screenshot(b: Body): Promise<Response> {
  const url = b.url;
  if (!validUrl(url)) return err('url must be a non-empty string of at most 8192 characters');
  if (!validViewport(b.viewport)) return err('viewport must contain integer width/height within supported bounds');
  const fmt: 'png' | 'jpeg' = str(b.format) === 'jpeg' ? 'jpeg' : 'png';
  const fullPage = bool(b.fullPage);
  const selector = str(b.selector);
  if (selector && selector.length > 4096) return err('selector too long');
  const waitFor = wait(b.waitFor);

  const buf = await withPage(async (page) => {
    await page.goto(url, { waitUntil: waitFor });
    if (selector) {
      return page.locator(selector).first().screenshot({ type: fmt });
    }
    return page.screenshot({ fullPage, type: fmt });
  }, viewport(b.viewport));

  return binary(buf, `image/${fmt}`);
}

async function render(b: Body): Promise<Response> {
  const html = str(b.html);
  if (!html) return err('html required');
  if (!validViewport(b.viewport)) return err('viewport must contain integer width/height within supported bounds');
  const fmt: 'png' | 'jpeg' = str(b.format) === 'jpeg' ? 'jpeg' : 'png';
  const fullPage = bool(b.fullPage, true);

  const buf = await withPage(async (page) => {
    await page.setContent(html, { waitUntil: 'networkidle' });
    return page.screenshot({ fullPage, type: fmt });
  }, viewport(b.viewport));

  return binary(buf, `image/${fmt}`);
}

async function pdf(b: Body): Promise<Response> {
  const url = b.url;
  if (!validUrl(url)) return err('url must be a non-empty string of at most 8192 characters');
  const format = str(b.format) ?? 'A4';
  const landscape = bool(b.landscape);

  const buf = await withPage(async (page) => {
    await page.goto(url, { waitUntil: 'networkidle' });
    return page.pdf({ format, landscape, printBackground: true });
  });

  return binary(buf, 'application/pdf');
}

async function evaluate(b: Body): Promise<Response> {
  const url = b.url;
  const script = b.script;
  if (!validUrl(url) || !validScript(script)) return err('valid url and script required');

  const consoleLogs: string[] = [];
  const pageErrors: string[] = [];
  const result = await withPage(async (page) => {
    page.on('console', (m) => {
      consoleLogs.push(`${m.type()}: ${m.text()}`);
    });
    page.on('pageerror', (e) => {
      pageErrors.push(`${e.name}: ${e.message}${e.stack ? '\n' + e.stack : ''}`);
    });
    await page.goto(url, { waitUntil: 'networkidle' });
    return page.evaluate(evalScript(script));
  });

  return json({ result, consoleLogs, pageErrors });
}

async function content(b: Body): Promise<Response> {
  const url = b.url;
  if (!validUrl(url)) return err('url must be a non-empty string of at most 8192 characters');

  const html = await withPage(async (page) => {
    await page.goto(url, { waitUntil: 'networkidle' });
    return page.content();
  });

  return new Response(html, { headers: { 'content-type': 'text/html' } });
}

async function runExtension(b: Body): Promise<Response> {
  const ext = str(b.extension);
  const url = b.url;
  if (!ext || !validUrl(url)) return err('extension and valid url required');
  if (!/^[a-zA-Z0-9_-]+$/.test(ext)) return err('invalid extension name');

  const extPath = `/extensions/${ext}`;
  const profile = `/config/ext-profiles/${ext}`;
  const script = str(b.script);
  if (script !== null && !validScript(script)) return err('script must contain at most 262144 characters');
  if (!validViewport(b.viewport)) return err('viewport must contain integer width/height within supported bounds');
  const wantShot = bool(b.screenshot);
  // Default 'load' (no 'networkidle'): los content scripts ya tienen el DOM
  // a 'load' y networkidle bloquea ~20s en sites con trackers persistentes.
  const waitFor: WaitUntil =
    (VALID_WAIT as readonly string[]).includes(str(b.waitFor) ?? '')
      ? (b.waitFor as WaitUntil)
      : 'load';
  const fresh = bool(b.fresh);

  if (fresh) await closeExtContext(ext);
  const ctx = await getExtContext(ext, extPath, profile, viewport(b.viewport));

  const page = await ctx.newPage();
  try {
    await page.goto(url, { waitUntil: waitFor });
    let result: unknown = null;
    let screenshot: string | undefined;
    if (script) result = await page.evaluate(evalScript(script));
    if (wantShot) {
      const buf = await page.screenshot({ type: 'png', fullPage: true });
      screenshot = Buffer.from(buf).toString('base64');
    }
    return json({ result, screenshot });
  } finally {
    await page.close();
  }
}

async function live(b: Body): Promise<Response> {
  const url = b.url;
  if (!validUrl(url)) return err('url must be a non-empty string of at most 8192 characters');
  if (!validViewport(b.viewport)) return err('viewport must contain integer width/height within supported bounds');
  await liveOpen(url, viewport(b.viewport));
  // noVNC se sirve por su propio puerto (6080) — el cliente debe usar el host
  // del navegador, así que sólo devolvemos el path para que el caller resuelva.
  const configuredPort = Number(process.env.SELKIES_PUBLIC_PORT ?? 6080);
  const publicPort = Number.isInteger(configuredPort) && configuredPort > 0 && configuredPort <= 65535
    ? configuredPort
    : 6080;
  return json({ ok: true, ...liveStatus(), vnc: { port: publicPort, path: '/' } });
}

async function liveCloseRoute(): Promise<Response> {
  await liveClose();
  return json({ ok: true });
}

async function liveEvalRoute(b: Body): Promise<Response> {
  const script = b.script;
  if (!validScript(script)) return err('script must be a non-empty string of at most 262144 characters');
  const { result, consoleLogs, pageErrors } = await liveEval(script);
  return json({ result, consoleLogs, pageErrors });
}

async function liveClickRoute(b: Body): Promise<Response> {
  const selector = str(b.selector);
  if (!selector) return err('selector required');
  if (selector.length > 4096) return err('selector too long');
  await liveClick(selector);
  return json({ ok: true });
}

async function liveMouseClickRoute(b: Body): Promise<Response> {
  const x = Number(b.x);
  const y = Number(b.y);
  if (!Number.isFinite(x) || !Number.isFinite(y) || Math.abs(x) > 100000 || Math.abs(y) > 100000) return err('valid x and y numbers required');
  const btn = str(b.button);
  const button: 'left' | 'right' | 'middle' = btn === 'right' || btn === 'middle' ? btn : 'left';
  await liveMouseClick(x, y, button);
  return json({ ok: true, x, y, button });
}

async function liveMouseMoveRoute(b: Body): Promise<Response> {
  const x = Number(b.x);
  const y = Number(b.y);
  if (!Number.isFinite(x) || !Number.isFinite(y) || Math.abs(x) > 100000 || Math.abs(y) > 100000) return err('valid x and y numbers required');
  await liveMouseMove(x, y);
  return json({ ok: true, x, y });
}

async function liveTypeRoute(b: Body): Promise<Response> {
  const text = str(b.text);
  if (text === null) return err('text required');
  if (text.length > 65536) return err('text too long');
  await liveType(text);
  return json({ ok: true });
}

async function liveKeyRoute(b: Body): Promise<Response> {
  const key = str(b.key);
  if (!key) return err('key required');
  if (key.length > 100) return err('key too long');
  await liveKey(key);
  return json({ ok: true });
}

async function liveScreenshotRoute(): Promise<Response> {
  const buf = await liveScreenshot();
  return binary(buf, 'image/png');
}

async function liveGetCookiesRoute(): Promise<Response> {
  if (!liveStatus().open) return err('live session not open', 400);
  const cookies = await liveGetCookies();
  return json({ cookies });
}

async function liveAddCookiesRoute(b: Body): Promise<Response> {
  if (!liveStatus().open) return err('live session not open', 400);
  if (!Array.isArray(b.cookies) || b.cookies.length === 0 || b.cookies.length > 200 || b.cookies.some((cookie) => !obj(cookie))) {
    return err('cookies must be an array of 1 to 200 objects');
  }
  await liveAddCookies(b.cookies as Parameters<typeof liveAddCookies>[0]);
  return json({ ok: true, count: (b.cookies as unknown[]).length });
}

const SELFTEST_HTML = `<!doctype html><html><head><meta charset="utf-8"><title>lupa media selftest</title>
<style>body{margin:0;background:#0b0d12;color:#e6edf3;font-family:ui-monospace,monospace;padding:1rem}
video{display:block;width:60%;margin:1rem auto;background:#000}
#stats{padding:1rem;background:#1a2330;border-radius:6px;white-space:pre-wrap;line-height:1.5}
button{background:#7cf3a0;color:#000;padding:.5rem 1rem;font-size:1rem;cursor:pointer;border:0;border-radius:4px;margin-right:.5rem}
button.danger{background:#ff3860;color:#fff}
h1{color:#00f0ff}
.row{display:flex;gap:1rem;align-items:center;margin:1rem 0}
</style></head><body>
<h1>lupa media selftest</h1>
<div class="row">
<button id="tone">▶ tono 440Hz (3s)</button>
<button id="bigtone">▶ tono 880Hz (5s, +louder)</button>
<button class="danger" id="stop">■ stop all</button>
</div>
<video id="v" controls autoplay muted playsinline>
  <source src="https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4" type="video/mp4">
</video>
<pre id="stats">click un botón para auto-test de audio · video debe arrancar muteado por autoplay policy</pre>
<script>
const stats = document.getElementById('stats');
const v = document.getElementById('v');
window.__media = { events: [], tone: null };
function log(s){ window.__media.events.push({t: Date.now(), s}); stats.textContent = window.__media.events.slice(-10).map(e=>new Date(e.t).toISOString().slice(11,23)+' '+e.s).join('\\n'); }
async function runTone(freq, ms, gain){
  if (window.__media.tone) { window.__media.tone.osc.stop(); window.__media.tone.ctx.close(); }
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const osc = ctx.createOscillator();
  const g = ctx.createGain();
  osc.frequency.value = freq;
  g.gain.value = gain;
  osc.type = 'sine';
  osc.connect(g).connect(ctx.destination);
  osc.start();
  window.__media.tone = { ctx, osc };
  log('tone '+freq+'Hz start ctx='+ctx.state+' sr='+ctx.sampleRate);
  setTimeout(() => { try{osc.stop(); ctx.close();}catch(_){} window.__media.tone = null; log('tone '+freq+'Hz done'); }, ms);
}
document.getElementById('tone').onclick = () => runTone(440, 3000, 0.2);
document.getElementById('bigtone').onclick = () => runTone(880, 5000, 0.5);
document.getElementById('stop').onclick = () => { v.pause(); if(window.__media.tone){window.__media.tone.osc.stop(); window.__media.tone.ctx.close(); window.__media.tone=null;} log('stopped'); };
window.__playTone = runTone;
v.addEventListener('loadeddata', () => log('video loadeddata'));
v.addEventListener('playing', () => log('video playing currentTime='+v.currentTime.toFixed(2)));
v.addEventListener('pause', () => log('video pause'));
v.addEventListener('ended', () => log('video ended'));
v.addEventListener('error', (e) => log('video err: '+v.error?.message));
log('page ready');
</script></body></html>`;
