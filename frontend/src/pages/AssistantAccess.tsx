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

// The guide to connecting an assistant, in the public repository next to the server's code.
const MCP_GUIDE = 'https://github.com/aa-blinov/petzy/blob/master/mcp/README.md';

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

  const remove = useMutation({
    mutationFn: (token: PersonalToken) => personalTokenService.remove(token),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PERSONAL_TOKENS_KEY });
      showToast.success('Доступ убран');
    },
    onError: (err: unknown) => {
      void queryClient.invalidateQueries({ queryKey: PERSONAL_TOKENS_KEY });
      showToast.failure(getApiErrorMessage(err, 'Не удалось убрать доступ'));
    },
  });

  const ask = async (token: PersonalToken) => {
    const sure = await Dialog.confirm({
      title: 'Отозвать доступ?',
      'aria-label': 'Отозвать доступ?',
      content: 'Скрипт или ассистент сразу потеряет доступ, вернуть его нельзя. Новый доступ можно сделать в любой момент',
      confirmText: 'Отозвать',
      cancelText: 'Оставить',
    });
    if (sure) revoke.mutate(token.id);
  };

  const askRemove = async (token: PersonalToken) => {
    const sure = await Dialog.confirm({
      title: 'Убрать доступ из списка?',
      'aria-label': 'Убрать доступ из списка?',
      content: 'Доступ уже не работает. Запись о нём пропадёт из списка, вернуть её нельзя',
      confirmText: 'Убрать',
      cancelText: 'Оставить',
    });
    if (sure) remove.mutate(token);
  };

  const list = tokens.data ?? [];
  const mcpAddress = `${window.location.origin}/mcp`;
  const copyAddress = async () => {
    try {
      await navigator.clipboard.writeText(mcpAddress);
      showToast.success('Адрес скопирован');
    } catch {
      showToast.failure('Не удалось скопировать, выделите адрес вручную');
    }
  };

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
          {/* The address of the MCP server: what an assistant is pointed at, next to the token it is given. */}
          <div className="card-soft assist__address">
            <p className="assist__address-title">Адрес сервера для ассистента</p>
            <code className="assist__address-url">{mcpAddress}</code>
            <div className="assist__address-actions">
              <Button size="small" fill="outline" color="primary" onClick={copyAddress}>Скопировать адрес</Button>
              <a className="tap-link assist__address-link" href={MCP_GUIDE} target="_blank" rel="noreferrer">Как подключить</a>
            </div>
          </div>
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
                  {isWorking(token) ? (
                    <Button
                      size="small"
                      color="danger"
                      loading={revoke.isPending && revoke.variables === token.id}
                      onClick={() => void ask(token)}
                    >
                      Отозвать
                    </Button>
                  ) : (
                    <Button
                      size="small"
                      color="danger"
                      loading={remove.isPending && remove.variables?.id === token.id}
                      onClick={() => void askRemove(token)}
                    >
                      Убрать
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
