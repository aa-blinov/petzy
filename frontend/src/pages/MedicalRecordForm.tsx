import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Controller, useForm, useWatch } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button, CheckList, Form, Input, Popup, Selector, TextArea } from 'antd-mobile';
import { medicalCardService } from '../services/medicalCard.service';
import {
  MEDICAL_KIND_LABELS,
  PARASITE_TARGET_LABELS,
  medicalRecordsService,
  type MedicalKind,
  type MedicalRecord,
  type ParasiteTarget,
} from '../services/medicalRecords.service';
import { documentsListQuery, DOCUMENT_CATEGORY_LABELS } from '../services/documents.service';
import { usePet } from '../hooks/usePet';
import { useUnsavedChangesGuard } from '../hooks/useUnsavedChangesGuard';
import { DatePickerField } from '../components/DatePickerField';
import { FieldError } from '../components/FieldError';
import { fieldNote } from '../components/FieldNote';
import { LoadError } from '../components/LoadError';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { PickerValue } from '../components/PickerValue';
import { SpinnerButton } from '../components/SpinnerButton';
import { getApiErrorMessage } from '../utils/apiError';
import { getCurrentDate } from '../utils/dateUtils';
import { deleteWithUndo } from '../utils/deferredDelete';
import { onInvalidSubmit } from '../utils/formErrors';
import { goBack } from '../utils/navigation';
import { addInterval, daysBetween, REPEAT_CHOICES, suggestionsFor } from '../utils/medicalSuggestions';
import { showToast } from '../utils/toast';

const KINDS: MedicalKind[] = ['vaccination', 'parasite', 'visit', 'procedure'];
const isKind = (v: string | null): v is MedicalKind => !!v && (KINDS as string[]).includes(v);

const schema = z
  .object({
    title: z.string().trim().min(1, 'Заполните это поле').max(100),
    date: z.string().min(1, 'Укажите дату'),
    next_due: z.string().optional(),
    target: z.string().optional(),
    batch: z.string().max(50).optional(),
    diagnosis: z.string().max(300).optional(),
    recommendations: z.string().max(500).optional(),
    clinic: z.string().max(100).optional(),
    vet: z.string().max(100).optional(),
    note: z.string().max(500).optional(),
    document_ids: z.array(z.string()),
  })
  .superRefine((data, ctx) => {
    if (data.next_due && data.next_due < data.date) {
      ctx.addIssue({ code: 'custom', path: ['next_due'], message: 'Повтор раньше самой записи' });
    }
  });

type FormData = z.infer<typeof schema>;

const left = { style: { '--text-align': 'left' } as React.CSSProperties };

/** One medical record: a vaccination, a treatment, a visit or a procedure.
    Made to be quick: the date is today, the title is a tap away, the repeat is a
    button, the clinic is already filled in. «Записать снова» and a certificate kept as a
    document both open it pre-filled. */
