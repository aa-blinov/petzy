/**
 * Pictures already shown in this session. The browser keeps them (the server sends them as immutable), but the screens
 * drew each one again from a blurred placeholder with a fade, so a picture from the cache looked like it was loading
 * anew every time a screen opened. One that was seen is shown at once.
 */
const seen = new Set<string>();

export function wasSeen(src: string): boolean {
  return seen.has(src);
}

export function markSeen(src: string): void {
  seen.add(src);
}
