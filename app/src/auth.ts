import { timingSafeEqual } from 'node:crypto';

export function authorized(req: Request, apiToken: string): boolean {
  const header = req.headers.get('authorization');
  if (!header?.startsWith('Bearer ')) return false;
  const supplied = Buffer.from(header.slice(7), 'utf8');
  const expected = Buffer.from(apiToken, 'utf8');
  return supplied.length === expected.length && timingSafeEqual(supplied, expected);
}
