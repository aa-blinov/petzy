import type { DeletionPreview } from '../services/account.service';
import { pluralRu } from './relativeTime';

const names = (pets: { name: string }[]) => pets.map((p) => `«${p.name}»`).join(', ');

/**
 * What the confirmation of an account deletion says, in the words of the plan above it: pets gone with their
 * records, pets handed over, access ended. A group with nobody in it is not mentioned, and one pet is said in the
 * singular.
 */
export function deletionSummary(preview: Pick<DeletionPreview, 'deleted' | 'transferred' | 'left'>): string {
  const { deleted, transferred, left } = preview;
  return [
    deleted.length
      ? `${deleted.length === 1 ? 'Удалится' : 'Удалятся'}: ${names(deleted)}, вместе с записями, лекарствами и документами.`
      : '',
    transferred.length ? `${transferred.length === 1 ? 'Перейдёт другому' : 'Перейдут другим'}: ${names(transferred)}.` : '',
    left.length ? `Пропадёт доступ к ${left.length} ${pluralRu(left.length, 'питомцу', 'питомцам', 'питомцам')} других людей.` : '',
  ]
    .filter(Boolean)
    .join(' ');
}
