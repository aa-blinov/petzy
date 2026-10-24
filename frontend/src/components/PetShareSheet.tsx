import { useEffect, useRef, useState } from 'react';
import { isAxiosError } from 'axios';
import { useQueryClient } from '@tanstack/react-query';
import { Button, Dialog, Input, Popup } from 'antd-mobile';

import { petsService, type Pet } from '../services/pets.service';
import { usersService } from '../services/users.service';
import { usePet } from '../hooks/usePet';
import { getApiErrorMessage } from '../utils/apiError';
import { SHARE_STATUS_LABEL, shareInviteFailure, shareLoginProblem, sharePeople } from '../utils/petShare';
import { showToast } from '../utils/toast';
import { DraggableSheetBody } from './DraggableSheetBody';
import { UserAvatar } from './UserAvatar';
import './PetShareSheet.css';

/**
 * Who a pet is shared with, and the way to add someone: the login, its own «Пригласить» (the invitation goes out at once,
 * not with a «Сохранить» of some form) and the people who have the access or an invitation, each with «Убрать». The pet
 * form shows it inline and the sheet below shows it over the feed and the list of pets: one piece, one wording.
 */
export function PetSharePanel({ pet }: { pet: Pet }) {
  const queryClient = useQueryClient();
  const [login, setLogin] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const people = sharePeople(pet);
  const ownLogin = typeof localStorage !== 'undefined' ? localStorage.getItem('username') : null;

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['pets'] });
    await queryClient.invalidateQueries({ queryKey: ['pet', pet._id] });
  };

  const change = (value: string) => {
    setLogin(value);
    setError(null);
    if (timer.current) clearTimeout(timer.current);
    const term = value.trim();
    if (term.length < 2) {
      setSuggestions([]);
      return;
    }
    // The server finds a person by the whole login, so what is offered is those the owner already shares other pets with.
    timer.current = setTimeout(async () => {
      try {
        const found = await usersService.searchUsers(term);
        setSuggestions(
          found
            .map((u) => u.username)
            .filter((u) => u !== ownLogin && !people.some((p) => p.username === u))
            .slice(0, 5),
        );
      } catch {
        setSuggestions([]);
      }
    }, 400);
  };

  const invite = async () => {
    const typed = login.trim();
    const problem = shareLoginProblem(typed, ownLogin, people);
    if (problem) {
      setError(problem);
      return;
    }
    setSending(true);
    try {
      await petsService.sharePet(pet._id, typed);
      setLogin('');
      setSuggestions([]);
      setError(null);
      showToast.success(`Приглашение отправлено: ${typed}`);
      await refresh();
    } catch (err) {
      const code = isAxiosError<{ code?: string }>(err) ? err.response?.data?.code : undefined;
      setError(shareInviteFailure(typed, code, getApiErrorMessage(err, '')));
      if (code === 'validation_error_already_shared' || code === 'share_already_invited') await refresh();
    } finally {
      setSending(false);
    }
  };

  const remove = async (username: string, member: boolean) => {
    // Taking access from someone who has it is not undone by a tap: ask. A waiting invitation is only withdrawn.
    if (member) {
      const confirmed = await Dialog.confirm({
        title: 'Закрыть доступ',
        'aria-label': 'Закрыть доступ',
        content: `${username} больше не увидит «${pet.name}» и его записи`,
        confirmText: 'Закрыть доступ',
        cancelText: 'Оставить',
        getContainer: () => document.body,
      });
      if (!confirmed) return;
    }
    setRemoving(username);
    try {
      await petsService.unsharePet(pet._id, username);
      showToast.success(member ? `Доступ закрыт: ${username}` : `Приглашение отменено: ${username}`);
      await refresh();
    } catch (err) {
      const said = getApiErrorMessage(err, '');
      showToast.failure(`${member ? 'Доступ' : 'Приглашение'} для ${username} не изменился${said ? `: ${said}` : ''}`);
    } finally {
      setRemoving(null);
    }
  };

  return (
    <div>
      <p className="pshare__lead">
        Человек получит приглашение и увидит питомца, когда примет его. Тогда он сможет смотреть и добавлять записи и данные
        для врача. Менять карточку питомца, типы записей и доступ сможете только вы
      </p>

      <form
        className="pshare__form"
        onSubmit={(e) => {
          e.preventDefault();
          void invite();
        }}
      >
        <label className="pshare__label" htmlFor={`pshare-login-${pet._id}`}>
          Логин человека
        </label>
        <div className="pshare__input">
          <Input
            id={`pshare-login-${pet._id}`}
            value={login}
            onChange={change}
            clearable
            autoCapitalize="none"
            autoCorrect="off"
            enterKeyHint="send"
            placeholder="Например, anna"
            aria-label="Логин человека"
            aria-invalid={error ? true : undefined}
          />
        </div>
        {error && (
          <p className="pshare__error" role="alert">
            {error}
          </p>
        )}
        {suggestions.length > 0 && (
          <div className="pshare__suggestions" role="group" aria-label="Подсказки логинов">
            {suggestions.map((u) => (
              <button
                key={u}
                type="button"
                className="chip chip--action"
                onClick={() => {
                  setLogin(u);
                  setSuggestions([]);
                  setError(null);
                }}
              >
                {u}
              </button>
            ))}
          </div>
        )}
        <Button className="pshare__button" block size="large" color="primary" loading={sending} disabled={sending} onClick={() => void invite()}>
          Пригласить
        </Button>
      </form>

      <section className="pshare__list" aria-label="Кто видит питомца">
        <h3 className="pshare__list-title">Кто видит питомца</h3>
        {people.length === 0 ? (
          <p className="pshare__hint">Пока никто. Питомец виден только вам</p>
        ) : (
          <ul>
            {people.map(({ username, status }) => (
              <li key={username} className="pshare__item">
                <span className="pshare__who">
                  <UserAvatar username={username} size={28} />
                  <span>
                    <span className="pshare__name">{username}</span>
                    <span className="pshare__status">
                      {SHARE_STATUS_LABEL[status]}
                      {status === 'member' && username === pet.next_owner ? ', станет владельцем, если вы удалите аккаунт' : ''}
                    </span>
                  </span>
                </span>
                <button
                  type="button"
                  className="pshare__remove"
                  disabled={removing === username}
                  aria-label={status === 'member' ? `Убрать доступ: ${username}` : `Убрать приглашение: ${username}`}
                  onClick={() => void remove(username, status === 'member')}
                >
                  Убрать
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

/** The sheet over the feed and the list of pets. It reads the pet from the list, so the people in it follow every change. */
export function PetShareSheet({ visible, petId, onClose }: { visible: boolean; petId: string | null; onClose: () => void }) {
  const { pets } = usePet();
  const pet = pets.find((p) => p._id === petId);
  return (
    <Popup visible={visible && !!pet} onMaskClick={onClose} position="bottom" bodyStyle={{ background: 'transparent' }}>
      <DraggableSheetBody visible={visible} onClose={onClose} maxHeight="88vh" label="Поделиться питомцем">
        {pet && (
          <>
            <h2 className="pshare__title">Поделиться: {pet.name}</h2>
            <PetSharePanel pet={pet} />
          </>
        )}
      </DraggableSheetBody>
    </Popup>
  );
}
