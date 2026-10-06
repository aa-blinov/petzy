import { useQueryClient } from '@tanstack/react-query';
import { Button } from 'antd-mobile';
import { CloudOff } from 'lucide-react';
import { flushPendingIntakes, usePendingIntakes } from '../utils/offlineIntakes';
import { formatRelativeDateTime } from '../utils/relativeTime';

/**
 * What a person needs to recognise a mark that did not go: which medicine, whose
 * pet it was for, and when it was made. The time is the mark's own date and time,
 * the moment the dose was given. The pet comes from the queue, not from the pet
 * open right now, which is no proof: a queued mark can outlive the screen it was
 * made on. An entry from before this field simply reads without the pet.
 */
function pendingSummary(pending: readonly { name: string; petName?: string; input: { date?: string; time?: string } }[]): string {
  const items = pending.map((item) => {
    const at = [item.input.date, item.input.time].filter(Boolean).join(' ');
    const what = item.petName ? `${item.name} у ${item.petName}` : item.name;
    return at ? `${what}, ${formatRelativeDateTime(at)}` : what;
  });
  return `Не отправлено: ${items.join(', ')}. Отправим, когда появится связь`;
}

/** Doses marked with no connection: «Не отправлено» until they are sent, with a button to try now. */
export function PendingIntakesNotice() {
  const pending = usePendingIntakes();
  const queryClient = useQueryClient();
  if (pending.length === 0) return null;
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
      <span style={{ flex: 1 }}>{pendingSummary(pending)}</span>
      <Button size="mini" fill="none" onClick={() => void flushPendingIntakes(queryClient)} style={{ color: 'inherit' }}>
        Отправить
      </Button>
    </div>
  );
}