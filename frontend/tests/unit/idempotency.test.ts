import { describe, expect, it } from 'vitest';
import { idempotencyHeaders, newFormKey } from '../../src/utils/idempotency';

describe('idempotency key', () => {
  it('has no header without a form key', () => {
    expect(idempotencyHeaders(undefined, { a: 1 })).toBeUndefined();
  });

  it('is the same for the same data from the same opening of a form', () => {
    const key = newFormKey();
    expect(idempotencyHeaders(key, { title: 'Нобивак', date: '2026-10-24' })).toEqual(
      idempotencyHeaders(key, { title: 'Нобивак', date: '2026-10-24' }),
    );
  });

  it('changes when a field is changed after a failure', () => {
    const key = newFormKey();
    expect(idempotencyHeaders(key, { title: 'Нобивак' })).not.toEqual(idempotencyHeaders(key, { title: 'Нобивак DHPPi' }));
  });

  it('changes with a new opening of the form, so an identical second record is a second record', () => {
    const body = { title: 'Нобивак' };
    expect(idempotencyHeaders(newFormKey(), body)).not.toEqual(idempotencyHeaders(newFormKey(), body));
  });

  it('is a header value the server accepts: printable ASCII without spaces, at most 128 characters', () => {
    const value = idempotencyHeaders(newFormKey(), { title: 'Привет, мир' })!['Idempotency-Key'];
    expect(value).toMatch(/^[!-~]{1,128}$/);
  });
});
