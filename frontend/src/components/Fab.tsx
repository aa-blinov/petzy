import { createPortal } from 'react-dom';
import { AddOutline } from 'antd-mobile-icons';

import { useFabAway } from '../hooks/useFabAway';

/** The round «+» that adds a thing to a list: at the bottom right under the thumb on every screen that has one (the feed, the
    medical card, the documents, the medicines, the pets). In a portal, so that no page-level containing block moves it, and
    stepping aside on a scroll down. `popup`: it opens a sheet and not a screen. */
export function Fab({ label, onClick, popup = false }: { label: string; onClick: () => void; popup?: boolean }) {
  const away = useFabAway();
  return createPortal(
    <button type="button" className={`app-fab${away ? ' app-fab--away' : ''}`} aria-label={label} aria-haspopup={popup ? 'dialog' : undefined} onClick={onClick}>
      <AddOutline fontSize={28} aria-hidden />
    </button>,
    document.body,
  );
}
