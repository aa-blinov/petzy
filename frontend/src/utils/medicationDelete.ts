import type { QueryClient } from '@tanstack/react-query';
import type { Medication } from '../services/medications.service';
import { deleteWithUndo } from './deferredDelete';
import { refreshMedicationViews } from './intakeViews';

/** One question for both places a course can be deleted from (the list's swipe and the edit form). */
export const medicationDeleteText = (name: string) =>
  `«${name}» удалится вместе со всеми отмеченными приёмами и пропадёт из медкарты. Чтобы оставить лекарство в истории, нажмите «Завершить курс». Сразу после удаления его можно вернуть кнопкой «Отменить»`;

/** The course leaves the lists and the dose card at once, «Отменить» stays on offer, and the server is asked when that time is up. */
export function deleteMedicationWithUndo(med: Pick<Medication, '_id' | 'name'>, queryClient: QueryClient): void {
  deleteWithUndo({
    id: med._id,
    path: `/medications/${med._id}`,
    message: 'Лекарство удалено',
    failure: `Не удалось удалить «${med.name}», лекарство на месте`,
    onDeleted: () => refreshMedicationViews(queryClient),
  });
}
