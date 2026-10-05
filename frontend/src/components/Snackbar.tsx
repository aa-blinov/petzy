import { useState, useSyncExternalStore } from 'react';
import { Check, CircleAlert } from 'lucide-react';
import { closeSnackbar, getSnackbar, runSnackbarAction, subscribeSnackbar } from '../utils/snackbar';
import './Snackbar.css';

/** The bar showSnackbar() raises (utils/snackbar.ts). Mounted once, in App. */
export function Snackbar() {
  const snackbar = useSyncExternalStore(subscribeSnackbar, getSnackbar);
  if (!snackbar) return null;
  // Keyed: a message that replaces another starts its own animation and
  // its own «pending» state.
  return <Bar key={snackbar.id} snackbar={snackbar} />;
}

function Bar({ snackbar }: { snackbar: NonNullable<ReturnType<typeof getSnackbar>> }) {
  const [pending, setPending] = useState(false);
  const { id, tone, message, action } = snackbar;

  const press = async () => {
    if (pending) return;
    setPending(true);
    const ok = await runSnackbarAction(id);
    if (!ok) setPending(false);
  };

  return (
    // The message is spoken through utils/announce; the bar itself is not a
    // second live region (it would be read twice). A tap closes it.
    <div className={`snackbar snackbar--${tone}`} role="region" aria-label="Уведомление" onClick={() => closeSnackbar(id)}>
      {tone === 'success' && <Check className="snackbar__icon" size={18} strokeWidth={2.4} aria-hidden />}
      {tone === 'error' && <CircleAlert className="snackbar__icon" size={18} strokeWidth={2.2} aria-hidden />}
      <span className="snackbar__text">{message}</span>
      {action && (
        <button
          type="button"
          className="snackbar__action"
          disabled={pending}
          onClick={(event) => {
            event.stopPropagation();
            void press();
          }}
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
