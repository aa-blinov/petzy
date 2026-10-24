import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { zodResolver } from '@hookform/resolvers/zod';
import { Controller, useForm } from 'react-hook-form';
import { Button, Checkbox, Form, Input } from 'antd-mobile';
import { z } from 'zod';

import { FieldError } from '../components/FieldError';
import { Segmented } from '../components/Segmented';
import { SpinnerButton } from '../components/SpinnerButton';
import { useUnsavedChangesGuard } from '../hooks/useUnsavedChangesGuard';
import {
  formatTokenTime,
  PERSONAL_TOKENS_KEY,
  personalTokenService,
  SCOPE_LABELS,
  TOKEN_DAYS,
  TOKEN_SCOPES,
  type CreatedToken,
} from '../services/personalTokens.service';
import { getApiErrorMessage } from '../utils/apiError';
import { onInvalidSubmit } from '../utils/formErrors';
import { goBack } from '../utils/navigation';
import { showToast } from '../utils/toast';
import './AssistantAccess.css';

const schema = z.object({
  name: z.string().trim().min(1, 'Введите название').max(60, 'Не больше 60 символов'),
  scopes: z.array(z.enum(TOKEN_SCOPES)).min(1, 'Выберите хотя бы одну область'),
  days: z.union([z.literal(30), z.literal(90), z.literal(365)]),
});

type FormValues = z.infer<typeof schema>;

const DAY_OPTIONS = TOKEN_DAYS.map((days) => ({ value: String(days), label: `${days} дней` }));

/**
 * Настройки → «Доступ для ассистентов» → «Создать доступ». The secret is shown here once, after it is made: the server
 * keeps only its hash, so a token that is not copied before leaving cannot be had again, and leaving asks first.
 */
export function AssistantAccessForm() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [created, setCreated] = useState<CreatedToken | null>(null);
  const [copied, setCopied] = useState(false);
  const {
    control,
    handleSubmit,
    formState: { errors, isDirty },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', scopes: [], days: 90 },
  });

  const create = useMutation({
    mutationFn: (values: FormValues) =>
      personalTokenService.create({ name: values.name, scopes: values.scopes, expires_in_days: values.days }),
    onSuccess: (result) => {
      setCreated(result);
      void queryClient.invalidateQueries({ queryKey: PERSONAL_TOKENS_KEY });
    },
    onError: (err: unknown) => showToast.failure(getApiErrorMessage(err, 'Не удалось создать доступ')),
  });

  // Typed-in fields ask before they are left. So does a made token that was not copied: it is never shown again.
  const { dialog: leaveDialog } = useUnsavedChangesGuard(created ? !copied : isDirty);
  const finish = () => goBack(navigate, '/settings/assistants');

  const copy = async () => {
    if (!created) return;
    try {
      await navigator.clipboard.writeText(created.token);
      setCopied(true);
      showToast.success('Токен скопирован');
    } catch {
      showToast.failure('Не удалось скопировать, выделите токен вручную');
    }
  };

  const submit = handleSubmit(
    (values) => create.mutate(values),
    (invalid) => onInvalidSubmit(invalid),
  );

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding assist__head">
          <div className="screen-head">
            <h1 className="screen-title display-headline" style={{ fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>
              {created ? 'Доступ создан' : 'Новый доступ'}
            </h1>
          </div>
        </div>

        {!created && (
          <div className="safe-area-padding assist__body">
            <Form layout="vertical" mode="card">
              <Controller
                name="name"
                control={control}
                render={({ field }) => (
                  <Form.Item
                    label="Название"
                    description={errors.name ? <FieldError message={errors.name.message} /> : 'Чтобы узнать доступ в списке'}
                  >
                    <Input
                      value={field.value}
                      onChange={field.onChange}
                      onBlur={field.onBlur}
                      placeholder="Например, ассистент для врача"
                    />
                  </Form.Item>
                )}
              />
              <Controller
                name="scopes"
                control={control}
                render={({ field }) => (
                  <Form.Item
                    label="Что может делать"
                    description={errors.scopes ? <FieldError message={errors.scopes.message} /> : undefined}
                  >
                    <div role="group" aria-label="Что может делать" className="assist__scopes-choice">
                      {TOKEN_SCOPES.map((scope) => (
                        <Checkbox
                          key={scope}
                          checked={field.value.includes(scope)}
                          onChange={(checked) =>
                            field.onChange(TOKEN_SCOPES.filter((s) => (s === scope ? checked : field.value.includes(s))))
                          }
                        >
                          {SCOPE_LABELS[scope]}
                        </Checkbox>
                      ))}
                    </div>
                  </Form.Item>
                )}
              />
              <Controller
                name="days"
                control={control}
                render={({ field }) => (
                  <Form.Item label="Срок действия">
                    <div className="assist__days">
                      <Segmented
                        label="Срок действия"
                        value={String(field.value)}
                        options={DAY_OPTIONS}
                        onChange={(value) => field.onChange(Number(value) as FormValues['days'])}
                      />
                    </div>
                  </Form.Item>
                )}
              />
            </Form>
            <p className="assist__note">Доступ не даёт больше ваших прав: питомцы, которых вы не видите, по нему тоже не открываются</p>
            <div className="form-actions">
              <SpinnerButton type="button" loading={create.isPending} onClick={() => void submit()}>
                Создать доступ
              </SpinnerButton>
              <Button block fill="none" onClick={finish}>
                Отмена
              </Button>
            </div>
          </div>
        )}

        {created && (
          <div className="safe-area-padding assist__body">
            <p className="assist__lead">
              Скопируйте токен и передайте его скрипту или ассистенту. Доступ действует до {formatTokenTime(created.expires_at)}
            </p>
            <p className="assist__token" data-testid="assistant-token">
              {created.token}
            </p>
            <p className="assist__warning" role="status">Токен показывается один раз, сохраните его сейчас</p>
            <div className="form-actions">
              <Button block color="primary" size="large" onClick={() => void copy()}>
                Скопировать
              </Button>
              <Button block fill="none" onClick={finish}>
                Готово
              </Button>
            </div>
          </div>
        )}
      </div>
      {leaveDialog}
    </div>
  );
}
