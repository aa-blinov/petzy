/** Who a queued dose belongs to.
 *
 *  The queue lives on the phone, and a phone can be handed to someone else. A dose marked under one login must not go
 *  out under another login's session (on a shared pet it would be written down as that person's), and must not show as
 *  pending to the other login either. So each entry records the login that was signed in when the dose was marked.
 *  An entry written before that record has no owner: it belongs to the first login that sends the queue, and is marked
 *  with that login from then on. Signing out does not clear the queue, so the person who comes back finds it.
 *
 *  Kept free of imports on purpose: these rules can be checked on their own, outside the app. */

/** The part of a queued entry that says whose it is. */
export interface OwnedEntry {
  owner?: string;
}

/** What one login sees and sends: its own entries, and the ones nobody has claimed yet. Nothing without a login. */
export function queueOf<T extends OwnedEntry>(items: readonly T[], login: string | null): T[] {
  if (!login) return [];
  return items.filter((item) => !item.owner || item.owner === login);
}

/** The same queue with the unclaimed entries given to this login. Returns the same array when nothing is unclaimed,
 *  so a caller can tell by reference whether anything changed. */
export function claimUnowned<T extends OwnedEntry>(items: T[], login: string): T[] {
  if (!items.some((item) => !item.owner)) return items;
  return items.map((item) => (item.owner ? item : { ...item, owner: login }));
}
