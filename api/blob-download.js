import { get } from '@vercel/blob';

function ensureBlobEnv() {
  if (!process.env.BLOB_READ_WRITE_TOKEN) {
    for (const [key, val] of Object.entries(process.env)) {
      if ((key.endsWith('_READ_WRITE_TOKEN') || key.includes('BLOB_READ_WRITE_TOKEN')) && typeof val === 'string' && val.startsWith('vercel_blob_')) {
        process.env.BLOB_READ_WRITE_TOKEN = val;
        break;
      }
    }
  }
  if (!process.env.BLOB_STORE_ID) {
    for (const [key, val] of Object.entries(process.env)) {
      if ((key.endsWith('_STORE_ID') || key.includes('BLOB_STORE_ID')) && typeof val === 'string' && val.trim() !== '') {
        process.env.BLOB_STORE_ID = val.trim();
        break;
      }
    }
  }
}

export default async function handler(request, response) {
  if (request.method !== 'GET') {
    return response.status(405).json({ error: 'Method not allowed' });
  }

  ensureBlobEnv();

  const blobUrlOrPathname = request.query?.url || request.query?.pathname || new URL(request.url, 'http://localhost').searchParams.get('url') || new URL(request.url, 'http://localhost').searchParams.get('pathname');
  
  if (!blobUrlOrPathname) {
    return response.status(400).json({ error: 'Missing url or pathname parameter' });
  }

  let safePathname = 'unknown';
  try {
    if (blobUrlOrPathname.startsWith('http')) {
      safePathname = new URL(blobUrlOrPathname).pathname.slice(1);
    } else {
      safePathname = blobUrlOrPathname;
    }
  } catch {
    safePathname = blobUrlOrPathname.slice(0, 50);
  }

  console.log(`[BLOB_RETRIEVAL_ATTEMPTED] target: ${safePathname}`);

  try {
    const options = {
      access: 'private',
      useCache: false
    };
    if (process.env.BLOB_READ_WRITE_TOKEN) {
      options.token = process.env.BLOB_READ_WRITE_TOKEN;
    }

    const result = await get(blobUrlOrPathname, options);
    if (!result || !result.stream) {
      console.log(`[BLOB_RETRIEVAL_RESULT] status: 404, target: ${safePathname}`);
      return response.status(404).json({
        error: 'STORAGE_OBJECT_NOT_FOUND',
        message: 'Uploaded project could not be retrieved from secure storage. Please retry.',
        detail: `Storage request returned status code 404 for pathname: ${safePathname}`
      });
    }

    console.log(`[BLOB_RETRIEVAL_RESULT] status: 200, target: ${safePathname}, size: ${result.blob?.size || 'unknown'}`);

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
    console.error(`[BLOB_RETRIEVAL_RESULT] status: 500, error: ${error.message}`);
    return response.status(500).json({
      error: 'STORAGE_OBJECT_NOT_FOUND',
      message: 'Uploaded project could not be retrieved from secure storage. Please retry.',
      detail: error.message || 'Failed to download private blob'
    });
  }
}
