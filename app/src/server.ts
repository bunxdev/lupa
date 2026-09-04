import { readFileSync } from 'node:fs';
import { createHandler } from './routes';
import { closeBrowser, liveSplash } from './browser';

const PORT = Number(process.env.PORT ?? 3000);
const HOST = process.env.API_HOST ?? '127.0.0.1';
const MAX_BODY_BYTES = Number(process.env.LUPA_MAX_BODY_BYTES ?? 5 * 1024 * 1024);

function loadApiToken(): string {
  const tokenFile = process.env.LUPA_API_TOKEN_FILE;
  const token = tokenFile
    ? readFileSync(tokenFile, 'utf8').trim()
    : (process.env.LUPA_API_TOKEN ?? '');

  if (token.length < 32 || token.length > 512 || new Set(token).size < 8 || /[\x00-\x1f\x7f]/.test(token)) {
    throw new Error('LUPA_API_TOKEN must be a strong secret of at least 32 characters');
  }
  return token;
}

if (!Number.isInteger(PORT) || PORT < 1 || PORT > 65535) {
  throw new Error('PORT must be an integer between 1 and 65535');
}
if (!Number.isInteger(MAX_BODY_BYTES) || MAX_BODY_BYTES < 1024 || MAX_BODY_BYTES > 16 * 1024 * 1024) {
  throw new Error('LUPA_MAX_BODY_BYTES must be between 1024 and 16777216');
}

const handle = createHandler({ apiToken: loadApiToken(), maxBodyBytes: MAX_BODY_BYTES });

const server = Bun.serve({
  port: PORT,
  hostname: HOST,
  idleTimeout: 60,
  maxRequestBodySize: MAX_BODY_BYTES,
  fetch: handle,
});

console.log(`lupa listening on ${HOST}:${PORT}`);

// Eager-spawn the headed browser with a splash so noVNC viewers always have
// something to see, even before any /live POST.
liveSplash().catch((e) => console.error('liveSplash failed:', e instanceof Error ? e.name : 'unknown error'));

const shutdown = async () => {
  await closeBrowser();
  server.stop();
  process.exit(0);
};

process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
