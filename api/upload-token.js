import { issueSignedToken, presignUrl, parseStoreIdFromDelegationToken } from '@vercel/blob';

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

export default async function handler(request, response) {
  if (request.method !== 'POST') {
    return response.status(405).json({ error: 'Method not allowed' });
  }

  ensureBlobEnv();

  const envKeys = Object.keys(process.env).filter(k => k.includes('BLOB') || k.includes('OIDC') || k.includes('VERCEL'));
  console.log('[UPLOAD_AUTH_ENDPOINT_CALLED] Route: /api/upload-token');
  console.log(`[BLOB_DIAGNOSTICS] SDK_VERSION: 2.8.0, Available Blob/Vercel Env Keys: [${envKeys.join(', ')}]`);

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

    const filename = body.filename || `manuscript_${Date.now()}.zip`;
    const size = body.size || 0;
    const cleanFilename = filename.replace(/[^a-zA-Z0-9._-]/g, '_');
    const pathname = `uploads/${Date.now()}_${cleanFilename}`;

    console.log(`[UPLOAD_REQUESTED] filename: ${cleanFilename}, size: ${size}`);

    // Command options for signed token API
    const commandOptions = {};
    if (process.env.BLOB_READ_WRITE_TOKEN) {
      commandOptions.token = process.env.BLOB_READ_WRITE_TOKEN;
    }

    // 1. Issue signed token (scoped for 'put' and 'get' operations)
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
      maximumSizeInBytes: 100 * 1024 * 1024,
      ...commandOptions,
    });

    let storeId = 'store';
    try {
      if (signedToken && signedToken.delegationToken) {
        storeId = parseStoreIdFromDelegationToken(signedToken.delegationToken) || 'store';
      }
    } catch (e) {
      console.warn('Could not parse storeId from delegation token:', e.message);
    }

    // 2. Generate signed PUT URL for browser direct upload
    const { presignedUrl: uploadUrl } = await presignUrl(signedToken, {
      operation: 'put',
      pathname,
      access: 'private',
      addRandomSuffix: false,
      ...commandOptions,
    });

    // 3. Generate signed GET URL for backend private retrieval
    const { presignedUrl: downloadUrl } = await presignUrl(signedToken, {
      operation: 'get',
      pathname,
      access: 'private',
      ...commandOptions,
    });

    const canonicalBlobUrl = `https://${storeId}.private.blob.vercel-storage.com/${pathname}`;

    console.log(`[BLOB_AUTH_SUCCESS] Presigned PUT URL generated for pathname: ${pathname}`);

    return response.status(200).json({
      uploadUrl,
      downloadUrl,
      presignedUrl: uploadUrl, // compatibility
      pathname,
      blobUrl: canonicalBlobUrl
    });

  } catch (error) {
    console.error('[BLOB_AUTH_ERROR] Client upload authorization failed:', error.name, error.message);
    if (error.stack) {
      console.error('[BLOB_AUTH_STACK]', error.stack.split('\n').slice(0, 5).join('\n'));
    }

    return response.status(500).json({
      error: 'STORAGE_AUTHORIZATION_ERROR',
      message: 'Secure large-file storage authorization failed. Please retry.',
      detail: `${error.name || 'BlobError'}: ${error.message || 'Storage authorization failed.'}`
    });
  }
}
