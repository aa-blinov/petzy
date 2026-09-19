import { useState, memo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Toast, Dialog } from 'antd-mobile';
import { EditSOutline, DeleteOutline } from 'antd-mobile-icons';
import { useQueryClient } from '@tanstack/react-query';
import type { HistoryItem as HistoryItemType, HistoryTypeConfig } from '../utils/historyConfig';
import { formatRelativeDateTime } from '../utils/relativeTime';
import { healthRecordsService } from '../services/healthRecords.service';
import { pastelColorMap, typeIconMap, type HealthRecordType } from '../utils/constants';

interface HistoryItemProps {
  item: HistoryItemType;
  config: HistoryTypeConfig;
  type: string;
  activeTab: string;
}

export const HistoryItem = memo(function HistoryItem({ item, config, type, activeTab }: HistoryItemProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const pillBg = pastelColorMap[config.color] || 'var(--tile-blue)';
  const PillIcon = typeIconMap[type];
  const [deleteDialogVisible, setDeleteDialogVisible] = useState(false);

  const handleEdit = () => {
    // Pass item data via state to avoid extra API call
    // ActiveTab is now in URL, so we pass it as query parameter
    navigate(`/form/${type}/${item._id}?tab=${activeTab}`, { state: { recordData: item } });
  };

  const handleDelete = async () => {
    try {
      await healthRecordsService.delete(type as HealthRecordType, item._id);
      await queryClient.invalidateQueries({ queryKey: ['history'] });

      // If deleting medication intake, also invalidate medications cache to update intakes_today
      if (type === 'medications') {
        await queryClient.invalidateQueries({ queryKey: ['medications'] });
        await queryClient.invalidateQueries({ queryKey: ['medications', 'upcoming'] });
      }

      Toast.show({ content: 'Запись удалена', icon: 'success', duration: 1500 });

      // Small delay to let Toast render before unmounting
      setTimeout(() => {
        setDeleteDialogVisible(false);
      }, 100);
    } catch (error) {
      console.error('Error deleting record:', error);
      Toast.show({ content: 'Ошибка при удалении', icon: 'fail', duration: 2000 });
      setDeleteDialogVisible(false);
    }
  };

  return (
    <>
      <div
        className="card-soft"
        style={{
          display: 'flex',
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
          {PillIcon ? <PillIcon size={22} strokeWidth={2} /> : null}
        </div>

        {/* Body */}
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {/* Header row: date + actions */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
            <span
              className="display-headline"
              style={{ fontSize: '15px', fontWeight: 600 }}
            >
              {formatRelativeDateTime(item.date_time)}
            </span>

            {/* Action buttons — kept small and discrete */}
            <div style={{ display: 'flex', gap: '4px', flexShrink: 0 }}>
              {type !== 'medications' && (
                <Button
                  size="mini"
                  fill="none"
                  onClick={handleEdit}
                  style={{
                    width: '32px',
                    height: '32px',
                    padding: 0,
                    borderRadius: '10px',
                    color: 'var(--app-text-secondary)',
                    '--background-color': 'transparent',
                  } as React.CSSProperties}
                >
                  <EditSOutline style={{ fontSize: '16px' }} />
                </Button>
              )}
              <Button
                size="mini"
                fill="none"
                onClick={() => setDeleteDialogVisible(true)}
                style={{
                  width: '32px',
                  height: '32px',
                  padding: 0,
                  borderRadius: '10px',
                  color: 'var(--app-text-tertiary)',
                  '--background-color': 'transparent',
                } as React.CSSProperties}
              >
                <DeleteOutline style={{ fontSize: '16px' }} />
              </Button>
            </div>
          </div>

          {item.username && (
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
            text: 'Удалить',
            danger: true,
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
