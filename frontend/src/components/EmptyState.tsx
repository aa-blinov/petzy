/**
 * Shared empty-state component.
 *
 * Used by every list/collection view (Pets, History, Medications,
 * AdminPanel users, HistoryChart). Renders a centered icon circle +
 * title + optional description + optional CTA.
 *
 * Use lucide icons. Pass an `onAction` for a CTA; omit it for purely
 * informational states.
 */

import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';

interface EmptyStateProps {
  /** Lucide icon component to render inside the tinted circle. */
  icon: LucideIcon;
  /** Big heading, e.g. "Здесь будут ваши питомцы". */
  title: string;
  /** Optional secondary line, e.g. "Добавьте первого — Petzy будет считать кормления и вес". */
  description?: string;
  /** CTA button label. Rendered only together with onAction. */
  actionLabel?: string;
  /** CTA callback. */
  onAction?: () => void;
  /** Optional additional content below the CTA (e.g. a link). */
  children?: ReactNode;
  /** Tighter vertical rhythm for inline empty-states inside cards. */
  compact?: boolean;
  /** `h1` where the state is the whole page and has no other heading (a link that no longer works). */
  heading?: 'h1' | 'h2';
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
  children,
  compact = false,
  heading: Heading = 'h2',
}: EmptyStateProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        textAlign: 'center',
        padding: compact ? '24px 16px' : '40px 24px',
      }}
    >
      <div
        aria-hidden
        style={{
          width: 72,
          height: 72,
          borderRadius: 20,
          marginBottom: 'var(--spacing-md)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'var(--app-accent-soft)',
          color: 'var(--app-accent-deep)',
        }}
      >
        <Icon size={36} strokeWidth={1.6} style={{ display: 'block' }} />
      </div>

      <Heading
        className="display-headline"
        style={{
          margin: 0,
          fontSize: 'var(--text-lg)',
          fontWeight: 500,
          color: 'var(--app-text-primary)',
        }}
      >
        {title}
      </Heading>

      {description && (
        <p
          style={{
            margin: 'var(--spacing-sm) 0 0',
            fontSize: 'var(--text-sm)',
            color: 'var(--app-text-secondary)',
            lineHeight: 1.5,
            maxWidth: 320,
          }}
        >
          {description}
        </p>
      )}

      {actionLabel && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="tap-feedback"
          style={{
            marginTop: 'var(--spacing-lg)',
            background: 'var(--app-primary-fill)',
            color: 'var(--app-on-primary-fill)',
            border: 'none',
            borderRadius: 'var(--radius-md)',
            padding: '12px 20px',
            fontSize: 'var(--text-md)',
            fontWeight: 500,
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 'var(--spacing-sm)',
          }}
        >
          {actionLabel}
        </button>
      )}

      {children && (
        <div style={{ marginTop: 'var(--spacing-md)' }}>{children}</div>
      )}
    </div>
  );
}