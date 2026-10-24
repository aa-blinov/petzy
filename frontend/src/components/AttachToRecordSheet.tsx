import { useMemo } from 'react';
import { Popup } from 'antd-mobile';
import { Check } from 'lucide-react';
import { useMutation, useQuery } from '@tanstack/react-query';

import { useRefreshAfterLink } from '../hooks/useRefreshAfterLink';
import { DraggableSheetBody } from './DraggableSheetBody';
import { medicalRecordsService } from '../services/medicalRecords.service';
import { attachDocumentToRecord, buildRecordRows, MAX_RECORD_DOCUMENTS, type RecordRow } from '../utils/documentRecords';
import { getApiErrorMessage } from '../utils/apiError';
import { hapticFeedback } from '../utils/haptic';
import { showToast } from '../utils/toast';
import './ChoiceSheetField.css';

/**
 * «Прикрепить к записи»: the pet's records, newest first, and a tap on one puts the document among its files. The records that
 * already hold it are marked, and so are the ones with no room left (a record holds ten documents at most).
 */
export function AttachToRecordSheet({
  visible,
  onClose,
  petId,
  documentId,
}: {
  visible: boolean;
  onClose: () => void;
  petId: string;
  documentId: string;
}) {
  const refresh = useRefreshAfterLink(petId);
  const records = useQuery({
    queryKey: ['medical-records', petId, 'all'],
    queryFn: () => medicalRecordsService.list(petId),
    enabled: visible,
    staleTime: 0,
  });
  const rows = useMemo(() => buildRecordRows(records.data ?? [], documentId), [records.data, documentId]);

  const attach = useMutation({
    mutationFn: (recordId: string) => attachDocumentToRecord(recordId, documentId),
    onSuccess: async () => {
      await refresh();
      showToast.success('Документ прикреплён к записи');
      onClose();
    },
    onError: (err: unknown) => {
      showToast.failure(getApiErrorMessage(err, 'Не удалось прикрепить документ'));
      void records.refetch();
    },
  });

  const pick = (row: RecordRow) => {
    if (attach.isPending) return;
    if (row.full) {
      showToast.info(`К записи можно прикрепить не больше ${MAX_RECORD_DOCUMENTS} документов`);
      return;
    }
    hapticFeedback('light');
    attach.mutate(row.id);
  };

  return (
    <Popup visible={visible} onMaskClick={onClose} position="bottom" closeOnSwipe bodyStyle={{ background: 'transparent' }}>
      <DraggableSheetBody visible={visible} onClose={onClose} maxHeight="75vh" label="Прикрепить к записи">
        <h2 className="choice-sheet__title">Прикрепить к записи</h2>
        {records.isError ? (
          <p className="choice-sheet__empty">Не удалось загрузить записи</p>
        ) : records.isFetching && !records.data ? (
          <p className="choice-sheet__empty">Загружаем записи…</p>
        ) : rows.length === 0 ? (
          <p className="choice-sheet__empty">Записей пока нет: прививки, обработки, визиты и операции записываются в медкарте</p>
        ) : (
          <ul className="choice-sheet__list">
            {rows.map((row) => (
              <li key={row.id}>
                <button
                  type="button"
                  className={`choice-sheet__row tap-feedback${row.attached ? ' choice-sheet__row--chosen' : ''}`}
                  disabled={row.attached || attach.isPending}
                  aria-disabled={row.full || undefined}
                  onClick={() => pick(row)}
                >
                  <span className="choice-sheet__label">
                    {row.label}
                    {row.attached && <span className="choice-sheet__note">Уже прикреплён</span>}
                    {row.full && <span className="choice-sheet__note">{`Уже ${MAX_RECORD_DOCUMENTS} документов`}</span>}
                  </span>
                  {row.attached && <Check size={18} strokeWidth={2.4} aria-hidden />}
                </button>
              </li>
            ))}
          </ul>
        )}
      </DraggableSheetBody>
    </Popup>
  );
}
