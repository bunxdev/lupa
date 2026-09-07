const out='/tmp/lupa-comparison';
const url=process.argv[2];
const probe=await Bun.file(out+'/probe.js').text();
const result={name:'lupa',adapter:'HTTP API',runs:[]};
const req=async(path,body)=>{
 const response=await fetch('http://127.0.0.1:3036'+path,{method:'POST',headers:{Authorization:'Bearer '+process.env.LUPA_API_TOKEN,'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(30000)});
 if(!response.ok)throw new Error(path+' HTTP '+response.status);return response;
};
for(let i=0;i<3;i++){
 const t=performance.now();const r=await(await req('/eval',{url,script:`return (${probe})()`})).json();
 result.runs.push({request_ms:performance.now()-t,checks:r.result,pageErrors:r.pageErrors});
}
result.interaction=(await(await req('/eval',{url,script:"document.querySelector('#name').value='Lupa';document.querySelector('#go').click();return document.querySelector('#greeting').textContent"})).json()).result;
for(const [key,path] of [['screenshot','/screenshot'],['pdf','/pdf']]){
 const start=performance.now();const r=await req(path,{url,viewport:{width:800,height:600},fullPage:false});await Bun.write(`${out}/${key==='pdf'?'lupa.pdf':'lupa.png'}`,await r.arrayBuffer());result[key]={ok:true,ms:performance.now()-start};
}
await Bun.write(out+'/lupa.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
