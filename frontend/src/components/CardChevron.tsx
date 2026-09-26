import { ChevronRight } from 'lucide-react';

/**
 * The "›" beside a card's title: this card opens a screen when tapped.
 * A touch screen has no hover or cursor to say so, and a card with its
 * own button inside (a medication's «Отметить приём») doesn't read as
 * tappable itself. Only for cards whose tap navigates, like iOS's
 * disclosure indicator; not for ones whose tap opens a dialog.
 */
export function CardChevron() {
  return (
    <ChevronRight
      size={18}
      strokeWidth={2.2}
      aria-hidden
      style={{ display: 'block', flexShrink: 0, color: 'var(--app-text-tertiary)' }}
    />
  );
}
