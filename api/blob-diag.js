import { list, head, put, get, del, issueSignedToken, presignUrl, parseStoreIdFromDelegationToken } from '@vercel/blob';

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
  ensureBlobEnv();

  const results = {
    timestamp: new Date().toISOString(),
    git_commit_sha: process.env.VERCEL_GIT_COMMIT_SHA || 'unknown',
    git_commit_msg: process.env.VERCEL_GIT_COMMIT_MESSAGE || 'unknown',
    sdk_version: "2.8.0",
    env_keys: Object.keys(process.env).filter(k => k.includes('BLOB') || k.includes('OIDC') || k.includes('VERCEL')),
    has_blob_token: !!process.env.BLOB_READ_WRITE_TOKEN,
    token_prefix: process.env.BLOB_READ_WRITE_TOKEN ? process.env.BLOB_READ_WRITE_TOKEN.substring(0, 15) + '...' : null,
    target_eaamr_pathname: "uploads/1789542733345_FINAL_EAAMR_JOURNAL_ESWA_JOURNAL.zip",
    eaamr_object_exists: false,
    eaamr_head_details: null,
    store_objects_count: 0,
    store_objects_recent: [],
    tiny_test: {
      put_succeeded: false,
      read_succeeded: false,
      pathname: null,
      error: null
    },
    signed_url_test: {
      issue_token_succeeded: false,
      presign_put_succeeded: false,
      presign_get_succeeded: false,
      direct_put_succeeded: false,
      direct_put_status: null,
      direct_put_response: null,
      read_after_presign_put_succeeded: false,
      error: null
    }
  };

  const options = { access: 'private' };
  if (process.env.BLOB_READ_WRITE_TOKEN) {
    options.token = process.env.BLOB_READ_WRITE_TOKEN;
  }

  // 1. Check if target EAAMR object exists via head()
  try {
    const headRes = await head(results.target_eaamr_pathname, options);
    if (headRes) {
      results.eaamr_object_exists = true;
      results.eaamr_head_details = {
        pathname: headRes.pathname,
        size: headRes.size,
        contentType: headRes.contentType,
        uploadedAt: headRes.uploadedAt,
        url: headRes.url
      };
    }
  } catch (err) {
    results.eaamr_object_exists = false;
    results.eaamr_head_details = { error: err.message };
  }

  // 2. List objects in store
  try {
    const listRes = await list({ ...options, limit: 50 });
    results.store_objects_count = listRes.blobs ? listRes.blobs.length : 0;
    results.store_objects_recent = (listRes.blobs || []).map(b => ({
      pathname: b.pathname,
      size: b.size,
      uploadedAt: b.uploadedAt,
      url: b.url
    }));
  } catch (err) {
    results.list_error = err.message;
  }

  // 3. Perform Tiny Blob Test (put -> get -> del)
  const tinyPath = `diagnostic/blob-test-${Date.now()}.txt`;
  try {
    results.tiny_test.pathname = tinyPath;
    const tinyPut = await put(tinyPath, "hello_diagnostic", options);
    results.tiny_test.put_succeeded = !!tinyPut;
    
    const tinyGet = await get(tinyPath, { ...options, useCache: false });
    if (tinyGet && tinyGet.stream) {
      const reader = tinyGet.stream.getReader();
      const chunks = [];
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
      }
      const text = Buffer.concat(chunks).toString('utf-8');
      results.tiny_test.read_succeeded = text === "hello_diagnostic";
    }

    // cleanup
    await del(tinyPath, options).catch(() => {});
  } catch (err) {
    results.tiny_test.error = err.message;
  }

  // 4. Test Presigned PUT & GET Cycle
  const presignTestPath = `diagnostic/presign-test-${Date.now()}.txt`;
  try {
    const signedToken = await issueSignedToken({
      pathname: presignTestPath,
      operations: ['put', 'get'],
      maximumSizeInBytes: 10 * 1024 * 1024,
      ...options
    });
    results.signed_url_test.issue_token_succeeded = !!signedToken;

    const { presignedUrl: uploadUrl } = await presignUrl(signedToken, {
      operation: 'put',
      pathname: presignTestPath,
      access: 'private',
      ...options
    });
    results.signed_url_test.presign_put_succeeded = !!uploadUrl;

    const { presignedUrl: downloadUrl } = await presignUrl(signedToken, {
      operation: 'get',
      pathname: presignTestPath,
      access: 'private',
      ...options
    });
    results.signed_url_test.presign_get_succeeded = !!downloadUrl;

    // Simulate browser PUT request to presigned URL
    const putResp = await fetch(uploadUrl, {
      method: 'PUT',
      headers: { 'Content-Type': 'text/plain' },
      body: 'presign_test_content'
    });
    results.signed_url_test.direct_put_status = putResp.status;
    results.signed_url_test.direct_put_succeeded = putResp.ok;
    
    let putBodyText = '';
    try {
      putBodyText = await putResp.text();
      results.signed_url_test.direct_put_response = putBodyText;
    } catch (e) {
      results.signed_url_test.direct_put_response = e.message;
    }

    // Verify if object is readable after presigned PUT
    const readAfterPut = await get(presignTestPath, { ...options, useCache: false });
    if (readAfterPut && readAfterPut.stream) {
      results.signed_url_test.read_after_presign_put_succeeded = true;
    }

    // cleanup
    await del(presignTestPath, options).catch(() => {});
  } catch (err) {
    results.signed_url_test.error = err.message;
  }

  return response.status(200).json(results);
}
