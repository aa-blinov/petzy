/** The app was added to the Home Screen (iOS says so with navigator.standalone). */
function isStandalone(): boolean {
  return window.matchMedia?.('(display-mode: standalone)').matches || (navigator as { standalone?: boolean }).standalone === true;
}

/** Hands a fetched file to the user. In the installed app it goes through the system share sheet («Сохранить в Файлы»,
 *  a messenger): a link to a blob there opens the file inside the app with no way back. In a browser it is a click on a
 *  temporary link, which a phone turns into its own «save» sheet. False when the person closed the share sheet. */
export async function saveBlob(data: BlobPart, filename: string, type?: string): Promise<boolean> {
  const blob = new Blob([data], type ? { type } : undefined);
  if (isStandalone() && typeof navigator.canShare === 'function' && typeof navigator.share === 'function') {
    const file = new File([blob], filename, { type: blob.type });
    if (navigator.canShare({ files: [file] })) {
      try {
        await navigator.share({ files: [file], title: filename });
        return true;
      } catch (err) {
        // Closed by the person: nothing was saved, and nothing to say. Any other refusal falls back to the link.
        if ((err as DOMException).name === 'AbortError') return false;
      }
    }
  }
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.parentNode?.removeChild(link);
  window.URL.revokeObjectURL(url);
  return true;
}

/** The file name a response asks for in its Content-Disposition, if any. */
export function filenameFromResponse(disposition: string | undefined): string | undefined {
  const match = disposition?.match(/filename\*=UTF-8''([^;]+)/i);
  return match?.[1] ? decodeURIComponent(match[1]) : undefined;
}
