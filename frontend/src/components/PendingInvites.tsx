import { createElement, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { PET_INVITES_QUERY_KEY, usePetInvites } from '../hooks/usePetInvites';
import { Button } from 'antd-mobile';
import { petsService, type PetInvite } from '../services/pets.service';
import { usePet } from '../hooks/usePet';
import { getSpecies } from '../utils/species';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';

/**
 * «anna приглашает вас…» with Принять / Отклонить. Sharing is an
 * invitation: nothing of the pet reaches this account (no records, no
 * reminders) until it's accepted here.
 */
export function PendingInvites() {
  const { data: invites = [] } = usePetInvites();
  if (invites.length === 0) return null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)', marginBottom: 'var(--spacing-lg)' }}>
      {invites.map((invite) => (
        <InviteCard key={invite.pet_id} invite={invite} />
      ))}
    </div>
  );
}

function InviteCard({ invite }: { invite: PetInvite }) {
  const queryClient = useQueryClient();
  const { selectPet } = usePet();
  const [busy, setBusy] = useState<'accept' | 'decline' | null>(null);
  const species = getSpecies(invite.species);

  const answer = async (accept: boolean) => {
    if (busy) return;
    setBusy(accept ? 'accept' : 'decline');
    try {
      if (accept) {
        await petsService.acceptInvite(invite.pet_id);
        // staleTime 0: the cached roster (fresh for 30 s by default) is the
        // one without this pet. The invitation must not vanish before the
        // pet is in the list, or the empty feed sends the user to onboarding.
        const pets = await queryClient.fetchQuery({
          queryKey: ['pets'],
          queryFn: () => petsService.getPets(),
          staleTime: 0,
        });
        const pet = pets.find((p) => p._id === invite.pet_id);
        if (pet) selectPet(pet);
        showToast.success('Приглашение принято');
      } else {
        await petsService.declineInvite(invite.pet_id);
        showToast.success('Приглашение отклонено');
      }
      await queryClient.invalidateQueries({ queryKey: PET_INVITES_QUERY_KEY });
      if (!accept) await queryClient.invalidateQueries({ queryKey: ['pets'] });
    } catch (err) {
      showToast.failure(getApiErrorMessage(err, 'Не удалось ответить на приглашение'));
      await queryClient.invalidateQueries({ queryKey: PET_INVITES_QUERY_KEY });
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="card-soft" style={{ padding: 'var(--spacing-lg)' }}>
      <div style={{ display: 'flex', gap: 'var(--spacing-md)', alignItems: 'center' }}>
        <div
          aria-hidden
          style={{
            width: 44,
            height: 44,
            borderRadius: 12,
            flexShrink: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'var(--app-accent-soft)',
            color: 'var(--app-accent-deep)',
          }}
        >
          {createElement(species.icon, { size: 24, strokeWidth: 2, style: { display: 'block' } })}
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 'var(--text-xs)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--app-accent-deep)' }}>
            Приглашение
          </div>
          <div style={{ fontSize: 'var(--text-md)', color: 'var(--app-text-primary)', marginTop: 'var(--spacing-2xs)', overflowWrap: 'anywhere' }}>
            <strong>{invite.owner}</strong> приглашает вас вести дневник питомца <strong>{invite.pet_name}</strong>
          </div>
        </div>
      </div>
      <div style={{ fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)', marginTop: 'var(--spacing-sm)' }}>
        Вы будете видеть его записи, лекарства и документы и получать напоминания
      </div>
      <div style={{ display: 'flex', gap: 'var(--spacing-sm)', marginTop: 'var(--spacing-md)' }}>
        <Button color="primary" shape="rounded" style={{ flex: 1, fontWeight: 600 }} loading={busy === 'accept'} disabled={!!busy} onClick={() => answer(true)}>
          Принять
        </Button>
        <Button fill="outline" shape="rounded" style={{ flex: 1 }} loading={busy === 'decline'} disabled={!!busy} onClick={() => answer(false)}>
          Отклонить
        </Button>
      </div>
    </div>
  );
}
