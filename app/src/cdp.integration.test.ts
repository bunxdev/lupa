import { expect, test } from 'bun:test';
import { chromium, type Browser } from 'playwright';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

// Requires the same Chromium installation and DISPLAY as the app container.
test.skipIf(process.env.RUN_BROWSER_TESTS !== '1')('CDP shares the live session, supports discovery and reconnects after close', async () => {
  const dir = mkdtempSync(join(tmpdir(), 'lupa-cdp-test-'));
  const token = '0123456789abcdef0123456789abcdef';
  writeFileSync(join(dir, 'token'), token + '\n');
  const fixture = Bun.serve({ port: 0, hostname: '0.0.0.0', fetch: () => new Response('<title>CDP fixture</title><h1>Shared session</h1>', { headers: { 'content-type': 'text/html' } }) });
  const reservation = Bun.serve({ port: 0, hostname: '127.0.0.1', fetch: () => new Response() });
  const port = reservation.port!;
  reservation.stop(true);
  const base = `http://127.0.0.1:${port}`;
  const headers = { authorization: `Bearer ${token}` };
  const child = Bun.spawn([process.execPath, 'run', join(import.meta.dir, 'server.ts')], {
    env: { ...process.env, PORT: String(port), API_HOST: '127.0.0.1', LUPA_LIVE_PROFILE: join(dir, 'profile'), LUPA_API_TOKEN: '', LUPA_API_TOKEN_FILE: join(dir, 'token') },
    stdout: 'ignore', stderr: 'inherit',
  });
  const clients: Browser[] = [];
  const post = async (path: string, body = {}) => {
    const response = await fetch(base + path, { method: 'POST', headers: { ...headers, 'content-type': 'application/json' }, body: JSON.stringify(body) });
    expect(response.status).toBe(200);
    return response;
  };
  try {
    let ready = false;
    for (let i = 0; i < 100; i++) {
      try { if ((await fetch(base + '/health')).ok) { ready = true; break; } } catch {}
      await Bun.sleep(100);
    }
    expect(ready).toBe(true);
    expect((await fetch(base + '/cdp/json/version')).status).toBe(401);
    await expect(chromium.connectOverCDP(base.replace('http:', 'ws:') + '/cdp', { timeout: 3000 })).rejects.toThrow();
    // Startup CDP races with the eager splash: both must use one profile launch.
    const [first, second] = await Promise.all([
      chromium.connectOverCDP(base + '/cdp', { headers }),
      chromium.connectOverCDP(base.replace('http:', 'ws:') + '/cdp', { headers }),
    ]);
    clients.push(first, second);
    await post('/live', { url: `http://127.0.0.1:${fixture.port}`, viewport: { width: 800, height: 600 } });
    const page = first.contexts()[0].pages().find(p => p.url().includes(`:${fixture.port}`));
    expect(page).toBeDefined();
    await page!.evaluate(() => { document.title = 'Changed through CDP'; document.cookie = 'cdp=shared; path=/; max-age=3600'; });
    const evaluation = await (await post('/live/eval', { script: 'return { title: document.title, cookie: document.cookie }' })).json();
    expect(evaluation.result).toEqual({ title: 'Changed through CDP', cookie: 'cdp=shared' });
    await page!.bringToFront();
    await page!.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
    expect((await page!.screenshot()).length).toBeGreaterThan(100);
    await first.close(); // Playwright disconnects its CDP transport.
    expect(second.isConnected()).toBe(true);
    const status = await (await fetch(base + '/live', { headers })).json();
    expect(status.open).toBe(true);
    await post('/live/close');
    for (let i = 0; i < 50 && second.isConnected(); i++) await Bun.sleep(20);
    expect(second.isConnected()).toBe(false);
    const reconnected = await chromium.connectOverCDP(base + '/cdp/', { headers });
    clients.push(reconnected);
    expect(reconnected.contexts().length).toBeGreaterThan(0);
    await post('/live', { url: `http://127.0.0.1:${fixture.port}`, viewport: { width: 800, height: 600 } });
    const cookies = await (await fetch(base + '/live/cookies', { headers })).json();
    expect(cookies.cookies.some((cookie: { name: string; value: string }) => cookie.name === 'cdp' && cookie.value === 'shared')).toBe(true);
  } finally {
    for (const client of clients) await client.close().catch(() => {});
    child.kill('SIGTERM');
    await child.exited;
    fixture.stop(true);
    rmSync(dir, { recursive: true, force: true });
  }
}, 60000);
