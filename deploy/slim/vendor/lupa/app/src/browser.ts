import { chromium, type Browser, type BrowserContext, type Cookie, type Page } from 'playwright';
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

// The container supervisor delegates shutdown to server.ts so profiles flush.
const MANAGED_SIGNALS = process.env.LUPA_MANAGED_SHUTDOWN === '1'
  ? { handleSIGTERM: false, handleSIGINT: false, handleSIGHUP: false }
  : {};

const BASE_ARGS = [
  '--no-sandbox',
  '--disable-dev-shm-usage',
  '--disable-blink-features=AutomationControlled',
];

// Extensions dropped into /extensions/<name>/ are auto-loaded into the live
// (headed) chromium so they appear in the toolbar of the visual session.
const EXTENSIONS_DIR = '/extensions';
function discoverExtensions(): string[] {
  if (!existsSync(EXTENSIONS_DIR)) return [];
  try {
    return readdirSync(EXTENSIONS_DIR)
      .filter((name) => existsSync(`${EXTENSIONS_DIR}/${name}/manifest.json`))
      .map((name) => `${EXTENSIONS_DIR}/${name}`);
  } catch { return []; }
}

let browserPromise: Promise<Browser> | null = null;
let headedPromise: Promise<Browser> | null = null;

// Si chromium crashea, el promise cacheado se invalida solo para que el
// próximo caller relance un browser nuevo en lugar de quedarse colgado.
function trackDisconnect(b: Browser, slot: 'headless' | 'headed') {
  b.on('disconnected', () => {
    if (slot === 'headless') browserPromise = null;
    else headedPromise = null;
  });
}

export async function getBrowser(): Promise<Browser> {
  if (!browserPromise) {
    browserPromise = chromium.launch({ ...MANAGED_SIGNALS, headless: true, channel: process.env.LUPA_HEADLESS_CHANNEL || undefined, args: BASE_ARGS })
      .then((b) => { trackDisconnect(b, 'headless'); return b; });
  }
  return browserPromise;
}

export async function getHeadedBrowser(): Promise<Browser> {
  if (!headedPromise) {
    // Sin --window-size fija: selkies cambia la resolución de Xvfb dinámicamente
    // para hacer match con el navegador del cliente, así que dejamos que el WM
    // (openbox) maximice y chromium ocupará lo que selkies decida.
    headedPromise = chromium.launch({
      ...MANAGED_SIGNALS,
      headless: false,
      args: [
        ...BASE_ARGS,
        '--start-maximized',
        '--autoplay-policy=no-user-gesture-required',
      ],
    }).then((b) => { trackDisconnect(b, 'headed'); return b; });
  }
  return headedPromise;
}

export async function closeBrowser(): Promise<void> {
  // Cerrar contextos persistentes de extensión antes que el browser headless.
  for (const [name, p] of extContexts) {
    try { const c = await p; await c.close(); } catch {}
    extContexts.delete(name);
  }
  if (browserPromise) {
    const b = await browserPromise;
    browserPromise = null;
    await b.close();
  }
  if (headedPromise) {
    const b = await headedPromise;
    headedPromise = null;
    await b.close();
  }
  await liveClose();
}

export type Viewport = { width: number; height: number };

// ---- contextos persistentes por extensión (cache) ----
// launchPersistentContext es caro (1-2s). Mantener uno vivo por extensión
// permite que /extension/run sólo abra una page nueva en cada call.

const extContexts = new Map<string, Promise<BrowserContext>>();

export async function getExtContext(
  ext: string,
  extPath: string,
  profile: string,
  viewport?: Viewport,
): Promise<BrowserContext> {
  let p = extContexts.get(ext);
  if (!p) {
    p = chromium.launchPersistentContext(profile, {
      ...MANAGED_SIGNALS,
      headless: false,
      args: [
        '--no-sandbox',
        '--disable-dev-shm-usage',
        `--disable-extensions-except=${extPath}`,
        `--load-extension=${extPath}`,
      ],
      viewport: viewport ?? { width: 1280, height: 720 },
    }).then((c) => {
      c.on('close', () => extContexts.delete(ext));
      return c;
    }).catch((e) => { extContexts.delete(ext); throw e; });
    extContexts.set(ext, p);
  }
  return p;
}

