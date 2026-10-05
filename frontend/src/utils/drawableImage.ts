import api from '../services/api';

/** A phone's HEIC/HEIF photo, by its type or, where the browser leaves the type empty, by its name. */
export const isHeicFile = (file: File): boolean => /^image\/hei[cf]$/i.test(file.type) || /\.(heic|heif)$/i.test(file.name);

/**
 * A picture the browser can draw. Safari draws a HEIC and nothing else does: elsewhere the thumbnail of a picked file is a broken
 * image and the crop window of a pet's photo is empty. A HEIC that this browser cannot decode is sent to the server, which sends
 * it back as WebP (nothing is stored there: the form sends the original when it is saved). Any other file is returned as it is.
 * `onWait` is called when that round trip starts, so that the screen can say something is happening.
 */
export async function drawableImage(file: File, onWait?: () => void): Promise<Blob> {
  if (!isHeicFile(file)) return file;
  try {
    const bitmap = await createImageBitmap(file);
    bitmap.close();
    return file;
  } catch {
    /* this browser does not draw HEIC */
  }
  onWait?.();
  const form = new FormData();
  // The server takes the declared type for a claim and checks the bytes: a HEIC from a browser that does not know the type has none.
  form.append('file', file.type ? file : new File([file], file.name, { type: 'image/heic' }), file.name);
  const response = await api.post<Blob>('/images/preview', form, { responseType: 'blob' });
  return response.data;
}
