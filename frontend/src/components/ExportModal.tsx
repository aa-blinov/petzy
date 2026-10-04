import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { eventTypesService } from '../services/eventTypes.service';
import { getApiErrorMessage } from '../utils/apiError';
import { showToast } from '../utils/toast';
import { Popup, Button, Selector, Form } from 'antd-mobile';
import { exportService, type ExportFormat } from '../services/export.service';
import { useEventTypes } from '../hooks/useEventTypes';
import { usePet } from '../hooks/usePet';
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
  const { pets } = usePet();
  const displayConfigs = useMemo(() => buildEventDisplayConfigs(eventTypes), [eventTypes]);
  const [exportType, setExportType] = useState<string[]>([defaultType]);
  // Only what the pet has records of: the catalogue is long, and a file of a type with nothing in it is not worth a chip.
  const used = useQuery({ queryKey: ['used-types', petId], queryFn: () => eventTypesService.usedBy(petId), enabled: visible && !!petId, staleTime: 0 });
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
      const saved = await exportService.exportData(petId, exportType[0], format[0] as ExportFormat);
      if (saved) {
        showToast.success('Файл сохранён');
        onClose();
      }
    } catch (err) {
      showToast.failure(getApiErrorMessage(err, 'Не удалось экспортировать'));
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
    ...Object.entries(displayConfigs)
      .filter(([key]) => key === 'medications' || key === defaultType || exportType.includes(key) || (used.data ?? []).includes(key))
      .map(([key, config]) => ({
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
      bodyStyle={{ borderTopLeftRadius: 'var(--radius-xl)', borderTopRightRadius: 'var(--radius-xl)' }}
    >
      <div style={{ padding: '16px' }}>
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center', 
          marginBottom: '16px' 
        }}>
          <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 600 }}>Экспорт: {pets.find((p) => p._id === petId)?.name ?? 'данные питомца'}</h3>
          <Button fill="none" size="small" onClick={onClose}>Закрыть</Button>
        </div>

        <Form layout="vertical">
          <Form.Item label="Тип данных">
            <Selector
              className="selector-chips export-chips"
              options={typeOptions}
              value={exportType}
              onChange={v => v.length && setExportType(v)}
            />
          </Form.Item>

          <Form.Item label="Формат файла">
            <Selector
              className="selector-chips export-chips"
              options={formatOptions}
              value={format}
              onChange={v => v.length && setFormat(v)}
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

