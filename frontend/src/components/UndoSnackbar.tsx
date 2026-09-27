import { useEffect, useRef, useState } from 'react';
import { subscribeUndo, type UndoRequest } from '../utils/undo';
import { showToast } from '../utils/toast';
import { announce } from '../utils/announce';
import './UndoSnackbar.css';

/** How long «Отменить» stays up: long enough to notice a mistake, short
 *  enough not to sit over the tab bar. */
const VISIBLE_MS = 6000;

/** The bar showUndo() raises (utils/undo.ts). Mounted once, in App. */
export function UndoSnackbar() {
  const [request, setRequest] = useState<UndoRequest | null>(null);
  const [pending, setPending] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const unsubscribe = subscribeUndo((next) => {
      if (timer.current) clearTimeout(timer.current);
      setRequest(next);
      setPending(false);
      if (next) {
        announce(next.message, 'polite');
        timer.current = setTimeout(() => setRequest(null), VISIBLE_MS);
      }
    });
    return () => {
      unsubscribe();
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  if (!request) return null;

  const undo = async () => {
    if (pending) return;
    setPending(true);
    if (timer.current) clearTimeout(timer.current);
    try {
      await request.onUndo();
      setRequest(null);
      showToast.success('Отменено');
    } catch {
      setRequest(null);
      showToast.failure('Не удалось отменить');
    }
  };

  return (
    <div className="undo-snackbar" role="status">
      <span className="undo-snackbar__text">{request.message}</span>
      <button type="button" className="undo-snackbar__action" onClick={undo} disabled={pending}>
        Отменить
      </button>
    </div>
  );
}
