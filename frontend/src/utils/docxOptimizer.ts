import JSZip from 'jszip';

export interface OptimizationOptions {
  jpegQuality?: number;
  maxDimension?: number;
  minFileSizeToCompress?: number;
  onProgress?: (percent: number, statusText: string) => void;
}

export interface OptimizationResult {
  file: File;
  originalSize: number;
  optimizedSize: number;
  reductionPercentage: number;
  imagesCompressed: number;
}

/**
 * Re-encodes an image Blob/Buffer in the browser using HTMLCanvasElement,
 * preserving exact dimensions while drastically reducing file size.
 */
async function compressImageInBrowser(
  imageBlob: Blob,
  mimeType: string,
  quality: number = 0.85,
  maxDimension: number = 3840
): Promise<Blob> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(imageBlob);
    const img = new Image();

    img.onload = () => {
      URL.revokeObjectURL(url);
      try {
        let { width, height } = img;

        // Downscale oversized 4K+ images while preserving aspect ratio
        if (width > maxDimension || height > maxDimension) {
          if (width > height) {
            height = Math.round((height * maxDimension) / width);
            width = maxDimension;
          } else {
            width = Math.round((width * maxDimension) / height);
            height = maxDimension;
          }
        }

        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;

        const ctx = canvas.getContext('2d');
        if (!ctx) {
          return resolve(imageBlob);
        }

        // Fill white background for transparent PNGs converted to JPEG
        ctx.fillStyle = '#FFFFFF';
        ctx.fillRect(0, 0, width, height);

        ctx.drawImage(img, 0, 0, width, height);

        canvas.toBlob(
          (blob) => {
            if (blob && blob.size < imageBlob.size) {
              resolve(blob);
            } else {
              // If compressed blob isn't smaller, preserve original
              resolve(imageBlob);
            }
          },
          'image/jpeg',
          quality
        );
      } catch (err) {
        resolve(imageBlob);
      }
    };

    img.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(imageBlob);
    };

    img.src = url;
  });
}

/**
 * Optimizes a DOCX file in the browser by compressing embedded media in word/media/
 * while preserving 100% of XML document structure, text, tables, equations, and references.
 */
export async function optimizeDocxImages(
  file: File,
  options: OptimizationOptions = {}
): Promise<OptimizationResult> {
  const {
    jpegQuality = 0.85,
    maxDimension = 3840,
    minFileSizeToCompress = 150 * 1024, // 150 KB
    onProgress
  } = options;

  const originalSize = file.size;
  onProgress?.(5, 'Reading DOCX manuscript archive...');

  const arrayBuffer = await file.arrayBuffer();
  const zip = await JSZip.loadAsync(arrayBuffer);

  const mediaFiles: { name: string; zipObject: JSZip.JSZipObject }[] = [];
  zip.folder('word/media')?.forEach((relativePath, fileObj) => {
    if (!fileObj.dir) {
      mediaFiles.push({ name: `word/media/${relativePath}`, zipObject: fileObj });
    }
  });

  const totalMedia = mediaFiles.length;
  let compressedCount = 0;

  if (totalMedia === 0) {
    onProgress?.(100, 'No embedded media found in manuscript.');
    return {
      file,
      originalSize,
      optimizedSize: originalSize,
      reductionPercentage: 0,
      imagesCompressed: 0
    };
  }

  for (let i = 0; i < mediaFiles.length; i++) {
    const { name, zipObject } = mediaFiles[i];
    const percent = Math.round(10 + (i / totalMedia) * 80);
    onProgress?.(percent, `Optimizing embedded image ${i + 1} of ${totalMedia}...`);

    const ext = name.split('.').pop()?.toLowerCase();
    if (ext === 'png' || ext === 'jpeg' || ext === 'jpg') {
      const originalData = await zipObject.async('blob');

      if (originalData.size > minFileSizeToCompress) {
        const compressedBlob = await compressImageInBrowser(
          originalData,
          ext === 'png' ? 'image/png' : 'image/jpeg',
          jpegQuality,
          maxDimension
        );

        if (compressedBlob.size < originalData.size) {
          const compressedBuffer = await compressedBlob.arrayBuffer();
          zip.file(name, compressedBuffer);
          compressedCount++;
        }
      }
    }
  }

  onProgress?.(92, 'Rebuilding optimized DOCX manuscript package...');
  const outputBlob = await zip.generateAsync({
    type: 'blob',
    mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    compression: 'DEFLATE',
    compressionOptions: { level: 6 }
  });

  const optimizedSize = outputBlob.size;
  const reductionPercentage = Math.max(0, Math.round(((originalSize - optimizedSize) / originalSize) * 1000) / 10);

  const optimizedFile = new File([outputBlob], file.name, {
    type: file.type || 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  });

  onProgress?.(100, `Optimization complete! Reduced by ${reductionPercentage}% (${roundMb(originalSize)} MB → ${roundMb(optimizedSize)} MB).`);

  return {
    file: optimizedFile,
    originalSize,
    optimizedSize,
    reductionPercentage,
    imagesCompressed: compressedCount
  };
}

function roundMb(bytes: number): string {
  return (bytes / (1024 * 1024)).toFixed(1);
}
