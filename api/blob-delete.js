import { del, list } from '@vercel/blob';

export default async function handler(request, response) {
  return response.status(401).json({ error: 'UNAUTHORIZED_TEST_CONFIRMATION' });
}
