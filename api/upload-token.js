module.exports = async function handler(request, response) {
  if (request.method !== 'POST') {
    return response.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const blobClient = require('@vercel/blob/client');
    const blobServer = require('@vercel/blob');

    const generateClientTokenFromReadWriteToken = blobClient.generateClientTokenFromReadWriteToken;
    const parseStoreIdFromDelegationToken = blobClient.parseStoreIdFromDelegationToken;
    const issueSignedToken = blobServer.issueSignedToken;
    const presignUrl = blobServer.presignUrl;

    // Auto-alias store-prefixed Vercel Blob environment variables if standard names are missing
    let rwToken = process.env.BLOB_READ_WRITE_TOKEN;
    if (!rwToken) {
      for (const [key, val] of Object.entries(process.env)) {
        if ((key.endsWith('_READ_WRITE_TOKEN') || key.includes('BLOB_READ_WRITE_TOKEN')) && typeof val === 'string' && val.startsWith('vercel_blob_')) {
          rwToken = val;
          process.env.BLOB_READ_WRITE_TOKEN = val;
          break;
        }
      }
    }

    if (!rwToken) {
      return response.status(500).json({ error: 'MISSING_BLOB_TOKEN', message: 'Vercel Blob token is not configured in env.' });
    }

    let body = {};
    if (typeof request.body === 'string') {
      try { body = JSON.parse(request.body); } catch {}
    } else {
      body = request.body || {};
    }

    const rawFilename = body.payload?.pathname || body.pathname || body.filename || `manuscript_${Date.now()}.docx`;
    const cleanFilename = String(rawFilename).split(/[\/\\]/).pop().replace(/[^a-zA-Z0-9._-]/g, '_');
    const pathname = `uploads/${Date.now()}_${cleanFilename}`;

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
      maximumSizeInBytes: 500 * 1024 * 1024,
      addRandomSuffix: false,
      token: rwToken
    });

    if (body && body.type === 'blob.generate-client-token') {
      return response.status(200).json({
        type: 'blob.generate-client-token',
        clientToken
      });
    }

    let storeId = 'store';
    try {
      if (clientToken) {
        storeId = parseStoreIdFromDelegationToken(clientToken) || 'store';
      }
    } catch {}

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

  } catch (err) {
    return response.status(500).json({
      error: 'DIAGNOSTIC_ERROR',
      message: err.message,
      name: err.name,
      stack: err.stack ? err.stack.split('\n').slice(0, 5) : []
    });
  }
};
