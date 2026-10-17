import { chromium } from '/app/node_modules/playwright';
const api='http://127.0.0.1:3036';
const timeoutMs=Number(process.env.LUPA_TEST_TIMEOUT_MS||30000);
if(!Number.isInteger(timeoutMs)||timeoutMs<1000||timeoutMs>120000)throw new Error('LUPA_TEST_TIMEOUT_MS must be 1000–120000');
const token=process.env.LUPA_API_TOKEN_FILE ? (await Bun.file(process.env.LUPA_API_TOKEN_FILE).text()).trim() : process.env.LUPA_API_TOKEN;
const headers={authorization:`Bearer ${token}`, 'content-type':'application/json'};
async function post(path:string,body:any){const r=await fetch(api+path,{method:'POST',headers,body:JSON.stringify(body),signal:AbortSignal.timeout(timeoutMs)});if(!r.ok)throw new Error(await r.text());return r.json() as Promise<any>;}
const fixture=Bun.serve({hostname:'127.0.0.1',port:0,fetch:()=>new Response(`<!doctype html><title>Lupa stream test</title><style>body{margin:0;background:#123;color:white;font:24px sans-serif}button,input{font-size:24px}</style><h1>Lupa stream test</h1><button id="click" onclick="this.textContent='REMOTE CLICK OK'">Click remotely</button><input id="text"><canvas id="c" width="400" height="200"></canvas><script>let t=0;const c=document.querySelector('canvas').getContext('2d');setInterval(()=>{c.fillStyle='hsl('+(t++%360)+',90%,50%)';c.fillRect(0,0,400,200)},50)</script>`,{headers:{'Content-Type':'text/html'}})});
console.log('desktop: open fixture');
await post('/live',{url:`http://127.0.0.1:${fixture.port}`});
console.log('desktop: launch viewer');
const browser=await chromium.launch({channel:'chromium',headless:true,timeout:timeoutMs,args:['--no-sandbox','--autoplay-policy=no-user-gesture-required']});
const password=process.env.SELKIES_PASSWORD || process.env.PASSWORD;
console.log('desktop: create viewer context');
const context=await browser.newContext({httpCredentials:password?{username:process.env.SELKIES_USER || process.env.CUSTOM_USER || 'lupa',password}:undefined,viewport:{width:1280,height:800},permissions:['clipboard-read','clipboard-write']});
context.setDefaultTimeout(timeoutMs);
context.setDefaultNavigationTimeout(timeoutMs);
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
console.log('desktop: create viewer page');
const page=await context.newPage();
const logs:any[]=[];page.on('console',m=>{if(m.type()==='error'||m.type()==='warning')logs.push(m.text());});page.on('pageerror',e=>logs.push(e.message));
let binaryBytes=0;page.on('websocket',ws=>ws.on('framereceived',e=>{if(Buffer.isBuffer(e.payload))binaryBytes+=e.payload.length;}));
const report:any={timeoutMs,configuredFramerate:process.env.SELKIES_FRAMERATE||'60',failedRequests:[]};
page.on('response',response=>{if(response.status()>=400)report.failedRequests.push({path:new URL(response.url()).pathname,status:response.status()});});
try {
  console.log('desktop: load dashboard');
  await page.goto('http://127.0.0.1:3000/',{waitUntil:'networkidle'});
  const play=page.getByRole('button',{name:'Play Stream',exact:true});
  await page.waitForTimeout(2000);
  if(await play.isVisible())await play.click();
  await page.waitForTimeout(3000);
  report.body=(await page.locator('body').innerText()).slice(0,4000);
  report.buttons=await page.locator('button').evaluateAll(bs=>bs.map(b=>({text:b.textContent,title:b.getAttribute('title'),'aria-label':b.getAttribute('aria-label')})));
  console.log('desktop: capture dashboard');
  await page.screenshot({path:'/tmp/lupa-verify/desktop-before.png'});
  // A user gesture unlocks audio in dashboards that wait for interaction.
  await page.mouse.click(500,400);
  await page.waitForTimeout(3000);
  await post('/live/eval',{script:'const ctx=new AudioContext();const osc=ctx.createOscillator();const g=ctx.createGain();g.gain.value=.5;osc.frequency.value=440;osc.connect(g).connect(ctx.destination);osc.start();window.streamTone={ctx,osc};return ctx.state;'});
  console.log('desktop: measure audio and video');
  // Sample in the viewer to avoid adding one CDP round trip per sample.
  const peak=await page.evaluate(async()=>{
    let peak=0;
    for(let i=0;i<30;i++){
      for(const a of (window as any).__stream.audioAnalysers){
        const samples=new Float32Array(a.fftSize);a.getFloatTimeDomainData(samples);
        for(const v of samples)peak=Math.max(peak,Math.abs(v));
      }
      if(peak>.01)break;
      await new Promise(resolve=>setTimeout(resolve,100));
    }
    return peak;
  });
  report.stream=await page.evaluate(()=>({videoDecodes:(window as any).__stream.videoDecodes,draws:(window as any).__stream.draws,audioNodes:(window as any).__stream.audioAnalysers.length}));
  // Map DOM coordinates through Chromium's toolbar into the streamed X desktop.
  const canvasBox=await page.locator('canvas').first().boundingBox();
  async function remotePoint(selector:string){
    const {result}=await post('/live/eval',{script:`const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2+outerHeight-innerHeight,w:screen.width,h:screen.height};`});
    return {x:canvasBox!.x+result.x*canvasBox!.width/result.w,y:canvasBox!.y+result.y*canvasBox!.height/result.h};
  }
  console.log('desktop: remote mouse, keyboard and clipboard');
  let point=await remotePoint('#click');await page.mouse.click(point.x,point.y);await page.waitForTimeout(500);
  report.remoteClick=(await post('/live/eval',{script:'return document.querySelector("#click").textContent;'})).result;
  point=await remotePoint('#text');await page.mouse.click(point.x,point.y);
  // Queue each down/up pair together. Waiting for a CDP round trip between
  // them can leave a key held long enough for X11 autorepeat on a slow host.
  const keyboardSession=await context.newCDPSession(page);
  const keyEvents:Promise<unknown>[]=[];
  const dispatch=(type:'keyDown'|'keyUp',key:string,code:string,windowsVirtualKeyCode:number,modifiers=0,text?:string)=>
    keyEvents.push(keyboardSession.send('Input.dispatchKeyEvent',{type,key,code,windowsVirtualKeyCode,modifiers,...(text?{text}:{} )}));
  for(const character of 'Selkies input OK'){
    const shifted=/[A-Z]/.test(character);
    const code=character===' '?'Space':'Key'+character.toUpperCase();
    const vk=character.toUpperCase().charCodeAt(0);
    if(shifted)dispatch('keyDown','Shift','ShiftLeft',16,8);
    dispatch('keyDown',character,code,vk,shifted?8:0,character);
    dispatch('keyUp',character,code,vk,shifted?8:0);
    if(shifted)dispatch('keyUp','Shift','ShiftLeft',16);
  }
  await Promise.all(keyEvents);await keyboardSession.detach();
  const keyboardDeadline=performance.now()+timeoutMs;
  do{
    report.remoteKeyboard=(await post('/live/eval',{script:'return document.querySelector("#text").value;'})).result;
    if(report.remoteKeyboard==='Selkies input OK')break;
    await Bun.sleep(250);
  }while(performance.now()<keyboardDeadline);
  await page.evaluate(()=>window.postMessage({type:'clipboardUpdateFromUI',text:'Clipboard OK'},window.location.origin));
  await page.waitForTimeout(700);
  await page.keyboard.press('Control+a');await page.keyboard.press('Control+v');await page.waitForTimeout(700);
  report.remoteClipboard=(await post('/live/eval',{script:'return document.querySelector("#text").value;'})).result;
  console.log('desktop: resize');
  const {result:sizeBefore}=await post('/live/eval',{script:'return {width:screen.width,height:screen.height};'});
  await page.setViewportSize({width:1120,height:740});
  const resizeDeadline=performance.now()+timeoutMs;
  let sizeAfter=sizeBefore;
  do{
    sizeAfter=(await post('/live/eval',{script:'return {width:screen.width,height:screen.height};'})).result;
    if(sizeAfter.width!==sizeBefore.width)break;
    await Bun.sleep(250);
  }while(performance.now()<resizeDeadline);
  report.resize={before:sizeBefore,after:sizeAfter};
  report.audioPeak=peak;report.binaryBytes=binaryBytes;
  report.canvases=await page.locator('canvas').evaluateAll(cs=>cs.map(c=>({width:c.width,height:c.height,visible:!!c.getBoundingClientRect().width})));
  report.errors=logs;
  console.log('desktop: wait for repainted frame after resize');
  // Resizing a canvas clears it before the remote full frame arrives. Check a
  // stable region of the fixture background, not only the server dimensions.
  await page.waitForFunction(()=>{
    const canvas=document.querySelector('canvas');
    const ctx=canvas?.getContext('2d');
    if(!canvas||!ctx)return false;
    const pixel=ctx.getImageData(Math.floor(canvas.width*.1),Math.floor(canvas.height*.8),1,1).data;
    return Math.abs(pixel[0]-17)<20&&Math.abs(pixel[1]-34)<20&&Math.abs(pixel[2]-51)<20;
  },null,{timeout:timeoutMs,polling:250});
  report.frameRepainted=true;
  console.log('desktop: capture final frame');
  await page.screenshot({path:'/tmp/lupa-verify/desktop.png'});
  report.ok=report.stream.videoDecodes>5 && peak>.01 && report.remoteClick==='REMOTE CLICK OK' && report.remoteKeyboard==='Selkies input OK' && report.remoteClipboard==='Clipboard OK' && sizeAfter.width!==sizeBefore.width;
} finally {
  await Bun.write('/tmp/lupa-verify/desktop.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
  await browser.close();await post('/live',{url:'about:blank'});fixture.stop(true);
}
if(!report.ok)process.exitCode=1;