export async function closeExtContext(ext: string): Promise<void> {
  const p = extContexts.get(ext);
  if (!p) return;
  extContexts.delete(ext);
  try { const c = await p; await c.close(); } catch {}
}

export async function withPage<T>(
  fn: (page: Page) => Promise<T>,
  viewport?: Viewport,
): Promise<T> {
  const browser = await getBrowser();
  const ctx = await browser.newContext({
    viewport: viewport ?? { width: 1280, height: 720 },
  });
  try {
    const page = await ctx.newPage();
    return await fn(page);
  } finally {
    await ctx.close();
  }
}

// ---- live (headed) browser session, single page reused ----

const SPLASH_HTML = `<!doctype html><html><head><title>lupa · idle</title>
<style>html,body{margin:0;height:100%;background:#0b0d12;color:#9aa3b2;font-family:JetBrains Mono,ui-monospace,monospace;display:flex;align-items:center;justify-content:center;text-align:center}
.box{padding:2rem 3rem;border:1px solid #1f2733;border-radius:6px}
.brand{font-size:2rem;color:#7cf3a0;letter-spacing:0.2em}
.brand b{color:#ff2d8b}
.hint{margin-top:1rem;font-size:.9rem;line-height:1.6;color:#5f6675}
code{color:#00f0ff}</style></head>
<body><div class="box">
<div class="brand">[ <b>lupa</b> ]</div>
<div class="hint">navegador en directo · esperando URL<br><br>
<code>POST /live { url }</code> en <code>:3036</code></div>
</div></body></html>`;

let liveCtx: BrowserContext | null = null;
let livePage: Page | null = null;

const LIVE_PROFILE = process.env.LUPA_LIVE_PROFILE ?? '/config/live-profile';

// Carpeta donde aterrizan las descargas del Chromium headed. Sibling de Desktop
// dentro del HOME del container y bind-mounteada al host (`./downloads` en
// compose) para que el usuario las recupere desde fuera del container.
const DOWNLOAD_DIR = '/config/Downloads';

// Listener que guarda cada download que Playwright intercepta en DOWNLOAD_DIR
// con el nombre sugerido por la página, en vez del UUID que cae en
// /tmp/playwright-artifacts-* por defecto.
function attachDownloadHandler(page: Page) {
  page.on('download', async (download) => {
    const suggested = download.suggestedFilename() || 'download';
    // sanitize: filename real, sin path traversal
    const safe = suggested.replace(/[/\\]/g, '_').replace(/^\.+/, '');
    const target = join(DOWNLOAD_DIR, safe);
    try {
      mkdirSync(DOWNLOAD_DIR, { recursive: true });
      await download.saveAs(target);
    } catch (e) {
      console.error('[lupa] download save failed:', e instanceof Error ? e.name : 'unknown error');
    }
  });
}

// Pre-seed Preferences del live-profile para que Chromium use DOWNLOAD_DIR
// como ubicación por defecto y no muestre el diálogo "Save As" cada vez.
// Hace merge sobre Preferences existente — conserva otros settings del usuario.
function ensureDownloadPrefs(profileDir: string, downloadDir: string) {
  try { mkdirSync(downloadDir, { recursive: true }); } catch {}
  const defaultDir = join(profileDir, 'Default');
  try { mkdirSync(defaultDir, { recursive: true }); } catch {}
  const prefsPath = join(defaultDir, 'Preferences');
  let prefs: Record<string, unknown> = {};
  try { prefs = JSON.parse(readFileSync(prefsPath, 'utf-8')); } catch {}
  const dl = (prefs.download as Record<string, unknown>) || {};
  dl.default_directory = downloadDir;
  dl.prompt_for_download = false;
  prefs.download = dl;
  const sf = (prefs.savefile as Record<string, unknown>) || {};
  sf.default_directory = downloadDir;
  prefs.savefile = sf;
  try { writeFileSync(prefsPath, JSON.stringify(prefs)); } catch {}
}

