import type { QueryClient } from '@tanstack/react-query';
import { medicalCardService, type MedicalCard } from '../services/medicalCard.service';
import { showSnackbar } from './snackbar';
import { showToast } from './toast';

export interface ReadinessCheck {
  key: string;
  label: string;
  hint: string;
  /** What the button says when this is the next step. */
  action: string;
  done: boolean;
  /** Where the missing thing is filled in. */
  to: string;
}

/** What a vet looks for first, and whether the card has it. One list for the card's own block
    and for the line after a save, so the two never count differently. */
export function readinessChecks(card: MedicalCard, petId: string): ReadinessCheck[] {
  const { profile } = card;
  return [
    {
      key: 'allergies',
      action: 'Указать аллергии',
      label: 'Аллергии',
      hint: 'Укажите или отметьте, что аллергий нет',
      done: profile.allergies.length > 0 || profile.allergies_none_known,
      to: `/pets/${petId}/medical-profile`,
    },
    {
      key: 'vaccination',
      action: 'Записать прививку',
      label: 'Прививки',
      hint: 'Запишите последнюю, придёт напоминание о повторе',
      done: card.record_counts.vaccination > 0 || card.vaccinations.length > 0,
      to: `/pets/${petId}/medical-records/new?kind=vaccination`,
    },
    {
      key: 'parasite',
      action: 'Записать обработку',
      label: 'Обработки от паразитов',
      hint: 'Запишите последнюю, придёт напоминание о повторе',
      done: card.record_counts.parasite > 0,
      to: `/pets/${petId}/medical-records/new?kind=parasite`,
    },
    {
      key: 'clinic',
      action: 'Указать клинику',
      label: 'Клиника и врач',
      hint: 'Название и телефон, чтобы не искать в чатах',
      done: profile.clinics.some((c) => !!(c.name || c.phone || c.doctors.length)),
      to: `/pets/${petId}/medical-profile?section=clinic`,
    },
    {
      key: 'weight',
      action: 'Записать вес',
      label: 'Вес',
      hint: 'Врач считает по нему дозы',
      done: !!card.weight,
      to: '/form/weight',
    },
  ];
}

/** «Прививка добавлена. Заполнено 3 из 5.» after a save: the owner sees the card is getting there.
    The saved thing is confirmed at once; the count comes with the fresh card and is left out if it can't be had. */
export async function confirmWithProgress(queryClient: QueryClient, petId: string, saved: string, action?: { label: string; run: () => void }): Promise<void> {
  try {
    const card = await queryClient.fetchQuery({ queryKey: ['medical-card', petId], queryFn: () => medicalCardService.get(petId), staleTime: 0 });
    const checks = readinessChecks(card, petId);
    const done = checks.filter((c) => c.done).length;
    if (done === checks.length) {
      // The card was not complete a moment ago and is now: it stays the whole card when the person returns to it, and says
      // so there, instead of turning into the reading mode under their hands (see MedicalCard).
      try {
        sessionStorage.setItem(`petzy:justCompleted:${petId}`, '1');
      } catch {
        /* no storage: the card opens as it usually does */
      }
    }
    const message = done === checks.length ? `${saved}. Главное для врача заполнено` : `${saved}. Заполнено ${done} из ${checks.length}`;
    if (action) showSnackbar({ message, tone: 'success', action });
    else showToast.success(message);
  } catch {
    if (action) showSnackbar({ message: saved, tone: 'success', action });
    else showToast.success(saved);
  }
}

/** The one line the feed shows under «Медкарта»: what is overdue first, else how far the card is filled in. */
export function cardStatusLine(card: MedicalCard, petId: string): { text: string; alert: boolean } {
  const records = (['vaccination', 'parasite'] as const).map((kind) => ({
    kind,
    overdue: card.records[kind].some((r) => r.status === 'overdue' && !r.superseded) || (kind === 'vaccination' && card.vaccinations.some((v) => v.status === 'expired')),
  }));
  const vaccine = records[0].overdue;
  const parasite = records[1].overdue;
  if (vaccine && parasite) return { text: 'Прививка и обработка просрочены', alert: true };
  if (vaccine) return { text: 'Прививка просрочена', alert: true };
  if (parasite) return { text: 'Обработка просрочена', alert: true };
  const checks = readinessChecks(card, petId);
  const done = checks.filter((c) => c.done).length;
  return { text: done === checks.length ? 'Всё заполнено' : `Заполнено ${done} из ${checks.length}`, alert: false };
}
