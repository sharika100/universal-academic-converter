import { handleUpload } from '@vercel/blob';

function getBlobToken() {
  if (process.env.BLOB_READ_WRITE_TOKEN) {
    return process.env.BLOB_READ_WRITE_TOKEN;
  }
  for (const [key, value] of Object.entries(process.env)) {
    if ((key.endsWith('_READ_WRITE_TOKEN') || key.includes('BLOB')) && typeof value === 'string' && value.startsWith('vercel_blob_')) {
      return value;
    }
  }
  return null;
}

export default async function handler(request, response) {
  if (request.method !== 'POST') {
    return response.status(405).json({ error: 'Method not allowed' });
  }

  const token = getBlobToken();
  if (!token) {
    console.error('Vercel Blob Storage token not found in environment variables.');
    return response.status(500).json({
      error: 'Vercel Blob Storage token is not configured. Please connect a Vercel Blob store to your Vercel Project Settings.'
    });
  }

  try {
    let body;
    if (typeof request.body === 'string') {
      body = JSON.parse(request.body);
    } else {
      body = request.body;
    }

    const jsonResponse = await handleUpload({
      body,
      request,
      token,
      onBeforeGenerateToken: async (pathname /*, clientPayload */) => {
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
          maximumSizeInBytes: 100 * 1024 * 1024, // 100 MB max for direct Blob upload
        };
      },
      onUploadCompleted: async ({ blob, tokenPayload }) => {
        console.log('[BLOB_UPLOAD_COMPLETED] Private Vercel Blob upload completed:', blob.url);
      },
    });

    return response.status(200).json(jsonResponse);
  } catch (error) {
    console.error('Vercel Blob upload token error:', error);
    return response.status(400).json({ error: error.message || 'Blob token generation failed' });
  }
}
