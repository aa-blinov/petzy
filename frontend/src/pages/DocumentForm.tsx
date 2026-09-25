import { useEffect, useMemo, useRef, useState } from 'react';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { parseRecordDate } from '../utils/relativeTime';
import { useNavigate, useParams } from 'react-router-dom';
import { goBack } from '../utils/navigation';
import { Button, Form, Input, TextArea, Picker } from 'antd-mobile';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm, useWatch, Controller, type FieldErrors } from 'react-hook-form';
import { isAxiosError } from 'axios';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Archive, FileText, Image as ImageIcon, Upload } from 'lucide-react';
import {
  documentsService,
  DOCUMENT_CATEGORY_LABELS,
  SCAN_EXTENSIONS,
  ScanUploadError,
  isScanFilename,
  type DocumentCategory,
} from '../services/documents.service';
import { formatFileSize } from '../utils/fileSize';
import { usePet } from '../hooks/usePet';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { SpinnerButton } from '../components/SpinnerButton';
import { FieldError } from '../components/FieldError';
import { onInvalidSubmit } from '../utils/formErrors';

const ALL_CATEGORY_OPTIONS = (Object.entries(DOCUMENT_CATEGORY_LABELS) as [DocumentCategory, string][]).map(
  ([value, label]) => ({ label, value }),
);

const documentSchema = z.object({
  category: z.string().min(1, 'Выберите категорию'),
  title: z.string().min(1, 'Введите название').max(100, 'Не длиннее 100 символов'),
  note: z.string().max(500, 'Не длиннее 500 символов').optional(),
  expires_at: z.string().optional(),
});

type DocumentFormData = z.infer<typeof documentSchema>;

// The host proxy caps request bodies at 10 MB; bigger files are scans.
const MAX_DOCUMENT_BYTES = 10 * 1024 * 1024;
const DOCUMENT_ACCEPT = 'image/*,application/pdf';
const SCAN_ACCEPT = SCAN_EXTENSIONS.join(',');
const SCAN_FORMATS_HINT = 'ZIP, 7Z, RAR, TAR, GZ, DICOM и ISO';

function scanErrorMessage(err: unknown): string {
  if (err instanceof ScanUploadError) return err.message;
  return getApiErrorMessage(err, 'Не удалось загрузить снимки');
}

