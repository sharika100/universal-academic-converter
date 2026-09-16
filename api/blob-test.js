import { put, get } from '@vercel/blob';

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
  const token = getBlobToken();
  const options = { access: 'private' };
  if (token) {
    options.token = token;
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
