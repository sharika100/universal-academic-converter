import { handleUpload } from '@vercel/blob/client';
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

    // 1. If this is an official @vercel/blob/client SDK token generation / event request
    if (body && body.type) {
      console.log(`[BLOB_CLIENT_EVENT] Handling client SDK upload event: ${body.type}`);
      const jsonResponse = await handleUpload({
        body,
        request,
        token: process.env.BLOB_READ_WRITE_TOKEN,
        onBeforeGenerateToken: async (pathname, clientPayload) => {
          const rawFilename = pathname || clientPayload || `manuscript_${Date.now()}.docx`;
          const cleanFilename = String(rawFilename).split(/[\/\\]/).pop().replace(/[^a-zA-Z0-9._-]/g, '_');
          const targetPath = `uploads/${Date.now()}_${cleanFilename}`;
          console.log(`[BLOB_TOKEN_GENERATION] Authorized target path: ${targetPath} (up to 500 MB / multipart 5 TB)`);
          return {
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
            pathname: targetPath
          };
        }
      });

      return response.status(200).json(jsonResponse);
    }

    // 2. Direct presigned PUT fallback for legacy clients
    const rawFilename = body.payload?.pathname || body.filename || `manuscript_${Date.now()}.docx`;
    const cleanFilename = String(rawFilename).split(/[\/\\]/).pop().replace(/[^a-zA-Z0-9._-]/g, '_');
    const pathname = `uploads/${Date.now()}_${cleanFilename}`;

    console.log(`[LEGACY_UPLOAD_REQUESTED] filename: ${cleanFilename}, pathname: ${pathname}`);

    const commandOptions = {};
    if (process.env.BLOB_READ_WRITE_TOKEN) {
      commandOptions.token = process.env.BLOB_READ_WRITE_TOKEN;
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
      ...commandOptions,
    });

    const clientToken = (signedToken && typeof signedToken === 'object' && signedToken.delegationToken)
      ? signedToken.delegationToken
      : (typeof signedToken === 'string' ? signedToken : '');

    let storeId = 'store';
    try {
      if (clientToken) {
        storeId = parseStoreIdFromDelegationToken(clientToken) || 'store';
      }
    } catch (e) {
      console.warn('Could not parse storeId:', e.message);
    }

    const { presignedUrl: uploadUrl } = await presignUrl(signedToken, {
      operation: 'put',
      pathname,
      access: 'private',
      addRandomSuffix: false,
      ...commandOptions,
    });

    const { presignedUrl: downloadUrl } = await presignUrl(signedToken, {
      operation: 'get',
      pathname,
      access: 'private',
      ...commandOptions,
    });

    const canonicalBlobUrl = `https://${storeId}.private.blob.vercel-storage.com/${pathname}`;

    console.log(`[LEGACY_BLOB_AUTH_SUCCESS] Generated URLs for pathname: ${pathname}`);

    return response.status(200).json({
      uploadUrl,
      downloadUrl,
      presignedUrl: uploadUrl,
      pathname,
      blobUrl: canonicalBlobUrl,
      clientToken
    });

  } catch (error) {
    console.error('[BLOB_AUTH_ERROR] Client upload authorization failed:', error.name, error.message);
    return response.status(500).json({
      error: 'STORAGE_AUTHORIZATION_ERROR',
      message: 'Secure large-file storage authorization failed. Please retry.',
      detail: `${error.name || 'BlobError'}: ${error.message || 'Storage authorization failed.'}`
    });
  }
}
