import type { ReactNode } from 'react';

/**
 * The sign-in and sign-up screens: the Petzy wordmark over one card.
 */
export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div style={{
      minHeight: 'var(--app-vh)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '16px',
      backgroundColor: 'var(--app-page-background)',
      paddingTop: 'env(safe-area-inset-top)',
      paddingBottom: 'env(safe-area-inset-bottom)',
    }}>
      <div style={{ width: '100%', maxWidth: '400px' }}>
        {/* Stylized wordmark — gradient copper fill, no icon, no subtitle
           so the brand reads as the literal name, not a logo.

           Same face as the navbar wordmark (--app-font-bubble, DynaPuff):
           this and the navbar are the only two places the brand name is
           set, so they have to be the same letterform or the login
           screen reads as a different product. Tracking is kept near the
           navbar's (-0.5px at 28px ≈ -0.018em) — DynaPuff's rounded
           terminals collide under the -0.04em the display face took. */}
        <h1
          style={{
            textAlign: 'center',
            margin: '0 0 32px',
            fontFamily: 'var(--app-font-bubble)',
            fontSize: 56,
            fontWeight: 700,
            letterSpacing: '-0.02em',
            lineHeight: 1,
            background: 'var(--app-brand-gradient)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            color: 'var(--app-accent)',
          }}
        >
          Petzy
        </h1>

        {/* Form card.
            spellCheck / autoCapitalize / autoCorrect sit here rather
            than on the Input: antd-mobile's Input only forwards a
            whitelist of native props, and these three are inherited by
            descendants anyway. A username is not prose — spellcheck
            drew a red squiggle under it (and under nothing else, so the
            two fields read as mismatched), and auto-capitalisation on
            mobile turns "admin" into "Admin" against a case-sensitive
            lookup. */}
        <div
          className="card-soft"
          style={{ padding: 'var(--spacing-xl)' }}
          spellCheck={false}
          autoCapitalize="none"
          autoCorrect="off"
        >
          {children}
        </div>
        <p style={{ margin: '16px 0 0', textAlign: 'center', fontSize: 'var(--text-xs)' }}>
          <a href="/privacy" className="tap-link" style={{ color: 'var(--app-text-secondary)' }}>
            Политика конфиденциальности
          </a>
        </p>
      </div>
    </div>
  );
}
