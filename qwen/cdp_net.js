// Captura las respuestas de red de la página live de Lupa vía CDP crudo (bun, sin dependencias).
// Uso: TOKEN=<token> bun qwen/cdp_net.js [url-destino]
// Guarda cada respuesta filtrada en /tmp/cap_N.json como {url, body}.
import fs from 'node:fs';

const TOKEN = process.env.TOKEN;
if (!TOKEN) { console.error('Falta TOKEN'); process.exit(1); }
const API = (process.env.LUPA_URL || 'http://127.0.0.1:3136').replace(/\/$/, '');
const target = process.argv[2] || 'https://www.google.com/maps/search/veterinarias%20en%20Zapopan?hl=es&gl=mx';
const FILTER = /tbm=map|\/search|\/maps\//;

const ws = new WebSocket(API.replace('http://', 'ws://') + '/cdp', { headers: { Authorization: 'Bearer ' + TOKEN } });
let seq = 0;
const pending = new Map();
const captured = [];

function send(method, params = {}, sessionId) {
  return new Promise((resolve, reject) => {
    const id = ++seq;
    pending.set(id, { resolve, reject });
    const msg = { id, method, params };
    if (sessionId) msg.sessionId = sessionId;
    ws.send(JSON.stringify(msg));
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(new Error('timeout ' + method)); } }, 30000);
  });
}

ws.onmessage = async (ev) => {
  const m = JSON.parse(typeof ev.data === 'string' ? ev.data : Buffer.from(ev.data).toString('utf8'));
  if (m.id && pending.has(m.id)) {
    const p = pending.get(m.id);
    pending.delete(m.id);
    if (m.error) p.reject(new Error(m.error.message)); else p.resolve(m.result);
    return;
  }
  if (m.method === 'Network.responseReceived' && FILTER.test(m.params.response.url)) {
    captured.push({ url: m.params.response.url, requestId: m.params.requestId, sessionId: m.sessionId, done: false });
  }
  if (m.method === 'Network.loadingFinished') {
    const c = captured.find(x => x.requestId === m.params.requestId && !x.done);
    if (!c) return;
    try {
      const r = await send('Network.getResponseBody', { requestId: c.requestId }, c.sessionId);
      c.body = r.base64Encoded ? Buffer.from(r.body, 'base64').toString('utf8') : r.body;
      c.done = true;
      console.error('capturado:', c.url.slice(0, 150), 'len:', (c.body || '').length);
    } catch (e) {
      c.bodyError = e.message;
      c.done = true;
      console.error('body falló:', e.message, c.url.slice(0, 100));
    }
  }
};

ws.onerror = (e) => { console.error('ws error:', e.message || e); process.exit(1); };

ws.onopen = async () => {
  try {
    const { targetInfos } = await send('Target.getTargets');
    const page = targetInfos.find(t => t.type === 'page' && t.url.includes('google.com/maps')) || targetInfos.find(t => t.type === 'page');
    if (!page) throw new Error('sin target de página');
    console.error('target actual:', page.url.slice(0, 100));
    const { sessionId } = await send('Target.attachToTarget', { targetId: page.targetId, flatten: true });
    await send('Page.enable', {}, sessionId);
    await send('Network.enable', {}, sessionId);
    console.error('navegando a:', target);
    await fetch(API + '/live', {
      method: 'POST',
      headers: { Authorization: 'Bearer ' + TOKEN, 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: target }),
    });
    await new Promise(r => setTimeout(r, 15000));
    captured.forEach((c, i) => {
      if (!c.body) return;
      fs.writeFileSync('/tmp/cap_' + i + '.json', JSON.stringify({ url: c.url, body: c.body }));
      console.error('guardado /tmp/cap_' + i + '.json  ' + c.url.slice(0, 120));
    });
    console.log(JSON.stringify({ captured: captured.map(c => ({ url: c.url.slice(0, 220), len: (c.body || '').length, done: c.done, err: c.bodyError })) }));
    ws.close();
    process.exit(0);
  } catch (e) {
    console.error('falla:', e.message);
    process.exit(1);
  }
};
