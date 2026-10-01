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
import { documentsListQuery, documentsService, DOCUMENT_CATEGORY_LABELS, type DocumentCategory } from '../services/documents.service';
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
import { getCurrentDate, getCurrentTime } from '../utils/dateUtils';
import { healthRecordsService } from '../services/healthRecords.service';
import { deleteWithUndo } from '../utils/deferredDelete';
import { onInvalidSubmit } from '../utils/formErrors';
import { goBack } from '../utils/navigation';
import { addInterval, daysBetween, REPEAT_CHOICES, suggestionsFor } from '../utils/medicalSuggestions';
import { showToast } from '../utils/toast';
import { confirmWithProgress } from '../utils/medicalReadiness';
import { formatFileSize } from '../utils/fileSize';
import { Camera, FileUp, FileText, X } from 'lucide-react';
import './MedicalRecordForm.css';

/** «Когда сделано» in one tap: a record is often entered a day, a week or a year after the fact,
    and the day, month, year wheels are a long way to turn for that. */
const QUICK_DATES: { label: string; date: (today: string) => string }[] = [
  { label: 'Сегодня', date: (today) => today },
  { label: 'Вчера', date: (today) => shiftByDays(today, -1) },
  { label: 'Неделю назад', date: (today) => shiftByDays(today, -7) },
  { label: 'Месяц назад', date: (today) => addInterval(today, { months: -1 }) },
  { label: 'Год назад', date: (today) => addInterval(today, { years: -1 }) },
];

/** A file added in the form: a photo or a PDF, up to the size the Documents accept. */
const MAX_FILE_BYTES = 10 * 1024 * 1024;
const MAX_DOCUMENTS = 10; // the most one record points at
/** The Documents category a file made here is filed under, by the kind of record. */
const UPLOAD_CATEGORY: Record<MedicalKind, DocumentCategory> = {
  vaccination: 'vaccination',
  parasite: 'other',
  visit: 'conclusion',
  procedure: 'other',
};

interface StagedFile {
  key: string;
  file: File;
}

/** A file waiting to be saved with the record: a small picture for a photo, an icon for a PDF. */
function StagedRow({ item, onRemove }: { item: StagedFile; onRemove: () => void }) {
  const isImage = item.file.type.startsWith('image/');
  const preview = useMemo(() => (isImage ? URL.createObjectURL(item.file) : null), [isImage, item.file]);
  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview);
  }, [preview]);
  return (
    <li className="medrec__file">
      {preview ? <img src={preview} alt="" className="medrec__file-thumb" /> : <FileText size={28} strokeWidth={1.6} aria-hidden className="medrec__file-icon" />}
      <span className="medrec__file-name">
        {item.file.name}
        <span className="medrec__file-size">{formatFileSize(item.file.size)}</span>
      </span>
      <button type="button" className="touch-target medrec__file-remove" aria-label={`Убрать файл ${item.file.name}`} onClick={onRemove}>
        <X size={18} strokeWidth={2.2} aria-hidden />
      </button>
    </li>
  );
}

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
    weight: z
      .string()
      .optional()
      .refine((v) => !v?.trim() || (Number(v.replace(',', '.')) > 0 && Number(v.replace(',', '.')) <= 100), 'Вес от 0 до 100 кг'),
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

/** The date field is named for what it dates: a visit is not «сделано». */
const DATE_LABELS: Partial<Record<MedicalKind, string>> = {
  vaccination: 'Когда сделана прививка',
  parasite: 'Когда обработали',
  visit: 'Дата визита',
  procedure: 'Дата операции',
};

