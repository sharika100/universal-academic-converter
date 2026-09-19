const { generateClientTokenFromReadWriteToken, parseStoreIdFromDelegationToken } = require('@vercel/blob/client');
const { issueSignedToken, presignUrl } = require('@vercel/blob');

// Auto-alias store-prefixed Vercel Blob environment variables if standard names are missing
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

module.exports = async function handler(request, response) {
  if (request.method !== 'POST') {
    return response.status(405).json({ error: 'Method not allowed' });
  }

  ensureBlobEnv();

  console.log('[UPLOAD_AUTH_ENDPOINT_CALLED] Route: /api/upload-token');

  try {
    let body;
    if (typeof request.body === 'string') {
      try {
        body = JSON.parse(request.body);
      } catch {
        body = {};
      }
    } else {
      body = request.body || {};
    }

    const rwToken = process.env.BLOB_READ_WRITE_TOKEN;
    if (!rwToken) {
      console.error('[BLOB_AUTH_ERROR] Missing BLOB_READ_WRITE_TOKEN in environment');
      return response.status(500).json({ error: 'MISSING_BLOB_TOKEN', message: 'Vercel Blob token is not configured.' });
    }

    const rawFilename = body.payload?.pathname || body.pathname || body.filename || `manuscript_${Date.now()}.docx`;
    const cleanFilename = String(rawFilename).split(/[\/\\]/).pop().replace(/[^a-zA-Z0-9._-]/g, '_');
    const pathname = `uploads/${Date.now()}_${cleanFilename}`;

    console.log(`[BLOB_TOKEN_REQUEST] Generating token for file: ${cleanFilename} -> pathname: ${pathname}`);

    const clientToken = await generateClientTokenFromReadWriteToken({
      pathname,
      allowedContentTypes: [
        'application/zip',
        'application/x-zip-compressed',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/x-tex',
        'text/plain',
        'application/pdf',
        'application/octet-stream'
      ],
      maximumSizeInBytes: 500 * 1024 * 1024, // 500 MB (up to 5 TB with multipart)
      addRandomSuffix: false,
      token: rwToken
    });

    // If request comes from @vercel/blob/client SDK upload() helper
    if (body && body.type === 'blob.generate-client-token') {
      console.log(`[BLOB_SDK_TOKEN_SUCCESS] Client token issued for @vercel/blob/client upload()`);
      return response.status(200).json({
        type: 'blob.generate-client-token',
        clientToken
      });
    }

    // Direct presigned PUT fallback for legacy clients
    let storeId = 'store';
    try {
      if (clientToken) {
        storeId = parseStoreIdFromDelegationToken(clientToken) || 'store';
      }
    } catch (e) {
      console.warn('Could not parse storeId:', e.message);
    }

    const signedToken = await issueSignedToken({
      pathname,
      operations: ['put', 'get'],
      allowedContentTypes: [
        'application/zip',
        'application/x-zip-compressed',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/x-tex',
        'text/plain',
        'application/pdf',
        'application/octet-stream'
      ],
      maximumSizeInBytes: 500 * 1024 * 1024,
      token: rwToken
    });

    const { presignedUrl: uploadUrl } = await presignUrl(signedToken, {
      operation: 'put',
      pathname,
      access: 'private',
      addRandomSuffix: false,
      token: rwToken
    });

    const { presignedUrl: downloadUrl } = await presignUrl(signedToken, {
      operation: 'get',
      pathname,
      access: 'private',
      token: rwToken
    });

    const canonicalBlobUrl = `https://${storeId}.private.blob.vercel-storage.com/${pathname}`;

    return response.status(200).json({
      uploadUrl,
      downloadUrl,
      presignedUrl: uploadUrl,
      pathname,
      blobUrl: canonicalBlobUrl,
      clientToken
    });

  } catch (error) {
    console.error('[BLOB_AUTH_ERROR] Client upload authorization failed:', error);
    return response.status(500).json({
      error: 'STORAGE_AUTHORIZATION_ERROR',
      message: error.message || 'Secure large-file storage authorization failed.'
    });
  }
};
