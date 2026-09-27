/**
 * Screens for someone who isn't signed in: sign-in, sign-up and the links
 * from letters. No session probe runs there, and no tab bar is shown.
 */
export const PUBLIC_PAGES = ['/login', '/register', '/forgot-password', '/reset-password', '/verify-email'];

export function isPublicPage(pathname: string): boolean {
  return PUBLIC_PAGES.some((page) => pathname === page || pathname.endsWith(page));
}
