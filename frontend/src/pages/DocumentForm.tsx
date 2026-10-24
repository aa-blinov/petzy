import { useEffect, useRef, useState } from 'react';
import { showToast } from '../utils/toast';
import { showSnackbar } from '../utils/snackbar';
import { useUnsavedChangesGuard } from '../hooks/useUnsavedChangesGuard';
import { useSessionDraft } from '../hooks/useSessionDraft';
import { fieldNote } from '../components/FieldNote';
import { getApiErrorMessage } from '../utils/apiError';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { goBack } from '../utils/navigation';
import { Button, Form, Input, TextArea } from 'antd-mobile';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm, useWatch, Controller, type FieldErrors } from 'react-hook-form';
import { isAxiosError } from 'axios';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Archive, FileText, Image as ImageIcon, Upload } from 'lucide-react';
import {
  documentsService,
  documentDeleteText,
  DOCUMENT_CATEGORY_LABELS,
  SCAN_EXTENSIONS,
  ScanUploadError,
  isScanFilename,
  isUploadCancelled,
  type DocumentCategory,
} from '../services/documents.service';
import { isMissing } from '../utils/notFound';
import { deviceTimeZone } from '../utils/timezone';
import { formatFileSize } from '../utils/fileSize';
import { usePet } from '../hooks/usePet';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { EmptyState } from '../components/EmptyState';
import { LoadError } from '../components/LoadError';
import { SpinnerButton } from '../components/SpinnerButton';
import { FieldError } from '../components/FieldError';
import { onInvalidSubmit } from '../utils/formErrors';
import { FormDangerButton } from '../components/FormDangerButton';
import { ChoiceSheetField } from '../components/ChoiceSheetField';
import { AttachToRecordSheet } from '../components/AttachToRecordSheet';
import { useRefreshAfterLink } from '../hooks/useRefreshAfterLink';
import { detachDocumentFromRecord, attachDocumentToRecord, recordLabel } from '../utils/documentRecords';
import { showUndo } from '../utils/undo';
import { takePendingDocumentFile } from '../utils/pendingDocumentFile';
import { drawableImage } from '../utils/drawableImage';
import { DatePickerField } from '../components/DatePickerField';
import { useTypedDateProblems } from '../hooks/useTypedDateProblems';
import './DocumentForm.css';

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
/** The types the server takes (ALLOWED_CONTENT_TYPES in web/documents.py): a GIF or an SVG is an image the server refuses. */
const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif', 'application/pdf'];
const SCAN_ACCEPT = SCAN_EXTENSIONS.join(',');
const SCAN_FORMATS_HINT = 'ZIP, 7Z, RAR, TAR, GZ, DICOM и ISO';

function scanErrorMessage(err: unknown): string {
  if (err instanceof ScanUploadError) return err.message;
  return getApiErrorMessage(err, 'Не удалось загрузить снимки');
}

// The frame of the screen: the same whether the form is shown or its document did not load.
const PAGE_STYLE = {
  minHeight: 'var(--app-vh)',
  paddingTop: 'calc(env(safe-area-inset-top) + 88px)',
  paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)',
  backgroundColor: 'var(--app-page-background)',
  color: 'var(--app-text-color)',
};

