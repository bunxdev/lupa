import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { readFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { resolve } from 'node:path';
import { createServer } from './server';
try {
  const token=process.env.LUPA_API_TOKEN_FILE ? (await readFile(process.env.LUPA_API_TOKEN_FILE,'utf8')).trim() : (process.env.LUPA_API_TOKEN||'').trim();
  const timeoutMs=Number(process.env.LUPA_MCP_TIMEOUT_MS||60000);
  if(!Number.isInteger(timeoutMs)||timeoutMs<1000||timeoutMs>300000)throw Error('Invalid LUPA_MCP_TIMEOUT_MS (1000..300000)');
  const server=createServer({baseUrl:process.env.LUPA_URL||'http://127.0.0.1:3036',token,outputDir:process.env.LUPA_MCP_OUTPUT_DIR||resolve(homedir(),'.local/share/lupa-mcp/artifacts'),timeoutMs});
  await server.connect(new StdioServerTransport());
} catch {
  console.error('Lupa MCP could not start. Check LUPA_URL, API token/file, output directory and timeout configuration.');
  process.exitCode=1;
}
