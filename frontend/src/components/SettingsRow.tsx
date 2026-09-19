/**
 * Reusable settings row — icon + label/description + control/chevron.
 *
 * Renders as a <button> when `onClick` is provided, otherwise a <div>.
 * Use the `.setting-row` class from globals.css for the consistent
 * warm-minimal look that pairs with our copper accent.
 */

import type { ReactNode } from 'react';

interface SettingsRowProps {
  icon: ReactNode;
  label: ReactNode;
  description?: ReactNode;
  control?: ReactNode;   // right-aligned control (Switch, badge, ...)
  chevron?: boolean;     // show right-pointing chevron
  onClick?: () => void;
  danger?: boolean;
}

export function SettingsRow({
  icon,
  label,
  description,
  control,
  chevron,
  onClick,
  danger,
}: SettingsRowProps) {
  const interactive = !!onClick;

  const content = (
    <>
      <div className="setting-row__icon" aria-hidden>
        {icon}
      </div>
      <div className="setting-row__body">
        <div className="setting-row__label">{label}</div>
        {description != null && (
          <div className="setting-row__description">{description}</div>
        )}
      </div>
      {(control || chevron) && (
        <div className="setting-row__trailing">
          {control}
          {chevron && !control && (
            <span aria-hidden style={{ color: 'var(--app-text-tertiary)', fontSize: 20 }}>›</span>
          )}
        </div>
      )}
    </>
  );

  const className = `setting-row${danger ? ' setting-row--danger' : ''}`;

  if (interactive) {
    return (
      <button type="button" className={className} onClick={onClick}>
        {content}
      </button>
    );
  }
  return <div className={className}>{content}</div>;
}