export function DocumentForm() {
  const { id } = useParams<{ id: string }>();
  // A link can open the form already filed under a category (the medical
  // card's «Добавить» for vaccinations).
  const [searchParams] = useSearchParams();
  const presetParam = searchParams.get('category') ?? '';
  const presetCategory = presetParam in DOCUMENT_CATEGORY_LABELS ? presetParam : '';
  const isEditing = !!id;
  const navigate = useNavigate();
  const { selectedPetId } = usePet();
  const queryClient = useQueryClient();

  // «Прикрепить к записи»: the sheet of the pet's records, and the record being let go of (so its button waits).
  const [attachOpen, setAttachOpen] = useState(false);
  const [detaching, setDetaching] = useState<string | null>(null);
  const refreshLinks = useRefreshAfterLink(selectedPetId);
  // The file itself isn't a react-hook-form field — it's a one-shot pick:
  // the file a new document is made of, or, while editing, the file that
  // will replace the one the document has (null = keep it).
  const [file, setFile] = useState<File | null>(null);
  // A picture the browser can draw, so the chosen file is seen and not only named.
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const previewToken = useRef(0);
  // The file lives outside react-hook-form, so its message is kept here
  // and merged into the same inline error flow as the schema fields.
  const [fileError, setFileError] = useState<string | undefined>();

  // Scan upload progress (0..1) while the archive goes to storage.
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const uploadAbort = useRef<AbortController | null>(null);
  // Leaving the screen mid-upload stops it; the unconfirmed slot is
  // swept on the server.
  useEffect(() => () => uploadAbort.current?.abort(), []);
  // The preview is a temporary address of a blob this page made: it goes with the page.
  useEffect(
    () => () => {
      previewToken.current++;
      setPreviewUrl((old) => {
        if (old) URL.revokeObjectURL(old);
        return null;
      });
    },
    [],
  );

  const { control, handleSubmit, reset, setValue, getValues, formState: { errors, isSubmitting, isDirty } } = useForm<DocumentFormData>({
    // onInvalidSubmit scrolls to and focuses the first error in page order;
    // RHF's own focus picked the first registered ref instead.
    // Validated when a field is left, and after that as it changes: an error
    // shows as soon as it is known, not only after «Сохранить».
    mode: 'onTouched',
    shouldFocusError: false,
    resolver: zodResolver(documentSchema),
    defaultValues: { category: presetCategory, title: '', note: '', expires_at: '' },
  });
  // Typed text or a chosen file is unsaved until «Добавить» / «Сохранить».
  const { dialog: leaveDialog, release } = useUnsavedChangesGuard(isDirty || file !== null);
  // useWatch (a proper subscribing hook) instead of methods.watch(name) —
  // the latter is what the React Compiler flags as an "incompatible
  // library" API and opts the whole component out of memoization for.
  const categoryValue = useWatch({ control, name: 'category' });
  const isImaging = categoryValue === 'imaging';
  // An archive goes straight to storage (up to 500 MB); photos and PDFs,
  // scans included, take the ordinary upload.
  const fileIsArchive = !!file && isScanFilename(file.name);

  // A typed date that is unfinished or impossible is not in the form's value: saving would keep the older one in silence.
  const typedDates = useTypedDateProblems();

  const {
    data: document,
    isLoading: isLoadingDocument,
    error: documentError,
    refetch: refetchDocument,
  } = useQuery({
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
    if (isEditing) {
      // An archive lives in storage under its own key and is downloaded
      // through a signed link; replacing one takes a different route
      // altogether, so the form only offers a photo or a PDF here.
      if (isScanFilename(picked.name)) return 'Архив здесь заменить нельзя. Удалите документ и загрузите архив заново';
    } else if (isScanFilename(picked.name)) {
      if (!scansEnabled) return 'Архивы сейчас не принимаются. Загрузите фото или PDF';
      if (picked.size > maxScanBytes) return `Архив больше ${formatFileSize(maxScanBytes)}. Разделите его на части`;
      return undefined;
    }
    // A photo or a PDF: by its type, or by its name where the browser leaves the type empty (a HEIC from a phone). Anything else
    // the server would refuse after the wait; a picker of the phone does not always keep to `accept`.
    const named = /\.(jpe?g|png|webp|heic|heif|pdf)$/i.test(picked.name);
    if (!(ACCEPTED_TYPES.includes(picked.type) || (!picked.type && named))) {
      return `«${picked.name}»: подходят фото и PDF${scansEnabled ? ', а снимки МРТ и КТ принимаются архивом' : ''}`;
    }
    if (picked.size > MAX_DOCUMENT_BYTES) {
      return scansEnabled
        ? 'Файл больше 10 МБ. Если это снимки, упакуйте их в ZIP: архивы принимаются до 500 МБ'
        : 'Файл больше 10 МБ';
    }
    return undefined;
  };

  const pickFile = (picked: File | null) => {
    setPreviewUrl(null);
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
    if (!problem && picked.type.startsWith('image/')) showPreview(picked);
  };

  // A phone's photo is a HEIC, which only Safari draws: the row would show a name and nothing else.
  // The server sends it back as WebP for the preview alone, nothing is stored.
  const showPreview = async (picked: File) => {
    const token = ++previewToken.current;
    try {
      const blob = await drawableImage(picked);
      if (previewToken.current !== token) return;
      setPreviewUrl((old) => {
        if (old) URL.revokeObjectURL(old);
        return URL.createObjectURL(blob);
      });
    } catch {
      /* no preview: the file's name is what the row shows */
    }
  };

  // A file chosen on the list (the camera, the files) is already here when the form opens: it only has to be named.
  useEffect(() => {
    if (isEditing) return;
    const waiting = takePendingDocumentFile();
    if (waiting) pickFile(waiting);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // The form is filled from the fields of the document, not from the document itself: attaching it to a record reloads it, and
  // that must not wipe what was typed meanwhile.
  const savedFields = document
    ? JSON.stringify({ category: document.category, title: document.title, note: document.note || '', expires_at: document.expires_at || '' })
    : '';
  useEffect(() => {
    if (savedFields) reset(JSON.parse(savedFields));
  }, [savedFields, reset]);
  // The typed fields come back after a session that ran out; the chosen file has to be chosen again.
  useSessionDraft({ dirty: isDirty, petId: selectedPetId, getValues, reset, ready: !isEditing || !!document, release });

  const createMutation = useMutation({
    mutationFn: (data: DocumentFormData) => {
      const controller = new AbortController();
      uploadAbort.current = controller;
      setUploadProgress(0);
      return documentsService.create({
        pet_id: selectedPetId!,
        category: data.category as DocumentCategory,
        title: data.title,
        note: data.note,
        expires_at: data.expires_at || undefined,
        // The zone the file is added in: «Добавлен <дата>» is then read the
        // same way by everyone who opens the list, not on each phone's clock.
        tz: deviceTimeZone(),
        file: file!,
        onProgress: setUploadProgress,
        signal: controller.signal,
      });
    },
    onSuccess: (newId, data) => {
      queryClient.invalidateQueries({ queryKey: ['documents', selectedPetId] });
      release();
      goBack(navigate, '/documents');
      if (data.category === 'vaccination' && selectedPetId) {
        // A vaccination certificate is also a record of the medical card, with a date to repeat it:
        // one tap makes it that (the form opens filled from the certificate).
        showSnackbar({
          message: 'Документ добавлен',
          tone: 'success',
          action: {
            label: 'В медкарту',
            run: () => navigate(`/pets/${selectedPetId}/medical-records/new?kind=vaccination&doc=${newId}`),
          },
        });
      } else {
        showToast.success('Документ добавлен');
      }
    },
    onError: (err: unknown) => {
      // The service has already asked the server to drop what the stopped
      // upload may have stored; here it is only about saying what happened.
      if (isUploadCancelled(err)) {
        showToast.failure('Загрузка остановлена');
        return;
      }
      // The chosen file stays where it was, so the retry is one press of
      // «Добавить» again and not another trip to the picker.
      showToast.failure(`${getApiErrorMessage(err, 'Не удалось загрузить файл')}. Файл на месте, нажмите «Добавить» ещё раз`);
    },
    onSettled: () => {
      uploadAbort.current = null;
      setUploadProgress(null);
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
      release();
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
    // The description first, the file after: it is a small JSON request, and
    // if the file is then refused or stopped the document keeps the file it
    // had, with only the words that were typed already saved.
    mutationFn: async (data: DocumentFormData) => {
      await documentsService.update(id!, {
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
      });
      if (!file) return;
      const controller = new AbortController();
      uploadAbort.current = controller;
      setUploadProgress(0);
      await documentsService.replaceFile(id!, file, setUploadProgress, controller.signal);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents', selectedPetId] });
      showToast.success('Документ сохранён');
      release();
      goBack(navigate, '/documents');
    },
    onError: (err: unknown) => {
      if (isUploadCancelled(err)) {
        showToast.failure('Загрузка остановлена, файл остался прежним');
        return;
      }
      showToast.failure(getApiErrorMessage(err, file ? 'Не удалось заменить файл' : 'Не удалось обновить документ'));
    },
    onSettled: () => {
      uploadAbort.current = null;
      setUploadProgress(null);
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
    typedDates.refuse();
    const missingFile = !isEditing && !file ? (isImaging ? 'Выберите снимки: фото, PDF или архив' : scansEnabled ? 'Выберите фото, PDF или архив' : 'Выберите фото или PDF') : undefined;
    // A file that was refused on the pick keeps its reason here; «no file» is said only when there is none.
    setFileError((current) => (file ? undefined : current ?? missingFile));
    const fileErrors = missingFile ? { file: { type: 'required', message: missingFile } } : {};
    handleSubmit(
      (data) => (missingFile ? onInvalidSubmit(fileErrors as FieldErrors) : typedDates.blocked ? undefined : onSubmit(data)),
      (errors) => onInvalidSubmit({ ...errors, ...fileErrors } as FieldErrors),
    )();
  };

  // Lets go of the document in one record and offers the way back; the file itself stays among the documents.
  const detach = async (recordId: string) => {
    if (!id || detaching) return;
    setDetaching(recordId);
    try {
      await detachDocumentFromRecord(recordId, id);
      await refreshLinks();
      showUndo({
        message: 'Документ откреплён от записи',
        onUndo: async () => {
          await attachDocumentToRecord(recordId, id);
          await refreshLinks();
        },
      });
    } catch (error) {
      showToast.failure(getApiErrorMessage(error, 'Не удалось открепить документ'));
    } finally {
      setDetaching(null);
    }
  };

  if (isEditing && isLoadingDocument) {
    return <LoadingSpinner />;
  }

  // The heading is the same on the form and on the screen that says the document did not load.
  const pageHead = (
    <div style={{ marginBottom: '16px', padding: '0 max(16px, env(safe-area-inset-left))' }}>
      <div className="screen-head">
        <h1 className="screen-title" style={{ fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>
          {isEditing ? 'Изменить документ' : 'Новый документ'}
        </h1>
      </div>
    </div>
  );

  // Without the document the form would open empty, and «Сохранить» would write an empty note and expiry over the saved
  // ones. So the form is not drawn at all: the screen says what happened and offers a way on.
  if (isEditing && !document) {
    const gone = isMissing(documentError);
    return (
      <div style={PAGE_STYLE}>
        <div style={{ maxWidth: '800px', margin: '0 auto' }}>
          {pageHead}
          {gone ? (
            <EmptyState
              icon={FileText}
              title="Документ не найден"
              description="Возможно, его удалили или у вас нет к нему доступа"
              actionLabel="К документам"
              onAction={() => navigate('/documents', { replace: true })}
            />
          ) : (
            <LoadError what="документ" onRetry={refetchDocument} />
          )}
        </div>
      </div>
    );
  }

  const isUploading = uploadProgress !== null;
  // What the file row counts: the file that will be uploaded, or, while
  // editing with nothing chosen, the one the document has now.
  const shownFileSize = file ? file.size : (document?.file_size ?? 0);
  const isLoading = isSubmitting || createMutation.isPending || updateMutation.isPending || scanMutation.isPending;

  return (
    <div style={PAGE_STYLE}>
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        {pageHead}

        <div>
          <Form layout="horizontal" mode="card" style={{ '--prefix-width': '7em' } as React.CSSProperties}>
            <Form.Item
              label="Файл"
              required={!isEditing}
              description={
                fileError ? (
                  <FieldError message={fileError} />
                ) : file && isEditing ? (
                  'Новый файл заменит прежний'
                ) : isImaging && scansEnabled && !file ? (
                  `Фото и PDF до 10 МБ, архивы ${SCAN_FORMATS_HINT} до ${formatFileSize(maxScanBytes)}`
                ) : undefined
              }
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-sm)' }}>
                <label
                  htmlFor="document-file-input"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    minHeight: 'var(--touch-min)',
                    cursor: 'pointer',
                    color: file || isEditing ? 'var(--app-text-primary)' : 'var(--app-accent-deep)',
                    fontWeight: 500,
                  }}
                >
                  {previewUrl ? (
                    <img
                      src={previewUrl}
                      alt=""
                      style={{ width: 44, height: 44, borderRadius: 'var(--radius-sm)', objectFit: 'cover', flexShrink: 0 }}
                    />
                  ) : isEditingScan && !file ? (
                    <Archive size={18} strokeWidth={2} style={{ display: 'block', flexShrink: 0 }} />
                  ) : file?.type.startsWith('image/') ? (
                    <ImageIcon size={18} strokeWidth={2} style={{ display: 'block', flexShrink: 0 }} />
                  ) : fileIsArchive ? (
                    <Archive size={18} strokeWidth={2} style={{ display: 'block', flexShrink: 0 }} />
                  ) : (
                    <Upload size={18} strokeWidth={2} style={{ display: 'block', flexShrink: 0 }} />
                  )}
                  {/* A file name is cut with an ellipsis, the prompt «Выбрать фото или PDF» wraps: it is the main action of the form. */}
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: file || isEditing ? 'nowrap' : 'normal', textAlign: 'right' }}>
                    {file
                      ? file.name
                      : isEditing
                        ? (document?.original_filename ?? '')
                        : isImaging
                          ? 'Выбрать снимки'
                          : 'Выбрать фото или PDF'}
                  </span>
                  {shownFileSize > 0 && (
                    <span
                      style={{
                        flexShrink: 0,
                        fontWeight: 400,
                        color: 'var(--app-text-tertiary)',
                        fontVariantNumeric: 'tabular-nums',
                      }}
                    >
                      {formatFileSize(shownFileSize)}
                    </span>
                  )}
                </label>
                {isEditing && !file && (
                  // The row above shows the file the document has, which
                  // reads as a fact rather than a control: this is what says
                  // the row can be picked from.
                  <label
                    htmlFor="document-file-input"
                    style={{
                      alignSelf: 'flex-start',
                      display: 'flex',
                      alignItems: 'center',
                      minHeight: 'var(--touch-min)',
                      color: 'var(--app-accent-deep)',
                      fontSize: 'var(--text-sm)',
                      cursor: 'pointer',
                    }}
                  >
                    Заменить файл
                  </label>
                )}
                {isEditing && file && (
                  <button
                    type="button"
                    onClick={() => pickFile(null)}
                    style={{
                      alignSelf: 'flex-start',
                      minHeight: 'var(--touch-min)',
                      padding: 0,
                      border: 'none',
                      background: 'none',
                      color: 'var(--app-accent-deep)',
                      fontFamily: 'inherit',
                      fontSize: 'var(--text-sm)',
                      cursor: 'pointer',
                    }}
                  >
                    Оставить прежний файл
                  </button>
                )}
              </div>
              <input
                id="document-file-input"
                type="file"
                // Archives wherever scans are on: a picked archive files
                // itself under «Снимки» (pickFile).
                accept={scansEnabled ? `${DOCUMENT_ACCEPT},${SCAN_ACCEPT}` : DOCUMENT_ACCEPT}
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
                      : fileIsArchive
                        ? 'Проверяем архив…'
                        : 'Сохраняем файл…'}
                  </span>
                  {/* Stopping only while the body is still going: once it
                      has all arrived the server is already storing it, and
                      a «stopped» that didn't stop anything would be a lie. */}
                  {uploadProgress! < 1 && (
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
                  )}
                </div>
                <div
                  role="progressbar"
                  aria-label="Загрузка файла"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.round(uploadProgress! * 100)}
                  style={{ height: 6, borderRadius: 3, background: 'var(--app-accent-soft)', overflow: 'hidden' }}
                >
                  <div
                    // Scaled, not resized: a width transition re-laid the
                    // page out on every progress tick.
                    style={{
                      height: '100%',
                      width: '100%',
                      transform: `scaleX(${uploadProgress!})`,
                      transformOrigin: 'left',
                      background: 'var(--app-accent)',
                      // No radius of its own: scaled, it would squash; the track clips the ends.
                      transition: 'transform 200ms linear',
                    }}
                  />
                </div>
              </div>
            )}

            <Form.Header>Описание</Form.Header>

            <Controller
              name="category"
              control={control}
              render={({ field }) => (
                <ChoiceSheetField
                  label="Категория"
                  required
                  value={field.value}
                  options={ALL_CATEGORY_OPTIONS}
                  placeholder="Выберите категорию"
                  disabled={isEditingScan || isUploading}
                  description={
                    errors.category?.message ? (
                      <FieldError message={errors.category.message} />
                    ) : field.value === 'vaccination' && !isEditing ? (
                      'Срок следующей прививки и напоминание появятся, когда оформите её записью в медкарте. Предложим это после сохранения'
                    ) : undefined
                  }
                  onChange={(next) => {
                    field.onChange(next);
                    // An archive can only be filed under «Снимки».
                    if (fileIsArchive && next !== 'imaging') {
                      setFile(null);
                      setFileError('Архив можно добавить только в «Снимки». Выберите фото или PDF');
                    }
                  }}
                />
              )}
            />

            <Controller
              name="title"
              control={control}
              render={({ field, fieldState: { error } }) => (
                <Form.Item label="Название" required description={fieldNote({ error: error?.message, value: field.value, max: 100 })}>
                  <Input {...field} placeholder="Например, Прививка от бешенства" clearable maxLength={100} />
                </Form.Item>
              )}
            />

            <Controller
              name="note"
              control={control}
              render={({ field }) => (
                <Form.Item label="Заметка" description={fieldNote({ value: field.value, max: 500, always: true })}>
                  <TextArea {...field} placeholder="Необязательно" rows={3} maxLength={500} />
                </Form.Item>
              )}
            />

            <Controller
              name="expires_at"
              control={control}
              render={({ field }) => (
                <DatePickerField
                  label="Действует до"
                  value={field.value ?? ''}
                  onChange={field.onChange}
                  onBlur={field.onBlur}
                  onTypedProblem={typedDates.report('expires_at')}
                  refusals={typedDates.refusals}
                  // The server takes a date up to ten years ahead (validate_expires_at); an expired one can be logged for the record.
                  yearsBack={2}
                  yearsForward={10}
                  clearLabel="Убрать срок действия"
                  placeholder="Не указано"
                  description="Например, для прививок и страховки"
                />
              )}
            />

            {isEditing && document && selectedPetId && (
              <>
                <Form.Header>Записи медкарты</Form.Header>
                {(document.medical_records ?? []).length === 0 ? (
                  <Form.Item description="Файл можно прикрепить к визиту, прививке или обработке: он будет виден и в записи">
                    <span className="picker-value picker-value--empty">Не прикреплён ни к одной записи</span>
                  </Form.Item>
                ) : (
                  (document.medical_records ?? []).map((record) => (
                    <Form.Item key={record.id}>
                      <div className="doc-links__row">
                        <button
                          type="button"
                          className="doc-links__open touch-target"
                          onClick={() => navigate(`/pets/${selectedPetId}/medical-records/${record.id}`)}
                        >
                          {`Прикреплён к записи: ${recordLabel(record)}`}
                        </button>
                        <button
                          type="button"
                          className="doc-links__detach touch-target"
                          disabled={detaching === record.id}
                          onClick={() => detach(record.id)}
                        >
                          Открепить
                        </button>
                      </div>
                    </Form.Item>
                  ))
                )}
                <Form.Item>
                  <button type="button" className="doc-links__attach touch-target" onClick={() => setAttachOpen(true)}>
                    Прикрепить к записи
                  </button>
                </Form.Item>
              </>
            )}
          </Form>

          {/* A long form: the main button stays above the tab bar, not three screens down. */}
          <div className="form-sticky-action safe-area-padding">
            <button
              style={{ display: 'none' }}
              type="submit"
              onClick={(e) => {
                e.preventDefault();
                submit();
              }}
            />
            <SpinnerButton loading={isLoading} onClick={() => submit()}>
              {isEditing ? 'Сохранить' : isUploading ? 'Загружаем…' : 'Добавить'}
            </SpinnerButton>
          </div>
          <div className="safe-area-padding form-actions" style={{ paddingBottom: 'var(--spacing-xl)' }}>
            <Button
              block
              size="large"
              // The upload is aborted when the form unmounts, so leaving is
              // enough; aborting here would cancel it even if «Остаться» is chosen.
              onClick={() => goBack(navigate, '/documents')}
            >
              Отмена
            </Button>
            {isEditing && id && document && (
              <FormDangerButton
                label="Удалить документ"
                confirmTitle="Удаление документа"
                confirmContent={documentDeleteText(document)}
                onConfirm={async () => {
                  try {
                    await documentsService.delete(id);
                  } catch (error) {
                    showToast.failure(getApiErrorMessage(error, 'Не удалось удалить документ'));
                    throw error;
                  }
                  await queryClient.invalidateQueries({ queryKey: ['documents', selectedPetId] });
                  showToast.success('Документ удалён');
                  release();
                  goBack(navigate, '/documents');
                }}
              />
            )}
          </div>
        </div>
      </div>
      {isEditing && id && selectedPetId && attachOpen && (
        <AttachToRecordSheet visible petId={selectedPetId} documentId={id} onClose={() => setAttachOpen(false)} />
      )}
      {leaveDialog}
    </div>
  );
}