export function MedicalRecordForm() {
  const { id: petId, recordId } = useParams<{ id: string; recordId?: string }>();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { pets } = usePet();
  const pet = pets.find((p) => p._id === petId);
  const isEditing = !!recordId;
  const cardPath = `/pets/${petId}/medical-card`;

  const card = useQuery({ queryKey: ['medical-card', petId], queryFn: () => medicalCardService.get(petId!), enabled: !!petId });
  const record = useQuery({ queryKey: ['medical-record', recordId], queryFn: () => medicalRecordsService.get(recordId!), enabled: isEditing, staleTime: 0, refetchOnMount: 'always' });
  const documents = useQuery({ ...documentsListQuery(petId ?? ''), enabled: !!petId });

  // The kind: from the record being edited, else from the link.
  const kindParam = params.get('kind');
  const kind: MedicalKind | null = record.data?.kind ?? (isKind(kindParam) ? kindParam : null);
  const labels = kind ? MEDICAL_KIND_LABELS[kind] : null;
  const repeating = kind === 'vaccination' || kind === 'parasite';

  const today = getCurrentDate();
  const { control, handleSubmit, reset, setValue, formState: { isDirty, isSubmitting } } = useForm<FormData>({
    mode: 'onTouched',
    shouldFocusError: false,
    resolver: zodResolver(schema),
    defaultValues: { title: '', date: today, next_due: '', target: '', batch: '', diagnosis: '', recommendations: '', clinic: '', vet: '', note: '', document_ids: [] },
  });
  const { dialog: leaveDialog, release } = useUnsavedChangesGuard(isDirty);
  const date = useWatch({ control, name: 'date' });
  const nextDue = useWatch({ control, name: 'next_due' });
  const title = useWatch({ control, name: 'title' });
  const documentIds = useWatch({ control, name: 'document_ids' });
  const [docsOpen, setDocsOpen] = useState(false);

  // Filled once, when what it needs has arrived: a record being edited, or the
  // defaults (and, when asked, a record or a certificate to copy from) of a new one.
  const filled = useRef(false);
  const fromId = params.get('from');
  const docId = params.get('doc');
  const source: MedicalRecord | undefined = useMemo(
    () => (fromId && kind ? card.data?.records[kind]?.find((r) => r._id === fromId) : undefined),
    [fromId, kind, card.data],
  );
  const sourceDoc = docId ? documents.data?.find((d) => d._id === docId) : undefined;
  useEffect(() => {
    if (filled.current || !kind) return;
    if (isEditing) {
      const r = record.data;
      if (!r) return;
      filled.current = true;
      reset({
        title: r.title, date: r.date, next_due: r.next_due ?? '', target: r.target ?? '', batch: r.batch ?? '', diagnosis: r.diagnosis ?? '',
        recommendations: r.recommendations ?? '', clinic: r.clinic ?? '', vet: r.vet ?? '', note: r.note ?? '', document_ids: r.documents.map((d) => d.id),
      });
      return;
    }
    if (!card.data || (fromId && !source) || (docId && !sourceDoc && documents.isPending)) return;
    filled.current = true;
    // The clinic the pet was last taken to, else the one in its profile.
    const last = Object.values(card.data.records).flat().sort((a, b) => b.date.localeCompare(a.date)).find((r) => r.clinic || r.vet);
    const clinic = last?.clinic ?? card.data.profile.clinic.name ?? '';
    const vet = last?.vet ?? card.data.profile.clinic.vet ?? '';
    const blank: FormData = { title: '', date: today, next_due: '', target: '', batch: '', diagnosis: '', recommendations: '', clinic, vet, note: '', document_ids: [] };
    if (!source && !sourceDoc) {
      reset(blank);
      return;
    }
    // A copy (the same again, or a certificate made a record) is unsaved until
    // «Добавить»: the form starts blank and the copied values are typed into it,
    // so leaving it asks, like any form with typed-in text.
    const copy: Partial<FormData> = {};
    if (source) {
      // The same again, today; the repeat keeps the interval it had.
      copy.title = source.title;
      copy.target = source.target ?? '';
      copy.clinic = source.clinic ?? clinic;
      copy.vet = source.vet ?? vet;
      if (source.next_due) copy.next_due = shiftByDays(today, daysBetween(source.date, source.next_due));
    } else if (sourceDoc) {
      copy.title = sourceDoc.title;
      copy.date = sourceDoc.created_at.slice(0, 10);
      copy.next_due = sourceDoc.expires_at ?? '';
      copy.document_ids = [sourceDoc._id];
    }
    reset(blank);
    (Object.keys(copy) as (keyof FormData)[]).forEach((key) => setValue(key, copy[key] as never, { shouldDirty: true }));
  }, [kind, isEditing, record.data, card.data, source, sourceDoc, documents.isPending, fromId, docId, reset, setValue, today]);

  const own = useMemo(() => (kind && card.data ? card.data.records[kind].map((r) => r.title) : []), [kind, card.data]);
  const chips = kind ? suggestionsFor(kind, pet?.species, own) : [];
  const repeatChoices = kind ? REPEAT_CHOICES[kind] ?? [] : [];

  const save = useMutation({
    mutationFn: async (data: FormData) => {
      const input = {
        date: data.date,
        title: data.title.trim(),
        next_due: repeating && data.next_due ? data.next_due : null,
        clinic: data.clinic?.trim() || null,
        vet: data.vet?.trim() || null,
        note: data.note?.trim() || null,
        batch: kind === 'vaccination' ? data.batch?.trim() || null : null,
        target: kind === 'parasite' ? ((data.target || null) as ParasiteTarget | null) : null,
        diagnosis: kind === 'visit' ? data.diagnosis?.trim() || null : null,
        recommendations: kind === 'visit' ? data.recommendations?.trim() || null : null,
        document_ids: data.document_ids,
      };
      if (isEditing) await medicalRecordsService.update(recordId!, input);
      else await medicalRecordsService.create(petId!, kind!, input);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['medical-card', petId] });
      queryClient.invalidateQueries({ queryKey: ['medical-record', recordId] });
      showToast.success(isEditing ? 'Запись сохранена' : 'Запись добавлена');
      release();
      goBack(navigate, cardPath);
    },
    onError: (err: unknown) => {
      showToast.failure(getApiErrorMessage(err, 'Не удалось сохранить'));
    },
  });

  const onSubmit = (data: FormData) => {
    if (kind === 'parasite' && !data.target) {
      showToast.failure('Укажите, от чего обработка');
      return;
    }
    save.mutate(data);
  };

  if (!petId || !kind) {
    return (
      <div className="page-container">
        <div className="max-width-container safe-area-padding">
          <LoadError what="запись" onRetry={() => (isEditing ? record.refetch() : navigate(cardPath, { replace: true }))} />
        </div>
      </div>
    );
  }
  if (record.isError || card.isError) {
    return (
      <div className="page-container">
        <div className="max-width-container safe-area-padding">
          <LoadError what="запись" onRetry={() => Promise.all([record.refetch(), card.refetch()])} />
        </div>
      </div>
    );
  }
  if (isEditing ? !record.data : !card.data) return <LoadingSpinner />;

  const chosenDocs = (documents.data ?? []).filter((d) => documentIds.includes(d._id));

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-lg)' }}>
          <h1 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>
            {isEditing ? labels!.one : fromId ? 'Записать снова' : `Новая запись: ${labels!.one.toLowerCase()}`}
          </h1>
        </div>

        <Form layout="vertical" mode="card">
          <Controller
            name="title"
            control={control}
            render={({ field, fieldState: { error } }) => (
              <Form.Item label={labels!.titleLabel} required description={error?.message ? <FieldError message={error.message} /> : fieldNote({ value: field.value, max: 100 })}>
                <Input {...left} value={field.value} onChange={field.onChange} onBlur={field.onBlur} placeholder={labels!.titlePlaceholder} maxLength={100} />
                {chips.length > 0 && (
                  <div className="medrec__chips" role="group" aria-label="Подсказки">
                    {chips.map((chip) => (
                      <button
                        key={chip}
                        type="button"
                        className="medrec__chip"
                        aria-pressed={title.trim().toLowerCase() === chip.toLowerCase()}
                        onClick={() => setValue('title', chip, { shouldDirty: true, shouldValidate: true })}
                      >
                        {chip}
                      </button>
                    ))}
                  </div>
                )}
              </Form.Item>
            )}
          />

          {kind === 'parasite' && (
            <Controller
              name="target"
              control={control}
              render={({ field }) => (
                <Form.Item label="От чего" required>
                  <Selector
                    columns={3}
                    options={(Object.keys(PARASITE_TARGET_LABELS) as ParasiteTarget[]).map((value) => ({ label: PARASITE_TARGET_LABELS[value], value }))}
                    value={field.value ? [field.value] : []}
                    onChange={(v) => field.onChange(v[0] ?? '')}
                  />
                </Form.Item>
              )}
            />
          )}

          <Controller
            name="date"
            control={control}
            render={({ field, fieldState: { error } }) => (
              <DatePickerField
                label="Когда сделано"
                value={field.value}
                onChange={field.onChange}
                onBlur={field.onBlur}
                yearsBack={30}
                yearsForward={0}
                description={error?.message ? <FieldError message={error.message} /> : undefined}
              />
            )}
          />

          {repeating && (
            <Controller
              name="next_due"
              control={control}
              render={({ field, fieldState: { error } }) => (
                <>
                  <DatePickerField
                    label="Следующая"
                    value={field.value ?? ''}
                    onChange={field.onChange}
                    onBlur={field.onBlur}
                    yearsBack={0}
                    yearsForward={10}
                    clearLabel="Убрать дату повтора"
                    placeholder="Повтор не нужен"
                    description={error?.message ? <FieldError message={error.message} /> : 'Срок повтора будет виден в медкарте'}
                  />
                  <Form.Item>
                    <div className="medrec__chips" role="group" aria-label="Повторить через">
                      {repeatChoices.map((choice) => {
                        const target = addInterval(date || today, choice);
                        return (
                          <button
                            key={choice.label}
                            type="button"
                            className="medrec__chip"
                            aria-pressed={nextDue === target}
                            onClick={() => setValue('next_due', target, { shouldDirty: true, shouldValidate: true })}
                          >
                            {choice.label}
                          </button>
                        );
                      })}
                    </div>
                  </Form.Item>
                </>
              )}
            />
          )}

          {kind === 'vaccination' && (
            <Controller
              name="batch"
              control={control}
              render={({ field }) => (
                <Form.Item label="Серия или лот" description={fieldNote({ value: field.value, max: 50 })}>
                  <Input {...left} value={field.value ?? ''} onChange={field.onChange} onBlur={field.onBlur} placeholder="Необязательно" maxLength={50} />
                </Form.Item>
              )}
            />
          )}

          {kind === 'visit' && (
            <>
              <Controller
                name="diagnosis"
                control={control}
                render={({ field }) => (
                  <Form.Item label="Диагноз" description={fieldNote({ value: field.value, max: 300 })}>
                    <Input {...left} value={field.value ?? ''} onChange={field.onChange} onBlur={field.onBlur} placeholder="Необязательно" maxLength={300} />
                  </Form.Item>
                )}
              />
              <Controller
                name="recommendations"
                control={control}
                render={({ field }) => (
                  <Form.Item label="Рекомендации врача" layout="vertical" description={fieldNote({ value: field.value, max: 500, always: true })}>
                    <TextArea value={field.value ?? ''} onChange={field.onChange} onBlur={field.onBlur} placeholder="Необязательно" maxLength={500} rows={3} autoSize={{ minRows: 3, maxRows: 8 }} />
                  </Form.Item>
                )}
              />
            </>
          )}

          <Controller
            name="clinic"
            control={control}
            render={({ field }) => (
              <Form.Item label="Клиника">
                <Input {...left} value={field.value ?? ''} onChange={field.onChange} onBlur={field.onBlur} placeholder="Необязательно" maxLength={100} />
              </Form.Item>
            )}
          />
          <Controller
            name="vet"
            control={control}
            render={({ field }) => (
              <Form.Item label="Врач">
                <Input {...left} value={field.value ?? ''} onChange={field.onChange} onBlur={field.onBlur} placeholder="Необязательно" maxLength={100} />
              </Form.Item>
            )}
          />
          <Controller
            name="note"
            control={control}
            render={({ field }) => (
              <Form.Item label="Заметка" layout="vertical" description={fieldNote({ value: field.value, max: 500, always: true })}>
                <TextArea value={field.value ?? ''} onChange={field.onChange} onBlur={field.onBlur} placeholder="Необязательно" maxLength={500} rows={2} autoSize={{ minRows: 2, maxRows: 6 }} />
              </Form.Item>
            )}
          />

          <Form.Item
            label="Документы"
            clickable
            arrow
            onClick={() => setDocsOpen(true)}
            description="Сертификат, выписка, фото наклейки. Добавляются в разделе «Документы»"
          >
            <PickerValue value={chosenDocs.length ? chosenDocs.map((d) => d.title).join(', ') : ''} placeholder="Не прикреплены" />
          </Form.Item>
        </Form>

        <div className="safe-area-padding" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)', margin: 'var(--spacing-xl) 0' }}>
          <SpinnerButton loading={save.isPending || isSubmitting} onClick={() => handleSubmit(onSubmit, onInvalidSubmit)()}>
            {isEditing ? 'Сохранить' : 'Добавить'}
          </SpinnerButton>
          <Button block size="large" onClick={() => goBack(navigate, cardPath)}>
            Отмена
          </Button>
          {isEditing && (
            <Button
              block
              size="large"
              fill="none"
              color="danger"
              onClick={() => {
                deleteWithUndo({
                  id: recordId!,
                  path: `/medical-records/${recordId}`,
                  message: 'Запись удалена',
                  onDeleted: () => queryClient.invalidateQueries({ queryKey: ['medical-card', petId] }),
                });
                release();
                goBack(navigate, cardPath);
              }}
            >
              Удалить запись
            </Button>
          )}
        </div>
      </div>

      <Popup visible={docsOpen} onMaskClick={() => setDocsOpen(false)} onClose={() => setDocsOpen(false)} bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, maxHeight: '70vh', overflow: 'auto' }}>
        <div style={{ padding: 'var(--spacing-md)' }}>
          <h2 style={{ margin: '0 0 var(--spacing-sm)', fontSize: 'var(--text-lg)' }}>Документы питомца</h2>
          {(documents.data ?? []).length === 0 ? (
            <p style={{ color: 'var(--app-text-secondary)' }}>Документов пока нет. Добавьте их в разделе «Документы».</p>
          ) : (
            <CheckList
              multiple
              value={documentIds}
              onChange={(v) => setValue('document_ids', v as string[], { shouldDirty: true })}
            >
              {(documents.data ?? []).map((d) => (
                <CheckList.Item key={d._id} value={d._id} description={DOCUMENT_CATEGORY_LABELS[d.category]}>
                  {d.title}
                </CheckList.Item>
              ))}
            </CheckList>
          )}
          <Button block color="primary" size="large" style={{ marginTop: 'var(--spacing-md)' }} onClick={() => setDocsOpen(false)}>
            Готово
          </Button>
        </div>
      </Popup>
      {leaveDialog}
    </div>
  );
}

/** Today moved by a number of days, as YYYY-MM-DD. */
function shiftByDays(isoDate: string, days: number): string {
  const [y, m, d] = isoDate.split('-').map(Number);
  const date = new Date(y, m - 1, d + days);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}
