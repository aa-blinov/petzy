import type { Area } from 'react-easy-crop';

/** Max output dimension (px) for a cropped pet photo. Keeps the upload
 * small on slow connections, and stays under optimize_image()'s 1920px
 * cap so the backend can store the WebP as-is. */
const MAX_OUTPUT_SIZE = 1000;

/** Exported as WebP at the backend's own quality: the backend stores a
 * ready WebP untouched, so the photo is compressed once, not JPEG then
 * WebP again. Browsers that can't encode WebP (older Safari) hand back
 * a lossless PNG instead, which the backend converts. */
const OUTPUT_TYPE = 'image/webp';
const OUTPUT_QUALITY = 0.85;
const EXTENSION_BY_TYPE: Record<string, string> = { 'image/webp': 'webp', 'image/png': 'png', 'image/jpeg': 'jpg' };

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.addEventListener('load', () => resolve(img));
    img.addEventListener('error', (e) => reject(e));
    img.crossOrigin = 'anonymous';
    img.src = src;
  });
}

/** Renders the cropped, square area of `imageSrc` onto a canvas and
 * returns it as an image File — this is what actually gets uploaded, so
 * every place that displays the photo later can just show it as-is
 * instead of guessing at a crop with CSS object-position. */
export async function getCroppedImageFile(
  imageSrc: string,
  croppedAreaPixels: Area,
  filename: string,
): Promise<File> {
  const image = await loadImage(imageSrc);
  const outputSize = Math.min(MAX_OUTPUT_SIZE, Math.round(croppedAreaPixels.width));

  const canvas = document.createElement('canvas');
  canvas.width = outputSize;
  canvas.height = outputSize;
  // Opaque canvas: a photo has no transparency, and this keeps an alpha
  // channel out of the encoded file.
  const ctx = canvas.getContext('2d', { alpha: false });
  if (!ctx) throw new Error('Canvas 2D context unavailable');

  ctx.drawImage(
    image,
    croppedAreaPixels.x,
    croppedAreaPixels.y,
    croppedAreaPixels.width,
    croppedAreaPixels.height,
    0,
    0,
    outputSize,
    outputSize,
  );

  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, OUTPUT_TYPE, OUTPUT_QUALITY));
  if (!blob) throw new Error('Canvas is empty');

  const baseName = filename.includes('.') ? filename.slice(0, filename.lastIndexOf('.')) : filename;
  const extension = EXTENSION_BY_TYPE[blob.type] ?? 'png';
  return new File([blob], `${baseName}.${extension}`, { type: blob.type || 'image/png' });
}
