/** A file chosen (or photographed) on the Documents list waits here for the form that names and files it: a File cannot go
    through an address, and the form takes it once, on opening. */
let pending: File | null = null;

export function setPendingDocumentFile(file: File | null): void {
  pending = file;
}

export function takePendingDocumentFile(): File | null {
  const file = pending;
  pending = null;
  return file;
}
