import { useState } from 'react';
import { Popup, Button, Selector, Form, Toast } from 'antd-mobile';
import { exportService } from '../services/export.service';
import { historyConfig } from '../utils/historyConfig';

interface ExportModalProps {
  visible: boolean;
  onClose: () => void;
  petId: string;
  defaultType?: string;
}

export function ExportModal({ visible, onClose, petId, defaultType = 'feeding' }: ExportModalProps) {
  const [exportType, setExportType] = useState<string[]>([defaultType]);
  const [format, setFormat] = useState<string[]>(['csv']);
  const [loading, setLoading] = useState(false);

  // Update export type when defaultType changes and modal opens
  // (Optional, can be handled by useEffect if needed, but simplistic approach works too)
  
  const handleExport = async () => {
    if (!exportType[0] || !format[0]) {
      Toast.show({ content: 'Выберите тип данных и формат' });
      return;
    }

    setLoading(true);
    try {
      await exportService.exportData(petId, exportType[0], format[0] as any);
      Toast.show({ content: 'Файл успешно скачан', icon: 'success' });
      onClose();
    } catch (error) {
      Toast.show({ content: 'Ошибка при экспорте', icon: 'fail' });
    } finally {
      setLoading(false);
    }
  };

  const typeOptions = Object.entries(historyConfig).map(([key, config]) => ({
    label: config.displayName,
    value: key,
  }));

  const formatOptions = [
    { label: 'CSV (Excel)', value: 'csv' },
    { label: 'TSV', value: 'tsv' },
    { label: 'HTML', value: 'html' },
    { label: 'Markdown', value: 'md' },
  ];

  return (
    <Popup
      visible={visible}
      onMaskClick={onClose}
      onClose={onClose}
      bodyStyle={{ borderTopLeftRadius: '8px', borderTopRightRadius: '8px' }}
    >
      <div style={{ padding: '16px' }}>
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center', 
          marginBottom: '16px' 
        }}>
          <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 600 }}>Экспорт данных</h3>
          <Button fill="none" size="small" onClick={onClose}>Закрыть</Button>
        </div>

        <Form layout="vertical">
          <Form.Item label="Тип данных">
            <Selector
              options={typeOptions}
              value={exportType}
              onChange={v => setExportType(v)}
              columns={1}
            />
          </Form.Item>

          <Form.Item label="Формат файла">
            <Selector
              options={formatOptions}
              value={format}
              onChange={v => setFormat(v)}
              columns={2}
            />
          </Form.Item>

          <Button 
            block 
            color="primary" 
            onClick={handleExport}
            loading={loading}
            style={{ marginTop: '16px' }}
          >
            Скачать файл
          </Button>
        </Form>
      </div>
    </Popup>
  );
}

