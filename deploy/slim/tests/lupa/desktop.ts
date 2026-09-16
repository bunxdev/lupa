import { chromium } from '/app/node_modules/playwright';
const api='http://127.0.0.1:3036';
const headers={authorization:`Bearer ${process.env.LUPA_API_TOKEN}`, 'content-type':'application/json'};
async function post(path:string,body:any){const r=await fetch(api+path,{method:'POST',headers,body:JSON.stringify(body)});if(!r.ok)throw new Error(await r.text());return r.json() as Promise<any>;}
const fixture=Bun.serve({hostname:'127.0.0.1',port:0,fetch:()=>new Response(`<!doctype html><title>Lupa stream test</title><style>body{margin:0;background:#123;color:white;font:24px sans-serif}button,input{font-size:24px}</style><h1>Lupa stream test</h1><button id="click" onclick="this.textContent='REMOTE CLICK OK'">Click remotely</button><input id="text"><canvas id="c" width="400" height="200"></canvas><script>let t=0;const c=document.querySelector('canvas').getContext('2d');setInterval(()=>{c.fillStyle='hsl('+(t++%360)+',90%,50%)';c.fillRect(0,0,400,200)},50)</script>`,{headers:{'Content-Type':'text/html'}})});
await post('/live',{url:`http://127.0.0.1:${fixture.port}`});
const browser=await chromium.launch({channel:'chromium',headless:true,args:['--no-sandbox','--autoplay-policy=no-user-gesture-required']});
const context=await browser.newContext({viewport:{width:1280,height:800},permissions:['clipboard-read','clipboard-write']});
await context.addInitScript(()=>{
  const w=window as any;w.__stream={videoDecodes:0,draws:0,audioAnalysers:[],websockets:0};
  const originalDecode=VideoDecoder.prototype.decode;
  VideoDecoder.prototype.decode=function(...args:any[]){w.__stream.videoDecodes++;return originalDecode.apply(this,args as any);};
  const connect=AudioNode.prototype.connect;
  AudioNode.prototype.connect=function(destination:any,...rest:any[]){
    if(destination instanceof AudioDestinationNode){
      const analyser=(this.context as AudioContext).createAnalyser();analyser.fftSize=2048;
      w.__stream.audioAnalysers.push(analyser);connect.call(this,analyser);return connect.call(analyser,destination);
    }
    return connect.apply(this,[destination,...rest] as any);
  } as any;
  for(const method of ['drawImage','putImageData']) {
    const old=(CanvasRenderingContext2D.prototype as any)[method];
    (CanvasRenderingContext2D.prototype as any)[method]=function(...args:any[]){w.__stream.draws++;return old.apply(this,args);};
  }
});
const page=await context.newPage();
const logs:any[]=[];page.on('console',m=>{if(m.type()==='error'||m.type()==='warning')logs.push(m.text());});page.on('pageerror',e=>logs.push(e.message));
let binaryBytes=0;page.on('websocket',ws=>ws.on('framereceived',e=>{if(Buffer.isBuffer(e.payload))binaryBytes+=e.payload.length;}));
const report:any={failedRequests:[]};
page.on('response',response=>{if(response.status()>=400)report.failedRequests.push({path:new URL(response.url()).pathname,status:response.status()});});
try {
  await page.goto('http://127.0.0.1:3000/',{waitUntil:'networkidle'});
  const play=page.getByRole('button',{name:'Play Stream',exact:true});
  await page.waitForTimeout(2000);
  if(await play.isVisible())await play.click();
  await page.waitForTimeout(3000);
  report.body=(await page.locator('body').innerText()).slice(0,4000);
  report.buttons=await page.locator('button').evaluateAll(bs=>bs.map(b=>({text:b.textContent,title:b.getAttribute('title'),'aria-label':b.getAttribute('aria-label')})));
  await page.screenshot({path:'/tmp/lupa-verify/desktop-before.png'});
  // A user gesture unlocks audio in dashboards that wait for interaction.
  await page.mouse.click(500,400);
  await page.waitForTimeout(3000);
  await post('/live/eval',{script:'const ctx=new AudioContext();const osc=ctx.createOscillator();const g=ctx.createGain();g.gain.value=.5;osc.frequency.value=440;osc.connect(g).connect(ctx.destination);osc.start();window.streamTone={ctx,osc};return ctx.state;'});
  let peak=0;
  for(let i=0;i<30;i++){
    peak=Math.max(peak,await page.evaluate(()=>{let p=0;for(const a of (window as any).__stream.audioAnalysers){const samples=new Float32Array(a.fftSize);a.getFloatTimeDomainData(samples);for(const v of samples)p=Math.max(p,Math.abs(v));}return p;}));
    await page.waitForTimeout(100);
  }
  report.stream=await page.evaluate(()=>({videoDecodes:(window as any).__stream.videoDecodes,draws:(window as any).__stream.draws,audioNodes:(window as any).__stream.audioAnalysers.length}));
  // Map DOM coordinates through Chromium's toolbar into the streamed X desktop.
  const canvasBox=await page.locator('canvas').first().boundingBox();
  async function remotePoint(selector:string){
    const {result}=await post('/live/eval',{script:`const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2+outerHeight-innerHeight,w:screen.width,h:screen.height};`});
    return {x:canvasBox!.x+result.x*canvasBox!.width/result.w,y:canvasBox!.y+result.y*canvasBox!.height/result.h};
  }
  let point=await remotePoint('#click');await page.mouse.click(point.x,point.y);await page.waitForTimeout(500);
  report.remoteClick=(await post('/live/eval',{script:'return document.querySelector("#click").textContent;'})).result;
  point=await remotePoint('#text');await page.mouse.click(point.x,point.y);await page.keyboard.press('Shift+KeyS');await page.keyboard.type('elkies input ');await page.keyboard.press('Shift+KeyO');await page.keyboard.press('Shift+KeyK');await page.waitForTimeout(500);
  report.remoteKeyboard=(await post('/live/eval',{script:'return document.querySelector("#text").value;'})).result;
  await page.evaluate(()=>window.postMessage({type:'clipboardUpdateFromUI',text:'Clipboard OK'},window.location.origin));
  await page.waitForTimeout(700);
  await page.keyboard.press('Control+a');await page.keyboard.press('Control+v');await page.waitForTimeout(700);
  report.remoteClipboard=(await post('/live/eval',{script:'return document.querySelector("#text").value;'})).result;
  const {result:sizeBefore}=await post('/live/eval',{script:'return {width:screen.width,height:screen.height};'});
  await page.setViewportSize({width:1120,height:740});await page.waitForTimeout(2500);
  const {result:sizeAfter}=await post('/live/eval',{script:'return {width:screen.width,height:screen.height};'});
  report.resize={before:sizeBefore,after:sizeAfter};
  report.audioPeak=peak;report.binaryBytes=binaryBytes;
  report.canvases=await page.locator('canvas').evaluateAll(cs=>cs.map(c=>({width:c.width,height:c.height,visible:!!c.getBoundingClientRect().width})));
  report.errors=logs;
  await page.screenshot({path:'/tmp/lupa-verify/desktop.png'});
  report.ok=report.stream.videoDecodes>5 && peak>.01 && report.remoteClick==='REMOTE CLICK OK' && report.remoteKeyboard==='Selkies input OK' && report.remoteClipboard==='Clipboard OK' && sizeAfter.width!==sizeBefore.width;
} finally {
  await Bun.write('/tmp/lupa-verify/desktop.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
  await browser.close();await post('/live',{url:'about:blank'});fixture.stop(true);
}
if(!report.ok)process.exitCode=1;
