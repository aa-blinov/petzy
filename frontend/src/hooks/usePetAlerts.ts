import { useQueries } from '@tanstack/react-query';
import { medicalCardService, type MedicalAlerts } from '../services/medicalCard.service';
import type { Pet } from '../services/pets.service';

/** What is overdue on each pet's card, by pet id. The same query as the dot on the «Медкарта» tab, so a pet
    already read there is not asked about twice; a pet not read yet is simply absent until its answer comes. */
export function usePetAlerts(pets: Pet[], enabled: boolean): ReadonlyMap<string, MedicalAlerts> {
  const results = useQueries({
    queries: pets.map((pet) => ({
      queryKey: ['medical-card', pet._id, 'alerts'],
      queryFn: () => medicalCardService.alerts(pet._id),
      enabled,
      staleTime: 60_000,
    })),
  });
  const byPet = new Map<string, MedicalAlerts>();
  pets.forEach((pet, i) => {
    const data = results[i]?.data;
    if (data) byPet.set(pet._id, data);
  });
  return byPet;
}

/** «Просрочена прививка», «Не отмечен приём лекарства», in words: the picker says what, the dot only says that. */
export function alertText(alerts: MedicalAlerts | undefined): string | null {
  if (!alerts) return null;
  const parts: string[] = [];
  if (alerts.vaccination && alerts.parasite) parts.push('Просрочены прививка и обработка');
  else if (alerts.vaccination) parts.push('Просрочена прививка');
  else if (alerts.parasite) parts.push('Просрочена обработка');
  if (alerts.medication) parts.push('Не отмечен приём лекарства');
  return parts.length ? parts.join('. ') : null;
}
