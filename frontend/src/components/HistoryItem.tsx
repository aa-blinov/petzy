import { useState, memo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Toast, Dialog } from 'antd-mobile';
import { Pencil, Trash2 } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import type { HistoryItem as HistoryItemType, HistoryTypeConfig } from '../utils/historyConfig';
import { formatRelativeDateTime } from '../utils/relativeTime';
import { healthRecordsService } from '../services/healthRecords.service';
import { pastelColorMap, typeIconMap, type HealthRecordType } from '../utils/constants';
import { useAuth } from '../hooks/useAuth';
import { SwipeableRow, type SwipeAction } from './SwipeableRow';

interface HistoryItemProps {
  item: HistoryItemType;
  config: HistoryTypeConfig;
  type: string;
  activeTab: string;
}

export const HistoryItem = memo(function HistoryItem({ item, config, type, activeTab }: HistoryItemProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { username: currentUsername } = useAuth();
  const pillBg = pastelColorMap[config.color] || 'var(--tile-blue)';
  const PillIcon = typeIconMap[type];
  const [deleteDialogVisible, setDeleteDialogVisible] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // Hide the author chip when the record was logged by the current user —
  // single-owner households shouldn't see "admin" on every row.
  const showAuthor = item.username && item.username !== currentUsername;
  const canEdit = type !== 'medications';

  const handleEdit = () => {
    // Pass item data via state to avoid extra API call.
    navigate(`/form/${type}/${item._id}?tab=${activeTab}`, { state: { recordData: item } });
  };

  const handleDelete = async () => {
    if (isDeleting) return;
    setIsDeleting(true);
    try {
      await healthRecordsService.delete(type as HealthRecordType, item._id);
      await queryClient.invalidateQueries({ queryKey: ['history'] });

      // If deleting medication intake, also invalidate medications cache to update intakes_today
      if (type === 'medications') {
        await queryClient.invalidateQueries({ queryKey: ['medications'] });
        await queryClient.invalidateQueries({ queryKey: ['medications', 'upcoming'] });
      }

      Toast.show({ content: 'Запись удалена', icon: 'success', duration: 1500 });
      setDeleteDialogVisible(false);
    } catch (error) {
      console.error('Error deleting record:', error);
      Toast.show({ content: 'Ошибка при удалении', icon: 'fail', duration: 2000 });
      setDeleteDialogVisible(false);
    } finally {
      setIsDeleting(false);
    }
  };

  // Actions revealed by swipe. Right-swipe opens edit; left-swipe asks
  // for delete confirmation. Edit action omitted for medication intakes
  // — they're immutable per dose.
  const leftAction: SwipeAction | undefined = canEdit
    ? {
        icon: <Pencil size={20} strokeWidth={2.4} />,
        label: 'Изменить',
        color: 'var(--app-accent)',
        onTrigger: handleEdit,
      }
    : undefined;

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
        disabled={deleteDialogVisible}
      >
        <div
          className="card-soft card-soft--interactive tap-ripple"
          style={{
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
              <span style={{ fontSize: '12px', color: 'var(--app-text-secondary)' }}>
                {item.username}
              </span>
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
              }}
              dangerouslySetInnerHTML={{ __html: config.renderDetails(item) }}
            />
          </div>
        </div>
      </SwipeableRow>

      {/* Delete Confirmation Dialog */}
      <Dialog
        visible={deleteDialogVisible}
        title="Удаление записи"
        content="Вы уверены, что хотите удалить эту запись?"
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
