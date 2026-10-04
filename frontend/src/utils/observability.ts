import * as Sentry from '@sentry/react';

/**
 * Errors and page performance to Sentry, the same project as the backend
 * (web/observability.py). Off unless the build got VITE_SENTRY_DSN (the
 * deploy passes the SENTRY_DSN secret; local and CI builds have none).
 * No session replay: it would record pets' records and documents.
 */
/** The part of an event this file touches: the request it happened in. */
interface WithRequest {
  request?: { url?: string; query_string?: unknown; cookies?: unknown; headers?: Record<string, string> };
  transaction?: string;
  breadcrumbs?: { message?: string; data?: Record<string, unknown> }[];
}

/** The page of a link to a pet's medical card has its secret in the address (/share/medical/<secret>); the API call behind it
 *  too. Neither goes to Sentry. */
const LINK_SECRET = /(\/shared\/medical-card\/|\/share\/medical\/)[^/?#\s]+/g;
const scrubLink = (text: string) => text.replace(LINK_SECRET, '$1[Filtered]');

/** Belt and braces over dataCollection below: a reset or confirmation
 *  link carries its one-time token in the page URL. */
function scrub<T extends WithRequest>(event: T): T {
  const request = event.request;
  if (request?.url) request.url = scrubLink(request.url);
  if (event.transaction) event.transaction = scrubLink(event.transaction);
  for (const crumb of event.breadcrumbs ?? []) {
    if (crumb.message) crumb.message = scrubLink(crumb.message);
    for (const [key, value] of Object.entries(crumb.data ?? {})) {
      if (typeof value === 'string') crumb.data![key] = scrubLink(value);
    }
  }
  if (request?.url && /[?&]token=/.test(request.url)) {
    request.url = request.url.replace(/([?&]token=)[^&#]*/, '$1[Filtered]');
  }
  if (request && typeof request.query_string === 'string' && /token=/.test(request.query_string)) {
    request.query_string = '[Filtered]';
  }
  if (request) delete request.cookies;
  return event;
}

export function initSentry(): void {
  const dsn = import.meta.env.VITE_SENTRY_DSN as string | undefined;
  if (!dsn) return;
  Sentry.init({
    dsn,
    environment: (import.meta.env.VITE_SENTRY_ENVIRONMENT as string | undefined) || 'production',
    release: (import.meta.env.VITE_SENTRY_RELEASE as string | undefined) || undefined,
    // The user and their address, as the backend sends; never cookies,
    // the Authorization header or bodies (records, documents, passwords).
    dataCollection: {
      userInfo: true,
      cookies: false,
      httpHeaders: { request: { deny: ['authorization', 'cookie'] }, response: false },
      httpBodies: [],
      urlQueryParams: { deny: ['token'] },
    },
    integrations: [Sentry.browserTracingIntegration()],
    tracesSampleRate: 1.0,
    // Same-origin /api calls carry the trace, so a slow screen and the
    // backend request behind it show up as one trace.
    tracePropagationTargets: [/^\/api\//],
    beforeSend: (event) => scrub(event),
    beforeSendTransaction: (event) => scrub(event),
  });
}

/** The signed-in login on every event; null after signing out. */
export function setSentryUser(username: string | null): void {
  Sentry.setUser(username ? { username } : null);
}

export function reportError(error: unknown, componentStack?: string): void {
  Sentry.captureException(error, componentStack ? { contexts: { react: { componentStack } } } : undefined);
}
