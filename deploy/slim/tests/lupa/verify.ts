import { chromium } from '/app/node_modules/playwright';
import { mkdir, readFile, stat } from 'node:fs/promises';

const api = `http://127.0.0.1:${process.env.PORT || 3036}`;
const timeoutMs = Number(process.env.LUPA_TEST_TIMEOUT_MS || 30000);
if (!Number.isInteger(timeoutMs) || timeoutMs < 1000 || timeoutMs > 120000) throw new Error('LUPA_TEST_TIMEOUT_MS must be 1000–120000');
const token = process.env.LUPA_API_TOKEN_FILE
  ? (await Bun.file(process.env.LUPA_API_TOKEN_FILE).text()).trim()
  : process.env.LUPA_API_TOKEN;
const headers = { authorization: `Bearer ${token}`, 'content-type': 'application/json' };
const reportDir = '/tmp/lupa-verify';
await mkdir(reportDir, {recursive:true});
const results: any[] = [];
function assert(value: unknown, message: string): asserts value { if (!value) throw new Error(message); }
async function check(name: string, fn: () => Promise<unknown>) {
  try { const details = await fn(); results.push({name,ok:true,details}); console.log(`PASS ${name}: ${JSON.stringify(details)}`); }
  catch(error) { results.push({name,ok:false,error:String(error)}); console.error(`FAIL ${name}: ${error}`); }
}
async function post(path: string, body: unknown = {}) {
  const response = await fetch(api + path, {method:'POST',headers,body:JSON.stringify(body),signal:AbortSignal.timeout(timeoutMs)});
  assert(response.ok, `${path}: HTTP ${response.status} ${await response.clone().text()}`);
  return response;
}
async function liveEval(script: string) { return (await (await post('/live/eval',{script})).json() as any).result; }
const fixture = Bun.serve({hostname:'127.0.0.1',port:0,fetch(req) {
  const path = new URL(req.url).pathname;
  if(path === '/download') return new Response('Lupa persisted download\n', {headers:{'Content-Disposition':'attachment; filename="lupa-verify.txt"','Content-Type':'text/plain'}});
  return new Response(`<!doctype html><title>Lupa compatibility</title><meta charset="utf-8">
    <style>body{margin:24px;background:#123;color:#fff;font:24px sans-serif}button,input{font:24px sans-serif}canvas{display:block}</style>
    <h1>Lupa · 日本語 · Español 😀</h1><input id="name"><button id="go" onclick="document.querySelector('#result').textContent=document.querySelector('#name').value">Enviar</button>
    <p id="result"></p><a id="download" href="/download">Descargar</a><canvas id="canvas" width="320" height="180"></canvas>
    <script>window.answer=42;const c=document.querySelector('canvas');const x=c.getContext('2d');let tick=0;
    function frame(){x.fillStyle='hsl('+(tick++%360)+',90%,50%)';x.fillRect(0,0,320,180);x.fillStyle='white';x.fillText('Frame '+tick,40,80);requestAnimationFrame(frame)}frame();</script>`, {headers:{'Content-Type':'text/html'}});
}});
const url=`http://127.0.0.1:${fixture.port}`;
let client: Awaited<ReturnType<typeof chromium.connectOverCDP>> | undefined;
try {
  await check('authentication',async()=>{
    assert((await fetch(api+'/health')).ok,'health');
    assert((await fetch(api+'/selftest')).ok,'selftest');
    assert((await fetch(api+'/live')).status===401,'live must require token');
    assert((await fetch(api+'/cdp/json/version')).status===401,'CDP must require token');
    return {health:true,selftest:true,protected:true};
  });
  await check('headless-eval-and-isolation',async()=>{
    const script='document.cookie="isolated=1"; return {title:document.title,answer:window.answer,canvas:!!document.querySelector("canvas").getContext("2d")};';
    const data=await(await post('/eval',{url,script})).json() as any;
    assert(data.result.answer===42 && data.result.canvas,'JS/canvas');
    const next=await(await post('/eval',{url,script:'return document.cookie;'})).json() as any;
    assert(!next.result.includes('isolated=1'),'headless contexts share cookies');
    return data.result;
  });
  for (const format of ['png','jpeg']) await check(`screenshot-${format}`,async()=>{
    const response=await post('/screenshot',{url,format,viewport:{width:800,height:600},fullPage:true});
    const bytes=Buffer.from(await response.arrayBuffer());
    assert(format==='png'?bytes.subarray(1,4).toString()==='PNG':bytes[0]===255&&bytes[1]===216,'signature');
    await Bun.write(`${reportDir}/screenshot.${format}`,bytes);return {bytes:bytes.length};
  });
  await check('html-render',async()=>{
    const response=await post('/render',{html:'<h1>Rendered HTML 日本語 😀</h1>',viewport:{width:640,height:480}});
    const bytes=Buffer.from(await response.arrayBuffer());assert(bytes.subarray(1,4).toString()==='PNG','PNG');return {bytes:bytes.length};
  });
  await check('pdf',async()=>{
    const response=await post('/pdf',{url,format:'A4',landscape:true});const bytes=Buffer.from(await response.arrayBuffer());
    assert(bytes.subarray(0,5).toString()==='%PDF-','PDF signature');await Bun.write(`${reportDir}/page.pdf`,bytes);return {bytes:bytes.length};
  });
  await check('content',async()=>{const text=await(await post('/content',{url})).text();assert(text.includes('Lupa compatibility'),'HTML');return {bytes:text.length};});
  await check('extension-isolated-profile',async()=>{
    const data=await(await post('/extension/run',{extension:'lupa-test',url,fresh:true,screenshot:true,script:'return document.documentElement.dataset.lupaExtension;'})).json() as any;
    assert(data.result==='loaded','content script');assert(data.screenshot.length>100,'extension screenshot');return {contentScript:data.result};
  });
  await check('live-keyboard-mouse',async()=>{
    await post('/live',{url,viewport:{width:1024,height:768}});
    await post('/live/click',{selector:'#name'});await post('/live/type',{text:'Lupa slim'});await post('/live/key',{key:'Tab'});await post('/live/key',{key:'Enter'});
    assert(await liveEval('return document.querySelector("#result").textContent;')==='Lupa slim','keyboard/form');
    const bounds=await liveEval('const b=document.querySelector("#go").getBoundingClientRect();return {x:b.x+b.width/2,y:b.y+b.height/2};');
    await post('/live/mouse-move',bounds);await post('/live/mouse-click',bounds);
    const screenshot=await post('/live/screenshot');assert((await screenshot.arrayBuffer()).byteLength>100,'live screenshot');
    assert(await liveEval('return document.documentElement.dataset.lupaExtension;')==='loaded','live extension');return {form:true,coordinates:true,extension:true};
  });
  await check('download-to-host-mount',async()=>{
    await post('/live/click',{selector:'#download'});
    for(let i=0;i<50;i++){try{if((await readFile('/config/Downloads/lupa-verify.txt','utf8')).includes('Lupa persisted'))return {saved:true};}catch{}await Bun.sleep(100);}
    throw new Error('download missing');
  });
  await check('cdp-shared-session',async()=>{
    client=await chromium.connectOverCDP(api+'/cdp',{headers,timeout:timeoutMs});
    const page=client.contexts()[0].pages().find(p=>p.url().startsWith(url));assert(page,'live tab missing');
    await page.evaluate(()=>{document.title='Changed via CDP';});
    assert(await liveEval('return document.title;')==='Changed via CDP','shared title');
    return {shared:true};
  });
  await check('cookie-profile-persistence',async()=>{
    await post('/live/cookies/add',{cookies:[{name:'slim-persist',value:'yes',url,expires:Math.floor(Date.now()/1000)+86400}]});
    await post('/live/close');await client?.close();client=undefined;
    await post('/live',{url});const data=await(await fetch(api+'/live/cookies',{headers})).json() as any;
    assert(data.cookies.some((c:any)=>c.name==='slim-persist'&&c.value==='yes'),'cookie missing after reopen');return {persisted:true};
  });
  await check('audio-pulseaudio',async()=>{
    const data=await liveEval(`const ctx=new AudioContext();const osc=ctx.createOscillator();const gain=ctx.createGain();gain.gain.value=.4;osc.frequency.value=440;osc.connect(gain).connect(ctx.destination);osc.start();window.verifyAudio={ctx,osc};return {state:ctx.state,rate:ctx.sampleRate};`);
    assert(data.state==='running','AudioContext suspended');
    const record=Bun.spawn(['timeout','2','parec','--device=output.monitor','--format=s16le','--rate=48000','--channels=2'],{stdout:'pipe',stderr:'pipe'});
    const bytes=Buffer.from(await new Response(record.stdout).arrayBuffer());await record.exited;
    let peak=0;for(let i=0;i+1<bytes.length;i+=2)peak=Math.max(peak,Math.abs(bytes.readInt16LE(i)));
    assert(peak>500,'silent PulseAudio output');await liveEval('window.verifyAudio.osc.stop();window.verifyAudio.ctx.close();return true;');return {state:data.state,samples:bytes.length/2,peak};
  });
  await check('video-decode',async()=>{
    const data=await liveEval(`const canvas=document.querySelector('canvas');const stream=canvas.captureStream(10);const recorder=new MediaRecorder(stream,{mimeType:'video/webm;codecs=vp8'});const chunks=[];const stopped=new Promise(r=>recorder.onstop=r);recorder.ondataavailable=e=>chunks.push(e.data);recorder.start();await new Promise(r=>setTimeout(r,800));recorder.stop();await stopped;stream.getTracks().forEach(t=>t.stop());const video=document.createElement('video');video.muted=true;video.src=URL.createObjectURL(new Blob(chunks,{type:'video/webm'}));document.body.append(video);await video.play();await new Promise(r=>setTimeout(r,300));return {time:video.currentTime,width:video.videoWidth,frames:video.getVideoPlaybackQuality().totalVideoFrames};`);
    assert(data.time>0 && data.width===320 && data.frames>0,'video decode');return data;
  });
  await check('desktop-http-https',async()=>{
    const user=process.env.SELKIES_USER || process.env.CUSTOM_USER || 'lupa'; const password=process.env.SELKIES_PASSWORD || process.env.PASSWORD || ''; const auth='Basic '+Buffer.from(user+':'+password).toString('base64'); assert((await fetch('http://127.0.0.1:3000/',{headers:password?{authorization:auth}:{}})).ok,'desktop HTTP');
    const https=Bun.spawn(['curl','-kfsS',...(password?['-H','Authorization: '+auth]:[]),'https://127.0.0.1:3001/'],{stdout:'pipe',stderr:'pipe'});
    const body=await new Response(https.stdout).text();assert(await https.exited===0&&body.includes('<html'),'desktop HTTPS');return {http:true,https:true};
  });
} finally {
  await client?.close();
  // Leave the fixture serving only until all tests finish; idle live page stays usable.
  await post('/live',{url:'about:blank'}).catch(()=>{});
  fixture.stop(true);
  await Bun.write(`${reportDir}/results.json`,JSON.stringify({timestamp:new Date().toISOString(),timeoutMs,results},null,2));
}
if(results.some(r=>!r.ok))process.exitCode=1;
