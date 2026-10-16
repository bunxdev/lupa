// Run from deploy/slim after building and starting the dedicated test instance.
// Bun loads .env here. A token file must also be readable on this host.
const token=(process.env.LUPA_API_TOKEN_FILE ? await Bun.file(process.env.LUPA_API_TOKEN_FILE).text() : process.env.LUPA_API_TOKEN || "").trim();
if(!token)throw new Error("LUPA_API_TOKEN or LUPA_API_TOKEN_FILE is required");
process.env.LUPA_API_TOKEN=token;
const compose=['docker','compose','-p',process.env.LUPA_COMPOSE_PROJECT||'lupa-validation','-f','lupa.yml'];
const headers={authorization:`Bearer ${token}`, 'content-type':'application/json'};
const base=`http://127.0.0.1:${process.env.LUPA_API_PORT||3136}`;
async function api(path:string,body?:unknown){const r=await fetch(base+path,{headers,method:body===undefined?'GET':'POST',body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(20000)});if(!r.ok)throw new Error(`${path}: ${r.status}`);return r.json() as Promise<any>;}
async function command(args:string[],allowFail=false){const p=Bun.spawn(args,{stdout:'pipe',stderr:'pipe'});const out=await new Response(p.stdout).text();const err=await new Response(p.stderr).text();const code=await p.exited;if(code&&!allowFail)throw new Error(err||out);return {out,err,code};}
const result:any={};
await api('/live',{url:'about:blank'});
await api('/live/cookies/add',{cookies:[{name:'lifecycle',value:'preserved',domain:'lupa.test',path:'/',expires:Math.floor(Date.now()/1000)+3600}]});
await api('/extension/run',{extension:'lupa-test',url:'http://127.0.0.1:3036/health',fresh:true,script:'document.cookie="extensionLifecycle=preserved; Max-Age=3600; path=/"; return document.cookie;'});
const started=performance.now();
await command([...compose,'up','-d','--no-build','--force-recreate','--wait','--wait-timeout','120']);
result.recreateSeconds=Number(((performance.now()-started)/1000).toFixed(2));
const cookies=await api('/live/cookies');
result.cookiesPersisted=cookies.cookies.some((c:any)=>c.name==='lifecycle'&&c.value==='preserved');
if(!result.cookiesPersisted)throw new Error('Cookie lost on container recreation');
const extension=await api('/extension/run',{extension:'lupa-test',url:'http://127.0.0.1:3036/health',script:'return document.cookie;'});
result.extensionProfilePersisted=extension.result.includes('extensionLifecycle=preserved');
if(!result.extensionProfilePersisted)throw new Error('Extension profile lost on recreation');
const id=(await command([...compose,'ps','-q','lupa'])).out.trim();
const lock=await command(['docker','exec',id,'flock','-n','/config/.lupa-runtime.lock','true'],true);
result.volumeExclusive=lock.code!==0;
if(!result.volumeExclusive)throw new Error('Profile volume lock not held');
// A new empty profile must start without network access or runtime downloads.
const offline=(process.env.LUPA_COMPOSE_PROJECT||'lupa-validation')+'-offline-check';
try{
 await command(['docker','run','-d','--name',offline,'--network','none','--shm-size','512m','-e','LUPA_API_TOKEN','-e','SELKIES_USER=validation','-e','SELKIES_PASSWORD=validation-only',process.env.LUPA_IMAGE||'bunxdev/lupa:0.0.3']);
 for(let i=0;i<90;i++){
  const h=await command(['docker','inspect',offline,'--format','{{.State.Health.Status}}']);
  if(h.out.trim()==='healthy'){result.offlineStartup=true;break;}
  await Bun.sleep(1000);
 }
 if(!result.offlineStartup)throw new Error('Offline empty-profile startup did not become healthy');
 const denied=await command(['docker','exec',offline,'curl','-sS','-o','/dev/null','-w','%{http_code}','http://127.0.0.1:3000/']);
 const allowed=await command(['docker','exec',offline,'curl','-sS','-u','validation:validation-only','-o','/dev/null','-w','%{http_code}','http://127.0.0.1:3000/']);
 result.desktopBasicAuth=denied.out==='401'&&allowed.out==='200';
 if(!result.desktopBasicAuth)throw new Error('Desktop Basic auth failed');
 const config=await command(['docker','exec',offline,'du','-sb','/config']);
 result.freshProfileBytes=Number(config.out.split(/\s/)[0]);
 const download=await command(['docker','exec',id,'cat','/config/Downloads/lupa-verify.txt']);
 result.downloadPersisted=download.out.includes('Lupa persisted download');
 if(!result.downloadPersisted)throw new Error('Download missing after recreation');
}finally{await command(['docker','rm','-fv',offline],true);}
await Bun.write('reports/lifecycle.json',JSON.stringify({timestamp:new Date().toISOString(),...result},null,2)+'\n');
console.log(JSON.stringify(result,null,2));
