import { useNavigate } from 'react-router-dom';
import { Card, Button, Toast } from 'antd-mobile';
import { useQueryClient } from '@tanstack/react-query';
import type { HistoryItem as HistoryItemType, HistoryTypeConfig } from '../utils/historyConfig';
import { formatDateTime } from '../utils/historyConfig';
import { healthRecordsService } from '../services/healthRecords.service';
import type { HealthRecordType } from '../utils/constants';

interface HistoryItemProps {
  item: HistoryItemType;
  config: HistoryTypeConfig;
  type: string;
}

// Пастельные цвета для карточек истории (соответствуют дашборду)
const pastelColorMap: Record<string, string> = {
  brown: '#E8D5C4',    // Пастельный коричневый
  orange: '#FFE5B4',   // Пастельный оранжевый
  red: '#FFD1CC',      // Пастельный красный
  green: '#D4F4DD',    // Пастельный зеленый
  purple: '#E8D5F2',   // Пастельный фиолетовый
  teal: '#D4F4F1',     // Пастельный бирюзовый
  cyan: '#D4F0FF',     // Пастельный голубой
  yellow: '#FFF9D4',   // Пастельный желтый
  blue: '#D4E8FF',     // Пастельный синий
  pink: '#FFE5EB',     // Пастельный розовый
};

export function HistoryItem({ item, config, type }: HistoryItemProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const backgroundColor = pastelColorMap[config.color] || '#D4E8FF';

  const handleEdit = () => {
    navigate(`/form/${type}/${item._id}`);
  };

  const handleDelete = async () => {
    const confirmed = window.confirm('Вы уверены, что хотите удалить эту запись?');
    if (confirmed) {
      try {
        await healthRecordsService.delete(type as HealthRecordType, item._id);
        await queryClient.invalidateQueries({ queryKey: ['history'] });
        Toast.show({ content: 'Запись удалена', icon: 'success' });
      } catch (error) {
        console.error('Error deleting record:', error);
        Toast.show({ content: 'Ошибка при удалении', icon: 'fail' });
      }
    }
  };

  return (
    <Card
      style={{
        backgroundColor: backgroundColor,
        borderRadius: '12px',
        border: 'none',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
      }}
    >
      <div style={{ padding: '16px' }}>
        <div style={{ 
          color: '#000000', 
          fontWeight: 500, 
          marginBottom: '8px', 
          fontSize: '16px' 
        }}>
          {formatDateTime(item.date_time)}
        </div>
        {item.username && (
          <div style={{ color: '#666666', fontSize: '14px', marginBottom: '12px' }}>
            <strong>Пользователь:</strong> {item.username}
          </div>
        )}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            marginBottom: '16px',
            color: '#000000',
          }}
          dangerouslySetInnerHTML={{ __html: config.renderDetails(item) }}
        />
        <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
          <Button
            size="small"
            fill="outline"
            onClick={handleEdit}
            style={{
              '--text-color': '#000000',
              '--border-color': 'rgba(0, 0, 0, 0.15)',
            }}
          >
            Редактировать
          </Button>
          <Button
            size="small"
            fill="outline"
            onClick={handleDelete}
            style={{
              '--text-color': '#000000',
              '--border-color': 'rgba(0, 0, 0, 0.15)',
            }}
          >
            Удалить
          </Button>
        </div>
      </div>
    </Card>
  );
}

