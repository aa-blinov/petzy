import { useSyncExternalStore } from 'react';
import { isUpdateReady, subscribeUpdate } from '../utils/swUpdate';

/** «Вышла новая версия»: a release reached the server while the app was open. One tap loads it; it stays until then. */
export function UpdateBanner() {
  const ready = useSyncExternalStore(subscribeUpdate, isUpdateReady);
  if (!ready) return null;
  return (
    <div className="snackbar snackbar--update" role="status">
      <span className="snackbar__text">Вышла новая версия Petzy</span>
      <button type="button" className="snackbar__action" onClick={() => window.location.reload()}>
        Обновить
      </button>
    </div>
  );
}