// Si chromium murió (usuario cerró la ventana, renderer crash, OOM-kill, etc)
// reseteamos las refs para que la próxima call respawne en vez de hablarle a
// un fantasma. La señal correcta es `browser.isConnected()` — `context.pages()`
// devuelve una lista cacheada y NO tira aunque el proceso esté muerto.
function liveCtxIsHealthy(): boolean {
  if (!liveCtx) return false;
  const b = liveCtx.browser();
  return b ? b.isConnected() : false;
}

// Share startup across HTTP and CDP callers to avoid launching the same profile twice.
let livePagePromise: Promise<Page> | null = null;
let liveClosePromise: Promise<void> | null = null;
async function ensureLivePage(viewport?: Viewport): Promise<Page> {
  if (liveClosePromise) await liveClosePromise;
  if (!livePagePromise) {
    livePagePromise = prepareLivePage(viewport).finally(() => { livePagePromise = null; });
  }
  return livePagePromise;
}

async function prepareLivePage(viewport?: Viewport): Promise<Page> {
  if (liveCtx && !liveCtxIsHealthy()) {
    liveCtx = null;
    livePage = null;
  }
  if (!liveCtx) {
    // viewport: null → playwright NO fija un viewport; el page reflowa al
    // tamaño real de la ventana de chromium, que selkies redimensiona
    // dinámicamente al cliente conectado.
    // launchPersistentContext (no chromium.launch) para soportar
    // --load-extension; cualquier extensión en /extensions/<name>/ se carga.
    const exts = discoverExtensions();
    const extArgs = exts.length
      ? [`--disable-extensions-except=${exts.join(',')}`, `--load-extension=${exts.join(',')}`]
      : [];
    // Pre-seed download path antes de lanzar — evita el diálogo "Save As".
    ensureDownloadPrefs(LIVE_PROFILE, DOWNLOAD_DIR);
    rmSync(join(LIVE_PROFILE, 'DevToolsActivePort'), { force: true });
    liveCtx = await chromium.launchPersistentContext(LIVE_PROFILE, {
      ...MANAGED_SIGNALS,
      headless: false,
      // acceptDownloads:true es el default; Playwright intercepta cada download.
      // Lo usamos a propósito y lo redirigimos al DOWNLOAD_DIR con el filename
      // sugerido por la página (en vez del UUID que caería en
      // /tmp/playwright-artifacts-*). Ver attachDownloadHandler abajo.
      acceptDownloads: true,
      args: [
        '--remote-debugging-address=127.0.0.1',
        '--remote-debugging-port=0',
        ...BASE_ARGS,
        '--start-maximized',
        '--autoplay-policy=no-user-gesture-required',
        ...extArgs,
      ],
      viewport: viewport ?? null,
      bypassCSP: true,
    });
    // Cualquier page nueva (incluida la inicial) recibe el listener de download.
    liveCtx.on('page', attachDownloadHandler);
    for (const page of liveCtx.pages()) attachDownloadHandler(page);
    // Reset refs cuando chromium muere. Usamos `browser.disconnected` en
    // lugar de `context.close` — el context.close NO emite si el process
    // se va por crash/OOM/kill, sólo en cierres explícitos. disconnected
    // sí cubre ambos casos.
    const browser = liveCtx.browser();
    if (browser) {
      browser.on('disconnected', () => {
        console.log('[lupa] live chromium disconnected — invalidando refs');
        liveCtx = null;
        livePage = null;
      });
    }
    liveCtx.on('close', () => { liveCtx = null; livePage = null; });
  }
  if (!livePage || livePage.isClosed()) {
    livePage = await liveCtx.newPage();
  }
  return livePage;
}

