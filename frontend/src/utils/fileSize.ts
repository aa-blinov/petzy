const MB = 1024 * 1024;

/** "840 КБ", "12 МБ", "1,2 ГБ" — the way file sizes read in Russian. Below ten megabytes the
 *  tenth part is shown, above it the round number. */
export function formatFileSize(bytes: number): string {
  if (bytes < MB) return `${Math.max(1, Math.round(bytes / 1024))} КБ`;
  if (bytes < 1024 * MB) {
    const mb = bytes / MB;
    return `${mb.toLocaleString('ru-RU', { maximumFractionDigits: mb < 10 ? 1 : 0 })} МБ`;
  }
  return `${(bytes / (1024 * MB)).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} ГБ`;
}
