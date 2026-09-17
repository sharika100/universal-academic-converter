import { del, list } from '@vercel/blob';

function ensureBlobEnv() {
  if (!process.env.BLOB_READ_WRITE_TOKEN) {
    for (const [key, val] of Object.entries(process.env)) {
      if ((key.endsWith('_READ_WRITE_TOKEN') || key.includes('BLOB_READ_WRITE_TOKEN')) && typeof val === 'string' && val.startsWith('vercel_blob_')) {
        process.env.BLOB_READ_WRITE_TOKEN = val;
        break;
      }
    }
  }
}

function isAuthorized(request) {
  const authHeader = request.headers.authorization || request.headers['authorization'] || '';
  const internalSecret = request.headers['x-internal-delete-key'] || request.headers['X-Internal-Delete-Key'] || '';
  const token = process.env.BLOB_READ_WRITE_TOKEN;

  if (!token) return false;

  // 1. Allow calls with server's private BLOB_READ_WRITE_TOKEN in Authorization header
  if (authHeader && (authHeader.includes(token) || authHeader === `Bearer ${token}`)) {
    return true;
  }

  // 2. Allow calls with matching internal delete key header
  if (internalSecret && internalSecret === token.slice(-16)) {
    return true;
  }

  return false;
}

function isUploadsNamespace(urlOrPathname) {
  if (!urlOrPathname || typeof urlOrPathname !== 'string') return false;
  return urlOrPathname.includes('/uploads/') || urlOrPathname.startsWith('uploads/');
}

export default async function handler(request, response) {
  ensureBlobEnv();

  // SECURITY CHECK: Verify caller authorization
  if (!isAuthorized(request)) {
    return response.status(401).json({ error: 'Unauthorized cleanup request.' });
  }

  const options = { access: 'private' };
  if (process.env.BLOB_READ_WRITE_TOKEN) {
    options.token = process.env.BLOB_READ_WRITE_TOKEN;
  }

  // 1. Abandoned Uploads Sweep (delete Blobs in uploads/ older than 1 hour)
  if (request.method === 'GET' && (request.query?.clean_abandoned === 'true' || request.query?.sweep === 'true')) {
    try {
      const listRes = await list({ ...options, limit: 100 });
      const now = Date.now();
      const ONE_HOUR_MS = 60 * 60 * 1000;
      const deleted = [];

      for (const blob of listRes.blobs || []) {
        // SCOPE RESTRICTION: Only touch files inside uploads/ namespace
        if (!isUploadsNamespace(blob.pathname) && !isUploadsNamespace(blob.url)) {
          continue;
        }

        const uploadedAtMs = new Date(blob.uploadedAt).getTime();
        if (now - uploadedAtMs > ONE_HOUR_MS) {
          await del(blob.url, options).catch(() => {});
          deleted.push(blob.pathname);
        }
      }

      console.log(`[BLOB_SWEEP_COMPLETED] Deleted ${deleted.length} abandoned temporary Blob objects in uploads/ namespace.`);
      return response.status(200).json({
        success: true,
        cleaned_count: deleted.length,
        deleted_pathnames: deleted
      });
    } catch (err) {
      console.warn('[BLOB_SWEEP_ERROR]', err.message);
      return response.status(500).json({ error: err.message });
    }
  }

  // 2. Specific Temporary Object Deletion
  let blobUrlOrPathname = null;
  if (request.method === 'POST') {
    let body = {};
    if (typeof request.body === 'string') {
      try { body = JSON.parse(request.body); } catch { body = {}; }
    } else {
      body = request.body || {};
    }
    blobUrlOrPathname = body.url || body.blob_url || body.pathname;
  } else if (request.method === 'DELETE' || request.method === 'GET') {
    blobUrlOrPathname = request.query?.url || request.query?.pathname;
  }

  if (!blobUrlOrPathname) {
    return response.status(400).json({ error: 'Missing url or pathname' });
  }

  // SCOPE RESTRICTION: Deletion strictly restricted to uploads/ namespace
  if (!isUploadsNamespace(blobUrlOrPathname)) {
    return response.status(403).json({ error: 'Deletion restricted strictly to temporary uploads/ namespace.' });
  }

  try {
    await del(blobUrlOrPathname, options);
    console.log(`[TEMPORARY_BLOB_DELETED] Successfully deleted temporary Blob object in uploads/ namespace.`);
    return response.status(200).json({ success: true, deleted: true });
  } catch (err) {
    console.warn(`[TEMPORARY_BLOB_DELETE_ERROR] Could not delete Blob (${err.message}).`);
    return response.status(200).json({ success: false, error: err.message });
  }
}
