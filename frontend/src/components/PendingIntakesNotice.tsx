import { useQueryClient } from '@tanstack/react-query';
import { Button } from 'antd-mobile';
import { CloudOff } from 'lucide-react';
import { flushPendingIntakes, usePendingIntakes } from '../utils/offlineIntakes';

/** Doses marked with no connection: «Не отправлено» until they are sent, with a button to try now. */
export function PendingIntakesNotice() {
  const pending = usePendingIntakes();
  const queryClient = useQueryClient();
  if (pending.length === 0) return null;
  const names = [...new Set(pending.map((p) => p.name))].join(', ');
  return (
    <div
      role="status"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--spacing-sm)',
        padding: 'var(--spacing-sm) var(--spacing-md)',
        marginBottom: 'var(--spacing-md)',
        borderRadius: 'var(--radius-sm)',
        backgroundColor: 'var(--app-warning-soft, var(--app-danger-soft))',
        color: 'var(--app-warning-text, var(--app-danger-text))',
        fontSize: 'var(--text-sm)',
      }}
    >
      <CloudOff size={16} strokeWidth={2} style={{ display: 'block', flexShrink: 0 }} aria-hidden />
      <span style={{ flex: 1 }}>Не отправлено: {names}. Отправим, когда появится связь</span>
      <Button size="mini" fill="none" onClick={() => void flushPendingIntakes(queryClient)} style={{ color: 'inherit', fontWeight: 600 }}>
        Отправить
      </Button>
    </div>
  );
}
