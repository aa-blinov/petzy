import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Dialog, Form, TextArea } from 'antd-mobile';
import { isAxiosError } from 'axios';
import { FileHeart } from 'lucide-react';

import { medicalCardService, VISIT_CHECKS, VISIT_CHECK_LABELS, type VisitCheck, type VisitPrep } from '../services/medicalCard.service';
import { EmptyState } from '../components/EmptyState';
import { LoadError } from '../components/LoadError';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { SpinnerButton } from '../components/SpinnerButton';
import { fieldNote } from '../components/FieldNote';
import { httpStatus } from '../services/api';
import { usePet } from '../hooks/usePet';
import { useUnsavedChangesGuard } from '../hooks/useUnsavedChangesGuard';
import { useSessionDraft } from '../hooks/useSessionDraft';
import { goBack } from '../utils/navigation';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import './MedicalRecordForm.css';
import { ChoiceChip, ChoiceChips } from '../components/ChoiceChips';

type Checks = VisitPrep['checks'];
type Typed = { complaint: string; checks: Checks };

/** «К приёму»: what to tell the vet next time. The complaint, and for each thing a vet asks about (appetite, thirst,
    stool, …) «как обычно» or «изменилось»; a thing left alone was not answered. It waits on the pet until a visit is
    recorded, then it is cleared. */
export function VisitPrepForm() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const cardPath = `/pets/${id}/medical-card`;
  const { pets, selectedPetId, selectPet } = usePet();
  // The same as the card: the address of another pet makes that pet the chosen one, so the switcher at the top is not lying.
  useEffect(() => {
    const target = pets.find((p) => p._id === id);
    if (target && target._id !== selectedPetId) selectPet(target);
  }, [id, pets, selectedPetId, selectPet]);

  const query = useQuery({
    queryKey: ['medical-card', id],
    queryFn: () => medicalCardService.get(id!),
    enabled: !!id,
    staleTime: 0,
    refetchOnMount: 'always',
  });
  const saved = query.data?.visit_prep ?? null;

  // What was typed on this screen; until something is, what is saved is shown.
  const [typed, setTyped] = useState<Typed | null>(null);
  const complaint = typed?.complaint ?? saved?.complaint ?? '';
  const checks: Checks = typed?.checks ?? saved?.checks ?? {};
  // Changed means it says something the saved note does not: an answer taken back leaves the note as it was, and the
  // question about leaving then has nothing to ask about.
  const savedChecks: Checks = saved?.checks ?? {};
  const changed = complaint.trim() !== (saved?.complaint ?? '').trim() || Object.keys(checks).some((key) => checks[key as VisitCheck] !== savedChecks[key as VisitCheck]) || Object.keys(savedChecks).some((key) => !(key in checks));
  const dirty = typed !== null && changed;
  const { dialog: leaveDialog, release } = useUnsavedChangesGuard(dirty);
  useSessionDraft({
    dirty,
    petId: id ?? null,
    getValues: () => typed as Typed,
    reset: (values) => setTyped(values),
    ready: !!query.data,
    release,
  });

  // The version the form was made from: the server refuses a save from an older one (someone else saved since).
  const baseVersion = useRef<string | null>(null);
  const loaded = useRef(false);
  useEffect(() => {
    if (!query.data || loaded.current) return;
    loaded.current = true;
    baseVersion.current = saved?.version ?? null;
  }, [query.data, saved]);

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
    mutationFn: () => medicalCardService.saveVisitPrep(id!, { complaint: complaint.trim() || null, checks, base_version: baseVersion.current ?? '' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['medical-card', id] });
      // What happened to the note, said as it happened: only a note that was there can be taken away.
      showToast.success(empty && saved ? 'Заметка к приёму убрана' : empty ? 'Заметка не заполнена' : 'Записано к приёму');
      release();
      goBack(navigate, cardPath);
    },
    onError: (err: unknown) => {
      // 409 with the note as it is now: say so and let the person look at it, instead of saving over it.
      const current = isAxiosError(err) && err.response?.status === 409 ? (err.response.data as { visit_prep?: VisitPrep | null } | undefined)?.visit_prep : undefined;
      if (current !== undefined) {
        void resolveConflict(current);
        return;
      }
      showToast.failure(getApiErrorMessage(err, 'Не удалось сохранить'));
    },
  });

  // Someone else saved the note while this form was open. Saving over it would wipe what they wrote: say so,
  // and let the person take their copy, or knowingly keep their own version.
  const resolveConflict = async (current: VisitPrep | null) => {
    const showCurrent = await Dialog.confirm({
      title: 'Заметку изменили в другом месте',
      content: 'Пока вы её правили, её сохранили с другого устройства или в другой форме. Показать, что там сейчас? Ваши правки в этой форме тогда не сохранятся',
      confirmText: 'Показать актуальную',
      cancelText: 'Сохранить мою',
    });
    baseVersion.current = current?.version ?? null;
    if (showCurrent) {
      setTyped(null);
      queryClient.invalidateQueries({ queryKey: ['medical-card', id] });
      showToast.info(current ? 'Показали актуальную заметку. Внесите правки ещё раз' : 'Заметку убрали в другом месте');
    } else {
      save.mutate();
    }
  };

  if (query.isError) {
    // A pet that is gone and a screen that did not load are different: one asks the person to go back to the list,
    // the other to try once more.
    const gone = [403, 404].includes(httpStatus(query.error) ?? 0);
    return (
      <div className="page-container">
        <div className="max-width-container safe-area-padding">
          {gone ? (
            <EmptyState icon={FileHeart} title="Питомец не найден" description="Возможно, его удалили или закрыли вам доступ" actionLabel="К питомцам" onAction={() => navigate('/pets', { replace: true })} />
          ) : (
            <LoadError what="анкету к приёму" onRetry={() => query.refetch()} />
          )}
        </div>
      </div>
    );
  }
  if (!query.data) return <LoadingSpinner />;

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-lg)' }}>
          <h1 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 500, margin: 0 }}>К приёму</h1>
          <p className="medrec__pet">{query.data.pet.name}</p>
          <p style={{ margin: '4px 0 0', fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)' }}>
            Врач увидит это первой строкой. После записи визита заметка очищается
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
        <div className="safe-area-padding form-actions">
          <Button block size="large" onClick={() => goBack(navigate, cardPath)}>
            Отмена
          </Button>
        </div>
      </div>
      {leaveDialog}
    </div>
  );
}
