// Captura los XHR de "cargar más" de Maps mientras se hace scroll en la página live.
// Uso: TOKEN=<token> bun qwen/cdp_net_scroll.js [query-para-asegurar-búsqueda]
import fs from 'node:fs';

const TOKEN = process.env.TOKEN;
if (!TOKEN) { console.error('Falta TOKEN'); process.exit(1); }
const API = (process.env.LUPA_URL || 'http://127.0.0.1:3136').replace(/\/$/, '');
const FILTER = /\/search\?tbm=map|s\?tbm=map/;
const SCROLLS = Number(process.env.SCROLLS || 6);

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

async function liveEval(script) {
  const r = await fetch(API + '/live/eval', {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + TOKEN, 'Content-Type': 'application/json' },
    body: JSON.stringify({ script }),
  });
  return (await r.json()).result;
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
    console.error('xhr visto:', captured.length, m.params.response.url.slice(0, 120));
  }
  if (m.method === 'Network.loadingFinished') {
    const c = captured.find(x => x.requestId === m.params.requestId && !x.done);
    if (!c) return;
    try {
      const r = await send('Network.getResponseBody', { requestId: c.requestId }, c.sessionId);
      c.body = r.base64Encoded ? Buffer.from(r.body, 'base64').toString('utf8') : r.body;
      c.done = true;
      console.error('cuerpo guardado len:', (c.body || '').length);
    } catch (e) { c.done = true; c.bodyError = e.message; }
  }
};

ws.onerror = (e) => { console.error('ws error:', e.message || e); process.exit(1); };

ws.onopen = async () => {
  try {
    const { targetInfos } = await send('Target.getTargets');
    const page = targetInfos.find(t => t.type === 'page') ;
    const { sessionId } = await send('Target.attachToTarget', { targetId: page.targetId, flatten: true });
    await send('Network.enable', {}, sessionId);
    const state = JSON.parse(await liveEval('return JSON.stringify({href:location.href.slice(0,120),cards:document.querySelectorAll("[role=feed] a[href*=\'/maps/place/\']").length})'));
    console.error('estado live:', JSON.stringify(state));
    for (let i = 0; i < SCROLLS; i++) {
      await liveEval('const f=document.querySelector("[role=feed]"); if(f){f.scrollTop=f.scrollHeight;} return (f&&f.scrollHeight)||0');
      await new Promise(r => setTimeout(r, 2500));
    }
    captured.forEach((c, i) => {
      if (!c.body) return;
      fs.writeFileSync('/tmp/scrollcap_' + i + '.json', JSON.stringify({ url: c.url, body: c.body }));
      console.error('guardado /tmp/scrollcap_' + i + '.json');
    });
    console.log(JSON.stringify({ n: captured.length, urls: captured.map(c => ({ url: c.url.slice(0, 250), len: (c.body || '').length })) }));
    ws.close();
    process.exit(0);
  } catch (e) {
    console.error('falla:', e.message);
    process.exit(1);
  }
};
