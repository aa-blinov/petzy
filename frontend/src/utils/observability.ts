import * as Sentry from '@sentry/react';
import type { BrowserOptions } from '@sentry/react';

/** A span as the SDK hands it to beforeSendSpan: the streamed format, which the default trace lifecycle sends. */
type StreamedSpan = Parameters<NonNullable<BrowserOptions['beforeSendSpan']>>[0];

/**
 * Errors, page performance and session replay to Sentry, the same project as the backend
 * (web/observability.py). Off unless the build got VITE_SENTRY_DSN (the
 * deploy passes the SENTRY_DSN secret; local and CI builds have none).
 * The replay shows how the screens moved, never what is on them: every text,
 * every field and every picture is masked or blocked before it is recorded,
 * so pets' records and documents do not leave the phone in it.
 */
/** The part of an event this file touches: the request it happened in. */
interface WithRequest {
  request?: { url?: string; query_string?: unknown; cookies?: unknown; headers?: Record<string, string> };
  transaction?: string;
  breadcrumbs?: { message?: string; data?: Record<string, unknown> }[];
}

/** The page of a link to a pet's medical card has its secret in the address (/share/medical/<secret>); the API call behind it
 *  too (/api/shared/medical-card/<secret>/pdf). Neither goes to Sentry. */
const LINK_SECRET = /(\/shared\/medical-card\/|\/share\/medical\/)[^/?#\s]+/g;

/** The address with the secret of a medical card link replaced by ***; the rest of the address stays. */
export const scrubUrl = (url: string): string => url.replace(LINK_SECRET, '$1***');

/** The address with a one-time token in it replaced. A reset or confirmation link carries
 *  the token in the address, and the address may turn up anywhere: in the name of the event,
 *  in a breadcrumb, in the url of a span. */
const scrubToken = (text: string): string => text.replace(/([?&]token=)[^&#\s]*/, '$1[Filtered]');

/** The address with both secrets taken out of it. */
const scrubAddress = (text: string): string => scrubToken(scrubUrl(text));

/** Belt and braces over dataCollection below: a reset or confirmation
 *  link carries its one-time token in the page URL. */
function scrub<T extends WithRequest>(event: T): T {
  const request = event.request;
  if (request?.url) request.url = scrubAddress(request.url);
  if (event.transaction) event.transaction = scrubAddress(event.transaction);
  for (const crumb of event.breadcrumbs ?? []) {
    if (crumb.message) crumb.message = scrubAddress(crumb.message);
    for (const [key, value] of Object.entries(crumb.data ?? {})) {
      if (typeof value === 'string') crumb.data![key] = scrubAddress(value);
    }
  }
  if (request && typeof request.query_string === 'string' && /token=/.test(request.query_string)) {
    request.query_string = '[Filtered]';
  }
  if (request) delete request.cookies;
  return event;
}

/** A span carries the address too: a page's name is its path, and an API call's name and url attributes hold the whole address. */
function scrubSpan(span: StreamedSpan): StreamedSpan {
  span.name = scrubAddress(span.name);
  for (const [key, value] of Object.entries(span.attributes)) {
    if (typeof value === 'string') span.attributes[key] = scrubAddress(value);
  }
  return span;
}

export function initSentry(): void {
  const dsn = import.meta.env.VITE_SENTRY_DSN as string | undefined;
  if (!dsn) return;
  Sentry.init({
    dsn,
    environment: (import.meta.env.VITE_SENTRY_ENVIRONMENT as string | undefined) || 'production',
    release: (import.meta.env.VITE_SENTRY_RELEASE as string | undefined) || undefined,
    // userInfo is off: the SDK adds no IP address of its own. The login comes from setSentryUser (App.tsx), not from here.
    // Never cookies, the Authorization header or bodies (records, documents, passwords).
    dataCollection: {
      userInfo: false,
      cookies: false,
      httpHeaders: { request: { deny: ['authorization', 'cookie'] }, response: false },
      httpBodies: [],
      urlQueryParams: { deny: ['token'] },
    },
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration({ maskAllText: true, maskAllInputs: true, blockAllMedia: true }),
    ],
    tracesSampleRate: 1.0,
    // One ordinary session in ten, and every session that hit an error.
    replaysSessionSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0,
    // Same-origin /api calls carry the trace, so a slow screen and the
    // backend request behind it show up as one trace.
    tracePropagationTargets: [/^\/api\//],
    beforeSend: (event) => scrub(event),
    beforeSendTransaction: (event) => scrub(event),
    // The default trace lifecycle sends spans, and beforeSendTransaction runs only for the static one: scrub spans here.
    beforeSendSpan: scrubSpan,
  });
}

/** The signed-in login on every event; null after signing out. */
export function setSentryUser(username: string | null): void {
  Sentry.setUser(username ? { username } : null);
}

export function reportError(error: unknown, componentStack?: string): void {
  Sentry.captureException(error, componentStack ? { contexts: { react: { componentStack } } } : undefined);
}