export function DocumentForm() {
  const { id } = useParams<{ id: string }>();
  const isEditing = !!id;
  const navigate = useNavigate();
  const { selectedPetId } = usePet();
  const queryClient = useQueryClient();

  const [categoryPickerVisible, setCategoryPickerVisible] = useState(false);
  const [expiryPickerVisible, setExpiryPickerVisible] = useState(false);
  const [internalPickerDate, setInternalPickerDate] = useState<string[]>([]);
  // The file itself isn't a react-hook-form field — it's a one-shot pick
  // for create only; editing never touches it (delete + re-upload to
  // replace, per the v1 scope), so it lives in its own bit of state.
  const [file, setFile] = useState<File | null>(null);
  // The file lives outside react-hook-form, so its message is kept here
  // and merged into the same inline error flow as the schema fields.
  const [fileError, setFileError] = useState<string | undefined>();

  // Scan upload progress (0..1) while the archive goes to storage.
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const uploadAbort = useRef<AbortController | null>(null);
  // Leaving the screen mid-upload stops it; the unconfirmed slot is
  // swept on the server.
  useEffect(() => () => uploadAbort.current?.abort(), []);

  const { control, handleSubmit, reset, setValue, formState: { errors, isSubmitting } } = useForm<DocumentFormData>({
    // onInvalidSubmit scrolls to and focuses the first error in page order;
    // RHF's own focus picked the first registered ref instead.
    shouldFocusError: false,
    resolver: zodResolver(documentSchema),
    defaultValues: { category: '', title: '', note: '', expires_at: '' },
  });
  // useWatch (a proper subscribing hook) instead of methods.watch(name) —
  // the latter is what the React Compiler flags as an "incompatible
  // library" API and opts the whole component out of memoization for.
  const expiresAtValue = useWatch({ control, name: 'expires_at' });
  const categoryValue = useWatch({ control, name: 'category' });
  const isImaging = categoryValue === 'imaging';
  // An archive goes straight to storage (up to 500 MB); photos and PDFs,
  // scans included, take the ordinary upload.
  const fileIsArchive = !!file && isScanFilename(file.name);

  // Documents don't all expire on the same kind of schedule as a birth
  // date (which only ever looks backward) — an already-expired policy
  // can legitimately be logged for the record, and a fresh one can be
  // valid many years out, so the year range runs a couple of years back
  // and comfortably far forward instead of only backward like PetForm's.
  const expiryDateColumns = useMemo(() => {
    let month = new Date().getMonth();
    let year = new Date().getFullYear();

    if (internalPickerDate.length === 3) {
      month = parseInt(internalPickerDate[1]);
      year = parseInt(internalPickerDate[2]);
    } else if (expiresAtValue) {
      const d = parseRecordDate(expiresAtValue);
      if (d) {
        month = d.getMonth();
        year = d.getFullYear();
      }
    }

    const daysCount = new Date(year, month + 1, 0).getDate();
    const days = Array.from({ length: daysCount }, (_, i) => ({
      label: String(i + 1).padStart(2, '0'),
      value: String(i + 1),
    }));
    const months = [
      'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
      'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
    ].map((m, i) => ({ label: m, value: String(i) }));
    const currentYear = new Date().getFullYear();
    // Mirrors the backend's own cap (web/schemas.py, validate_expires_at:
    // max_future_days=3650) so the picker can't offer a date the server
    // will then reject with a 422 at submit time. `new Date()` + setDate,
    // not Date.now() — the compiler treats the latter as an impure call
    // during render.
    const maxDate = new Date();
    maxDate.setDate(maxDate.getDate() + 3650);
    const maxYear = maxDate.getFullYear();
    // `year` above already accounts for an existing document's own expiry
    // year (possibly well in the past, e.g. an intentionally-kept expired
    // record) — the range must stretch to include it, or the picker has no
    // matching option and silently snaps to whatever it defaults to.
    const minYearBound = Math.min(currentYear - 2, year);
    const maxYearBound = Math.max(maxYear, year);
    const years = Array.from({ length: maxYearBound - minYearBound + 1 }, (_, i) => {
      const y = minYearBound + i;
      return { label: String(y), value: String(y) };
    });
    return [days, months, years];
  }, [internalPickerDate, expiresAtValue]);

  const { data: document, isLoading: isLoadingDocument } = useQuery({
    queryKey: ['document', id],
    queryFn: () => documentsService.getById(id!),
    enabled: isEditing && !!id,
  });

  const { data: storageStatus } = useQuery({
    queryKey: ['documents-storage'],
    queryFn: () => documentsService.getStorageStatus(),
    enabled: !isEditing,
    staleTime: 5 * 60_000,
  });
  const scansEnabled = !!storageStatus?.scans_enabled;
  const maxScanBytes = storageStatus?.max_scan_bytes ?? 500 * 1024 * 1024;

  // A scan archive is downloaded rather than previewed, so it stays in
  // «Снимки» (the backend holds it there too).
  const isEditingScan = isEditing && !!document?.scan;

  /** Why ``picked`` can't be uploaded, if it can't. */
  const fileProblem = (picked: File): string | undefined => {
    if (isScanFilename(picked.name)) {
      if (!scansEnabled) return 'Архивы сейчас не принимаются. Загрузите фото или PDF';
      if (picked.size > maxScanBytes) return `Архив больше ${formatFileSize(maxScanBytes)}. Разделите его на части`;
      return undefined;
    }
    if (picked.size > MAX_DOCUMENT_BYTES) {
      return scansEnabled
        ? 'Файл больше 10 МБ. Если это снимки, упакуйте их в ZIP: архивы принимаются до 500 МБ'
        : 'Файл больше 10 МБ';
    }
    return undefined;
  };

  const pickFile = (picked: File | null) => {
    if (!picked) {
      setFile(null);
      return;
    }
    const problem = fileProblem(picked);
    setFileError(problem);
    setFile(problem ? null : picked);
    // Only scans come as archives, so an archive files itself there.
    if (!problem && isScanFilename(picked.name) && !isImaging) {
      setValue('category', 'imaging', { shouldValidate: true });
    }
  };

  useEffect(() => {
    if (document) {
      reset({
        category: document.category,
        title: document.title,
        note: document.note || '',
        expires_at: document.expires_at || '',
      });
    }
  }, [document, reset]);

  const createMutation = useMutation({
    mutationFn: (data: DocumentFormData) =>
      documentsService.create({
        pet_id: selectedPetId!,
        category: data.category as DocumentCategory,
        title: data.title,
        note: data.note,
        expires_at: data.expires_at || undefined,
        file: file!,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents', selectedPetId] });
      showToast.success('Документ добавлен');
      goBack(navigate, '/documents');
    },
    onError: (err: unknown) => {
      showToast.failure(getApiErrorMessage(err, 'Не удалось добавить документ'));
    },
  });

  const scanMutation = useMutation({
    mutationFn: (data: DocumentFormData) => {
      const controller = new AbortController();
      uploadAbort.current = controller;
      setUploadProgress(0);
      return documentsService.createScan({
        pet_id: selectedPetId!,
        title: data.title,
        note: data.note,
        expires_at: data.expires_at || undefined,
        file: file!,
        onProgress: setUploadProgress,
        signal: controller.signal,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents', selectedPetId] });
      showToast.success('Снимки загружены');
      goBack(navigate, '/documents');
    },
    onError: (err: unknown) => {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      // A rejected file (wrong format inside, size changed) has to be
      // picked again; anything else can simply be retried.
      if (isAxiosError(err) && err.response?.data?.code === 'scan_content_mismatch') setFile(null);
      showToast.failure(scanErrorMessage(err));
    },
    onSettled: () => {
      uploadAbort.current = null;
      setUploadProgress(null);
    },
  });

  const cancelUpload = () => uploadAbort.current?.abort();

  const updateMutation = useMutation({
    mutationFn: (data: DocumentFormData) =>
      documentsService.update(id!, {
        category: data.category as DocumentCategory,
        title: data.title,
        note: data.note,
        // Always the current form value, including '' — unlike create
        // (where an empty value just means "don't set one"), update has
        // to be able to clear an expiry date that was set before (a
        // typo fix, or a renewed document that no longer expires the
        // old way). Falling back to undefined here would make that
        // value vanish from the request entirely, so the backend would
        // never see the clear and the stale date would silently persist.
        expires_at: data.expires_at,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents', selectedPetId] });
      showToast.success('Документ обновлён');
      goBack(navigate, '/documents');
    },
    onError: (err: unknown) => {
      showToast.failure(getApiErrorMessage(err, 'Не удалось обновить документ'));
    },
  });

  const onSubmit = (data: DocumentFormData) => {
    if (isEditing) {
      updateMutation.mutate(data);
    } else if (fileIsArchive) {
      scanMutation.mutate(data);
    } else {
      createMutation.mutate(data);
    }
  };

  // A missing file used to be reported by a toast, and only after every
  // other field had passed, so a user fixed one thing and hit the next.
  const submit = () => {
    const missingFile = !isEditing && !file ? (isImaging ? 'Выберите снимки: фото, PDF или архив' : 'Выберите фото или PDF') : undefined;
    setFileError((current) => missingFile ?? (file ? undefined : current));
    const fileErrors = missingFile ? { file: { type: 'required', message: missingFile } } : {};
    handleSubmit(
      (data) => (missingFile ? onInvalidSubmit(fileErrors as FieldErrors) : onSubmit(data)),
      (errors) => onInvalidSubmit({ ...errors, ...fileErrors } as FieldErrors),
    )();
  };

  if (isEditing && isLoadingDocument) {
    return <LoadingSpinner />;
  }

  const isUploading = uploadProgress !== null;
  const isLoading = isSubmitting || createMutation.isPending || updateMutation.isPending || scanMutation.isPending;

  return (
    <div
      style={{
        minHeight: '100vh',
        paddingTop: 'calc(env(safe-area-inset-top) + 88px)',
        paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)',
        backgroundColor: 'var(--app-page-background)',
        color: 'var(--app-text-color)',
      }}
    >
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        <div style={{ marginBottom: '16px', padding: '0 max(16px, env(safe-area-inset-left))' }}>
          <h1 style={{ fontSize: '24px', fontWeight: 600, margin: 0 }}>
            {isEditing ? 'Редактировать документ' : 'Новый документ'}
          </h1>
        </div>

        <div>
          <Form layout="horizontal" mode="card" style={{ '--prefix-width': '7em' } as React.CSSProperties}>
            <Form.Header>Файл</Form.Header>
            {isEditing ? (
              <Form.Item label="Файл">
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--app-text-secondary)' }}>
                  {isEditingScan ? (
                    <Archive size={18} strokeWidth={2} style={{ display: 'block', flexShrink: 0 }} />
                  ) : (
                    <FileText size={18} strokeWidth={2} style={{ display: 'block', flexShrink: 0 }} />
                  )}
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {document?.original_filename}
                  </span>
                  {document && (
                    <span style={{ flexShrink: 0, color: 'var(--app-text-tertiary)', fontVariantNumeric: 'tabular-nums' }}>
                      {formatFileSize(document.file_size)}
                    </span>
                  )}
                </div>
              </Form.Item>
            ) : (
              <Form.Item
                label="Файл"
                required
                description={
                  fileError ? (
                    <FieldError message={fileError} />
                  ) : isImaging && scansEnabled && !file ? (
                    `Фото и PDF до 10 МБ, архивы ${SCAN_FORMATS_HINT} до ${formatFileSize(maxScanBytes)}`
                  ) : undefined
                }
              >
                <label
                  htmlFor="document-file-input"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    cursor: 'pointer',
                    color: file ? 'var(--app-text-primary)' : 'var(--app-accent-deep)',
                    fontWeight: 500,
                  }}
                >
                  {file?.type.startsWith('image/') ? (
                    <ImageIcon size={18} strokeWidth={2} style={{ display: 'block', flexShrink: 0 }} />
                  ) : fileIsArchive ? (
                    <Archive size={18} strokeWidth={2} style={{ display: 'block', flexShrink: 0 }} />
                  ) : (
                    <Upload size={18} strokeWidth={2} style={{ display: 'block', flexShrink: 0 }} />
                  )}
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {file ? file.name : isImaging ? 'Выбрать снимки' : 'Выбрать фото или PDF'}
                  </span>
                  {file && (
                    <span
                      style={{
                        flexShrink: 0,
                        fontWeight: 400,
                        color: 'var(--app-text-tertiary)',
                        fontVariantNumeric: 'tabular-nums',
                      }}
                    >
                      {formatFileSize(file.size)}
                    </span>
                  )}
                </label>
                <input
                  id="document-file-input"
                  type="file"
                  // Archives only where they can go: «Снимки», or no
                  // category yet (picking one files it there).
                  accept={scansEnabled && (!categoryValue || isImaging) ? `${DOCUMENT_ACCEPT},${SCAN_ACCEPT}` : DOCUMENT_ACCEPT}
                  disabled={isUploading}
                  // Visually hidden, not display:none: the input stays in
                  // the Tab order, so the picker opens from the keyboard.
                  className="sr-only file-picker-input"
                  onChange={(e) => {
                    // Same limits the backend enforces, checked here so the
                    // user hears about them before the upload, not after it.
                    pickFile(e.target.files?.[0] ?? null);
                    e.target.value = '';
                  }}
                />
              </Form.Item>
            )}
            {isUploading && file && (
              <div
                role="status"
                aria-live="polite"
                style={{
                  padding: 'var(--spacing-sm) var(--spacing-lg) var(--spacing-md)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 8,
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'baseline',
                    gap: 'var(--spacing-md)',
                    fontSize: 'var(--text-sm)',
                    color: 'var(--app-text-secondary)',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  <span>
                    {uploadProgress! < 1
                      ? `Загружено ${formatFileSize(file.size * uploadProgress!)} из ${formatFileSize(file.size)}`
                      : 'Проверяем архив…'}
                  </span>
                  <button
                    type="button"
                    onClick={cancelUpload}
                    style={{
                      padding: '8px 0 8px 8px',
                      border: 'none',
                      background: 'none',
                      color: 'var(--app-danger-text)',
                      fontFamily: 'inherit',
                      fontSize: 'var(--text-sm)',
                      cursor: 'pointer',
                    }}
                  >
                    Остановить
                  </button>
                </div>
                <div
                  role="progressbar"
                  aria-label="Загрузка снимков"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.round(uploadProgress! * 100)}
                  style={{ height: 6, borderRadius: 3, background: 'var(--app-accent-soft)', overflow: 'hidden' }}
                >
                  <div
                    style={{
                      height: '100%',
                      width: `${Math.round(uploadProgress! * 100)}%`,
                      background: 'var(--app-accent)',
                      borderRadius: 3,
                      transition: 'width 200ms linear',
                    }}
                  />
                </div>
              </div>
            )}
            {isEditing && (
              <div
                style={{
                  padding: '0 var(--spacing-lg) var(--spacing-md)',
                  fontSize: 'var(--text-xs)',
                  color: 'var(--app-text-tertiary)',
                }}
              >
                Чтобы заменить файл, удалите документ и загрузите новый
              </div>
            )}

            <Form.Header>Описание</Form.Header>

            <Controller
              name="category"
              control={control}
              render={({ field }) => (
                <>
                  <Form.Item
                    label="Категория"
                    required
                    onClick={isEditingScan || isUploading ? undefined : () => setCategoryPickerVisible(true)}
                    description={errors.category?.message ? <FieldError message={errors.category.message} /> : undefined}
                    style={{ cursor: isEditingScan || isUploading ? 'default' : 'pointer' }}
                    arrow={!isEditingScan && !isUploading}
                  >
                    <Input
                      readOnly
                      value={DOCUMENT_CATEGORY_LABELS[field.value as DocumentCategory] || ''}
                      placeholder="Выберите категорию"
                      style={{ pointerEvents: 'none' }}
                    />
                  </Form.Item>
                  <Picker
                    columns={[ALL_CATEGORY_OPTIONS]}
                    visible={categoryPickerVisible}
                    onClose={() => setCategoryPickerVisible(false)}
                    value={[field.value]}
                    onConfirm={(val) => {
                      const next = val[0] as string;
                      field.onChange(next);
                      setCategoryPickerVisible(false);
                      // An archive can only be filed under «Снимки».
                      if (fileIsArchive && next !== 'imaging') {
                        setFile(null);
                        setFileError('Архив можно добавить только в «Снимки». Выберите фото или PDF');
                      }
                    }}
                    cancelText="Отмена"
                    confirmText="Выбрать"
                  />
                </>
              )}
            />

            <Controller
              name="title"
              control={control}
              render={({ field, fieldState: { error } }) => (
                <Form.Item label="Название" required description={error?.message ? <FieldError message={error.message} /> : undefined}>
                  <Input {...field} placeholder="Например, Прививка от бешенства" clearable />
                </Form.Item>
              )}
            />

            <Controller
              name="note"
              control={control}
              render={({ field }) => (
                <Form.Item label="Заметка">
                  <TextArea {...field} placeholder="Необязательно" rows={3} />
                </Form.Item>
              )}
            />

            <Controller
              name="expires_at"
              control={control}
              render={({ field: { value, onChange } }) => {
                const displayDate = value ? (parseRecordDate(value)?.toLocaleDateString('ru-RU') ?? value) : '';
                let pickerValue: string[] = [];
                if (value) {
                  const d = parseRecordDate(value);
                  if (d) pickerValue = [String(d.getDate()), String(d.getMonth()), String(d.getFullYear())];
                } else {
                  const now = new Date();
                  pickerValue = [String(now.getDate()), String(now.getMonth()), String(now.getFullYear())];
                }
                return (
                  <Form.Item
                    label="Действует до"
                    clickable
                    arrow
                    onClick={() => {
                      setInternalPickerDate(pickerValue);
                      setExpiryPickerVisible(true);
                    }}
                    extra={
                      value && (
                        // A plain click target, not a Button — the row
                        // is already clickable to open the picker, and a
                        // full-width Button here would visually compete
                        // with that instead of reading as a small aside.
                        <button
                          type="button"
                          aria-label="Убрать срок действия"
                          onClick={(e) => {
                            e.stopPropagation();
                            onChange('');
                          }}
                          style={{
                            padding: '8px 0 8px 8px',
                            border: 'none',
                            background: 'none',
                            color: 'var(--app-danger-text)',
                            fontFamily: 'inherit',
                            fontSize: 'var(--text-sm)',
                            cursor: 'pointer',
                          }}
                        >
                          Убрать
                        </button>
                      )
                    }
                  >
                    <Input
                      readOnly
                      value={displayDate}
                      placeholder="Не указано (например, для прививок и страховки)"
                      style={{ pointerEvents: 'none' }}
                    />
                    <Picker
                      columns={expiryDateColumns}
                      visible={expiryPickerVisible}
                      onClose={() => setExpiryPickerVisible(false)}
                      value={internalPickerDate.length ? internalPickerDate : pickerValue}
                      onSelect={(val) => setInternalPickerDate(val as string[])}
                      onConfirm={(val) => {
                        const day = val[0];
                        const month = parseInt(val[1] as string);
                        const year = val[2];
                        const monthStr = String(month + 1).padStart(2, '0');
                        const dayStr = String(day).padStart(2, '0');
                        onChange(`${year}-${monthStr}-${dayStr}`);
                        setExpiryPickerVisible(false);
                        setInternalPickerDate([]);
                      }}
                      cancelText="Отмена"
                      confirmText="Сохранить"
                    />
                  </Form.Item>
                );
              }}
            />
          </Form>

          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
              marginTop: '24px',
              paddingBottom: '24px',
              marginLeft: '12px',
              marginRight: '12px',
            }}
          >
            <button
              style={{ display: 'none' }}
              type="submit"
              onClick={(e) => {
                e.preventDefault();
                submit();
              }}
            />
            <SpinnerButton loading={isLoading} onClick={() => submit()} style={{ borderRadius: '12px', fontWeight: 600 }}>
              {isEditing ? 'Сохранить' : isUploading ? 'Загружаем…' : 'Добавить'}
            </SpinnerButton>
            <Button
              block
              size="large"
              onClick={() => {
                cancelUpload();
                goBack(navigate, '/documents');
              }}
              style={{ borderRadius: '12px', fontWeight: 500 }}
            >
              Отмена
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
