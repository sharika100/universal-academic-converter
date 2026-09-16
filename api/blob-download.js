import { get, head } from '@vercel/blob';

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

  // Safe extraction of pathname for diagnostic logging
  let safePathname = 'unknown';
  try {
    const urlObj = new URL(blobUrl);
    safePathname = urlObj.pathname.slice(1);
  } catch {
    safePathname = blobUrl.slice(0, 50);
  }

  console.log(`[BLOB_RETRIEVAL_ATTEMPTED] pathname: ${safePathname}`);

  try {
    const token = getBlobToken();
    const options = { access: 'private' };
    if (token) {
      options.token = token;
    }

    // Existence check via head / get
    const result = await get(blobUrl, options);
    if (!result || !result.stream) {
      console.log(`[BLOB_RETRIEVAL_RESULT] status: 404, pathname: ${safePathname}`);
      return response.status(404).json({
        error: 'STORAGE_OBJECT_NOT_FOUND',
        message: 'Uploaded project could not be retrieved from secure storage. Please retry the upload.',
        detail: `Storage request returned status code 404 for pathname: ${safePathname}`
      });
    }

    console.log(`[BLOB_RETRIEVAL_RESULT] status: 200, pathname: ${safePathname}, size: ${result.blob?.size || 'unknown'}`);

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
      message: 'Uploaded project could not be retrieved from secure storage. Please retry the upload.',
      detail: error.message || 'Failed to download private blob'
    });
  }
}
