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
export function readinessChecks(card: MedicalCard, petId = ''): ReadinessCheck[] {
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
      label: 'Клиника',
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

/** What a vet will not find on the card, in the order they ask: the same five checks the block «Для врача» counts,
    read as words. The reading mode says them in one line, so an empty card says what is empty instead of
    «не указана» five times over. */
export function missingReadiness(card: MedicalCard): string[] {
  return readinessChecks(card).filter((c) => !c.done).map((c) => c.label.toLowerCase());
}

/** «аллергии, прививки и вес»: one line that reads as a list, without «·» between the parts. */
export function listWords(items: string[]): string {
  if (items.length <= 1) return items[0] ?? '';
  if (items.length === 2) return `${items[0]} и ${items[1]}`;
  return `${items.slice(0, -1).join(', ')} и ${items[items.length - 1]}`;
}

/** «Прививка добавлена. Заполнено 3 из 5.» after a save: the owner sees the card is getting there.
    The saved thing is confirmed at once; the count comes with the fresh card and is left out if it can't be had. */
export async function confirmWithProgress(
  queryClient: QueryClient,
  petId: string,
  saved: string,
  action?: { label: string; run: () => void },
  options: ProgressOptions = {},
): Promise<void> {
  const show = (message: string) => {
    // «Отменить» takes the record back; next to another action it is the second button, alone it is the only one.
    const undo = options.undo ? { label: 'Отменить', run: () => runUndo(options.undo!) } : undefined;
    if (action && undo) showSnackbar({ message, tone: 'success', action, secondaryAction: undo });
    else if (action || undo) showSnackbar({ message, tone: 'success', action: action ?? undo });
    else showToast.success(message);
  };
  try {
    const card = await queryClient.fetchQuery({ queryKey: ['medical-card', petId], queryFn: () => medicalCardService.get(petId), staleTime: 0 });
    const checks = readinessChecks(card, petId);
    show(progressMessage(saved, checks.filter((c) => c.done).length, checks.length, options.before));
  } catch {
    show(saved);
  }
}

export interface ProgressOptions {
  /** How many of the checks were done before this save: the count is said only when the save changed it. */
  before?: number;
  /** Takes the saved thing back; offered as «Отменить». */
  undo?: () => Promise<void>;
}

/** What follows «Запись добавлена»: the count of the card, but only when this save moved it (a second vaccination
    does not make «Заполнено 3 из 5» any more true than it was a minute ago). Without a count to compare, it is said. */
export function progressMessage(saved: string, done: number, total: number, before?: number): string {
  if (before !== undefined && before === done) return saved;
  return done === total ? `${saved}. Главное для врача заполнено` : `${saved}. Заполнено ${done} из ${total}`;
}

async function runUndo(undo: () => Promise<void>): Promise<void> {
  try {
    await undo();
  } catch {
    showToast.failure('Не удалось отменить');
    return;
  }
  showToast.success('Отменено');
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
