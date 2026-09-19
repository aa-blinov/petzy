import { useState, memo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Toast, Dialog, Card } from 'antd-mobile';
import { EditSOutline, DeleteOutline } from 'antd-mobile-icons';
import { useQueryClient } from '@tanstack/react-query';
import type { HistoryItem as HistoryItemType, HistoryTypeConfig } from '../utils/historyConfig';
import { formatRelativeDateTime } from '../utils/relativeTime';
import { healthRecordsService } from '../services/healthRecords.service';
import { pastelColorMap, type HealthRecordType } from '../utils/constants';

interface HistoryItemProps {
  item: HistoryItemType;
  config: HistoryTypeConfig;
  type: string;
  activeTab: string;
}

export const HistoryItem = memo(function HistoryItem({ item, config, type, activeTab }: HistoryItemProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const backgroundColor = pastelColorMap[config.color] || 'var(--tile-blue)';
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
      <Card
        style={{
          backgroundColor: backgroundColor,
          borderRadius: '12px',
          border: 'none',
          boxShadow: 'var(--app-shadow)',
        }}
      >
        <div style={{ padding: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
            <span style={{ fontWeight: 700, color: 'var(--app-text-on-tile)', fontSize: '17px' }}>{formatRelativeDateTime(item.date_time)}</span>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              {type !== 'medications' && (
                <Button
                  size="mini"
                  fill="outline"
                  onClick={handleEdit}
                  style={{
                    '--text-color': 'var(--app-text-on-tile)',
                    '--border-color': 'var(--app-black-20)',
                  } as React.CSSProperties}
                >
                  <EditSOutline style={{ color: 'var(--app-text-on-tile)', fontSize: '16px' }} />
                </Button>
              )}
              <Button
                size="mini"
                color="danger"
                fill="outline"
                onClick={() => setDeleteDialogVisible(true)}
              >
                <DeleteOutline />
              </Button>
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {item.username && (
              <span style={{ fontSize: '12px', color: 'var(--app-text-secondary-on-tile)' }}>Пользователь: {item.username}</span>
            )}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
                color: 'var(--app-text-on-tile)',
              }}
              dangerouslySetInnerHTML={{ __html: config.renderDetails(item) }}
            />
          </div>
        </div>
      </Card>

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
