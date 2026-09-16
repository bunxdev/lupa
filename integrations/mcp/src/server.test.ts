import { test, expect } from 'bun:test';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createServer } from './server';

async function harness(fetch:(req:Request)=>Response|Promise<Response>, action:(c:Client,dir:string)=>Promise<void>, timeoutMs=1000){
 const http=Bun.serve({port:0,hostname:'127.0.0.1',fetch});
 const dir=await mkdtemp(join(tmpdir(),'lupa-mcp-test-'));
 const server=createServer({baseUrl:`http://127.0.0.1:${http.port}`,token:'test-secret-token',outputDir:dir,timeoutMs});
 const [a,b]=InMemoryTransport.createLinkedPair();const client=new Client({name:'test',version:'1'});
 try{await server.connect(a);await client.connect(b);await action(client,dir);}finally{await client.close();await server.close();http.stop(true);await rm(dir,{recursive:true,force:true});}
}
test('discover tools, preserve authentication and live route; invalid arguments never reach API',async()=>{
 const requests:any[]=[];
 await harness(async req=>{requests.push({path:new URL(req.url).pathname,auth:req.headers.get('authorization'),body:await req.json()});return Response.json({ok:true});},async client=>{
  const {tools}=await client.listTools();expect(tools).toHaveLength(21);
  const ok:any=await client.callTool({name:'lupa_live_open',arguments:{url:'https://example.com'}});expect(ok.isError).not.toBe(true);
  expect(requests).toEqual([{path:'/live',auth:'Bearer test-secret-token',body:{url:'https://example.com'}}]);
  const bad:any=await client.callTool({name:'lupa_live_mouse_click',arguments:{x:999999,y:0}});expect(bad.isError).toBe(true);expect(requests).toHaveLength(1);
 });
});
test('HTTP authentication errors are MCP errors without upstream body/secret',async()=>{
 await harness(()=>new Response('test-secret-token',{status:401}),async client=>{
  const r:any=await client.callTool({name:'lupa_live_status',arguments:{}});expect(r.isError).toBe(true);expect(r.content[0].text).toContain('401');expect(JSON.stringify(r)).not.toContain('test-secret-token');
 });
});
test('binary images and PDFs are saved and readable through MCP resources',async()=>{
 await harness(req=>new Response(new URL(req.url).pathname==='/pdf'?'%PDF-1.7 test':'png-test',{headers:{'content-type':new URL(req.url).pathname==='/pdf'?'application/pdf':'image/png'}}),async(client)=>{
  for(const [name,args,type] of [['lupa_live_screenshot',{},'image'],['lupa_pdf',{url:'https://example.com'},'resource_link']] as const){
   const r:any=await client.callTool({name,arguments:args});expect(r.isError,JSON.stringify(r)).not.toBe(true);expect(r.content[1].type).toBe(type);
   const file=JSON.parse(r.content[0].text);const bytes=await readFile(file.path);expect(bytes.length).toBe(file.bytes);
   const resource:any=await client.readResource({uri:file.uri});expect(resource.contents[0].blob).toBe(bytes.toString('base64'));
  }
 });
});
test('API redirects do not forward the token and timeout returns MCP error',async()=>{
 let redirected=0;const target=Bun.serve({port:0,fetch:()=>{redirected++;return new Response('unexpected');}});
 try{await harness(()=>Response.redirect(`http://127.0.0.1:${target.port}`),async c=>{const r:any=await c.callTool({name:'lupa_health',arguments:{}});expect(r.isError).toBe(true);expect(redirected).toBe(0);});}finally{target.stop(true);}
 await harness(async()=>{await Bun.sleep(100);return Response.json({ok:true});},async c=>{const r:any=await c.callTool({name:'lupa_health',arguments:{}});expect(r.isError).toBe(true);},10);
});
