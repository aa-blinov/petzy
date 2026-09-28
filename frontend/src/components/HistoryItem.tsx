import { useState, memo } from 'react';
import { showToast } from '../utils/toast';
import { useNavigate } from 'react-router-dom';
import { Dialog } from 'antd-mobile';
import { Pencil, Trash2 } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import type { HistoryItem as HistoryItemType, EventDisplayConfig } from '../utils/eventDisplay';
import { formatRelativeDateTime } from '../utils/relativeTime';
import { healthRecordsService } from '../services/healthRecords.service';
import { medicationsService } from '../services/medications.service';
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
  const [deleteDialogVisible, setDeleteDialogVisible] = useState(false);
  // A medication intake isn't a form: its tap offers what can change
  // about a dose, its time (marked late, or by mistake), or deleting it.
  const [intakeInfoVisible, setIntakeInfoVisible] = useState(false);
  const [timePickerVisible, setTimePickerVisible] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

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

  const handleDelete = async () => {
    if (isDeleting) return;
    setIsDeleting(true);
    try {
      if (type === 'medications') {
        // An intake is not an event: deleting it through /events/ was a
        // 404, so a dose could never be removed from the feed or History.
        await medicationsService.deleteIntake(item._id);
        await refreshAfterIntake(queryClient);
      } else {
        await healthRecordsService.delete(item._id);
        // See HealthRecordForm's onSubmit for why this is a predicate rather
        // than queryKey: ['history'] — none of these views' query keys start
        // with 'history', so that form never actually matched anything.
        await queryClient.invalidateQueries({
          predicate: (query) =>
            ['timeline', 'history-timeline', 'stats', 'pet-summary'].includes(query.queryKey[0] as string),
        });
      }

      showToast.success('Запись удалена');
      setDeleteDialogVisible(false);
      setIntakeInfoVisible(false);
    } catch (error) {
      console.error('Error deleting record:', error);
      showToast.failure('Не удалось удалить');
      setDeleteDialogVisible(false);
      setIntakeInfoVisible(false);
    } finally {
      setIsDeleting(false);
    }
  };

  // Swipe shortcuts for what a tap and the edit form's button also do.
  // Right-swipe opens edit (for a dose, its time); left-swipe asks to delete.
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
    onTrigger: () => setDeleteDialogVisible(true),
  };

  return (
    <>
      <SwipeableRow
        leftAction={leftAction}
        rightAction={rightAction}
        disabled={deleteDialogVisible || intakeInfoVisible || timePickerVisible}
        itemLabel={`${config.displayName}, ${formatRelativeDateTime(item.date_time)}`}
      >
        <div
          className="card-soft card-soft--interactive"
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
            {/* Header row: relative date/time */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
              <span
                className="display-headline"
                style={{ fontSize: '15px', fontWeight: 600 }}
              >
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
          { key: 'delete', text: isDeleting ? 'Удаление...' : 'Удалить', danger: true, disabled: isDeleting, onClick: handleDelete },
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

      {/* Delete Confirmation Dialog */}
      <Dialog
        visible={deleteDialogVisible}
        title="Удаление записи"
        content="Удалить эту запись?"
        closeOnAction
        onClose={() => setDeleteDialogVisible(false)}
        getContainer={() => document.body}
        actions={[
          {
            key: 'delete',
            text: isDeleting ? 'Удаление...' : 'Удалить',
            danger: true,
            disabled: isDeleting,
            onClick: handleDelete,
          },
          {
            key: 'cancel',
            text: 'Отмена',
            onClick: () => setDeleteDialogVisible(false),
          },
        ]}
      />
    </>
  );
});
