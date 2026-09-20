/**
 * Submit button with built-in loading spinner.
 *
 * Wraps a primary CTA so that:
 *  - While `loading`, the label fades out and an inline spinner replaces it.
 *  - The button is auto-disabled while loading to prevent double-submits.
 *  - `aria-busy` is set so screen readers announce the loading state.
 *
 * Visual states come from the surrounding card surface — the button
 * itself is just a 44-px-tall copper pill, matching the shared
 * vocabulary used elsewhere (auth login, admin-panel FAB, etc).
 */

import type { ReactNode, MouseEventHandler } from 'react';
import { Loader2 } from 'lucide-react';

interface SpinnerButtonProps {
  /** Submitting state — shows spinner + disables the button. */
  loading: boolean;
  /** Text rendered when not loading. */
  children: ReactNode;
  /** Click handler (form submit handler in most cases). */
  onClick?: MouseEventHandler<HTMLButtonElement>;
  /** Submit button type — defaults to "submit" for forms. */
  type?: 'button' | 'submit' | 'reset';
  /** Disabled when not loading too — e.g. invalid form. */
  disabled?: boolean;
  /** Optional variant — primary (copper) by default, secondary (ghost) when false. */
  variant?: 'primary' | 'secondary';
  /** Optional extra style passthrough. */
  style?: React.CSSProperties;
  /** Full-width block button. */
  block?: boolean;
}

export function SpinnerButton({
  loading,
  children,
  onClick,
  type = 'submit',
  disabled = false,
  variant = 'primary',
  style,
  block = true,
}: SpinnerButtonProps) {
  const isPrimary = variant === 'primary';
  const isDisabled = disabled || loading;

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={isDisabled}
      aria-busy={loading}
      style={{
        position: 'relative',
        display: block ? 'flex' : 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 8,
        height: 44,
        padding: '0 20px',
        background: isPrimary ? 'var(--app-primary-color)' : 'transparent',
        color: isPrimary ? '#FFFFFF' : 'var(--app-primary-color)',
        border: isPrimary ? 'none' : '1px solid var(--app-primary-color)',
        borderRadius: 'var(--radius-md)',
        fontSize: 'var(--text-md)',
        fontWeight: 600,
        cursor: isDisabled ? 'not-allowed' : 'pointer',
        opacity: isDisabled && !loading ? 0.5 : 1,
        width: block ? '100%' : 'auto',
        transition: `opacity var(--motion-duration-fast) var(--motion-ease-standard), background-color var(--motion-duration-fast) var(--motion-ease-standard)`,
        ...style,
      }}
    >
      {loading && (
        <Loader2
          size={18}
          strokeWidth={2.4}
          style={{
            /* Loop, not a state change — outside the motion scale on purpose. */
        animation: 'spin 700ms linear infinite',
          }}
          aria-hidden
        />
      )}
      <span
        style={{
          opacity: loading ? 0.6 : 1,
          transition: `opacity var(--motion-duration-fast) var(--motion-ease-standard)`,
        }}
      >
        {children}
      </span>
    </button>
  );
}