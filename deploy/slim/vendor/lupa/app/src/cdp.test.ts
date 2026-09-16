import { afterAll, describe, expect, test } from 'bun:test';
import { createCdpGateway, type CdpSocket } from './cdp';

const token = '0123456789abcdef0123456789abcdef';
let starts = 0;
const gateway = createCdpGateway(token, async () => { starts++; throw new Error('offline'); });
const server = Bun.serve<CdpSocket>({ port: 0, hostname: '127.0.0.1', ...gateway });
afterAll(() => server.stop(true));

describe('CDP authentication and failures', () => {
  test('discovery and WebSocket handshake require bearer auth before browser access', async () => {
    for (const path of ['/cdp', '/cdp/json/version', '/cdp/json/version/']) {
      for (const authorization of ['', `Bearer ${token}x`]) {
        const response = await fetch(new URL(path, server.url), {
          headers: { authorization, upgrade: 'websocket' },
        });
        expect(response.status).toBe(401);
        expect(response.headers.get('www-authenticate')).toBe('Bearer');
      }
    }
    expect(starts).toBe(0);
  });

  test('rejects unsupported routes and methods without starting Chromium', async () => {
    const headers = { authorization: `Bearer ${token}` };
    expect((await fetch(new URL('/cdp', server.url), { headers })).status).toBe(426);
    expect((await fetch(new URL('/cdp/json/version', server.url), { headers, method: 'POST' })).status).toBe(405);
    expect((await fetch(new URL('/cdp/anything', server.url), { headers })).status).toBe(404);
    expect(starts).toBe(0);
  });

  test('reports unavailable Chromium without leaking internal details', async () => {
    const response = await fetch(new URL('/cdp/json/version', server.url), {
      headers: { authorization: `Bearer ${token}` },
    });
    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ error: 'Live Chromium CDP unavailable' });
  });
});
