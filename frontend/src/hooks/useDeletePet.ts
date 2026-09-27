import { useQueryClient } from '@tanstack/react-query';
import { petsService, type Pet } from '../services/pets.service';
import { getApiErrorMessage } from '../utils/apiError';
import { showToast } from '../utils/toast';
import { usePet } from './usePet';

/**
 * Takes a pet off the list and keeps the selection sensible: if it was
 * the selected one, the pet in its place is selected next (or none, if it
 * was the last). Rejects on failure, after telling the user why.
 */
function useRemoveFromList(remove: (petId: string) => Promise<void>, done: string, failed: string) {
  const queryClient = useQueryClient();
  const { pets, selectPet, getSelectedPet } = usePet();

  return async (pet: Pet) => {
    try {
      const wasSelected = getSelectedPet?._id === pet._id;
      const index = pets.findIndex((p) => p._id === pet._id);

      await remove(pet._id);

      const updated = await petsService.getPets();
      queryClient.setQueryData(['pets'], updated);
      if (updated.length === 0) selectPet(null);
      else if (wasSelected) selectPet(updated[Math.min(index, updated.length - 1)]);

      showToast.success(done);
    } catch (error) {
      showToast.failure(getApiErrorMessage(error, failed));
      throw error;
    }
  };
}

/** The owner deletes a pet. Shared by the pets list's swipe and the edit form's button. */
export function useDeletePet() {
  return useRemoveFromList((id) => petsService.deletePet(id), 'Питомец удалён', 'Не удалось удалить');
}

/** Someone a pet was shared with stops seeing it; the owner keeps everything. */
export function useLeavePet() {
  return useRemoveFromList((id) => petsService.leavePet(id), 'Вы больше не видите этого питомца', 'Не удалось выйти');
}