// Chromium listens only on container loopback. The authenticated API relays CDP.
export async function getLiveCdpEndpoint(): Promise<string> {
  await ensureLivePage();
  const [port, path] = readFileSync(join(LIVE_PROFILE, 'DevToolsActivePort'), 'utf8').trim().split(/\r?\n/);
  if (!/^\d+$/.test(port) || Number(port) < 1 || Number(port) > 65535 ||
      !/^\/devtools\/browser\/[a-zA-Z0-9-]+$/.test(path ?? '')) {
    throw new Error('Invalid Chromium CDP endpoint');
  }
  return `ws://127.0.0.1:${port}${path}`;
}

export async function liveOpen(url: string, viewport?: Viewport): Promise<void> {
  const page = await ensureLivePage(viewport);
  if (viewport) await page.setViewportSize(viewport);
  await page.goto(url, { waitUntil: 'load' });
  // bringToFront fuerza al WM (openbox) a poner el chromium al frente — sin
  // esto, una `lupa` repetida sobre el mismo URL no es visible si el usuario
  // tenía otra ventana arriba o el window manager la había hidden.
  try { await page.bringToFront(); } catch {}
}

export async function liveEval(script: string): Promise<{ result: unknown; consoleLogs: string[]; pageErrors: string[] }> {
  const consoleLogs: string[] = [];
  const pageErrors: string[] = [];
  const page = await ensureLivePage();
  const onConsole = (m: any) => consoleLogs.push(`${m.type()}: ${m.text()}`);
  const onError = (e: Error) => pageErrors.push(`${e.name}: ${e.message}`);
  page.on('console', onConsole);
  page.on('pageerror', onError);
  try {
    const result = await page.evaluate(`(async () => { ${script} })()`);
    return { result, consoleLogs, pageErrors };
  } finally {
    page.off('console', onConsole);
    page.off('pageerror', onError);
  }
}

export async function liveClick(selector: string): Promise<void> {
  const page = await ensureLivePage();
  await page.locator(selector).first().click({ timeout: 5000 });
}

export async function liveMouseClick(x: number, y: number, button: 'left' | 'right' | 'middle' = 'left'): Promise<void> {
  const page = await ensureLivePage();
  await page.mouse.click(x, y, { button });
}

export async function liveMouseMove(x: number, y: number): Promise<void> {
  const page = await ensureLivePage();
  await page.mouse.move(x, y);
}

export async function liveType(text: string): Promise<void> {
  const page = await ensureLivePage();
  await page.keyboard.type(text);
}

export async function liveKey(key: string): Promise<void> {
  const page = await ensureLivePage();
  await page.keyboard.press(key);
}

export async function liveScreenshot(): Promise<Buffer> {
  const page = await ensureLivePage();
  return page.screenshot({ type: 'png', fullPage: false });
}

export async function liveSplash(): Promise<void> {
  const page = await ensureLivePage();
  await page.setContent(SPLASH_HTML, { waitUntil: 'load' });
}

export function liveStatus(): { open: boolean; url: string | null } {
  if (!liveCtxIsHealthy() || !livePage || livePage.isClosed()) return { open: false, url: null };
  return { open: true, url: livePage.url() };
}

export async function liveAddCookies(cookies: Parameters<BrowserContext['addCookies']>[0]): Promise<void> {
  const page = await ensureLivePage();
  await page.context().addCookies(cookies);
}

export async function liveGetCookies(): Promise<Cookie[]> {
  const page = await ensureLivePage();
  return page.context().cookies();
}

export async function liveClose(): Promise<void> {
  // Cierra de verdad: termina el context y mata el chromium subyacente, así
  // `lupa close && lupa` realmente respawna una ventana nueva en lugar de
  // quedar mostrando una página splash con el browser todavía vivo.
  if (!liveClosePromise) {
    liveClosePromise = (async () => {
      if (livePagePromise) await livePagePromise.catch(() => {});
      if (!liveCtx) return;
      const c = liveCtx;
      liveCtx = null;
      livePage = null;
      try { await c.close(); } catch {}
    })().finally(() => { liveClosePromise = null; });
  }
  await liveClosePromise;
}
