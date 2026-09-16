import { put, get } from '@vercel/blob';

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

  const options = { access: 'private' };
  if (process.env.BLOB_READ_WRITE_TOKEN) {
    options.token = process.env.BLOB_READ_WRITE_TOKEN;
  }

  const testPath = `test/blob-test-${Date.now()}.txt`;
  const testContent = "HELLO_BLOB_TEST";

  try {
    console.log(`[TINY_BLOB_TEST_START] Uploading tiny file to ${testPath}...`);
    const blob = await put(testPath, testContent, options);
    console.log(`[TINY_BLOB_UPLOADED] pathname: ${blob.pathname}, url: ${blob.url}`);

    console.log(`[TINY_BLOB_RETRIEVING] Fetching via get() with useCache: false...`);
    const getResult = await get(blob.pathname, {
      ...options,
      useCache: false
    });

    if (!getResult || !getResult.stream) {
      throw new Error(`get() returned empty result for pathname: ${blob.pathname}`);
    }

    const reader = getResult.stream.getReader();
    const chunks = [];
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      chunks.push(value);
    }
    const retrievedText = Buffer.concat(chunks).toString('utf-8');

    console.log(`[TINY_BLOB_VERIFIED] Content: "${retrievedText}"`);
    const isMatch = retrievedText === testContent;

    return response.status(200).json({
      status: isMatch ? "ok" : "mismatch",
      uploaded_pathname: blob.pathname,
      uploaded_url: blob.url,
      retrieved_content: retrievedText,
      verified: isMatch
    });
  } catch (error) {
    console.error(`[TINY_BLOB_FAILED] Error:`, error.message);
    return response.status(500).json({
      status: "error",
      error: error.message
    });
  }
}
