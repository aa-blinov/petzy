import { useState } from 'react';
import { CloudOff } from 'lucide-react';
import { EmptyState } from './EmptyState';

interface LoadErrorProps {
  /** What didn't load, in the genitive after «Не удалось загрузить»: «лекарства», «ленту». */
  what: string;
  /** Asks again; the button waits for it. */
  onRetry: () => Promise<unknown> | unknown;
  compact?: boolean;
}

/**
 * A list that failed to load. Shown instead of the empty state: «Здесь
 * будут лекарства питомца» after a failed request told the owner their
 * medicines were gone, and offered to add them again.
 */
export function LoadError({ what, onRetry, compact }: LoadErrorProps) {
  const [retrying, setRetrying] = useState(false);
  const offline = typeof navigator !== 'undefined' && navigator.onLine === false;

  const retry = async () => {
    if (retrying) return;
    setRetrying(true);
    try {
      await onRetry();
    } finally {
      setRetrying(false);
    }
  };

  return (
    <div role="alert">
      <EmptyState
        icon={CloudOff}
        title={`Не удалось загрузить ${what}`}
        description={
          offline
            ? 'Нет связи с интернетом. Когда связь появится, нажмите «Повторить»'
            : 'Сервер не ответил. Ваши записи на месте, попробуйте ещё раз'
        }
        actionLabel={retrying ? 'Загружаем…' : 'Повторить'}
        onAction={retry}
        compact={compact}
      />
    </div>
  );
}
