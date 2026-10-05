import { useNavigate } from 'react-router-dom';
import { useMutation, useQueries, useQueryClient } from '@tanstack/react-query';
import { Button, Dialog } from 'antd-mobile';
import { Link2 } from 'lucide-react';

import { EmptyState } from '../components/EmptyState';
import { MAX_ACTIVE_SHARES } from '../components/MedicalShareSheet';
import { usePet } from '../hooks/usePet';
import { formatShareEnd, medicalShareService } from '../services/medicalShare.service';
import { getApiErrorMessage } from '../utils/apiError';
import { showToast } from '../utils/toast';
import './MedicalLinks.css';

/**
 * Настройки → «Ссылки на медкарту»: every link to a card that works now, for every pet the person can see, in one place. A link is made
 * in the reading view of a card and is easy to forget; here it is seen and taken back, whichever pet it was made for.
 */
export function MedicalLinks() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { pets, selectedPetId } = usePet();

  const lists = useQueries({
    queries: pets.map((pet) => ({ queryKey: ['medical-shares', pet._id], queryFn: () => medicalShareService.list(pet._id), staleTime: 0 })),
  });
  const revoke = useMutation({
    mutationFn: ({ petId, shareId }: { petId: string; shareId: string }) => medicalShareService.revoke(petId, shareId),
    onSuccess: (_result, { petId }) => {
      void queryClient.invalidateQueries({ queryKey: ['medical-shares', petId] });
      showToast.success('Ссылка отозвана');
    },
    onError: (err: unknown) => showToast.failure(getApiErrorMessage(err, 'Не удалось отозвать ссылку')),
  });

  const ask = async (petId: string, shareId: string) => {
    const sure = await Dialog.confirm({
      title: 'Отозвать ссылку?',
      content: 'Врач, у которого она открыта, сразу потеряет доступ к карте. Новую ссылку можно сделать в любой момент',
      confirmText: 'Отозвать',
      cancelText: 'Оставить',
    });
    if (sure) revoke.mutate({ petId, shareId });
  };

  const rows = pets.map((pet, i) => ({ pet, query: lists[i] }));
  const loading = rows.some((r) => r.query.isPending);
  const total = rows.reduce((n, r) => n + (r.query.data?.length ?? 0), 0);
  const failed = rows.filter((r) => r.query.isError);

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding medlinks__head">
          <h1 className="display-headline" style={{ fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>Ссылки на медкарту</h1>
          <p className="medlinks__lead">Ссылки, по которым врач открывает карту без входа. Здесь видно все действующие и можно отозвать любую</p>
          <p className="medlinks__note" data-testid="medlinks-count">
            {loading ? 'Считаем действующие ссылки' : `Действующих ссылок: ${total}`}
          </p>
        </div>

        <div className="safe-area-padding medlinks__body">
          {loading && <p className="medlinks__note" aria-busy="true">Загружаем</p>}

          {failed.map(({ pet, query }) => (
            <p key={pet._id} className="medlinks__note" role="alert">
              Не удалось загрузить ссылки для {pet.name}.{' '}
              <button type="button" className="medlinks__retry" onClick={() => void query.refetch()}>
                Повторить
              </button>
            </p>
          ))}

          {pets.length === 0 && (
            <EmptyState
              icon={Link2}
              title="Питомцев пока нет"
              description="Ссылку для врача делают в медкарте питомца: сначала добавьте питомца"
              actionLabel="Добавить питомца"
              onAction={() => navigate('/pets/new')}
            />
          )}

          {pets.length > 0 && !loading && total === 0 && failed.length === 0 && (
            <EmptyState
              icon={Link2}
              title="Действующих ссылок нет"
              description="Ссылку для врача делают в медкарте, в режиме «Врачу»: на день, неделю или месяц"
              {...(selectedPetId ? { actionLabel: 'Открыть медкарту', onAction: () => navigate(`/pets/${selectedPetId}/medical-card?mode=vet`) } : {})}
            />
          )}

          {rows
            .filter((r) => (r.query.data?.length ?? 0) > 0)
            .map(({ pet, query }) => (
              <section key={pet._id} className="medlinks__pet" aria-label={pet.name}>
                <h2 className="section-header" style={{ marginBottom: 'var(--spacing-sm)' }}>{pet.name}</h2>
                <p className="medlinks__note" style={{ marginBottom: 'var(--spacing-sm)' }}>
                  Занято {query.data!.length} из {MAX_ACTIVE_SHARES} ссылок
                </p>
                <ul className="card-soft medlinks__list">
                  {query.data!.map((share) => (
                    <li key={share.id} className="medlinks__item">
                      <span>
                        До {formatShareEnd(share.expires_at)}
                        <span className="medlinks__by">Сделал {share.username || 'бывший участник'}, {formatShareEnd(share.created_at)}</span>
                      </span>
                      <Button size="small" fill="none" color="danger" loading={revoke.isPending && revoke.variables?.shareId === share.id} onClick={() => void ask(pet._id, share.id)}>
                        Отозвать
                      </Button>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
        </div>
      </div>
    </div>
  );
}
