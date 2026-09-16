import { get } from '@vercel/blob';

function getBlobToken() {
  if (process.env.BLOB_READ_WRITE_TOKEN) {
    return process.env.BLOB_READ_WRITE_TOKEN;
  }
  for (const [key, value] of Object.entries(process.env)) {
    if ((key.endsWith('_READ_WRITE_TOKEN') || key.includes('BLOB')) && typeof value === 'string' && value.startsWith('vercel_blob_')) {
      return value;
    }
  }
  return undefined;
}

export default async function handler(request, response) {
  if (request.method !== 'GET') {
    return response.status(405).json({ error: 'Method not allowed' });
  }

  const blobUrl = request.query?.url || new URL(request.url, 'http://localhost').searchParams.get('url');
  if (!blobUrl) {
    return response.status(400).json({ error: 'Missing url parameter' });
  }

  try {
    const token = getBlobToken();
    const options = { access: 'private' };
    if (token) {
      options.token = token;
    }

    const result = await get(blobUrl, options);
    if (!result) {
      return response.status(404).json({ error: 'Blob not found' });
    }

    const contentType = result.blob?.contentType || 'application/octet-stream';
    const reader = result.stream.getReader();
    const chunks = [];
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
    }
    const buffer = Buffer.concat(chunks);

    response.setHeader('Content-Type', contentType);
    response.setHeader('Content-Length', buffer.length);
    return response.status(200).send(buffer);
  } catch (error) {
    console.error('Blob download helper error:', error);
    return response.status(500).json({
      error: 'Private Blob retrieval failed',
      detail: error.message || 'Failed to download private blob'
    });
  }
}
