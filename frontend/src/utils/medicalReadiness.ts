import type { QueryClient } from '@tanstack/react-query';
import { medicalCardService, type MedicalCard } from '../services/medicalCard.service';
import { showToast } from './toast';

export interface ReadinessCheck {
  key: string;
  label: string;
  hint: string;
  done: boolean;
  /** Where the missing thing is filled in. */
  to: string;
}

/** What a vet looks for first, and whether the card has it. One list for the card's own block
    and for the line after a save, so the two never count differently. */
export function readinessChecks(card: MedicalCard, petId: string): ReadinessCheck[] {
  const { profile } = card;
  const clinic = profile.clinic;
  return [
    {
      key: 'allergies',
      label: 'Аллергии',
      hint: 'Укажите или отметьте, что аллергий нет',
      done: profile.allergies.length > 0 || profile.allergies_none_known,
      to: `/pets/${petId}/medical-profile`,
    },
    {
      key: 'vaccination',
      label: 'Прививки',
      hint: 'Запишите последнюю, придёт напоминание о повторе',
      done: card.record_counts.vaccination > 0 || card.vaccinations.length > 0,
      to: `/pets/${petId}/medical-records/new?kind=vaccination`,
    },
    {
      key: 'parasite',
      label: 'Обработки от паразитов',
      hint: 'Запишите последнюю, придёт напоминание о повторе',
      done: card.record_counts.parasite > 0,
      to: `/pets/${petId}/medical-records/new?kind=parasite`,
    },
    {
      key: 'clinic',
      label: 'Клиника и врач',
      hint: 'Название и телефон, чтобы не искать в чатах',
      done: !!(clinic.name || clinic.vet || clinic.phone),
      to: `/pets/${petId}/medical-profile`,
    },
    {
      key: 'weight',
      label: 'Вес',
      hint: 'Врач считает по нему дозы',
      done: !!card.weight,
      to: '/form/weight',
    },
  ];
}

/** «Прививка добавлена. Заполнено 3 из 5.» after a save: the owner sees the card is getting there.
    The saved thing is confirmed at once; the count comes with the fresh card and is left out if it can't be had. */
export async function confirmWithProgress(queryClient: QueryClient, petId: string, saved: string): Promise<void> {
  try {
    const card = await queryClient.fetchQuery({ queryKey: ['medical-card', petId], queryFn: () => medicalCardService.get(petId), staleTime: 0 });
    const checks = readinessChecks(card, petId);
    const done = checks.filter((c) => c.done).length;
    showToast.success(done === checks.length ? `${saved}. Главное для врача заполнено` : `${saved}. Заполнено ${done} из ${checks.length}`);
  } catch {
    showToast.success(saved);
  }
}
