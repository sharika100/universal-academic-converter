import { issueSignedToken, presignUrl, handleUpload } from '@vercel/blob';

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

function detectAuthMethod() {
  const token = getBlobToken();
  if (token) return 'static-token';
  if (process.env.VERCEL_OIDC_TOKEN || process.env.BLOB_STORE_ID) return 'oidc';
  if (process.env.VERCEL === '1') return 'vercel-platform-oidc';
  return 'unknown';
}

export default async function handler(request, response) {
  if (request.method !== 'POST') {
    return response.status(405).json({ error: 'Method not allowed' });
  }

  const authMethod = detectAuthMethod();
  const hasToken = !!getBlobToken();
  const hasOidc = !!(process.env.VERCEL_OIDC_TOKEN || process.env.BLOB_STORE_ID || process.env.VERCEL === '1');

  console.log('[UPLOAD_AUTH_ENDPOINT_CALLED] Route: /api/upload-token');
  console.log(`[BLOB_DIAGNOSTICS] SDK_VERSION: 2.8.0, BLOB_AUTH_METHOD: ${authMethod}, BLOB_STORE_CONFIGURATION_PRESENT: ${hasToken || hasOidc}`);

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

    // A. Handle standard @vercel/blob client event if type is present
    if (body && body.type && typeof body.type === 'string' && body.type.startsWith('blob.')) {
      const handleUploadOptions = {
        body,
        request,
        onBeforeGenerateToken: async (pathname) => {
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
            maximumSizeInBytes: 100 * 1024 * 1024,
          };
        },
        onUploadCompleted: async ({ blob }) => {
          console.log('[BLOB_UPLOAD_COMPLETED] Upload completed:', blob.url);
        },
      };

      const token = getBlobToken();
      if (token) {
        handleUploadOptions.token = token;
      }

      const jsonResponse = await handleUpload(handleUploadOptions);
      return response.status(200).json(jsonResponse);
    }

    // B. Direct Signed PUT URL Generation (supports OIDC natively)
    const filename = body.filename || `manuscript_${Date.now()}.zip`;
    const cleanFilename = filename.replace(/[^a-zA-Z0-9._-]/g, '_');
    const pathname = `uploads/${Date.now()}_${cleanFilename}`;

    const commandOptions = {};
    const token = getBlobToken();
    if (token) {
      commandOptions.token = token;
    }

    const signedToken = await issueSignedToken({
      pathname,
      operations: ['put'],
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

    const { presignedUrl } = await presignUrl(signedToken, {
      operation: 'put',
      pathname,
      access: 'private',
      ...commandOptions,
    });

    console.log('[BLOB_SIGNED_URL_ISSUED] Successfully generated direct signed PUT URL for:', pathname);

    return response.status(200).json({
      uploadUrl: presignedUrl,
      pathname,
      blobUrl: `https://blob.vercel-storage.com/${pathname}`
    });

  } catch (error) {
    console.error('[BLOB_AUTH_ERROR] Client upload authorization failed:', error.name, error.message);
    if (error.stack) {
      console.error('[BLOB_AUTH_STACK]', error.stack.split('\n').slice(0, 5).join('\n'));
    }

    return response.status(500).json({
      error: 'STORAGE_CONFIGURATION_ERROR',
      message: 'Secure large-file storage is not available for this deployment.',
      detail: error.message || 'Vercel Blob storage authorization failed.'
    });
  }
}
