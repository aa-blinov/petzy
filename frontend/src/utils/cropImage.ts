import type { Area } from 'react-easy-crop';

/** Max output dimension (px) for a cropped pet photo — the backend's own
 * optimize_image() re-encodes/resizes anyway, so this just keeps the
 * upload itself reasonably small on slow connections. */
const MAX_OUTPUT_SIZE = 1000;

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
 * returns it as a JPEG File — this is what actually gets uploaded, so
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
  const ctx = canvas.getContext('2d');
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

  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.92));
  if (!blob) throw new Error('Canvas is empty');

  const baseName = filename.includes('.') ? filename.slice(0, filename.lastIndexOf('.')) : filename;
  return new File([blob], `${baseName}.jpg`, { type: 'image/jpeg' });
}
