import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Dialog } from 'antd-mobile';
import { Bot } from 'lucide-react';

import { EmptyState } from '../components/EmptyState';
import { LoadError } from '../components/LoadError';
import { SkeletonList } from '../components/Skeletons';
import {
  formatTokenTime,
  isWorking,
  PERSONAL_TOKENS_KEY,
  personalTokenService,
  SCOPE_LABELS,
  type PersonalToken,
} from '../services/personalTokens.service';
import { getApiErrorMessage } from '../utils/apiError';
import { showToast } from '../utils/toast';
import './AssistantAccess.css';

/** When a token stopped or stops working, said in one line: revoked, ended, or until when. */
function statusLine(token: PersonalToken): string {
  if (token.revoked_at) return `Отозван ${formatTokenTime(token.revoked_at)}`;
  if (isWorking(token)) return `Действует до ${formatTokenTime(token.expires_at)}`;
  return `Истёк ${formatTokenTime(token.expires_at)}`;
}

/**
 * Настройки → «Доступ для ассистентов»: the personal access tokens of this account. A script or an assistant holds one
 * and reads or writes the diary with it, on the areas it was given. Here each one is seen, and taken back when it is not
 * needed any more.
 */
export function AssistantAccess() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const tokens = useQuery({ queryKey: PERSONAL_TOKENS_KEY, queryFn: () => personalTokenService.list() });
  const revoke = useMutation({
    mutationFn: (id: string) => personalTokenService.revoke(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PERSONAL_TOKENS_KEY });
      showToast.success('Доступ отозван');
    },
    onError: (err: unknown) => {
      // The token may already be gone (taken back on another device): asking again shows what is really there.
      void queryClient.invalidateQueries({ queryKey: PERSONAL_TOKENS_KEY });
      showToast.failure(getApiErrorMessage(err, 'Не удалось отозвать доступ'));
    },
  });

  const ask = async (token: PersonalToken) => {
    const sure = await Dialog.confirm({
      title: 'Отозвать доступ?',
      content: 'Скрипт или ассистент сразу потеряет доступ, вернуть его нельзя. Новый доступ можно сделать в любой момент',
      confirmText: 'Отозвать',
      cancelText: 'Оставить',
    });
    if (sure) revoke.mutate(token.id);
  };

  const list = tokens.data ?? [];

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding assist__head">
          <div className="screen-head">
            <h1 className="screen-title display-headline" style={{ fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>Доступ для ассистентов</h1>
          </div>
          <p className="assist__lead">
            Личный доступ нужен скрипту или ассистенту, который читает дневник или пишет в него от вашего имени. Он открывает только отмеченные области и истекает через срок
          </p>
          <Button block color="primary" size="large" onClick={() => navigate('/settings/assistants/new')}>
            Создать доступ
          </Button>
        </div>

        <div className="safe-area-padding assist__body">
          {tokens.isPending && <SkeletonList count={2} flush />}

          {tokens.isError && <LoadError what="доступы" onRetry={() => tokens.refetch()} />}

          {tokens.isSuccess && list.length === 0 && (
            <EmptyState
              icon={Bot}
              title="Доступов пока нет"
              description="Доступ делают для скрипта или ассистента, когда он должен работать с дневником без входа в аккаунт"
            />
          )}

          {list.length > 0 && (
            <ul className="card-soft assist__list" aria-label="Личные доступы">
              {list.map((token) => (
                <li key={token.id} className="assist__item">
                  <div className="assist__text">
                    <span className="assist__name">{token.name}</span>
                    <span className="assist__scopes">{token.scopes.map((scope) => SCOPE_LABELS[scope]).join(', ')}</span>
                    <span className="assist__meta">Начинается с {token.prefix}</span>
                    <span className="assist__meta">Создан {formatTokenTime(token.created_at)}</span>
                    <span className="assist__meta">
                      {token.last_used_at ? `Последний вход ${formatTokenTime(token.last_used_at)}` : 'Последнего входа не было'}
                    </span>
                    <span className="assist__meta">{statusLine(token)}</span>
                  </div>
                  {isWorking(token) && (
                    <Button
                      size="small"
                      color="danger"
                      loading={revoke.isPending && revoke.variables === token.id}
                      onClick={() => void ask(token)}
                    >
                      Отозвать
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
