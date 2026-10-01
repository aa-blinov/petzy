import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Form, TextArea } from 'antd-mobile';
import { medicalCardService, VISIT_CHECKS, VISIT_CHECK_LABELS, type VisitCheck, type VisitPrep } from '../services/medicalCard.service';
import { LoadError } from '../components/LoadError';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { SpinnerButton } from '../components/SpinnerButton';
import { fieldNote } from '../components/FieldNote';
import { useUnsavedChangesGuard } from '../hooks/useUnsavedChangesGuard';
import { goBack } from '../utils/navigation';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import './MedicalRecordForm.css';
import { ChoiceChip, ChoiceChips } from '../components/ChoiceChips';

type Checks = VisitPrep['checks'];

/** «К приёму»: what to tell the vet next time. The complaint, and for each thing a vet asks about (appetite, thirst,
    stool, …) «как обычно» or «изменилось»; a thing left alone was not answered. It waits on the pet until a visit is
    recorded, then it is cleared. */
export function VisitPrepForm() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const cardPath = `/pets/${id}/medical-card`;

  const query = useQuery({
    queryKey: ['medical-card', id],
    queryFn: () => medicalCardService.get(id!),
    enabled: !!id,
    staleTime: 0,
    refetchOnMount: 'always',
  });
  const saved = query.data?.visit_prep ?? null;

  // What was typed on this screen; until something is, what is saved is shown.
  const [typed, setTyped] = useState<{ complaint: string; checks: Checks } | null>(null);
  const complaint = typed?.complaint ?? saved?.complaint ?? '';
  const checks: Checks = typed?.checks ?? saved?.checks ?? {};
  const dirty = typed !== null;
  const { dialog: leaveDialog, release } = useUnsavedChangesGuard(dirty);

  const setComplaint = (value: string) => setTyped({ complaint: value, checks });
  const setCheck = (key: VisitCheck, value: 'normal' | 'changed') => {
    const next = { ...checks };
    // The same answer again takes it back: a thing can go back to «not answered».
    if (next[key] === value) delete next[key];
    else next[key] = value;
    setTyped({ complaint, checks: next });
  };

  const empty = !complaint.trim() && Object.keys(checks).length === 0;

  const save = useMutation({
    mutationFn: () => medicalCardService.saveVisitPrep(id!, { complaint: complaint.trim() || null, checks }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['medical-card', id] });
      showToast.success(empty ? 'Заметка к приёму убрана' : 'Записано к приёму');
      release();
      goBack(navigate, cardPath);
    },
    onError: (err: unknown) => showToast.failure(getApiErrorMessage(err, 'Не удалось сохранить')),
  });

  if (query.isError) {
    return (
      <div className="page-container">
        <div className="max-width-container safe-area-padding">
          <LoadError what="анкету к приёму" onRetry={() => query.refetch()} />
        </div>
      </div>
    );
  }
  if (!query.data) return <LoadingSpinner />;

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-lg)' }}>
          <h1 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>К приёму</h1>
          <p className="medrec__pet">{query.data.pet.name}</p>
          <p style={{ margin: '4px 0 0', fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)' }}>
            Врач увидит это первой строкой. После записи визита заметка очищается.
          </p>
        </div>

        <Form layout="vertical" mode="card">
          <Form.Item label="Что беспокоит" layout="vertical" description={fieldNote({ value: complaint, max: 500 })}>
            <TextArea
              value={complaint}
              onChange={setComplaint}
              placeholder="Например, третий день не ест, кашляет по ночам"
              maxLength={500}
              rows={3}
              autoSize={{ minRows: 3, maxRows: 8 }}
            />
          </Form.Item>
          <Form.Header>Что изменилось</Form.Header>
          {VISIT_CHECKS.map((key) => (
            <Form.Item key={key} label={VISIT_CHECK_LABELS[key]}>
              <ChoiceChips label={VISIT_CHECK_LABELS[key]} flush>
                <ChoiceChip pressed={checks[key] === 'normal'} onClick={() => setCheck(key, 'normal')}>
                  Как обычно
                </ChoiceChip>
                <ChoiceChip pressed={checks[key] === 'changed'} onClick={() => setCheck(key, 'changed')}>
                  Изменилось
                </ChoiceChip>
              </ChoiceChips>
            </Form.Item>
          ))}
        </Form>

        <div className="form-sticky-action safe-area-padding">
          <SpinnerButton loading={save.isPending} onClick={() => save.mutate()}>
            {empty && saved ? 'Убрать заметку' : 'Сохранить'}
          </SpinnerButton>
        </div>
        <div className="safe-area-padding" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)', margin: 'var(--spacing-md) 0 var(--spacing-xl)' }}>
          <Button block size="large" onClick={() => goBack(navigate, cardPath)}>
            Отмена
          </Button>
        </div>
      </div>
      {leaveDialog}
    </div>
  );
}
