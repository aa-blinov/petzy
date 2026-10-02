import { useQuery } from '@tanstack/react-query';
import { petsService, type Pet } from '../services/pets.service';
import { pluralRu } from '../utils/relativeTime';

/** The question asked before a pet is deleted: what goes with it, in numbers, and who loses access. */
export function PetDeleteSummary({ pet }: { pet: Pet }) {
  const { data } = useQuery({
    queryKey: ['pet-deletion-impact', pet._id],
    queryFn: () => petsService.deletionImpact(pet._id),
    staleTime: 0,
    gcTime: 0,
  });
  const people = pet.shared_with?.length ?? 0;
  const parts: string[] = [];
  if (data) {
    if (data.events) parts.push(`${data.events} ${pluralRu(data.events, 'запись', 'записи', 'записей')} в ленте`);
    if (data.medications) parts.push(`${data.medications} ${pluralRu(data.medications, 'лекарство', 'лекарства', 'лекарств')}`);
    if (data.documents) parts.push(`${data.documents} ${pluralRu(data.documents, 'документ', 'документа', 'документов')}`);
    if (data.medical_records) parts.push(`${data.medical_records} ${pluralRu(data.medical_records, 'запись', 'записи', 'записей')} медкарты`);
  }
  return (
    <>
      Удалить «{pet.name}»?{' '}
      {parts.length > 0 ? `Вместе с ним пропадут: ${parts.join(', ')}.` : 'Вместе с ним пропадут все записи, лекарства и документы.'}
      {people > 0 && ` ${people === 1 ? 'Один человек потеряет' : `${people} ${pluralRu(people, 'человек', 'человека', 'человек')} потеряют`} доступ.`}
      {' '}Сразу после удаления его можно вернуть кнопкой «Отменить». Если нужна история, сначала скачайте PDF медкарты или выгрузите записи в Настройках.
    </>
  );
}
