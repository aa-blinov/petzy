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
import { useEventTypes, useInvalidateEventTypes } from '../hooks/useEventTypes';
import { eventTypesService } from '../services/eventTypes.service';
import { pastelColorMap } from '../utils/constants';
import { getEventIcon } from '../utils/iconRegistry';
import { EmptyState } from '../components/EmptyState';
import { LoadingSpinner } from '../components/LoadingSpinner';

export function EventTypesSettings() {
  const navigate = useNavigate();
  const { eventTypes, isLoading } = useEventTypes();
  const invalidate = useInvalidateEventTypes();
  const [deletingKey, setDeletingKey] = useState<string | null>(null);
  const [confirmKey, setConfirmKey] = useState<string | null>(null);

  const handleDelete = async (key: string) => {
    setDeletingKey(key);
    try {
      await eventTypesService.remove(key);
      invalidate();
      showToast.success('Тип события удалён');
    } catch (error) {
      const message = getApiErrorMessage(error, 'Не удалось удалить тип события');
      showToast.failure(message);
    } finally {
      setDeletingKey(null);
      setConfirmKey(null);
    }
  };

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-lg)' }}>
          <h2 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>
            Типы событий
          </h2>
          <p style={{ margin: 'var(--spacing-sm) 0 0 0', fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)' }}>
            Встроенные типы можно переименовать и перекрасить. Свои можно создать с нуля, набор полей вы задаёте сами
          </p>
        </div>

        {isLoading ? (
          <LoadingSpinner fullscreen={false} />
        ) : eventTypes.length === 0 ? (
          <EmptyState
            icon={Sparkles}
            title="Типов пока нет"
            description="Создайте первый тип события, чтобы записывать что-то своё"
          />
        ) : (
          <div className="safe-area-padding">
            {/* One continuous list with row dividers — matches Settings'
                and TilesEditor's rhythm, rather than a stack of floating
                cards with gaps between them. */}
            <div className="card-soft" style={{ overflow: 'hidden' }}>
              {eventTypes.map((eventType, index) => {
                const Icon = getEventIcon(eventType.icon);
                const bg = pastelColorMap[eventType.color] ?? 'var(--tile-blue)';
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
                      onClick={() => navigate(`/event-types/${eventType.key}/edit`)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: '12px', flex: 1, minWidth: 0,
                        background: 'transparent', border: 'none', textAlign: 'left', cursor: 'pointer',
                        padding: '14px 16px',
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
                        <div style={{ fontWeight: 500, fontSize: '15px', color: 'var(--app-text-primary)' }}>
                          {eventType.label}
                        </div>
                        <div style={{ fontSize: 'var(--text-xs)', color: 'var(--app-text-secondary)', marginTop: 2 }}>
                          {eventType.is_builtin ? 'Встроенный' : `Свой · ${eventType.fields.length} пол.`}
                        </div>
                      </div>
                    </button>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', paddingRight: '16px', flexShrink: 0 }}>
                      {!eventType.is_builtin && (
                        <button
                          type="button"
                          aria-label={`Удалить ${eventType.label}`}
                          onClick={() => setConfirmKey(eventType.key)}
                          disabled={deletingKey === eventType.key}
                          style={{ background: 'transparent', border: 'none', color: 'var(--app-danger-color)', cursor: 'pointer', padding: 6, display: 'flex' }}
                        >
                          <Trash2 size={17} strokeWidth={2} />
                        </button>
                      )}
                      <span aria-hidden style={{ color: 'var(--app-text-tertiary)', fontSize: 20 }}>›</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div className="safe-area-padding" style={{ paddingTop: 'var(--spacing-lg)', paddingBottom: 'var(--spacing-lg)' }}>
          <Button
            block
            color="primary"
            size="large"
            onClick={() => navigate('/event-types/new')}
            style={{ borderRadius: 'var(--radius-md)', fontWeight: 600 }}
          >
            <Plus size={18} strokeWidth={2.4} style={{ verticalAlign: 'middle', marginRight: 6 }} />
            Создать тип события
          </Button>
        </div>
      </div>

      <Dialog
        visible={!!confirmKey}
        title="Удаление типа события"
        content="Тип и его настройки будут удалены. Это действие необратимо"
        closeOnAction
        onClose={() => setConfirmKey(null)}
        actions={[
          [
            { key: 'confirm', text: 'Удалить', bold: true, danger: true, onClick: () => { if (confirmKey) handleDelete(confirmKey); } },
            { key: 'cancel', text: 'Отмена', onClick: () => setConfirmKey(null) },
          ],
        ]}
      />
    </div>
  );
}
