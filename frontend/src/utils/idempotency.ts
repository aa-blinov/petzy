/** A key that makes a create safe to send twice. The server answers a repeat of the same key with the first answer
    and writes nothing again, so a retry after «Сервер не ответил» (the record was stored, its answer was lost) does
    not leave two of them.

    The key is one per opening of a form plus a short hash of what is sent: pressing the button again with the same
    data is the same request, while a changed field after a failure is a new one, and so is a second, deliberately
    identical record (a new opening of the form is a new key). */
export function newFormKey(): string {
  const raw = typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : '';
  return raw || `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`;
}

/** FNV-1a over the text, in base 36: short, and the same text always gives the same one. */
function hash(text: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(36);
}

/** The header for one send of `body` from the form opened under `formKey`; none without a key. */
export function idempotencyHeaders(formKey: string | undefined, body: unknown): Record<string, string> | undefined {
  if (!formKey) return undefined;
  return { 'Idempotency-Key': `${formKey}.${hash(JSON.stringify(body) ?? '')}` };
}
