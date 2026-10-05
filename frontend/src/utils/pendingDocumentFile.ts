/** A file chosen (or photographed) on the Documents list waits here for the form that names and files it: a File cannot go
 *  through an address, and the form takes it once, on opening.
 *
 *  A file nobody came for must not wait forever: the form may not have opened at all, and a photo taken an hour ago is
 *  not the file anyone wants filed under a new name now. So the wait has a life of its own, and an expired file is gone. */
let pending: { file: File; at: number } | null = null;

/** How long a chosen file waits for its form. Long enough to walk to it, short enough not to surprise later. */
const WAIT_MS = 5 * 60 * 1000;

export function setPendingDocumentFile(file: File | null): void {
  pending = file ? { file, at: Date.now() } : null;
}

export function takePendingDocumentFile(): File | null {
  const waiting = pending;
  pending = null;
  if (!waiting) return null;
  return Date.now() - waiting.at > WAIT_MS ? null : waiting.file;
}