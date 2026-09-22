import { useEffect, useMemo, useState } from 'react';
import { showToast } from '../utils/toast';
import { Popup, Button, Selector, Form } from 'antd-mobile';
import { exportService, type ExportFormat } from '../services/export.service';
import { useEventTypes } from '../hooks/useEventTypes';
import { buildEventDisplayConfigs } from '../utils/eventDisplay';

/** Matches ALL_TYPES on the backend: one ZIP with a file per record type. */
export const ALL_TYPES = 'all';

interface ExportModalProps {
  visible: boolean;
  onClose: () => void;
  petId: string;
  defaultType?: string;
}

export function ExportModal({ visible, onClose, petId, defaultType = 'feeding' }: ExportModalProps) {
  const { eventTypes } = useEventTypes();
  const displayConfigs = useMemo(() => buildEventDisplayConfigs(eventTypes), [eventTypes]);
  const [exportType, setExportType] = useState<string[]>([defaultType]);
  const [format, setFormat] = useState<string[]>(['csv']);
  const [loading, setLoading] = useState(false);

  // The modal stays mounted between openings, so useState's initial value
  // is only ever read once — without this the type stayed on whatever was
  // picked the first time and stopped following the history filter.
  // Format is deliberately left alone: which file type someone wants is a
  // standing preference, the record type is not.
  useEffect(() => {
    if (visible) setExportType([defaultType]);
  }, [visible, defaultType]);

  
  const handleExport = async () => {
    if (!exportType[0] || !format[0]) {
      showToast.info('Выберите тип данных и формат');
      return;
    }

    setLoading(true);
    try {
      await exportService.exportData(petId, exportType[0], format[0] as ExportFormat);
      showToast.success('Файл успешно скачан');
      onClose();
    } catch {
      showToast.failure('Ошибка при экспорте');
    } finally {
      setLoading(false);
    }
  };

  // "Все типы" ships every type that has records as separate files in one
  // ZIP rather than merging them into a single table: the column sets
  // genuinely differ per type, so a combined sheet would be either lossy
  // or mostly empty cells.
  const typeOptions = [
    { label: 'Все типы (архивом)', value: ALL_TYPES },
    ...Object.entries(displayConfigs).map(([key, config]) => ({
      label: config.displayName,
      value: key,
    })),
  ];

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

