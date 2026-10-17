import { describe, expect, test } from 'bun:test';
import { createHandler } from './routes';

const token = '0123456789abcdef0123456789abcdef';
const handle = createHandler({ apiToken: token, maxBodyBytes: 256 });

describe('HTTP security boundary', () => {
  test('health and selftest remain public', async () => {
    expect((await handle(new Request('http://localhost/health'))).status).toBe(200);
    expect((await handle(new Request('http://localhost/selftest'))).status).toBe(200);
  });

  test('control endpoints require the exact bearer token', async () => {
    const missing = await handle(new Request('http://localhost/live'));
    const wrong = await handle(new Request('http://localhost/live', {
      headers: { authorization: `Bearer ${token}x` },
    }));
    expect(missing.status).toBe(401);
    expect(missing.headers.get('www-authenticate')).toBe('Bearer');
    expect(wrong.status).toBe(401);
  });

  test('rejects oversized and non-json request bodies before browser work', async () => {
    const headers = { authorization: `Bearer ${token}`, 'content-type': 'application/json' };
    const oversized = await handle(new Request('http://localhost/render', {
      method: 'POST', headers, body: JSON.stringify({ html: 'x'.repeat(300) }),
    }));
    const wrongType = await handle(new Request('http://localhost/render', {
      method: 'POST', headers: { authorization: `Bearer ${token}` }, body: '{}',
    }));
    expect(oversized.status).toBe(413);
    expect(wrongType.status).toBe(415);
  });

  test('rejects invalid live navigation readiness before browser work', async () => {
    for (const waitFor of ['invalid', 12, null]) {
      const response = await handle(new Request('http://localhost/live', {
        method: 'POST',
        headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' },
        body: JSON.stringify({ url: 'https://example.com', waitFor }),
      }));
      expect(response.status).toBe(400);
    }
  });

  test('validates viewport bounds before browser work', async () => {
    const response = await handle(new Request('http://localhost/screenshot', {
      method: 'POST',
      headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' },
      body: JSON.stringify({ url: 'https://example.com', viewport: { width: -1, height: 720 } }),
    }));
    expect(response.status).toBe(400);
  });
});
