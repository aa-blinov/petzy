import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

/**
 * The sign-in and sign-up screens: the Petzy wordmark over one card.
 *
 * `title` is what the screen is called: it is drawn as the page's `h1`, so
 * the tab in the browser and the focus after a move are named after the
 * screen rather than after the product (RouteFocus reads the `h1`). Without a
 * title the wordmark stays the `h1`, the way a screen with no heading of its
 * own has to keep one.
 */
export function AuthShell({ title, children }: { title?: string; children: ReactNode }) {
  const wordmark = (
    <div
      aria-hidden={title ? true : undefined}
      style={{
        textAlign: 'center',
        margin: '0 0 var(--spacing-xxl)',
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
    </div>
  );

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
           terminals collide under the -0.04em the display face took.

           Not a heading: the screen's own title is the `h1` below, and a
           screen reader shouldn't hear the product's name where the
           screen's name belongs. A screen without a title keeps the
           wordmark as its `h1`. */}
        {title ? wordmark : <h1 style={{ margin: 0 }}>{wordmark}</h1>}

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
          {title && (
            <h1
              style={{
                margin: '0 0 var(--spacing-md)',
                fontSize: 'var(--text-lg)',
                fontWeight: 600,
                lineHeight: 1.3,
                textAlign: 'center',
                color: 'var(--app-text-primary)',
              }}
            >
              {title}
            </h1>
          )}
          {children}
        </div>
        <p style={{ margin: 'var(--spacing-md) 0 0', textAlign: 'center', fontSize: 'var(--text-xs)' }}>
          <Link to="/privacy" className="tap-link" style={{ color: 'var(--app-text-secondary)' }}>
            Политика конфиденциальности
          </Link>
        </p>
      </div>
    </div>
  );
}
