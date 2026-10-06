/**
 * "Фабрика событий" — the registry of event types (builtin + custom).
 *
 * Builtin types can be relabelled/recolored/re-iconed here too (nothing
 * about them is special once everything is data-driven), but not deleted.
 * Custom types are full CRUD; deleting one is blocked while it still has
 * events, so history never loses a type's field labels out from under it.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Dialog } from 'antd-mobile';
import { Plus, Trash2, Sparkles } from 'lucide-react';

import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { pluralRu } from '../utils/relativeTime';
import { useEventTypes, useInvalidateEventTypes } from '../hooks/useEventTypes';
import { eventTypesService } from '../services/eventTypes.service';
import { pastelColorMap } from '../utils/constants';
import { getEventIcon } from '../utils/iconRegistry';
import { EmptyState } from '../components/EmptyState';
import { LoadError } from '../components/LoadError';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { useAdmin } from '../hooks/useAdmin';
import { useAuth } from '../hooks/useAuth';

export function EventTypesSettings() {
  const navigate = useNavigate();
  const { eventTypes, isLoading, error, refetch } = useEventTypes();
  const invalidate = useInvalidateEventTypes();
  const [askingKey, setAskingKey] = useState<string | null>(null);
  const [deletingKey, setDeletingKey] = useState<string | null>(null);
  // What the person is about to be asked about, with how many records the type has: the number is counted before the
  // question, not discovered in a refusal after it.
  const [pending, setPending] = useState<{ key: string; count: number } | null>(null);
  const { isAdmin } = useAdmin();
  const { username: currentUsername } = useAuth();
  // The family's own types first. The built-in ones are the catalogue, added to a pet in its events; only an administrator
  // changes them, so for everyone else a list of thirty rows to look at and not touch is only noise.
  const listed = [...eventTypes.filter((t) => !t.is_builtin), ...(isAdmin ? eventTypes.filter((t) => t.is_builtin) : [])];

  const askDelete = async (key: string) => {
    if (askingKey) return;
    setAskingKey(key);
    try {
      const count = await eventTypesService.eventsCount(key);
      setPending({ key, count });
    } catch (countError) {
      showToast.failure(getApiErrorMessage(countError, 'Не удалось узнать, сколько записей у типа'));
    } finally {
      setAskingKey(null);
    }
  };

  const handleDelete = async (target: { key: string; count: number }) => {
    setDeletingKey(target.key);
    try {
      await eventTypesService.remove(target.key, target.count > 0);
      invalidate();
      showToast.success('Тип события удалён');
    } catch (deleteError) {
      const message = getApiErrorMessage(deleteError, 'Не удалось удалить тип события');
      showToast.failure(message);
    } finally {
      setDeletingKey(null);
      setPending(null);
    }
  };

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-lg)' }}>
          <h1 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>
            Типы событий
          </h1>
          <p style={{ margin: 'var(--spacing-sm) 0 0 0', fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)' }}>
            Свои типы можно создать с нуля, набор полей вы задаёте сами. Их видят те, с кем вы делитесь питомцем. Готовые события добавляются в «События питомца»
          </p>
        </div>

        {isLoading ? (
          <LoadingSpinner fullscreen={false} />
        ) : error ? (
          // «У вас ничего нет» after a failed request is a lie the person acts on: they start creating types again.
          <LoadError what="типы событий" onRetry={() => refetch()} compact />
        ) : listed.length === 0 ? (
          <EmptyState
            icon={Sparkles}
            title="Своих типов пока нет"
            description="Создайте тип события, чтобы записывать что-то своё. Готовые события добавляются в «События питомца»"
            actionLabel="Создать тип события"
            onAction={() => navigate('/event-types/new')}
          />
        ) : (
          <div className="safe-area-padding">
            {/* One continuous list with row dividers — matches Settings'
                and TilesEditor's rhythm, rather than a stack of floating
                cards with gaps between them. */}
            <div className="card-soft" style={{ overflow: 'hidden' }}>
              {listed.map((eventType, index) => {
                const Icon = getEventIcon(eventType.icon);
                const bg = pastelColorMap[eventType.color] ?? 'var(--tile-blue)';
                // A builtin type is everyone's (an admin's to change); a custom
                // one is its author's, even when family can use it.
                const mine = !eventType.is_builtin && eventType.created_by === currentUsername;
                const editable = eventType.is_builtin ? isAdmin : mine;
                const subtitle = eventType.is_builtin
                  ? (isAdmin ? 'Встроенный' : 'Встроенный, меняет администратор')
                  : mine
                    ? `Свой, ${eventType.fields.length} ${pluralRu(eventType.fields.length, 'поле', 'поля', 'полей')}`
                    : `Добавил(а) ${eventType.created_by}`;
                return (
                  <div
                    key={eventType.key}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '12px',
                      borderTop: index > 0 ? '1px solid var(--app-border-color)' : 'none',
                    }}
                  >
                    <button
                      type="button"
                      disabled={!editable}
                      onClick={() => navigate(`/event-types/${eventType.key}/edit`)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '12px', flex: 1, minWidth: 0,
                        background: 'transparent', border: 'none', textAlign: 'left',
                        cursor: editable ? 'pointer' : 'default', color: 'inherit', opacity: 1,
                        padding: 'var(--spacing-lg)',
                      }}
                    >
                      <div
                        aria-hidden
                        style={{
                          width: 32, height: 32, borderRadius: '8px', flexShrink: 0,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          background: bg, color: 'var(--app-text-on-tile)',
                        }}
                      >
                        <Icon size={18} strokeWidth={2} />
                      </div>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontWeight: 500, fontSize: 'var(--text-md)', color: 'var(--app-text-primary)' }}>
                          {eventType.label}
                        </div>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--app-text-secondary)', marginTop: 'var(--spacing-2xs)' }}>
                          {subtitle}
                        </div>
                      </div>
                    </button>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', paddingRight: '16px', flexShrink: 0 }}>
                      {mine && (
                        <button
                          type="button"
                          className="touch-target"
                          aria-label={`Удалить ${eventType.label}`}
                          onClick={() => void askDelete(eventType.key)}
                          disabled={askingKey === eventType.key || deletingKey === eventType.key}
                          style={{ background: 'transparent', border: 'none', color: 'var(--app-danger-text)', cursor: 'pointer', padding: 6, display: 'flex' }}
                        >
                          <Trash2 size={17} strokeWidth={2} />
                        </button>
                      )}
                      {editable && <span aria-hidden style={{ color: 'var(--app-text-tertiary)', fontSize: 20 }}>›</span>}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div className="safe-area-padding" style={{ paddingTop: 'var(--spacing-md)', paddingBottom: 'var(--spacing-lg)' }}>
          <Button
            block
            color="primary"
            size="large"
            onClick={() => navigate('/event-types/new')}
          >
            <Plus size={18} strokeWidth={2.4} style={{ verticalAlign: 'middle', marginRight: 'var(--spacing-sm)' }} />
            Создать тип события
          </Button>
        </div>
      </div>

      <Dialog
        visible={!!pending}
        title="Удаление типа события"
        content={pending && pending.count > 0
          ? `У типа ${pending.count} ${pluralRu(pending.count, 'запись', 'записи', 'записей')}. Они удалятся вместе с ним, вернуть их будет нельзя`
          : 'У этого типа нет записей, он будет удалён'}
        closeOnAction
        onClose={() => setPending(null)}
        actions={[
          [
            {
              key: 'confirm',
              text: pending && pending.count > 0 ? 'Удалить тип и записи' : 'Удалить',
              bold: true,
              danger: true,
              onClick: () => { if (pending) handleDelete(pending); },
            },
            { key: 'cancel', text: 'Оставить', onClick: () => setPending(null) },
          ],
        ]}
      />
    </div>
  );
}
