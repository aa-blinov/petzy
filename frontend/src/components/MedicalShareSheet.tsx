import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Popup } from 'antd-mobile';

import { getApiErrorMessage } from '../utils/apiError';
import { medicalShareService, shareUrl, type CreatedShare } from '../services/medicalShare.service';
import { showToast } from '../utils/toast';
import { DraggableSheetBody } from './DraggableSheetBody';
import { Segmented } from './Segmented';
import './MedicalShareSheet.css';

const DAYS = [
  { value: '1', label: '1 день' },
  { value: '7', label: '7 дней' },
  { value: '30', label: '30 дней' },
] as const;

const formatEnd = (iso: string) => new Date(iso).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });

/**
 * A link to the card for a vet: opens without signing in, only to read, for a day, a week or a month, and can be taken back at
 * once. The address is shown once, as it was made (the server keeps only a hash of its secret), then only the links that still
 * work are listed, each with «Отозвать».
 */
export function MedicalShareSheet({ visible, petId, petName, onClose }: { visible: boolean; petId: string; petName: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [days, setDays] = useState<'1' | '7' | '30'>('7');
  const [made, setMade] = useState<CreatedShare | null>(null);

  const shares = useQuery({ queryKey: ['medical-shares', petId], queryFn: () => medicalShareService.list(petId), enabled: visible });
  const create = useMutation({
    mutationFn: () => medicalShareService.create(petId, Number(days) as 1 | 7 | 30),
    onSuccess: (result) => {
      setMade(result);
      void queryClient.invalidateQueries({ queryKey: ['medical-shares', petId] });
    },
    onError: (err: unknown) => showToast.failure(getApiErrorMessage(err, 'Не удалось создать ссылку')),
  });
  const revoke = useMutation({
    mutationFn: (id: string) => medicalShareService.revoke(petId, id),
    onSuccess: (_result, id) => {
      if (made?.share.id === id) setMade(null);
      void queryClient.invalidateQueries({ queryKey: ['medical-shares', petId] });
      showToast.success('Ссылка отозвана');
    },
    onError: (err: unknown) => showToast.failure(getApiErrorMessage(err, 'Не удалось отозвать ссылку')),
  });

  const url = made ? shareUrl(made.path) : '';
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      showToast.success('Ссылка скопирована');
    } catch {
      showToast.failure('Не удалось скопировать, выделите ссылку вручную');
    }
  };
  const send = async () => {
    try {
      await navigator.share({ title: `Медкарта: ${petName}`, url });
    } catch {
      /* closed without sending: nothing to say */
    }
  };
  const close = () => {
    setMade(null);
    onClose();
  };

  return (
    <Popup visible={visible} onMaskClick={close} position="bottom" bodyStyle={{ background: 'transparent' }}>
      <DraggableSheetBody visible={visible} onClose={close} maxHeight="85vh" label="Ссылка для врача">
        <h2 className="shsheet__title">Ссылка для врача</h2>
        <p className="shsheet__lead">Врач откроет карту {petName} без входа и только прочитает её. Ссылка перестанет работать через выбранное время, её можно отозвать в любой момент.</p>

        {!made && (
          <>
            <div className="shsheet__group">
              <Segmented label="Сколько действует ссылка" value={days} options={DAYS.map((d) => ({ value: d.value, label: d.label }))} onChange={setDays} />
            </div>
            <p className="shsheet__note">В карте аллергии, лекарства и телефон клиники. Отправляйте ссылку только врачу.</p>
            <Button block color="primary" size="large" loading={create.isPending} disabled={create.isPending} onClick={() => create.mutate()}>
              Создать ссылку
            </Button>
          </>
        )}

        {made && (
          <div className="shsheet__made" role="group" aria-label="Новая ссылка">
            <p className="shsheet__url" data-testid="share-url">{url}</p>
            <p className="shsheet__note">Действует до {formatEnd(made.share.expires_at)}. Адрес показан один раз: потом его не восстановить, можно только сделать новую ссылку.</p>
            <div className="shsheet__actions">
              <Button block color="primary" size="large" onClick={() => void copy()}>
                Скопировать
              </Button>
              {typeof navigator.share === 'function' && (
                <Button block size="large" onClick={() => void send()}>
                  Поделиться
                </Button>
              )}
            </div>
          </div>
        )}

        {(shares.data?.length ?? 0) > 0 && (
          <section className="shsheet__list" aria-label="Действующие ссылки">
            <h3 className="shsheet__list-title">Действующие ссылки</h3>
            <ul>
              {shares.data!.map((share) => (
                <li key={share.id} className="shsheet__item">
                  <span>
                    До {formatEnd(share.expires_at)}
                    {share.username && <span className="shsheet__by">Сделал {share.username}</span>}
                  </span>
                  <Button size="small" fill="none" color="danger" loading={revoke.isPending && revoke.variables === share.id} onClick={() => revoke.mutate(share.id)}>
                    Отозвать
                  </Button>
                </li>
              ))}
            </ul>
          </section>
        )}
      </DraggableSheetBody>
    </Popup>
  );
}
