import { useState, memo } from 'react';
import { deleteWithUndo } from '../utils/deferredDelete';
import { showToast } from '../utils/toast';
import { useNavigate } from 'react-router-dom';
import { Dialog } from 'antd-mobile';
import { Pencil, Trash2 } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import type { HistoryItem as HistoryItemType, EventDisplayConfig } from '../utils/eventDisplay';
import { formatRelativeDateTime } from '../utils/relativeTime';
import { medicationsService, type IntakeInput } from '../services/medications.service';
import { showUndo } from '../utils/undo';
import { INTAKE_UNDO_MS } from '../utils/stock';
import { refreshAfterIntake } from '../utils/intakeViews';
import { pastelColorMap } from '../utils/constants';
import { useAuth } from '../hooks/useAuth';
import { SwipeableRow, type SwipeAction } from './SwipeableRow';
import { UserAvatar } from './UserAvatar';
import { CardChevron } from './CardChevron';
import { IntakeTimePicker } from './IntakeTimePicker';
import { whenLabel, whenPhrase, type IntakeWhen } from '../utils/intakeWhen';

interface HistoryItemProps {
  item: HistoryItemType;
  config: EventDisplayConfig;
  type: string;
  activeTab: string;
}

export const HistoryItem = memo(function HistoryItem({ item, config, type, activeTab }: HistoryItemProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { username: currentUsername } = useAuth();
  const pillBg = pastelColorMap[config.color] || 'var(--tile-blue)';
  const PillIcon = config.icon;
  // A medication intake isn't a form: its tap offers what can change
  // about a dose, its time (marked late, or by mistake), or deleting it.
  const [intakeInfoVisible, setIntakeInfoVisible] = useState(false);
  const [timePickerVisible, setTimePickerVisible] = useState(false);

  // Hide the author chip when the record was logged by the current user —
  // single-owner households shouldn't see "admin" on every row.
  const showAuthor = item.username && item.username !== currentUsername;
  const isIntake = type === 'medications';
  const canEdit = !isIntake;
  const [intakeDate = '', intakeTime = '00:00'] = String(item.date_time).split(' ');
  const intakeWhen: IntakeWhen = { date: intakeDate, time: intakeTime.slice(0, 5) };

  const moveIntake = async (when: IntakeWhen) => {
    try {
      await medicationsService.updateIntakeTime(item._id, when);
      await refreshAfterIntake(queryClient);
      showToast.success(`Время приёма: ${whenPhrase(when)}`);
    } catch {
      showToast.failure('Не удалось изменить время');
    }
  };

  const handleEdit = () => {
    // Pass item data via state to avoid extra API call.
    navigate(`/form/${type}/${item._id}?tab=${activeTab}`, { state: { recordData: item } });
  };

  // A dose is deleted at once, so the stock, the dose card and the slot are right straight away; «Отменить» writes the same
  // dose again (its dose, time, slot and comment). An event waits on its undo bar instead (utils/deferredDelete.ts).
  const deleteIntake = async () => {
    const name = String(item.medication_name || 'лекарство');
    const skipped = !!item.skipped;
    const again: IntakeInput = {
      date: intakeDate,
      time: intakeTime.slice(0, 5),
      dose_taken: skipped ? undefined : Number(item.dose_taken) || undefined,
      comment: typeof item.comment === 'string' && item.comment ? item.comment : undefined,
      skipped: skipped || undefined,
      slot_date: typeof item.slot_date === 'string' ? item.slot_date : undefined,
      slot_time: typeof item.slot_time === 'string' ? item.slot_time : undefined,
      force: true,
    };
    try {
      await medicationsService.deleteIntake(item._id);
    } catch {
      showToast.failure('Не удалось удалить приём');
      return;
    }
    await refreshAfterIntake(queryClient);
    showUndo({
      duration: INTAKE_UNDO_MS,
      message: `Удалён приём: ${name}, ${intakeTime.slice(0, 5)}`,
      onUndo: async () => {
        await medicationsService.logIntake(String(item.medication_id), again);
        await refreshAfterIntake(queryClient);
      },
    });
  };

  // No «Удалить эту запись?»: the record leaves the lists at once and
  // «Отменить» stays at the bottom for a few seconds; the server is only
  // asked when that time is up (utils/deferredDelete.ts).
  const handleDelete = () => {
    setIntakeInfoVisible(false);
    if (isIntake) {
      void deleteIntake();
      return;
    }
    deleteWithUndo({
      id: item._id,
      path: `/events/${item._id}`,
      message: `Удалена запись: ${config.displayName}`,
      onDeleted: () =>
        // See HealthRecordForm's onSubmit for why this is a predicate rather
        // than queryKey: ['history'] — none of these views' query keys start
        // with 'history', so that form never actually matched anything.
        queryClient.invalidateQueries({
          predicate: (query) =>
            ['timeline', 'history-timeline', 'stats', 'pet-summary'].includes(query.queryKey[0] as string),
        }),
    });
  };

  // Swipe shortcuts for what a tap and the edit form's button also do.
  // Right-swipe opens edit (for a dose, its time); left-swipe deletes, with «Отменить».
  const leftAction: SwipeAction = {
    icon: <Pencil size={20} strokeWidth={2.4} />,
    label: 'Изменить',
    color: 'var(--app-accent)',
    onTrigger: isIntake ? () => setTimePickerVisible(true) : handleEdit,
  };

  const rightAction: SwipeAction = {
    icon: <Trash2 size={20} strokeWidth={2.4} />,
    label: 'Удалить',
    color: 'var(--app-danger-color)',
    onTrigger: handleDelete,
  };

  return (
    <>
      <SwipeableRow
        leftAction={leftAction}
        rightAction={rightAction}
        disabled={intakeInfoVisible || timePickerVisible}
        itemLabel={`${config.displayName}, ${formatRelativeDateTime(item.date_time)}`}
      >
        <div
          className="card-soft card-soft--interactive"
          // A card that opens is a button for the keyboard and a screen reader too: Tab reaches it, Enter and Space open it.
          role="button"
          tabIndex={0}
          aria-label={`${config.displayName}, ${formatRelativeDateTime(item.date_time)}, открыть`}
          onKeyDown={(event) => {
            if (event.target !== event.currentTarget) return;
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              (canEdit ? handleEdit : () => setIntakeInfoVisible(true))();
            }
          }}
          onClick={canEdit ? handleEdit : () => setIntakeInfoVisible(true)}
          style={{
            cursor: 'pointer',
            display: 'flex',
            // Pill-icon sits on the first text line (the title). Aligning
            // with the row's vertical centre made the title drift above
            // the icon and the row looked unanchored.
            alignItems: 'flex-start',
            gap: '12px',
            padding: '14px',
          }}
        >
          {/* Pill-icon on the left — tinted rounded square with category icon */}
          <div
            className="pill-icon"
            style={{ backgroundColor: pillBg, color: 'var(--app-text-on-tile)' }}
            aria-hidden
          >
            {PillIcon ? <PillIcon size={22} strokeWidth={2} style={{ display: 'block' }} /> : null}
          </div>

          {/* Body */}
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {/* Header row: what it is, and when. An icon alone does not say «Смена лотка». */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '8px', flexWrap: 'wrap' }}>
              <span
                className="display-headline"
                style={{ fontSize: '15px', fontWeight: 600 }}
              >
                {config.displayName}
              </span>
              <span style={{ fontSize: '13px', color: 'var(--app-text-secondary)' }}>
                {formatRelativeDateTime(item.date_time)}
              </span>
            </div>

            {showAuthor && (
              <button
                type="button"
                className="touch-target"
                onClick={(e) => {
                  e.stopPropagation();
                  navigate(`/users/${item.username}`);
                }}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  alignSelf: 'flex-start',
                  background: 'none',
                  border: 'none',
                  padding: 0,
                  cursor: 'pointer',
                  fontSize: '12px',
                  color: 'var(--app-text-secondary)',
                  font: 'inherit',
                }}
              >
                <UserAvatar username={item.username!} size={16} />
                {item.username}
              </button>
            )}

            {/* Details — rendered as plain text blocks */}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '2px',
                color: 'var(--app-text-primary)',
                fontSize: '14px',
                lineHeight: 1.45,
                overflowWrap: 'anywhere',
              }}
            >
              {/* Three lines at most: a 500-character comment filled the
                  screen; the whole of it is in the record itself. */}
              {config.details(item).map((line, i) => (
                <span key={i} className="clamp-3">
                  <strong>{line.label}:</strong> {line.value}
                </span>
              ))}
            </div>
          </div>
          <span style={{ alignSelf: 'center' }}><CardChevron /></span>
        </div>
      </SwipeableRow>

      <Dialog
        visible={intakeInfoVisible}
        title={item.skipped ? 'Пропущенный приём' : 'Приём лекарства'}
        content={
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontWeight: 600 }}>{String(item.medication_name || 'Лекарство')}</div>
            <div style={{ marginTop: 4 }}>{whenLabel(intakeWhen)}</div>
            <div style={{ marginTop: 'var(--spacing-md)', fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)' }}>
              Если время неверное, поправьте его. Отметили по ошибке? Удалите
            </div>
          </div>
        }
        closeOnAction
        onClose={() => setIntakeInfoVisible(false)}
        getContainer={() => document.body}
        actions={[
          { key: 'time', text: 'Изменить время', bold: true, onClick: () => setTimePickerVisible(true) },
          { key: 'delete', text: 'Удалить', danger: true, onClick: handleDelete },
          { key: 'close', text: 'Закрыть', onClick: () => setIntakeInfoVisible(false) },
        ]}
      />

      {isIntake && (
        <IntakeTimePicker
          visible={timePickerVisible}
          value={intakeWhen}
          title={item.skipped ? 'Когда был приём' : 'Когда дали'}
          onClose={() => setTimePickerVisible(false)}
          onConfirm={moveIntake}
        />
      )}
    </>
  );
});
