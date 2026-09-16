import type { Server, WebSocketHandler } from 'bun';
import { authorized } from './auth';

export type CdpSocket = { upstream: WebSocket };

export function createCdpGateway(apiToken: string, endpoint: () => Promise<string>) {
  const websocket: WebSocketHandler<CdpSocket> = {
    idleTimeout: 0,
    maxPayloadLength: 64 * 1024 * 1024,
    backpressureLimit: 64 * 1024 * 1024,
    closeOnBackpressureLimit: true,
    open(client) {
      const upstream = client.data.upstream;
      upstream.onmessage = (event) => client.send(event.data);
      upstream.onclose = () => client.close(1011, 'Chromium disconnected');
      upstream.onerror = () => client.close(1011, 'CDP connection failed');
      if (upstream.readyState !== WebSocket.OPEN) client.close(1011, 'Chromium disconnected');
    },
    message(client, message) {
      const upstream = client.data.upstream;
      if (upstream.readyState !== WebSocket.OPEN) {
        client.close(1011, 'Chromium disconnected');
        return;
      }
      if (upstream.bufferedAmount > 64 * 1024 * 1024) {
        client.close(1013, 'CDP client is sending too fast');
        return;
      }
      upstream.send(message);
    },
    close(client) {
      // Disconnect the transport; never send Browser.close to the shared session.
      client.data.upstream.close();
    },
  };

  async function fetch(req: Request, server: Server<CdpSocket>): Promise<Response | undefined> {
    if (!authorized(req, apiToken)) {
      return Response.json({ error: 'unauthorized' }, {
        status: 401, headers: { 'www-authenticate': 'Bearer' },
      });
    }
    const url = new URL(req.url);
    const path = url.pathname.replace(/\/$/, '');
    if (req.method !== 'GET') return new Response('method not allowed', { status: 405, headers: { allow: 'GET' } });
    if (path !== '/cdp' && path !== '/cdp/json/version') return new Response('not found', { status: 404 });
    if (path === '/cdp' && req.headers.get('upgrade')?.toLowerCase() !== 'websocket') {
      return Response.json({ error: 'Use a WebSocket client or GET /cdp/json/version' }, { status: 426 });
    }
    let upstream: WebSocket | undefined;
    try {
      const target = await endpoint();
      if (path === '/cdp/json/version') {
        const discovery = new URL('/json/version', target.replace(/^ws:/, 'http:'));
        const response = await globalThis.fetch(discovery, { signal: AbortSignal.timeout(5000) });
        if (!response.ok) throw new Error('CDP discovery failed');
        const version = await response.json() as Record<string, unknown>;
        url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
        url.pathname = '/cdp';
        url.search = '';
        return Response.json({ ...version, webSocketDebuggerUrl: url.toString() }, {
          headers: { 'cache-control': 'no-store' },
        });
      }
      upstream = new WebSocket(target);
      upstream.binaryType = 'arraybuffer';
      const socket = upstream;
      await new Promise<void>((resolve, reject) => {
        const timer = setTimeout(() => { socket.close(); reject(new Error('CDP connection timeout')); }, 5000);
        socket.onopen = () => { clearTimeout(timer); resolve(); };
        socket.onerror = socket.onclose = () => { clearTimeout(timer); reject(new Error('CDP connection failed')); };
      });
      if (server.upgrade(req, { data: { upstream } })) return;
      upstream.close();
      return new Response('WebSocket upgrade failed', { status: 400 });
    } catch {
      upstream?.close();
      return Response.json({ error: 'Live Chromium CDP unavailable' }, { status: 503 });
    }
  }

  return { fetch, websocket };
}
