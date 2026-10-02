/** Where a person was going when they were sent to sign in: after signing in they go there, not to the feed. */
export function returnState(path: string): { from: string } | undefined {
  return path && path !== '/' && !path.startsWith('/login') ? { from: path } : undefined;
}

/** The address kept in the router state of /login, if it is one of ours (a path, never another site). */
export function returnPath(state: unknown): string {
  const from = (state as { from?: unknown } | null)?.from;
  return typeof from === 'string' && from.startsWith('/') && !from.startsWith('//') && !from.startsWith('/login') ? from : '/';
}
