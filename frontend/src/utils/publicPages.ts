/**
 * Screens for someone who isn't signed in: sign-in, sign-up and the links
 * from letters. No session probe runs there, and no tab bar is shown.
 */
export const PUBLIC_PAGES = ['/login', '/register', '/forgot-password', '/reset-password', '/verify-email', '/privacy', '/consent'];

/** The page of a link to a pet's medical card, made for a vet: opened by someone who has no account, so it is public too. */
export const SHARED_CARD_PREFIX = '/share/medical/';

export function isPublicPage(pathname: string): boolean {
  return pathname.startsWith(SHARED_CARD_PREFIX) || PUBLIC_PAGES.some((page) => pathname === page || pathname.endsWith(page));
}
