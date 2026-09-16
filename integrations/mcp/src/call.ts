// Use the same MCP protocol from a shell when the host cannot reload its tool list.
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { resolve } from 'node:path';
const client=new Client({name:'lupa-cli',version:'0.1.0'});
const env=Object.fromEntries(Object.entries(process.env).filter((e):e is [string,string]=>e[1]!==undefined));
try {
 const name=process.argv[2]||'list';
 const args=JSON.parse(process.argv[3]||'{}');
 await client.connect(new StdioClientTransport({command:process.execPath,args:['run',resolve(import.meta.dir,'index.ts')],env,stderr:'inherit'}));
 const result=name==='list'?await client.listTools():await client.callTool({name,arguments:args},undefined,{timeout:300000});
 console.log(JSON.stringify(result,null,2));
 if('isError' in result&&result.isError)process.exitCode=1;
}finally{await client.close();}
