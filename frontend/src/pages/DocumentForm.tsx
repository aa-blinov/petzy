import { useEffect, useState } from 'react';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';
import { useNavigate, useParams } from 'react-router-dom';
import { goBack } from '../utils/navigation';
import { Button, Form, Input, TextArea, Picker } from 'antd-mobile';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { FileText, Image as ImageIcon, Upload } from 'lucide-react';
import {
  documentsService,
  DOCUMENT_CATEGORY_LABELS,
  type DocumentCategory,
} from '../services/documents.service';
import { usePet } from '../hooks/usePet';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { SpinnerButton } from '../components/SpinnerButton';

const CATEGORY_OPTIONS = (Object.entries(DOCUMENT_CATEGORY_LABELS) as [DocumentCategory, string][]).map(
  ([value, label]) => ({ label, value }),
);

const documentSchema = z.object({
  category: z.string().min(1, 'Выберите категорию'),
  title: z.string().min(1, 'Название обязательно').max(100),
  note: z.string().max(500).optional(),
});

type DocumentFormData = z.infer<typeof documentSchema>;

export function DocumentForm() {
  const { id } = useParams<{ id: string }>();
  const isEditing = !!id;
  const navigate = useNavigate();
  const { selectedPetId } = usePet();
  const queryClient = useQueryClient();

  const [categoryPickerVisible, setCategoryPickerVisible] = useState(false);
  // The file itself isn't a react-hook-form field — it's a one-shot pick
  // for create only; editing never touches it (delete + re-upload to
  // replace, per the v1 scope), so it lives in its own bit of state.
  const [file, setFile] = useState<File | null>(null);

  const { control, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<DocumentFormData>({
    resolver: zodResolver(documentSchema),
    defaultValues: { category: '', title: '', note: '' },
  });

  const { data: document, isLoading: isLoadingDocument } = useQuery({
    queryKey: ['document', id],
    queryFn: () => documentsService.getById(id!),
    enabled: isEditing && !!id,
  });

  useEffect(() => {
    if (document) {
      reset({ category: document.category, title: document.title, note: document.note || '' });
    }
  }, [document, reset]);

  const createMutation = useMutation({
    mutationFn: (data: DocumentFormData) =>
      documentsService.create({
        pet_id: selectedPetId!,
        category: data.category as DocumentCategory,
        title: data.title,
        note: data.note,
        file: file!,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents', selectedPetId] });
      showToast.success('Документ добавлен');
      goBack(navigate, '/documents');
    },
    onError: (err: unknown) => {
      showToast.failure(getApiErrorMessage(err, 'Ошибка при добавлении документа'));
    },
  });

  const updateMutation = useMutation({
    mutationFn: (data: DocumentFormData) =>
      documentsService.update(id!, {
        category: data.category as DocumentCategory,
        title: data.title,
        note: data.note,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents', selectedPetId] });
      showToast.success('Документ обновлён');
      goBack(navigate, '/documents');
    },
    onError: (err: unknown) => {
      showToast.failure(getApiErrorMessage(err, 'Ошибка при обновлении документа'));
    },
  });

  const onSubmit = (data: DocumentFormData) => {
    if (!isEditing && !file) {
      showToast.failure('Выберите файл');
      return;
    }
    if (isEditing) {
      updateMutation.mutate(data);
    } else {
      createMutation.mutate(data);
    }
  };

  if (isEditing && isLoadingDocument) {
    return <LoadingSpinner />;
  }

  const isLoading = isSubmitting || createMutation.isPending || updateMutation.isPending;

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
          <h2 style={{ fontSize: '24px', fontWeight: 600, margin: 0 }}>
            {isEditing ? 'Редактировать документ' : 'Новый документ'}
          </h2>
        </div>

        <div>
          <Form layout="horizontal" mode="card" style={{ '--prefix-width': '7em' } as React.CSSProperties}>
            <Form.Header>Файл</Form.Header>
            {isEditing ? (
              <Form.Item label="Файл">
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--app-text-secondary)' }}>
                  <FileText size={18} strokeWidth={2} style={{ display: 'block', flexShrink: 0 }} />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {document?.original_filename}
                  </span>
                </div>
              </Form.Item>
            ) : (
              <Form.Item label="Файл" required>
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
                  ) : (
                    <Upload size={18} strokeWidth={2} style={{ display: 'block', flexShrink: 0 }} />
                  )}
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {file ? file.name : 'Выбрать фото или PDF'}
                  </span>
                </label>
                <input
                  id="document-file-input"
                  type="file"
                  accept="image/*,application/pdf"
                  style={{ display: 'none' }}
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </Form.Item>
            )}
            {isEditing && (
              <div
                style={{
                  padding: '0 var(--spacing-lg) var(--spacing-md)',
                  fontSize: 'var(--text-xs)',
                  color: 'var(--app-text-tertiary)',
                }}
              >
                Чтобы заменить файл, удалите документ и загрузите новый.
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
                    onClick={() => setCategoryPickerVisible(true)}
                    help={errors.category?.message}
                    style={{ cursor: 'pointer' }}
                    arrow
                  >
                    <Input
                      readOnly
                      value={DOCUMENT_CATEGORY_LABELS[field.value as DocumentCategory] || ''}
                      placeholder="Выберите категорию"
                      style={{ pointerEvents: 'none' }}
                    />
                  </Form.Item>
                  <Picker
                    columns={[CATEGORY_OPTIONS]}
                    visible={categoryPickerVisible}
                    onClose={() => setCategoryPickerVisible(false)}
                    value={[field.value]}
                    onConfirm={(val) => {
                      field.onChange(val[0] as string);
                      setCategoryPickerVisible(false);
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
                <Form.Item label="Название" required help={error?.message}>
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
                handleSubmit(onSubmit)();
              }}
            />
            <SpinnerButton loading={isLoading} onClick={() => handleSubmit(onSubmit)()} style={{ borderRadius: '12px', fontWeight: 600 }}>
              {isEditing ? 'Сохранить' : 'Добавить'}
            </SpinnerButton>
            <Button block size="large" onClick={() => goBack(navigate, '/documents')} style={{ borderRadius: '12px', fontWeight: 500 }}>
              Отмена
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