/** A label of a field that must be filled in: a red star the screen readers skip (the field itself says it is required). */
function RequiredLabel({ children }: { children: React.ReactNode }) {
  return (
    <>
      {children}
      <span className="medrec__required" aria-hidden="true"> *</span>
    </>
  );
}

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
    defaultValues: { title: '', date: today, next_due: '', target: '', batch: '', diagnosis: '', recommendations: '', weight: '', clinic: '', vet: '', note: '', document_ids: [] },
  });
  // Files added here are uploaded when the record is saved (so a form that is closed leaves nothing behind in
  // «Документы»); the ids of those already uploaded are kept, so a retry after a failure doesn't send them twice.
  const [staged, setStaged] = useState<StagedFile[]>([]);
  const uploaded = useRef(new Map<string, string>());
  const cameraInput = useRef<HTMLInputElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const { dialog: leaveDialog, release } = useUnsavedChangesGuard(isDirty || staged.length > 0);
  const date = useWatch({ control, name: 'date' });
  const nextDue = useWatch({ control, name: 'next_due' });
  const title = useWatch({ control, name: 'title' });
  const documentIds = useWatch({ control, name: 'document_ids' });
  const [docsOpen, setDocsOpen] = useState(false);
  const [targetError, setTargetError] = useState<string | null>(null);
  // The repeat date put in by the form itself (not typed): it moves with the date until the person changes it.
  const autoDue = useRef('');
  useEffect(() => {
    if (!autoDue.current || !date || nextDue !== autoDue.current) return;
    const moved = addInterval(date, { years: 1 });
    autoDue.current = moved;
    setValue('next_due', moved);
  }, [date, nextDue, setValue]);

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
        recommendations: r.recommendations ?? '', weight: '', clinic: r.clinic ?? '', vet: r.vet ?? '', note: r.note ?? '', document_ids: r.documents.map((d) => d.id),
      });
      return;
    }
    if (!card.data || (fromId && !source) || (docId && !sourceDoc && documents.isPending)) return;
    filled.current = true;
    // The clinic the pet was last taken to, else the one in its profile.
    const last = Object.values(card.data.records).flat().sort((a, b) => b.date.localeCompare(a.date)).find((r) => r.clinic || r.vet);
    const clinic = last?.clinic ?? card.data.profile.clinic.name ?? '';
    const vet = last?.vet ?? card.data.profile.clinic.vet ?? '';
    // A vaccination is nearly always repeated: a year on is put in, so that skipping the field does not
    // switch the reminder off. It follows the date until it is touched, and is one tap from gone.
    const firstDue = kind === 'vaccination' && !source && !sourceDoc ? addInterval(today, { years: 1 }) : '';
    autoDue.current = firstDue;
    const blank: FormData = { title: '', date: today, next_due: firstDue, target: '', batch: '', diagnosis: '', recommendations: '', weight: '', clinic, vet, note: '', document_ids: [] };
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

  const weightSaved = useRef(false);
  const save = useMutation({
    mutationFn: async (data: FormData) => {
      weightSaved.current = false;
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
        document_ids: [...data.document_ids],
      };
      // The new files first, each one a document of the pet filed by the kind of record; the record then
      // points at them with the ones chosen from the uploaded.
      for (const [index, item] of staged.entries()) {
        let id = uploaded.current.get(item.key);
        if (!id) {
          const name = staged.length > 1 ? `${input.title.slice(0, 85)}, файл ${index + 1}` : input.title;
          id = await documentsService.create({ pet_id: petId!, category: UPLOAD_CATEGORY[kind!], title: name.slice(0, 100), file: item.file });
          uploaded.current.set(item.key, id);
        }
        input.document_ids.push(id);
      }
      if (isEditing) await medicalRecordsService.update(recordId!, input);
      else await medicalRecordsService.create(petId!, kind!, input);
      // A weight said at the visit goes to the diary too, dated the visit: the graph and the PDF read it
      // from there. The visit is already saved, so a failure here must not make the owner save it twice.
      const weight = kind === 'visit' && !isEditing ? Number((data.weight ?? '').replace(',', '.')) : 0;
      if (weight > 0) {
        try {
          await healthRecordsService.create('weight', {
            pet_id: petId!,
            date: data.date,
            time: data.date === today ? getCurrentTime() : '12:00',
            fields: { weight },
          });
          weightSaved.current = true;
        } catch {
          showToast.failure('Визит сохранён, а вес не записался. Добавьте его в ленте.');
        }
      }
    },
    onSuccess: () => {
      if (weightSaved.current) {
        queryClient.invalidateQueries({
          predicate: (query) => ['timeline', 'history-timeline', 'stats', 'pet-summary'].includes(query.queryKey[0] as string),
        });
      }
      queryClient.invalidateQueries({ queryKey: ['medical-card', petId] });
      queryClient.invalidateQueries({ queryKey: ['medical-record', recordId] });
      // The Documents list says «В медкарте» for what a record points at.
      queryClient.invalidateQueries({ queryKey: ['documents', petId] });
      if (isEditing) showToast.success('Запись сохранена');
      else void confirmWithProgress(queryClient, petId!, 'Запись добавлена');
      release();
      goBack(navigate, cardPath);
    },
    onError: (err: unknown) => {
      showToast.failure(getApiErrorMessage(err, 'Не удалось сохранить'));
    },
  });

  const pickFiles = (list: FileList | null) => {
    const picked = Array.from(list ?? []);
    const room = MAX_DOCUMENTS - documentIds.length - staged.length;
    const accepted: StagedFile[] = [];
    for (const file of picked) {
      if (!(file.type.startsWith('image/') || file.type === 'application/pdf')) {
        showToast.failure(`«${file.name}»: подходят фото и PDF`);
      } else if (file.size > MAX_FILE_BYTES) {
        showToast.failure(`«${file.name}» больше ${formatFileSize(MAX_FILE_BYTES)}`);
      } else if (accepted.length >= room) {
        showToast.failure(`К записи можно прикрепить не больше ${MAX_DOCUMENTS} документов`);
        break;
      } else {
        accepted.push({ key: `${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(36).slice(2, 8)}`, file });
      }
    }
    if (accepted.length) setStaged((current) => [...current, ...accepted]);
  };

  const onSubmit = (data: FormData) => {
    if (kind === 'parasite' && !data.target) {
      setTargetError('Укажите, от чего обработка');
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
            {isEditing ? labels!.one : fromId ? (kind === 'parasite' ? 'Повторная обработка' : 'Повторная прививка') : `Новая запись: ${labels!.one.toLowerCase()}`}
          </h1>
          {pet && <p className="medrec__pet">{pet.name}</p>}
        </div>

        <Form layout="vertical" mode="card">
          <Controller
            name="title"
            control={control}
            render={({ field, fieldState: { error } }) => (
              <Form.Item label={<RequiredLabel>{labels!.titleLabel}</RequiredLabel>} description={error?.message ? <FieldError message={error.message} /> : fieldNote({ value: field.value, max: 100 })}>
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
                <Form.Item label={<RequiredLabel>От чего</RequiredLabel>} description={targetError ? <FieldError message={targetError} /> : undefined}>
                  <Selector
                    columns={3}
                    options={(Object.keys(PARASITE_TARGET_LABELS) as ParasiteTarget[]).map((value) => ({ label: PARASITE_TARGET_LABELS[value], value }))}
                    value={field.value ? [field.value] : []}
                    onChange={(v) => {
                      setTargetError(null);
                      field.onChange(v[0] ?? '');
                    }}
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
                label={DATE_LABELS[kind!] ?? 'Когда сделано'}
                value={field.value}
                onChange={field.onChange}
                onBlur={field.onBlur}
                yearsBack={30}
                yearsForward={0}
                description={error?.message ? <FieldError message={error.message} /> : undefined}
              />
            )}
          />

          <Form.Item>
            <div className="medrec__chips" role="group" aria-label={`${DATE_LABELS[kind!] ?? 'Когда сделано'}, быстро`}>
              {QUICK_DATES.map((choice) => {
                const value = choice.date(today);
                return (
                  <button
                    key={choice.label}
                    type="button"
                    className="medrec__chip"
                    aria-pressed={date === value}
                    onClick={() => setValue('date', value, { shouldDirty: true, shouldValidate: true })}
                  >
                    {choice.label}
                  </button>
                );
              })}
            </div>
          </Form.Item>

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
                    description={error?.message ? <FieldError message={error.message} /> : autoDue.current && nextDue === autoDue.current ? 'Поставили через год, как у большинства прививок. Измените или уберите. Напомним за две недели, за три дня, в день даты и после неё' : kind === 'parasite' ? 'Напомним за неделю, за три дня, в день даты и после неё' : 'Напомним за две недели, за три дня, в день даты и после неё'}
                  />
                  <Form.Item>
                    <div className="medrec__chips" role="group" aria-label="Повторить через">
                      <button
                        type="button"
                        className="medrec__chip"
                        aria-pressed={!nextDue}
                        onClick={() => {
                          autoDue.current = '';
                          setValue('next_due', '', { shouldDirty: true, shouldValidate: true });
                        }}
                      >
                        Без повтора
                      </button>
                      {repeatChoices.map((choice) => {
                        const target = addInterval(date || today, choice);
                        return (
                          <button
                            key={choice.label}
                            type="button"
                            className="medrec__chip"
                            aria-pressed={nextDue === target}
                            onClick={() => {
                              autoDue.current = '';
                              setValue('next_due', target, { shouldDirty: true, shouldValidate: true });
                            }}
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
              {!isEditing && (
                <Controller
                  name="weight"
                  control={control}
                  render={({ field, fieldState }) => (
                    <Form.Item label="Вес, кг" description={fieldState.error ? <FieldError message={fieldState.error.message} /> : 'Если взвешивали, запишется и в вес питомца'}>
                      <Input {...left} type="text" inputMode="decimal" value={field.value ?? ''} onChange={field.onChange} onBlur={field.onBlur} placeholder="Необязательно" maxLength={6} />
                    </Form.Item>
                  )}
                />
              )}
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
            description="Сертификат, выписка, фото наклейки: выберите из загруженных или добавьте новые"
          >
            <PickerValue
              value={[...chosenDocs.map((d) => d.title), ...staged.map((f) => f.file.name)].join(', ')}
              placeholder="Не прикреплены"
            />
          </Form.Item>
        </Form>

        {/* A long form: the button stays in reach above the tab bar, not three screens down. */}
        <div className="form-sticky-action safe-area-padding">
          <SpinnerButton loading={save.isPending || isSubmitting} onClick={() => handleSubmit(onSubmit, onInvalidSubmit)()}>
            {isEditing ? 'Сохранить' : 'Добавить'}
          </SpinnerButton>
        </div>
        <div className="safe-area-padding" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)', margin: 'var(--spacing-md) 0 var(--spacing-xl)' }}>
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
                  onDeleted: () => Promise.all([queryClient.invalidateQueries({ queryKey: ['medical-card', petId] }), queryClient.invalidateQueries({ queryKey: ['documents', petId] })]),
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

      <Popup visible={docsOpen} onMaskClick={() => setDocsOpen(false)} onClose={() => setDocsOpen(false)} bodyStyle={{ borderTopLeftRadius: 16, borderTopRightRadius: 16, maxHeight: '75vh', overflow: 'auto' }}>
        <div style={{ padding: 'var(--spacing-md)' }}>
          <h2 style={{ margin: '0 0 var(--spacing-sm)', fontSize: 'var(--text-lg)' }}>Документы к записи</h2>

          <div className="medrec__add-files">
            <Button fill="outline" color="primary" disabled={documentIds.length + staged.length >= MAX_DOCUMENTS} onClick={() => cameraInput.current?.click()}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <Camera size={18} strokeWidth={2.2} aria-hidden />
                Сфотографировать
              </span>
            </Button>
            <Button fill="outline" color="primary" disabled={documentIds.length + staged.length >= MAX_DOCUMENTS} onClick={() => fileInput.current?.click()}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <FileUp size={18} strokeWidth={2.2} aria-hidden />
                Выбрать файл
              </span>
            </Button>
          </div>
          <p className="medrec__add-hint">Фото или PDF до {formatFileSize(MAX_FILE_BYTES)}. Файл появится и в разделе «Документы», когда вы сохраните запись.</p>
          {/* Two inputs: one opens the camera, the other the gallery and files. */}
          <input ref={cameraInput} type="file" accept="image/*" capture="environment" hidden aria-label="Сфотографировать" onChange={(e) => { pickFiles(e.target.files); e.target.value = ''; }} />
          <input ref={fileInput} type="file" accept="image/*,application/pdf" multiple hidden aria-label="Выбрать файл" onChange={(e) => { pickFiles(e.target.files); e.target.value = ''; }} />

          {staged.length > 0 && (
            <>
              <h3 className="medrec__subhead">Будет добавлено</h3>
              <ul className="medrec__files">
                {staged.map((item) => (
                  <StagedRow key={item.key} item={item} onRemove={() => setStaged((current) => current.filter((f) => f.key !== item.key))} />
                ))}
              </ul>
            </>
          )}

          {(documents.data ?? []).length > 0 && (
            <>
              <h3 className="medrec__subhead">Уже загруженные</h3>
              <CheckList multiple value={documentIds} onChange={(v) => setValue('document_ids', v as string[], { shouldDirty: true })}>
                {(documents.data ?? []).map((d) => (
                  <CheckList.Item key={d._id} value={d._id} description={DOCUMENT_CATEGORY_LABELS[d.category]}>
                    {d.title}
                  </CheckList.Item>
                ))}
              </CheckList>
            </>
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
