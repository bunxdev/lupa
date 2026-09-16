// Real protocol test against an already-running Lupa. No model/API provider needed.
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
const env=Object.fromEntries(Object.entries(process.env).filter((e):e is [string,string]=>e[1]!==undefined));
const client=new Client({name:'lupa-smoke',version:'1'});
const transport=new StdioClientTransport({command:process.execPath,args:['run',resolve(import.meta.dir,'index.ts')],env,stderr:'pipe'});
const url="data:text/html,"+encodeURIComponent(`<title>Lupa MCP test</title><h1>MCP ready</h1><label>Search<input id="query"></label><button id="submit" onclick="document.querySelector('h1').textContent=document.querySelector('input').value">Apply</button>`);
async function call(name:string,args={}){const r:any=await client.callTool({name,arguments:args},undefined,{timeout:90000});if(r.isError)throw Error(JSON.stringify(r));return r;}
const json=(r:any)=>JSON.parse(r.content[0].text);
let previous:any;
try {
 await client.connect(transport);
 const tools=await client.listTools();if(tools.tools.length!==21)throw Error('missing tools');
 previous=json(await call('lupa_live_status'));
 await call('lupa_health');await call('lupa_live_open',{url});
 const inspected=json(await call('lupa_live_inspect'));
 if(inspected.result.title!=='Lupa MCP test'||!inspected.result.controls.some((c:any)=>c.selector==='#query'))throw Error('inspection mismatch');
 await call('lupa_live_click',{selector:'#query'});await call('lupa_live_type',{text:'MCP works'});await call('lupa_live_click',{selector:'#submit'});
 if(json(await call('lupa_live_eval',{script:'return document.querySelector("h1").textContent;'})).result!=='MCP works')throw Error('interaction failed');
 const screenshot=await call('lupa_live_screenshot');if(screenshot.content[1].type!=='image')throw Error('image missing');
 const pdf=json(await call('lupa_pdf',{url}));if(!(await readFile(pdf.path)).subarray(0,5).equals(Buffer.from('%PDF-')))throw Error('invalid PDF');
 const resource:any=await client.readResource({uri:pdf.uri});if(resource.contents[0].mimeType!=='application/pdf')throw Error('PDF resource missing');
 if(json(await call('lupa_eval',{url,script:'return document.title;'})).result!=='Lupa MCP test')throw Error('isolated evaluation failed');
 console.log(JSON.stringify({ok:true,tools:tools.tools.length,checks:['stdio initialization','discovery','health','visible navigation','inspection','click/type','live JS','PNG','PDF','MCP resource read','isolated JS'],pdf:pdf.path}));
} finally {
 if(previous?.open&&previous?.url)await call('lupa_live_open',{url:previous.url}).catch(()=>{});
 else if(previous)await call('lupa_live_close').catch(()=>{});
 await client.close();
}
