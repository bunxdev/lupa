import puppeteer from 'puppeteer-core';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';

// Bun loads the repository .env when this is invoked from the repository root.
const output = resolve(import.meta.dir, '.artifacts');
await mkdir(output, { recursive: true });
const fixture = Bun.serve({
  hostname: '0.0.0.0',
  port: 18090,
  fetch: () => new Response(`<!doctype html><title>Lupa browser lab</title>
    <h1>Browser lab</h1><button id="test" onclick="this.textContent='OK'">Test</button>
    <script>window.labReady = 6 * 7;</script>`,
    { headers: { 'Content-Type': 'text/html' } }),
});
const results: Record<string, unknown>[] = [];
async function check(name: string, action: () => Promise<unknown>) {
  try {
    const details = await action();
    results.push({ name, ok: true, details });
    console.log(`PASS ${name}: ${JSON.stringify(details)}`);
  } catch (error) {
    results.push({ name, ok: false, error: String(error) });
    console.error(`FAIL ${name}: ${error}`);
  }
}
async function cdp(name: string, endpoint: string, url: string, headers?: Record<string, string>) {
  const browser = await puppeteer.connect({ browserWSEndpoint: endpoint, headers, protocolTimeout: 15000, defaultViewport: null });
  let page;
  try {
    page = await browser.newPage();
    await page.goto(url, { waitUntil: 'load', timeout: 20000 });
    const actual = await page.evaluate(() => {
      (document.querySelector('#test') as HTMLButtonElement).click();
      return { title: document.title, js: (window as any).labReady, interaction: document.querySelector('#test')?.textContent };
    });
    if (actual.title !== 'Lupa browser lab' || actual.js !== 42 || actual.interaction !== 'OK') throw new Error(JSON.stringify(actual));
    if (name === 'browseros' || name === 'lupa-cdp') await page.screenshot({ path: resolve(output, `${name}.png`) });
    return actual;
  } finally {
    await page?.close().catch(() => {});
    await browser.disconnect();
  }
}
try {
  await check('obscura', () => cdp('obscura', `ws://127.0.0.1:${process.env.OBSCURA_PORT || 9231}`, 'http://127.0.0.1:18090'));
  await check('lightpanda', () => cdp('lightpanda', `ws://127.0.0.1:${process.env.LIGHTPANDA_PORT || 9232}`, 'http://127.0.0.1:18090'));
  await check('browseros', async () => {
    const port = process.env.BROWSEROS_CDP_PORT || 9233;
    const version = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json() as any;
    const endpoint = new URL(version.webSocketDebuggerUrl);
    endpoint.host = `127.0.0.1:${port}`;
    return cdp('browseros', endpoint.href, 'http://host.docker.internal:18090');
  });
  await check('browseros-backend', async () => {
    const proc = Bun.spawn([resolve(import.meta.dir, 'lab'), 'exec', '-T', 'browseros', 'curl', '-fsS', '--max-time', '10', 'http://127.0.0.1:9200/health'], { stdout: 'pipe', stderr: 'pipe' });
    await new Response(proc.stdout).text();
    const error = await new Response(proc.stderr).text();
    if (await proc.exited) throw new Error(error);
    return { healthy: true };
  });
  const headers = { Authorization: `Bearer ${process.env.LUPA_API_TOKEN || ''}` };
  const api = `http://127.0.0.1:${process.env.LUPA_API_PORT || 3036}`;
  await check('lupa-api', async () => {
    const unauthenticated = await fetch(`${api}/live`);
    if (unauthenticated.status !== 401) throw new Error('Expected 401 without token');
    const response = await fetch(`${api}/eval`, { method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: 'http://host.docker.internal:18090', script: 'return {title:document.title, js:window.labReady};' }) });
    const body = await response.json() as any;
    if (!response.ok || body.result?.js !== 42) throw new Error(JSON.stringify(body));
    return body;
  });
  await check('lupa-cdp', () => cdp('lupa-cdp', `${api.replace('http:', 'ws:')}/cdp`, 'http://host.docker.internal:18090', headers));
  await check('agent-browser', async () => {
    async function cli(args: string[]) {
      const proc = Bun.spawn([resolve(import.meta.dir, 'lab'), 'exec', '-T', 'agent-browser', 'agent-browser', ...args], { stdout: 'pipe', stderr: 'pipe' });
      const stdout = await new Response(proc.stdout).text();
      const stderr = await new Response(proc.stderr).text();
      if (await proc.exited) throw new Error(stderr || stdout);
      return stdout.trim();
    }
    await cli(['open', 'http://127.0.0.1:18090']);
    await cli(['click', '#test']);
    const title = await cli(['get', 'title']);
    const content = await cli(['get', 'text', '#test']);
    if (title !== 'Lupa browser lab' || content !== 'OK') throw new Error(JSON.stringify({ title, content }));
    await cli(['open', 'about:blank']);
    return { title, interaction: content };
  });
  for (const [name, port] of [['lupa-desktop', process.env.SELKIES_PORT || 6080], ['browseros-desktop', process.env.BROWSEROS_DESKTOP_PORT || 6081], ['agent-browser-dashboard', process.env.AGENT_BROWSER_DASHBOARD_PORT || 4848]]) {
    await check(name, async () => {
      const response = await fetch(`http://127.0.0.1:${port}/`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return { status: response.status };
    });
  }
} finally {
  fixture.stop(true);
  await Bun.write(resolve(output, 'smoke.json'), JSON.stringify({ timestamp: new Date().toISOString(), results }, null, 2));
}
if (results.some(r => !r.ok)) process.exitCode = 1;
