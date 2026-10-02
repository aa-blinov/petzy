/**
 * Format date to YYYY-MM-DD format
 */
export function formatDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * A moment the server stamps in UTC («2026-10-02 07:29», no zone written), as the wall clock of this device
 * («2026-10-02 12:29» in Almaty): what a document list shows, not a time five hours off.
 */
export function utcStampToLocal(stamp: string): string {
  const iso = stamp.replace(' ', 'T');
  const moment = new Date(iso.length === 16 ? `${iso}:00Z` : `${iso}Z`);
  if (Number.isNaN(moment.getTime())) return stamp;
  return `${formatDate(moment)} ${formatTime(moment)}`;
}

/**
 * Format time to HH:MM format
 */
export function formatTime(date: Date): string {
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${hours}:${minutes}`;
}

/**
 * Get current date in YYYY-MM-DD format
 */
export function getCurrentDate(): string {
  return formatDate(new Date());
}

/**
 * Get current time in HH:MM format
 */
export function getCurrentTime(): string {
  return formatTime(new Date());
}

/**
 * Parse date string (YYYY-MM-DD) and time string (HH:MM) to Date object
 */
export function parseDateTime(dateStr: string, timeStr: string): Date {
  const [year, month, day] = dateStr.split('-').map(Number);
  const [hours, minutes] = timeStr.split(':').map(Number);
  return new Date(year, month - 1, day, hours, minutes);
}

