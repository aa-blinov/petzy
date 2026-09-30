/** Hands a fetched file to the user: a click on a temporary link, which is
    what a phone turns into its own «save» or «share» sheet. */
export function saveBlob(data: BlobPart, filename: string, type?: string): void {
  const url = window.URL.createObjectURL(new Blob([data], type ? { type } : undefined));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.parentNode?.removeChild(link);
  window.URL.revokeObjectURL(url);
}

/** The file name a response asks for in its Content-Disposition, if any. */
export function filenameFromResponse(disposition: string | undefined): string | undefined {
  const match = disposition?.match(/filename\*=UTF-8''([^;]+)/i);
  return match?.[1] ? decodeURIComponent(match[1]) : undefined;
}
