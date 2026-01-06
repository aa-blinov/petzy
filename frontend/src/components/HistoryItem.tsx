import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Toast, Dialog, Card } from 'antd-mobile';
import { EditSOutline, DeleteOutline } from 'antd-mobile-icons';
import { useQueryClient } from '@tanstack/react-query';
import type { HistoryItem as HistoryItemType, HistoryTypeConfig } from '../utils/historyConfig';
import { formatDateTime } from '../utils/historyConfig';
import { healthRecordsService } from '../services/healthRecords.service';
import type { HealthRecordType } from '../utils/constants';

interface HistoryItemProps {
  item: HistoryItemType;
  config: HistoryTypeConfig;
  type: string;
  activeTab: string;
}

// Пастельные цвета для карточек истории (соответствуют дневнику)
const pastelColorMap: Record<string, string> = {
  brown: '#E8D5C4',
  orange: '#FFE5B4',
  red: '#FFD1CC',
  green: '#D4F4DD',
  purple: '#E8D5F2',
  teal: '#D4F4F1',
  cyan: '#D4F0FF',
  yellow: '#FFF9D4',
  blue: '#D4E8FF',
  pink: '#FFE5EB',
};

export function HistoryItem({ item, config, type, activeTab }: HistoryItemProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const backgroundColor = pastelColorMap[config.color] || '#D4E8FF';
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
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
        }}
      >
        <div style={{ padding: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
            <span style={{ fontWeight: 600, color: '#000000', fontSize: '16px' }}>{formatDateTime(item.date_time)}</span>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <Button
                size="mini"
                fill="outline"
                onClick={handleEdit}
                style={{
                  '--text-color': '#000000',
                  '--border-color': 'rgba(0, 0, 0, 0.3)',
                } as React.CSSProperties}
              >
                <EditSOutline style={{ color: '#000000', fontSize: '16px' }} />
              </Button>
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
              <span style={{ fontSize: '12px', color: '#666666' }}>Пользователь: {item.username}</span>
            )}
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
                color: '#000000',
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
}
